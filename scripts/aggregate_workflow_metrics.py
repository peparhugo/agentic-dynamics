"""Aggregate the machine's own workflow ledgers into the framework's Rules 6-10 metrics.

This is the operator-directed thread-1 instrument: consolidate the workflow-run and
campaign ledgers the machine has committed into the autonomous-workload operating metrics the
website's ``framework.html`` defines but never computes from a ledger — per campaign and
pooled across the corpus.

The instrument is *coverage-honest by construction*. The metric definitions are PINNED (hard
rule 3 of ``workflows/repository/workflow_metrics.yaml``) and reproduced verbatim in
:data:`PINNED_METRIC_DEFINITIONS` below — a deviating definition is a FAILED finding. A metric
whose backing ledger field does not exist is reported ``not_measurable`` with the named missing
field, never imputed (hard rule 2, "measured, not estimated"). The coverage — which workflows
have complete ledgers — is recorded exactly.

Ledger shapes this instrument recognizes (see ``src/agentic_dynamics/runtime/workflow_runner.py``
for the authoritative schema):

* **workflow run ledger** — ``WorkflowRunResult.to_dict()``: ``spec_name`` + ``phases`` (one
  ``PhaseResult`` per phase: ``status``, ``cost_usd``, ``duration_s``, ``confidence``,
  ``test_executed_success``), plus the I10 ``checkpoints`` array (``CheckpointRecord``:
  ``reached_at``/``decided_at``/``decision``). Written by ``scripts/run_workflow.py`` to
  ``experiments/results/workflows/<spec>/<timestamp>.json`` — which ``.gitignore`` excludes as
  "machine-local, not provenance".
* **campaign phase ledger** — ``campaign`` + ``phases`` (the ``cap_2a``/``cap_2b``/``cap_2c``
  p1/p2 wrappers), or ``campaign`` + ``run_ledger`` (the per-cell ``*_phase_ledger.json`` files
  that embed a nested ``WorkflowRunResult``).
* **attempt ledger** — ``cells`` (each with an ``attempts`` list carrying ``attempt_number`` /
  ``retry_reason`` / ``status`` / ``actual_cost``). The committed exemplar is
  ``experiments/results/cap_grit_grid_ledger.json``.

The pinned attempt-level fields ``attempt_count`` / ``first_pass`` / ``accepted`` /
``escalation_from`` / ``escalation_to`` are DECLARED in ``LEDGER_FIELDS``
(``experiment_spec.py``) but declared-not-written by the runtime
(``control/checkpoint.py`` — "``first_pass``/``accepted`` stay UNWRITTEN"). This instrument
therefore derives ``retry_rate`` from the ``attempts`` array length where one exists, and
reports ``first_call_resolution``/``escalation_rate``/``batch_fraction``/``sla_behavior`` as
not-measurable with the missing field named. That gap is the finding, not an accident.

Outputs (``experiments/results/workflow_metrics/``): ``aggregate.json`` (rows + pooled
aggregates + coverage), ``aggregate.csv`` (the same rows flattened), and ``coverage.csv``
(the exact complete-ledger table).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ── Pinned mandate ────────────────────────────────────────────────────────────
#
# Hard rule 3 of the workflow_metrics spec pins the metric definitions. They are the source of
# truth; a consumer that renames or redefines them is a FAILED finding. Each entry maps the
# metric's stable key to the verbatim §3 definition text.

PINNED_METRIC_DEFINITIONS: dict[str, str] = {
    "retry_rate": "r = attempts with attempt_count > 1 / total attempts (per campaign)",
    "first_call_resolution": "WOC = first_pass / total",
    "escalation_rate": "escalation rate = the escalations / total",
    "batch_fraction": "b = batch-mode jobs / total",
    "throughput": "throughput = cells or phases per hour per campaign",
    "cost_per_accepted": "cost-per-accepted = the accepted outcomes' cost",
    "checkpoint_latency": "the checkpoint latency = decided_at - reached_at per approval",
    "sla_behavior": "SLA = the timeouts/deadline breaches / total",
}

#: The attempt-level fields the pinned definitions consume but the runtime declares-not-writes
#: (control/checkpoint.py). When these are the only door to a metric, that metric is reported
#: not-measurable, never imputed.
DECLARED_NOT_WRITTEN = (
    "attempt_count",
    "first_pass",
    "accepted",
    "escalation_from",
    "escalation_to",
)

#: Ledger kinds this instrument classifies.
KIND_WORKFLOW_RUN = "workflow_run"
KIND_CAMPAIGN_PHASE = "campaign_phase"
KIND_ATTEMPT = "attempt"
KIND_OTHER = "other"

#: The per-phase runner fields that carry the SLA/limit-breach evidence (a timeout via the
#: phase watchdog ``stall_evidence``, and the mechanical gate breaches). A phase from a
#: post-hardening runner carries these keys (``None`` = no breach); a pre-hardening ledger omits
#: them entirely. The sla_behavior metric is only measurable over phases that actually carry them.
BREACH_FIELDS = ("stall_evidence", "deploy_gate", "commit_gate", "relabel_gate")


@dataclass
class Attempt:
    """One attempt row, normalized across the three ledger shapes."""

    job_id: str
    attempt_number: int
    status: str
    cost_usd: float
    retry_reason: str


@dataclass
class Job:
    """One job/cell, normalized. ``accepted`` is ``None`` when the ledger never recorded it."""

    job_id: str
    n_attempts: int
    status: str
    cost_usd: float
    accepted: bool | None
    started_at: str
    ended_at: str


@dataclass
class Phase:
    """One workflow/campaign phase, normalized.

    The runner writes structured limit/breach evidence as ``None``-or-dict fields
    (``stall_evidence`` = the phase-watchdog timeout; ``deploy_gate``/``commit_gate``/
    ``relabel_gate`` = the mechanical gate breaches). Those fields ARE the SLA/limit behavior the
    pinned ``sla_behavior`` metric consumes — a non-empty value is a measured breach, ``None`` is
    "no breach recorded".
    """

    phase: str
    kind: str
    status: str
    cost_usd: float
    duration_s: float
    model: str = ""
    error: str = ""
    test_executed_success: bool | None = None
    #: True when the raw phase dict carried any of BREACH_FIELDS — the runner version that wrote
    #: the ledger records breach evidence. A pre-hardening ledger omits these keys entirely, and
    #: "absent key" must not be read as "no breach".
    breach_fields_recorded: bool = False
    stall_evidence: dict[str, Any] | None = None
    deploy_gate: dict[str, Any] | None = None
    commit_gate: dict[str, Any] | None = None
    relabel_gate: dict[str, Any] | None = None


@dataclass
class Checkpoint:
    """One I10 checkpoint record, normalized (phase, decision, timestamps, reason, evidence)."""

    phase: str
    decision: str
    reached_at: str
    decided_at: str
    reason: str = ""
    approval_evidence: dict[str, Any] | None = None


@dataclass
class LedgerCorpus:
    """Everything extracted from one campaign's ledgers, plus the field-presence flags."""

    name: str
    paths: list[str] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    phases: list[Phase] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    started_at: str = ""
    ended_at: str = ""

    @property
    def has_attempts(self) -> bool:
        return bool(self.jobs) and any(j.n_attempts > 0 for j in self.jobs)

    @property
    def has_phases(self) -> bool:
        return bool(self.phases)

    @property
    def has_checkpoints(self) -> bool:
        return bool(self.checkpoints)


@dataclass
class MetricValue:
    """One metric result with its epistemic basis — never a bare number.

    ``measurable`` is the honest gate: a metric whose backing field is absent stays
    ``measurable=False`` with ``value=None`` and ``reason`` naming the missing field, rather than
    silently becoming 0.0 (which would read as a measured zero). ``basis`` is one of ``measured``
    (copied from a ledger field), ``derived`` (arithmetic over ledger fields), or
    ``not_measurable``.
    """

    name: str
    definition: str
    measurable: bool
    value: Any = None
    basis: str = "not_measurable"
    source_fields: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "definition": self.definition,
            "measurable": self.measurable,
            "value": self.value,
            "basis": self.basis,
            "source_fields": list(self.source_fields),
            "reason": self.reason,
        }


# ── Timestamps ────────────────────────────────────────────────────────────────


def parse_timestamp(text: str | None) -> datetime | None:
    """Parse any ISO-8601 shape the ledgers produce into an aware UTC datetime, or None.

    Mirrors ``spec_status.parse_timestamp``'s tolerance: ``...Z``, ``...+00:00``, and the bare
    run-ledger filename stem all occur and cannot be compared as strings.
    """
    if not text:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


# ── Discovery + classification ────────────────────────────────────────────────


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def classify(payload: dict[str, Any]) -> str:
    """Classify a JSON payload into one of the four ledger kinds.

    The precedence is deliberate. The attempt ledger is the ONLY shape that carries per-attempt
    rows (``cells[].attempts``), so it is detected by the presence of those rows — not by the bare
    ``cells`` key, which campaign manifests/score files also use for their own per-cell rows.
    A workflow-run ledger (``spec_name`` + ``phases``) and a campaign cell ledger (``campaign`` +
    ``run_ledger``) both carry phase data and are distinguished by their envelope key.
    """
    cells = payload.get("cells")
    if isinstance(cells, list) and any(
        isinstance(c, dict) and isinstance(c.get("attempts"), list) for c in cells
    ):
        return KIND_ATTEMPT
    if payload.get("spec_name") and isinstance(payload.get("phases"), list):
        return KIND_WORKFLOW_RUN
    if payload.get("campaign") and (
        isinstance(payload.get("phases"), list) or isinstance(payload.get("run_ledger"), dict)
    ):
        return KIND_CAMPAIGN_PHASE
    return KIND_OTHER


def discover_ledgers(root: Path) -> list[dict[str, Any]]:
    """Walk ``experiments/results/**/*.json`` and return ``{path, kind, payload}`` records.

    Every JSON is read and classified; unreadable files are skipped with a printed warning (the
    coverage table must be generatable from any state of the tree — a corrupt file is a coverage
    gap, not a crash). Only the three recognized ledger kinds are returned; ``other`` files
    (score JSONs, manifests, outcomes, gate evidence) are counted but not aggregated.
    """
    results_root = root / "experiments" / "results"
    found: list[dict[str, Any]] = []
    for path in sorted(results_root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"aggregate_workflow_metrics: skipping unreadable {path}: {exc}", file=sys.stderr)
            continue
        if not isinstance(payload, dict):
            continue
        kind = classify(payload)
        if kind == KIND_OTHER:
            continue
        found.append(
            {
                "path": _relative_to(path, root),
                "kind": kind,
                "payload": payload,
            }
        )
    return found


# ── Extraction ────────────────────────────────────────────────────────────────


def _campaign_name(path: str) -> str:
    """A stable campaign key from a ledger path: the directory that owns the ledger.

    A ledger nested under ``experiments/results/<campaign>/...`` keys on the campaign directory
    (``parts[2]``) — with one exception: the canonical run-ledger directory
    ``experiments/results/workflows/<spec>/...`` keys on the *spec* (``parts[3]``), since
    ``workflows/`` is a container, not a campaign. A ledger directly under
    ``experiments/results/`` (e.g. ``cap_grit_grid_ledger.json``) keys on its filename stem.
    """
    parts = Path(path).parts
    if len(parts) >= 3 and parts[:2] == ("experiments", "results"):
        if len(parts) > 3:
            return parts[3] if parts[2] == "workflows" else parts[2]
        return Path(path).stem
    return Path(path).stem


def _extract_attempt_ledger(payload: dict[str, Any], path: str) -> LedgerCorpus:
    """Normalize an attempt ledger (``cells`` each with ``attempts``) into jobs + attempts.

    The campaign name prefers the ledger's own ``spec_id`` (``"<name>@<version>"`` — the same
    identity the job/attempt rows carry) over the path-derived key, so the pooled campaign row is
    labelled with the spec the attempts actually belong to, not the file's location.
    """
    spec_id = str(payload.get("spec_id") or "")
    campaign = spec_id.split("@", 1)[0] if "@" in spec_id else _campaign_name(path)
    corpus = LedgerCorpus(name=campaign, paths=[path])
    for cell in payload.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        attempts = [a for a in (cell.get("attempts") or []) if isinstance(a, dict)]
        job_status = str(cell.get("status", ""))
        corpus.jobs.append(
            Job(
                job_id=str(cell.get("cell_id") or cell.get("job_id") or ""),
                n_attempts=len(attempts),
                status=job_status,
                cost_usd=float(cell["realized_cost"])
                if _is_number(cell.get("realized_cost"))
                else 0.0,
                accepted=True if job_status == "accepted" else None,
                started_at=str(cell.get("started_at") or ""),
                ended_at=str(cell.get("ended_at") or cell.get("completed_at") or ""),
            )
        )
        for a in attempts:
            corpus.attempts.append(
                Attempt(
                    job_id=str(cell.get("cell_id") or cell.get("job_id") or ""),
                    attempt_number=int(a.get("attempt_number") or 0),
                    status=str(a.get("status", "")),
                    cost_usd=float(a["actual_cost"]) if _is_number(a.get("actual_cost")) else 0.0,
                    retry_reason=str(a.get("retry_reason") or ""),
                )
            )
    return corpus


def _phases_from(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The phases list, descending into a nested ``run_ledger`` when the wrapper hides it."""
    phases = payload.get("phases")
    if isinstance(phases, list):
        return [p for p in phases if isinstance(p, dict)]
    run_ledger = payload.get("run_ledger")
    if isinstance(run_ledger, dict) and isinstance(run_ledger.get("phases"), list):
        return [p for p in run_ledger["phases"] if isinstance(p, dict)]
    return []


def _checkpoints_from(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The I10 checkpoint array, descending into a nested ``run_ledger`` when present."""
    checkpoints = payload.get("checkpoints")
    if isinstance(checkpoints, list):
        return [c for c in checkpoints if isinstance(c, dict)]
    run_ledger = payload.get("run_ledger")
    if isinstance(run_ledger, dict) and isinstance(run_ledger.get("checkpoints"), list):
        return [c for c in run_ledger["checkpoints"] if isinstance(c, dict)]
    return []


def _extract_run_like_ledger(payload: dict[str, Any], path: str) -> LedgerCorpus:
    """Normalize a workflow-run or campaign-phase ledger into phases + checkpoints.

    The campaign key is the DIRECTORY that owns the ledger under ``experiments/results/`` (the
    "per campaign" unit), not the ledger's own ``spec_name`` — a campaign's phase ledgers are
    often minted by a per-cell spec (e.g. the 26 session-routing ledgers all carry
    ``spec_name: cap_session_policy_cell``), and pooling them under the cell-spec name would
    fragment one campaign into a name per cell.
    """
    corpus = LedgerCorpus(name=_campaign_name(path), paths=[path])
    corpus.started_at = str(payload.get("started_at") or "")
    corpus.ended_at = str(payload.get("ended_at") or "")
    for p in _phases_from(payload):
        corpus.phases.append(
            Phase(
                phase=str(p.get("phase") or ""),
                kind=str(p.get("kind") or ""),
                status=str(p.get("status") or ""),
                cost_usd=float(p["cost_usd"]) if _is_number(p.get("cost_usd")) else 0.0,
                duration_s=float(p["duration_s"]) if _is_number(p.get("duration_s")) else 0.0,
                model=str(p.get("model") or ""),
                error=str(p.get("error") or ""),
                test_executed_success=p.get("test_executed_success")
                if isinstance(p.get("test_executed_success"), bool)
                else None,
                breach_fields_recorded=any(k in p for k in BREACH_FIELDS),
                stall_evidence=p.get("stall_evidence")
                if isinstance(p.get("stall_evidence"), dict)
                else None,
                deploy_gate=p.get("deploy_gate")
                if isinstance(p.get("deploy_gate"), dict)
                else None,
                commit_gate=p.get("commit_gate")
                if isinstance(p.get("commit_gate"), dict)
                else None,
                relabel_gate=p.get("relabel_gate")
                if isinstance(p.get("relabel_gate"), dict)
                else None,
            )
        )
    for c in _checkpoints_from(payload):
        corpus.checkpoints.append(
            Checkpoint(
                phase=str(c.get("phase") or ""),
                decision=str(c.get("decision") or ""),
                reached_at=str(c.get("reached_at") or ""),
                decided_at=str(c.get("decided_at") or ""),
                reason=str(c.get("reason") or ""),
                approval_evidence=c.get("approval_evidence")
                if isinstance(c.get("approval_evidence"), dict)
                else None,
            )
        )
    return corpus


def extract_ledger(payload: dict[str, Any], path: str) -> LedgerCorpus:
    """Dispatch to the shape-specific extractor based on the classified kind."""
    kind = classify(payload)
    if kind == KIND_ATTEMPT:
        return _extract_attempt_ledger(payload, path)
    if kind in (KIND_WORKFLOW_RUN, KIND_CAMPAIGN_PHASE):
        return _extract_run_like_ledger(payload, path)
    return LedgerCorpus(name=_campaign_name(path), paths=[path])


def merge_corpora(corpora: list[LedgerCorpus]) -> list[LedgerCorpus]:
    """Merge corpora that share a campaign name into a single corpus (sorted, stable).

    The phase ledgers of a campaign are spread across many files (e.g. the 26 session-routing
    ledgers); each file is its own ``LedgerCorpus`` under the same name. Pooling them by name
    is what turns the per-file phase rows into a per-campaign table.
    """
    by_name: dict[str, LedgerCorpus] = {}
    order: list[str] = []
    for corpus in corpora:
        if corpus.name not in by_name:
            by_name[corpus.name] = LedgerCorpus(name=corpus.name)
            order.append(corpus.name)
        target = by_name[corpus.name]
        target.paths.extend(corpus.paths)
        target.jobs.extend(corpus.jobs)
        target.attempts.extend(corpus.attempts)
        target.phases.extend(corpus.phases)
        target.checkpoints.extend(corpus.checkpoints)
        # A campaign's span is the min started_at to max ended_at across its ledgers.
        if corpus.started_at and (not target.started_at or corpus.started_at < target.started_at):
            target.started_at = corpus.started_at
        if corpus.ended_at and (not target.ended_at or corpus.ended_at > target.ended_at):
            target.ended_at = corpus.ended_at
    return [by_name[name] for name in order]


# ── Metric arithmetic (pure) ───────────────────────────────────────────────────


def _not_measurable(name: str, missing_fields: list[str]) -> MetricValue:
    return MetricValue(
        name=name,
        definition=PINNED_METRIC_DEFINITIONS[name],
        measurable=False,
        reason=f"missing field(s): {', '.join(missing_fields)} — not written by the runtime",
        source_fields=list(missing_fields),
    )


def compute_retry_rate(corpus: LedgerCorpus) -> MetricValue:
    """r = jobs with attempt_count > 1 / total jobs.

    ``attempt_count`` itself is declared-not-written, so it is derived from the ``attempts``
    array length (a real ledger field) — basis ``derived``, and the source field named. When no
    attempt rows exist the metric is not-measurable, not zero.
    """
    if not corpus.has_attempts:
        return _not_measurable("retry_rate", ["attempt_count", "attempts"])
    total = len(corpus.jobs)
    multi = sum(1 for j in corpus.jobs if j.n_attempts > 1)
    return MetricValue(
        name="retry_rate",
        definition=PINNED_METRIC_DEFINITIONS["retry_rate"],
        measurable=True,
        value=round(multi / total, 6) if total else None,
        basis="derived",
        source_fields=["attempts", "attempt_number"],
        reason=f"{multi}/{total} jobs with >1 attempt (attempt_count derived from the attempts array)",
    )


def compute_first_call_resolution(corpus: LedgerCorpus) -> MetricValue:
    """WOC = first_pass / total — ``first_pass`` is declared-not-written, so not-measurable."""
    return _not_measurable("first_call_resolution", ["first_pass"])


def compute_escalation_rate(corpus: LedgerCorpus) -> MetricValue:
    """escalation rate = escalations / total — no escalation marker is written, not-measurable."""
    return _not_measurable("escalation_rate", ["escalation_from", "escalation_to"])


def compute_batch_fraction(corpus: LedgerCorpus) -> MetricValue:
    """b = batch-mode jobs / total — no batch-mode marker exists on the ledger, not-measurable."""
    return _not_measurable("batch_fraction", ["batch_mode"])


def _span_hours(corpus: LedgerCorpus) -> float | None:
    """The campaign wall-clock span in hours, from the ledger timestamps (None if absent)."""
    start = parse_timestamp(corpus.started_at)
    end = parse_timestamp(corpus.ended_at)
    if start is None or end is None or end <= start:
        return None
    return (end - start).total_seconds() / 3600.0


def compute_throughput(corpus: LedgerCorpus) -> MetricValue:
    """throughput = cells or phases per hour per campaign.

    Computed from the phase rows when present (phases / span-hours), else from the job rows
    (cells / span-hours). Without timestamps the span is unknown and the metric is not-measurable
    — the phase count is reported in ``value`` alongside the missing-timestamp reason.
    """
    if corpus.has_phases:
        span = _span_hours(corpus)
        n = len(corpus.phases)
        if span is None:
            return MetricValue(
                name="throughput",
                definition=PINNED_METRIC_DEFINITIONS["throughput"],
                measurable=False,
                value={"phases": n},
                basis="not_measurable",
                source_fields=["phases"],
                reason=f"{n} phases but no started_at/ended_at span to divide by",
            )
        return MetricValue(
            name="throughput",
            definition=PINNED_METRIC_DEFINITIONS["throughput"],
            measurable=True,
            value={
                "phases_per_hour": round(n / span, 4),
                "phases": n,
                "span_hours": round(span, 4),
            },
            basis="derived",
            source_fields=["phases", "started_at", "ended_at"],
        )
    if corpus.has_attempts:
        span = _span_hours(corpus)
        n = len(corpus.jobs)
        if span is None:
            return MetricValue(
                name="throughput",
                definition=PINNED_METRIC_DEFINITIONS["throughput"],
                measurable=False,
                value={"cells": n},
                basis="not_measurable",
                source_fields=["cells"],
                reason=f"{n} cells but no started_at/ended_at span to divide by",
            )
        return MetricValue(
            name="throughput",
            definition=PINNED_METRIC_DEFINITIONS["throughput"],
            measurable=True,
            value={"cells_per_hour": round(n / span, 4), "cells": n, "span_hours": round(span, 4)},
            basis="derived",
            source_fields=["cells", "started_at", "ended_at"],
        )
    return _not_measurable("throughput", ["phases", "cells"])


def compute_cost_per_accepted(corpus: LedgerCorpus) -> MetricValue:
    """cost-per-accepted = the accepted outcomes' cost.

    Backed by the attempt ledger's ``status`` (``"accepted"``) and ``realized_cost`` fields —
    both are ledger fields, so this is ``measured``. Where no job records an ``accepted`` status
    the metric is not-measurable, never a fabricated zero.
    """
    accepted = [j for j in corpus.jobs if j.accepted is True]
    if not corpus.jobs or not accepted:
        return _not_measurable("cost_per_accepted", ["accepted"])
    total = round(sum(j.cost_usd for j in accepted), 6)
    return MetricValue(
        name="cost_per_accepted",
        definition=PINNED_METRIC_DEFINITIONS["cost_per_accepted"],
        measurable=True,
        value={"accepted_count": len(accepted), "total_accepted_cost_usd": total},
        basis="measured",
        source_fields=["status", "realized_cost"],
    )


def _decisions_distribution(checkpoints: list[Checkpoint]) -> dict[str, int]:
    """Count the I10 checkpoint records by ``decision`` (awaiting/approved/rejected/other)."""
    dist: dict[str, int] = {}
    for c in checkpoints:
        key = c.decision or "unrecorded"
        dist[key] = dist.get(key, 0) + 1
    return dict(sorted(dist.items()))


def _reasons_distribution(checkpoints: list[Checkpoint]) -> dict[str, int]:
    """Count the I10 checkpoint records by ``reason`` (checkpoint_reached/approval_required)."""
    dist: dict[str, int] = {}
    for c in checkpoints:
        key = c.reason or "unrecorded"
        dist[key] = dist.get(key, 0) + 1
    return dict(sorted(dist.items()))


def compute_checkpoint_latency(corpus: LedgerCorpus) -> MetricValue:
    """checkpoint latency = decided_at - reached_at per approval (plus the checkpoint behavior).

    The pinned definition is the latency; the p1 instrument additionally reports the checkpoint
    *behavior* that the latency belongs to — the record count, the decision distribution
    (awaiting/approved/rejected), the reason distribution (mechanical stop vs resume contract
    read), and how many records carry approval evidence. ``None`` timestamps or an empty checkpoint
    array make the latency not-measurable (the coverage gap is reported, not imputed).
    """
    latencies: list[float] = []
    for c in corpus.checkpoints:
        reached = parse_timestamp(c.reached_at)
        decided = parse_timestamp(c.decided_at)
        if reached is not None and decided is not None:
            latencies.append((decided - reached).total_seconds())
    decisions = _decisions_distribution(corpus.checkpoints)
    reasons = _reasons_distribution(corpus.checkpoints)
    with_evidence = sum(1 for c in corpus.checkpoints if c.approval_evidence is not None)
    if not corpus.checkpoints:
        return _not_measurable("checkpoint_latency", ["checkpoints"])
    if not latencies:
        return MetricValue(
            name="checkpoint_latency",
            definition=PINNED_METRIC_DEFINITIONS["checkpoint_latency"],
            measurable=False,
            value={
                "checkpoint_count": len(corpus.checkpoints),
                "decisions": decisions,
                "reasons": reasons,
                "with_approval_evidence": with_evidence,
            },
            basis="not_measurable",
            source_fields=["checkpoints", "reached_at", "decided_at"],
            reason=f"{len(corpus.checkpoints)} checkpoint record(s) but none carry both timestamps",
        )
    latencies.sort()
    mean = sum(latencies) / len(latencies)
    mid = len(latencies) // 2
    if len(latencies) % 2 == 0:
        median = (latencies[mid - 1] + latencies[mid]) / 2
    else:
        median = latencies[mid]
    return MetricValue(
        name="checkpoint_latency",
        definition=PINNED_METRIC_DEFINITIONS["checkpoint_latency"],
        measurable=True,
        value={
            "checkpoint_count": len(corpus.checkpoints),
            "approvals_with_timestamps": len(latencies),
            "mean_seconds": round(mean, 3),
            "median_seconds": round(median, 3),
            "max_seconds": round(latencies[-1], 3),
            "decisions": decisions,
            "reasons": reasons,
            "with_approval_evidence": with_evidence,
        },
        basis="measured",
        source_fields=["reached_at", "decided_at", "decision", "reason", "approval_evidence"],
    )


def compute_sla_behavior(corpus: LedgerCorpus) -> MetricValue:
    """SLA = timeouts/deadline breaches / total, plus the runner's limit-breach evidence.

    The pinned definition names ``timeouts``/``deadline breaches``. The runner writes those as
    structured per-phase fields (``BREACH_FIELDS``): ``stall_evidence`` (the phase-watchdog
    timeout) and the mechanical gate breaches ``deploy_gate``/``commit_gate``/``relabel_gate``. A
    non-empty value is a measured breach. The metric is measurable ONLY over phases whose ledger
    actually recorded the fields (``breach_fields_recorded``): a pre-hardening ledger omits the
    keys entirely, and "absent key" must not be read as "zero breaches" — that would impute a
    clean record onto a ledger that never recorded one.
    """
    recorded = [p for p in corpus.phases if p.breach_fields_recorded]
    if not recorded:
        return _not_measurable("sla_behavior", list(BREACH_FIELDS))

    def _breach(evidence: dict[str, Any] | None) -> bool:
        """A breach is a non-empty evidence dict (the runner writes ``None`` for no breach)."""
        return isinstance(evidence, dict) and bool(evidence)

    stall = sum(1 for p in recorded if _breach(p.stall_evidence))
    deploy = sum(1 for p in recorded if _breach(p.deploy_gate))
    commit = sum(1 for p in recorded if _breach(p.commit_gate))
    relabel = sum(1 for p in recorded if _breach(p.relabel_gate))
    total = len(recorded)
    return MetricValue(
        name="sla_behavior",
        definition=PINNED_METRIC_DEFINITIONS["sla_behavior"],
        measurable=True,
        value={
            "total_phases_with_breach_fields": total,
            "timeout_breaches": stall,
            "gate_breaches": deploy + commit + relabel,
            "breakdown": {
                "stall": stall,
                "deploy_gate": deploy,
                "commit_gate": commit,
                "relabel_gate": relabel,
            },
            "timeout_breach_rate": round(stall / total, 6) if total else None,
        },
        basis="measured",
        source_fields=list(BREACH_FIELDS),
    )


#: The metric name -> pure computation, in the §3 presentation order.
METRIC_COMPUTERS: list[tuple[str, Any]] = [
    ("retry_rate", compute_retry_rate),
    ("first_call_resolution", compute_first_call_resolution),
    ("escalation_rate", compute_escalation_rate),
    ("batch_fraction", compute_batch_fraction),
    ("throughput", compute_throughput),
    ("cost_per_accepted", compute_cost_per_accepted),
    ("checkpoint_latency", compute_checkpoint_latency),
    ("sla_behavior", compute_sla_behavior),
]


def _phase_cost_structure(corpus: LedgerCorpus) -> dict[str, Any]:
    """The wrapper-vs-cell phase cost structure: agent phases vs test phases (uniform across ledgers).

    The runner's ``PhaseResult.kind`` is ``"agent"`` or ``"test"`` — the agent phases carry the
    model cost, the test phases carry the independent-verification cost (``0.0`` in practice). This
    is the phase-cost half of the "wrapper vs cells" split; the cell-side total cost lives in the
    per-cell wrappers (heterogeneous shapes across campaigns), so this instrument reports the
    agent/test split it can read uniformly and leaves the campaign-specific cell split to the
    campaign's own score artifacts.
    """
    agent = [p for p in corpus.phases if p.kind == "agent"]
    test = [p for p in corpus.phases if p.kind == "test"]
    other = [p for p in corpus.phases if p.kind not in ("agent", "test")]
    return {
        "n_agent_phases": len(agent),
        "n_test_phases": len(test),
        "n_other_phases": len(other),
        "agent_cost_usd": round(sum(p.cost_usd for p in agent), 6),
        "test_cost_usd": round(sum(p.cost_usd for p in test), 6),
        "other_cost_usd": round(sum(p.cost_usd for p in other), 6),
        "total_phase_cost_usd": round(sum(p.cost_usd for p in corpus.phases), 6),
    }


def compute_campaign_metrics(corpus: LedgerCorpus) -> dict[str, Any]:
    """Compute every pinned metric for one campaign, plus the measured quantities.

    ``metrics`` is the eight pinned §3 metrics; ``workload_volume`` (W — the number of jobs
    observed) and ``phase_cost_structure`` (agent vs test) are measured quantities the p1
    instrument reports alongside, not redefinitions of the pinned metrics.
    """
    metrics = {name: fn(corpus).to_dict() for name, fn in METRIC_COMPUTERS}
    return {
        "campaign": corpus.name,
        "n_ledgers": len(corpus.paths),
        "n_jobs": len(corpus.jobs),
        "n_attempts": len(corpus.attempts),
        "n_phases": len(corpus.phases),
        "n_checkpoints": len(corpus.checkpoints),
        "started_at": corpus.started_at,
        "ended_at": corpus.ended_at,
        "workload_volume": {
            "W": len(corpus.jobs),
            "unit": "jobs",
            "note": "jobs/day requires a wall-clock window; W is the observed job count",
        },
        "phase_cost_structure": _phase_cost_structure(corpus),
        "metrics": metrics,
    }


# ── Aggregation + coverage ────────────────────────────────────────────────────


def aggregate(campaign_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool the per-campaign metrics across the corpus.

    A metric is pooled only when every campaign that could have measured it actually did; if any
    campaign's metric is not-measurable, the pooled value is a union that reports how many of the
    campaigns contributed (``measurable_in``). This preserves the measured-not-estimated rule at
    the aggregate level: a pooled figure never folds a coverage gap into a mean.
    """
    pooled: dict[str, Any] = {}
    names = [name for name, _ in METRIC_COMPUTERS]
    for name in names:
        values = [row["metrics"][name] for row in campaign_rows]
        measurable = [v for v in values if v["measurable"]]
        pooled[name] = {
            "definition": PINNED_METRIC_DEFINITIONS[name],
            "measurable_in": len(measurable),
            "campaigns_total": len(campaign_rows),
            "values": measurable,
        }
    return {"campaigns": len(campaign_rows), "pooled": pooled}


def coverage_table(campaign_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The exact complete-ledger table: which pinned metric each campaign can actually measure."""
    rows: list[dict[str, Any]] = []
    for row in campaign_rows:
        metrics = row["metrics"]
        complete = [
            name
            for name in ("retry_rate", "cost_per_accepted", "throughput", "checkpoint_latency")
            if metrics[name]["measurable"]
        ]
        rows.append(
            {
                "campaign": row["campaign"],
                "n_ledgers": row["n_ledgers"],
                "n_jobs": row["n_jobs"],
                "n_attempts": row["n_attempts"],
                "n_phases": row["n_phases"],
                "n_checkpoints": row["n_checkpoints"],
                "retry_rate_measurable": metrics["retry_rate"]["measurable"],
                "first_call_resolution_measurable": metrics["first_call_resolution"]["measurable"],
                "escalation_rate_measurable": metrics["escalation_rate"]["measurable"],
                "batch_fraction_measurable": metrics["batch_fraction"]["measurable"],
                "throughput_measurable": metrics["throughput"]["measurable"],
                "cost_per_accepted_measurable": metrics["cost_per_accepted"]["measurable"],
                "checkpoint_latency_measurable": metrics["checkpoint_latency"]["measurable"],
                "sla_behavior_measurable": metrics["sla_behavior"]["measurable"],
                "complete_metrics": complete,
            }
        )
    return rows


# ── Emission ──────────────────────────────────────────────────────────────────


def _json_default(value: Any) -> Any:
    """JSON serializer guard — dataclasses/mixed types degrade to strings rather than crash."""
    return str(value)


def run_ledger_coverage(root: Path) -> dict[str, Any]:
    """Cross-check the run ledgers the spec index references against the files on disk.

    The derived spec index (``experiments/specs/index.json``) records a ``results_pointer`` for
    every workflow it has seen run. Because ``.gitignore`` excludes
    ``experiments/results/workflows/`` ("machine-local, not provenance"), those pointers may name
    files that are absent from a checkout. This is the exact answer to "which workflows have
    complete ledgers": referenced vs present vs absent, never imputed.
    """
    index_path = root / "experiments" / "specs" / "index.json"
    referenced: list[str] = []
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"referenced": 0, "present": 0, "absent": 0, "note": "no spec index available"}
    for spec in index.get("specs", []) or []:
        pointer = spec.get("results_pointer") if isinstance(spec, dict) else None
        if pointer:
            referenced.append(str(pointer))
    present = [p for p in referenced if (root / p).exists()]
    absent = [p for p in referenced if p not in present]
    return {"referenced": len(referenced), "present": len(present), "absent": len(absent)}


def emit(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Run the full pipeline and write ``experiments/results/workflow_metrics/`` outputs.

    Returns the aggregate document (also what ``--json`` prints). Discovery, classification,
    per-campaign computation, aggregation, and coverage are each a separate stage so the pure
    arithmetic stays testable independently of the filesystem.
    """
    ledgers = discover_ledgers(root)
    corpora = merge_corpora([extract_ledger(rec["payload"], rec["path"]) for rec in ledgers])
    campaign_rows = [compute_campaign_metrics(c) for c in corpora]
    campaign_rows.sort(key=lambda r: r["campaign"])
    doc = {
        "schema": "workflow_metrics/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pinned_definitions": dict(PINNED_METRIC_DEFINITIONS),
        "n_ledgers_discovered": len(ledgers),
        "n_campaigns": len(campaign_rows),
        "run_ledger_coverage": run_ledger_coverage(root),
        "campaigns": campaign_rows,
        "aggregate": aggregate(campaign_rows),
        "coverage": coverage_table(campaign_rows),
    }

    out_dir = root / "experiments" / "results" / "workflow_metrics"
    if dry_run:
        return doc
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "aggregate.json").write_text(json.dumps(doc, indent=2, default=_json_default) + "\n")
    (out_dir / "aggregate.csv").write_text(rows_to_csv(campaign_rows))
    (out_dir / "coverage.csv").write_text(coverage_to_csv(coverage_table(campaign_rows)))
    return doc


def rows_to_csv(campaign_rows: list[dict[str, Any]]) -> str:
    """Flatten the per-campaign metric rows into CSV (one column per metric, JSON-encoded value)."""
    out = io.StringIO()
    writer = csv.writer(out)
    metric_names = [name for name, _ in METRIC_COMPUTERS]
    header = ["campaign", "n_ledgers", "n_jobs", "n_attempts", "n_phases", "n_checkpoints"]
    header += [f"{n}_measurable" for n in metric_names]
    header += [f"{n}_value" for n in metric_names]
    writer.writerow(header)
    for row in campaign_rows:
        line = [
            row["campaign"],
            row["n_ledgers"],
            row["n_jobs"],
            row["n_attempts"],
            row["n_phases"],
            row["n_checkpoints"],
        ]
        for name in metric_names:
            line.append("true" if row["metrics"][name]["measurable"] else "false")
        for name in metric_names:
            line.append(json.dumps(row["metrics"][name]["value"], default=_json_default))
        writer.writerow(line)
    return out.getvalue()


def coverage_to_csv(rows: list[dict[str, Any]]) -> str:
    """The complete-ledger coverage table as CSV."""
    out = io.StringIO()
    writer = csv.writer(out)
    if not rows:
        return out.getvalue()
    writer.writerow(list(rows[0].keys()))
    for row in rows:
        writer.writerow([row[k] if not isinstance(row[k], list) else ",".join(row[k]) for k in row])
    return out.getvalue()


def _relative_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Aggregate workflow ledgers into Rules 6-10 metrics.")
    ap.add_argument("--root", default=str(ROOT), help="repo root (default: repo checkout)")
    ap.add_argument(
        "--dry-run", action="store_true", help="print the aggregate JSON, write nothing"
    )
    ap.add_argument(
        "--json", action="store_true", help="emit the aggregate document as JSON on stdout"
    )
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    doc = emit(root, dry_run=args.dry_run or args.json)
    if args.json or args.dry_run:
        print(json.dumps(doc, indent=2, default=_json_default))
    else:
        out_dir = root / "experiments" / "results" / "workflow_metrics"
        print(
            f"aggregate_workflow_metrics: {doc['n_ledgers_discovered']} ledgers, "
            f"{doc['n_campaigns']} campaigns -> {out_dir}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
