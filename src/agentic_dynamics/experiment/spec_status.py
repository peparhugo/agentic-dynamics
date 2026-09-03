"""Derived spec lifecycle index — what specs exist, what is done, and when.

An agent authoring a new spec has, until now, had no way to answer "does this already
exist, and did it finish?" without reading all 60-odd YAMLs in ``experiments/specs/`` and
guessing. The run ledgers that would answer it
(``experiments/results/workflows/<spec>/<timestamp>.json``, written by
``scripts/run_workflow.py``) were write-only: nothing ever read them back.

This module joins the two sides and emits both halves of the answer:

* ``experiments/specs/index.json`` — the machine schema (one entry per spec, plus a
  ``generated_at`` stamp and a schema version), for the registry/knowledge producers and
  for the ``--resume`` fallback.
* ``experiments/specs/STATUS.md`` — the agent-facing table (one row per spec, a legend,
  a generated-at line), for a human or an LLM reading the repo.

**The spec_catalog is derived, never hand-maintained.** (`spec_catalog` is this
artifact's name in the control-plane vocabulary — see
``docs/architecture/current/control_plane_vocabulary.md``; it indexes *specs*, i.e. what work
exists, and must not be confused with `run_state`, the control database that records what
actually happened.) The spec YAML's lifecycle fields are the
*seed* (what the operator asserted); the run JSONs are the *measured evidence* (what
actually happened) and win wherever both speak. Nothing here writes back into a spec YAML.

**Missing data is normal, not a failure.** ``experiments/results/workflows/`` is untracked,
so a fresh checkout has zero run ledgers; every run-derived column then renders as an
em-dash and every spec still appears in the spec_catalog. A malformed run JSON is warned
about and skipped, never raised — the spec_catalog must be generatable from any state of the
working tree.

Design: ``code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`` (the spec layer);
``experiments/specs/spec_lifecycle.yaml`` (this layer).
"""

from __future__ import annotations

import hashlib
import json
import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.core.paths import PROJECT_ROOT
from agentic_dynamics.experiment.experiment_spec import (
    ExperimentSpec,
    committed_spec_paths,
    load_spec,
)

# ── Constants ───────────────────────────────────────────────────

#: Repo-root-relative location of the spec corpus and of the run ledgers. Relative
#: literals (rather than absolutes) so an alternate ``root=`` — a test's ``tmp_path``, a
#: worktree — reuses the same layout without a second set of constants.
SPECS_DIR_REL = "experiments/specs"
WORKFLOW_RESULTS_DIR_REL = "experiments/results/workflows"

INDEX_FILENAME = "index.json"
STATUS_FILENAME = "STATUS.md"

#: Bumped when the shape of an ``index.json`` entry changes, so a consumer that cached an
#: older index can tell rather than mis-parse it. v2 added the ``artifact_kind`` and
#: ``repeatable`` identity columns (refactor-repair P1-4 index).
INDEX_SCHEMA_VERSION = "spec-status/v2"

#: Rendered in place of any column with no evidence behind it. An em-dash reads as
#: "nothing measured", where a ``0``/``false``/``None`` would read as a measured failure.
MISSING = "—"

#: Row ordering for ``STATUS.md``: rank by status, then by name. Runnable-now specs come
#: first because that is what an authoring agent is scanning for; live runs and the three
#: "needs attention" states (``awaiting_approval``/``failed``/``blocked``) sit just behind
#: them; completed one-shots and retired lineage sink to the bottom. Any status outside this
#: tuple sorts after all of them (defensive: the validator already restricts the vocabulary,
#: but the index must never crash on a stray).
STATUS_ORDER: tuple[str, ...] = (
    "runnable",
    "running",
    "awaiting_approval",
    "failed",
    "blocked",
    "draft",
    "completed",
    "superseded",
    "tombstoned",
)

#: How recent an *open* run (a ledger with ``started_at`` but no ``ended_at``) must be to
#: count as "currently running". Older than this, an open run is ``blocked`` — a run that
#: started and never resolved must not masquerade as live forever (review item 8 / P2).
RUNNING_WINDOW = timedelta(hours=24)

#: Timestamp format of a run-ledger filename (``20260819T142530Z.json``) — the fallback
#: when the ledger body carries no ``ended_at``/``started_at``.
_FILENAME_TS_FORMAT = "%Y%m%dT%H%M%SZ"


# ── Timestamp normalization ─────────────────────────────────────


def _now() -> datetime:
    """Current UTC time. Isolated so tests can monkeypatch a fixed clock."""
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    """Canonical ISO-8601 UTC rendering used for every timestamp this module emits."""
    return moment.astimezone(timezone.utc).isoformat()


def parse_timestamp(text: str | None) -> datetime | None:
    """Parse any timestamp shape this repo produces into an aware UTC ``datetime``.

    Three shapes reach us and they cannot be compared as strings:

    * ``2026-08-19T14:25:30.123456+00:00`` — ``workflow_runner._now()`` (ISO with offset)
    * ``2026-08-19T14:25:30Z`` — ISO with a ``Z`` suffix (``fromisoformat`` rejects this
      on Python < 3.11, hence the explicit swap)
    * ``20260819T142530Z`` — the run-ledger *filename* stem

    Returns ``None`` for anything unparseable, so a corrupt field degrades to "no
    timestamp" instead of raising in the middle of an index refresh.
    """
    if not text:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            moment = datetime.strptime(raw, _FILENAME_TS_FORMAT)
        except ValueError:
            return None
    # A naive timestamp is treated as UTC: everything in this repo is written in UTC, and
    # leaving it naive would make it uncomparable with the aware ones.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


# ── Run ledgers (the measured evidence) ─────────────────────────


@dataclass
class RunSummary:
    """The handful of fields the index needs out of one run ledger.

    Deliberately a projection, not the whole ``WorkflowRunResult``: the index is a
    navigation aid, and keeping it small means ``index.json`` stays diffable.
    """

    path: str  # repo-relative path to the run ledger JSON
    timestamp: str  # canonical ISO-8601 UTC — when the run ended (or started)
    ok: bool | None = None
    model: str | None = None
    cost_usd: float | None = None
    git_sha: str | None = None
    #: w2 (revision identity): the run ledger's recorded ``workflow_revision_id`` — the
    #: ``sha256(canonicalized spec definition)`` the run executed. ``""`` for legacy ledgers
    #: written before the field existed; ``spec_status`` then attributes them to the current
    #: spec only through the phase-coverage compatibility check in ``derive_status``.
    workflow_revision_id: str = ""
    #: The phase names this run's ledger records as executed (``phases[].phase``). Used by
    #: ``derive_status`` to tell a legacy run of the CURRENT definition from a run of an
    #: OLDER one: if the current spec declares a phase no run ever executed (a gate appended
    #: after the last green run), the green runs predate it and cannot certify completion.
    executed_phases: frozenset[str] = frozenset()
    #: The split-run family link (engine_gaps_followups g1, F5). ``run_id`` is the run's own
    #: control-db identity (minted by ``scripts/run_workflow.py`` and stamped onto the ledger
    #: at write time; ``""`` for pre-g1 ledgers). ``parent_run_id`` names the run this run
    #: CONTINUES — a ``--resume`` child records its parent so a split run is one family, not
    #: two unrelated runs. ``family_id`` is the family ROOT's ``run_id``, shared by every
    #: member, so ``derive_status`` can group a resume's evidence into one unit. A run with an
    #: empty ``family_id`` (legacy ledger, or a genuinely new attempt) is its own family: it
    #: never unions with any other run.
    run_id: str = ""
    parent_run_id: str = ""
    family_id: str = ""
    #: P1 (awaiting-approval fix): True when the run ledger carries ``awaiting: true`` — the
    #: run stopped at a mechanical human checkpoint (or a resume refused past an unsatisfied
    #: one). A designed stop, never a failure: the index derives ``awaiting_approval`` for a
    #: spec whose LATEST run is awaiting, not ``failed``.
    awaiting: bool = False
    # Current-execution evidence (review item 8): a ledger with ``started_at`` but no
    # ``ended_at`` is *open* — it may still be in flight. ``started_at`` anchors the recency
    # window that separates "running now" from "blocked (started, never resolved)".
    started_at: str | None = None
    open: bool = False

    @property
    def moment(self) -> datetime | None:
        """Parsed ``timestamp``, for ordering. ``None`` sorts as "oldest"."""
        return parse_timestamp(self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "timestamp": self.timestamp,
            "ok": self.ok,
            "model": self.model,
            "cost_usd": self.cost_usd,
            "git_sha": self.git_sha,
            "workflow_revision_id": self.workflow_revision_id,
            "executed_phases": sorted(self.executed_phases),
            "awaiting": self.awaiting,
            "started_at": self.started_at,
            "open": self.open,
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "family_id": self.family_id,
        }


def summarize_run(path: Path, payload: dict[str, Any], *, root: Path) -> RunSummary:
    """Project one loaded run ledger into a :class:`RunSummary`.

    The run's time is ``ended_at`` (when the run *finished* — the honest completion
    stamp), falling back to ``started_at``, then to the filename stem. Every one of those
    can be absent in an older or truncated ledger, hence the ladder. A ledger with a
    ``started_at`` but no ``ended_at`` is marked ``open`` (review item 8) so the index can
    tell "still running" from "started and never resolved".
    """
    ended = parse_timestamp(payload.get("ended_at"))
    started = parse_timestamp(payload.get("started_at"))
    moment = ended or started or parse_timestamp(path.stem)
    cost = payload.get("total_cost_usd")
    return RunSummary(
        path=_relative_to(path, root),
        timestamp=_iso(moment) if moment else "",
        ok=payload.get("ok") if isinstance(payload.get("ok"), bool) else None,
        model=str(payload["model"]) if payload.get("model") else None,
        cost_usd=float(cost) if isinstance(cost, (int, float)) else None,
        git_sha=str(payload["git_sha"]) if payload.get("git_sha") else None,
        # w2 (revision identity): the digest the run executed — "" for legacy ledgers.
        # Read defensively (``.get``) so pre-w2 ledgers and unknown shapes parse unchanged.
        workflow_revision_id=str(payload.get("workflow_revision_id") or ""),
        # The phase names this run's ledger lists as executed, for the revision-coverage
        # check in derive_status (a gate appended after the last green run is a phase no
        # run ever executed).
        executed_phases=frozenset(
            str(p.get("phase"))
            for p in (payload.get("phases") or [])
            if isinstance(p, dict) and p.get("phase")
        ),
        awaiting=payload.get("awaiting") is True,
        started_at=_iso(started) if started else None,
        open=(ended is None and started is not None),
        # The split-run family link (engine_gaps_followups g1, F5) — stamped onto the ledger
        # by scripts/run_workflow.py at write time (run_id/parent_run_id/family_id keys).
        # Read defensively so pre-g1 ledgers parse unchanged (all three default to "").
        run_id=str(payload.get("run_id") or ""),
        parent_run_id=str(payload.get("parent_run_id") or ""),
        family_id=str(payload.get("family_id") or ""),
    )


def load_runs(spec_name: str, *, results_dir: Path, root: Path) -> list[RunSummary]:
    """Load every run ledger for one spec, oldest first.

    Tolerates the whole directory being absent (untracked in a fresh checkout) and skips
    individual malformed files with a warning. The index must be generatable from any
    state of the working tree, so nothing in here raises.
    """
    spec_dir = results_dir / spec_name
    if not spec_dir.is_dir():
        return []

    runs: list[RunSummary] = []
    for path in sorted(spec_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            warnings.warn(
                f"spec_status: skipping unreadable run ledger {path}: {exc}",
                UserWarning,
                stacklevel=2,
            )
            continue
        if not isinstance(payload, dict):
            warnings.warn(
                f"spec_status: skipping non-object run ledger {path}", UserWarning, stacklevel=2
            )
            continue
        runs.append(summarize_run(path, payload, root=root))

    # Oldest first. Runs with an unparseable timestamp sort to the front so they never
    # masquerade as "latest" and shadow a real, dated run.
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    runs.sort(key=lambda r: (r.moment is not None, r.moment or epoch))
    return runs


# ── The index entry ─────────────────────────────────────────────


@dataclass
class SpecStatusEntry:
    """One spec's derived lifecycle row — the unit of both ``index.json`` and ``STATUS.md``."""

    name: str
    version: str
    status: str
    spec_path: str  # repo-relative path to the spec YAML
    #: Artifact identity (refactor-repair P1-4 index) — surfaced so STATUS.md can answer
    #: "what work remains?" per kind, not just per name. ``repeatable`` is ``None`` only for
    #: an entry that predates the backfill; post-backfill every spec carries a concrete bool.
    artifact_kind: str = ""
    repeatable: bool | None = None
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    completed_at: str | None = None  # authored in the YAML; the index never invents it
    last_run_at: str | None = None  # measured (max run timestamp), else the YAML's seed
    latest_ok: bool | None = None
    latest_model: str | None = None
    latest_cost_usd: float | None = None
    latest_git_sha: str | None = None
    results_pointer: str | None = None  # repo-relative path to the latest run ledger
    n_runs: int = 0
    #: w2 (revision identity): this spec's CURRENT ``workflow_revision_id`` (sha256 of the
    #: canonicalized definition). The catalogue reports the revision's run state — a reader
    #: comparing it with a run ledger's recorded revision can see whether that run certifies
    #: the current definition.
    workflow_revision_id: str = ""
    #: w2 ('authored' marker): the ``status:`` the spec's own YAML authors, when it authors
    #: one. For a legacy authored-status spec this is a PROSE CLAIM, not a measurement —
    #: ``status`` above is derived from runs of the current revision (or, with no run
    #: evidence at all, carries the authored value). Recording it separately lets readers see
    #: the claim the file makes distinct from the state the run evidence supports.
    authored_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "spec_path": self.spec_path,
            "artifact_kind": self.artifact_kind,
            "repeatable": self.repeatable,
            "supersedes": list(self.supersedes),
            "superseded_by": self.superseded_by,
            "completed_at": self.completed_at,
            "last_run_at": self.last_run_at,
            "latest_ok": self.latest_ok,
            "latest_model": self.latest_model,
            "latest_cost_usd": self.latest_cost_usd,
            "latest_git_sha": self.latest_git_sha,
            "results_pointer": self.results_pointer,
            "n_runs": self.n_runs,
            # ADDED keys (w2 — additive, never renames an existing key): revision identity +
            # the authored-status provenance marker. Readers that predate w2 read the entry
            # via ``.get``/field defaults and are unaffected.
            "workflow_revision_id": self.workflow_revision_id,
            "authored_status": self.authored_status,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpecStatusEntry:
        """Rebuild an entry from ``index.json`` — the read path for the resume fallback."""
        return cls(
            name=d["name"],
            version=d.get("version", ""),
            status=d.get("status", ""),
            spec_path=d.get("spec_path", ""),
            artifact_kind=d.get("artifact_kind", ""),
            repeatable=d.get("repeatable") if isinstance(d.get("repeatable"), bool) else None,
            supersedes=list(d.get("supersedes") or []),
            superseded_by=d.get("superseded_by"),
            completed_at=d.get("completed_at"),
            last_run_at=d.get("last_run_at"),
            latest_ok=d.get("latest_ok"),
            latest_model=d.get("latest_model"),
            latest_cost_usd=d.get("latest_cost_usd"),
            latest_git_sha=d.get("latest_git_sha"),
            results_pointer=d.get("results_pointer"),
            n_runs=int(d.get("n_runs", 0)),
            workflow_revision_id=str(d.get("workflow_revision_id") or ""),
            authored_status=(
                str(d["authored_status"]) if d.get("authored_status") is not None else None
            ),
        )


def _is_currently_running(
    runs: list[RunSummary],
    *,
    now: datetime | None = None,
    window: timedelta = RUNNING_WINDOW,
) -> bool:
    """True when a run is *currently* executing — an open run whose start is recent.

    "Open" = the ledger recorded a ``started_at`` but no ``ended_at`` (the run is still in
    flight, or died without writing an end stamp). "Recent" = within ``window`` of ``now``,
    so a run that started last week and never wrote an end stamp is *blocked*, not running.
    """
    now = now or _now()
    for run in runs:
        if not run.open:
            continue
        start = parse_timestamp(run.started_at) or run.moment
        if start is not None and (now - start) <= window:
            return True
    return False


def _spec_phase_names(spec: ExperimentSpec) -> list[str]:
    """The phase names the spec's current definition declares, in workflow order."""
    phases = spec.workflow.params.get("phases") or []
    return [str(p.get("name")) for p in phases if isinstance(p, dict) and p.get("name")]


def _is_definition_changed_after_runs(spec: ExperimentSpec, runs: list[RunSummary]) -> bool:
    """True when the run corpus cannot certify the CURRENT spec definition.

    The w2 'edited after its runs' detector for LEGACY run ledgers (written before the
    revision digest existed, so they carry no ``workflow_revision_id`` to compare). A green
    run that completed the spec executed every phase the spec declared at the time; when the
    CURRENT spec's phases no longer match what the runs executed, the recorded runs predate
    the definition change and cannot certify the current revision. Two shapes count
    (engine_gaps_followups g1, F3/F4):

    1. **Mid-list structural edit (name evidence)** — a phase the runs executed does not
       exist in the current definition: the runs executed a phase that was RENAMED, or
       REMOVED (from the middle or the tail), between the runs and the current definition.
       The runs certify a definition that no longer exists — their executed_phase names do
       not match the current list by name+position. The pre-g1 code could not see this: its
       ``len(executed) >= len(spec_phases)`` early return let a same-count rename — and a
       corpus LARGER than the current list after a removal — short-circuit to "not changed".
    2. **Trailing append (unchanged)** — the runs executed every phase the current
       definition declares EXCEPT its final one (``executed == spec_phases[:-1]``): the
       shape of a single phase (typically a ``kind: test`` gate) appended after the last
       full run (``fleet_job_submission``'s appended ``p6_test_gate``). Deliberately
       narrower than 'any strict prefix': a partial-run corpus (``--only-phase`` runs whose
       union is a SMALL strict prefix, e.g. p1-only runs over a ``p1..p5`` definition)
       executed phases that exist in the current definition, in order — just not all of them
       — and must NOT read as 'edited' when no edit occurred (the f4 false-positive). Firing
       only at the one-gate depth keeps the real appended-gate corpus invalidating while a
       partial corpus derives its own honest partial state (``blocked``/``runnable`` per its
       union) instead.

    Only ever fires when a green (``ok``) run exists: a run that FAILED before reaching a
    later phase leaves that phase unexecuted too, but that is a failure, not a definition
    change, and must keep deriving ``failed`` rather than looking "never run of this
    revision". Name-preserving edits (a pure REORDER, or a kind/scope/tests-only change with
    no rename) are invisible to legacy ledgers — they record phase NAMES only — and are
    caught exactly by the revision digest once a post-w2 run exists.
    """
    spec_phases = _spec_phase_names(spec)
    if not spec_phases:
        return False
    has_green = any(run.ok is True for run in runs)
    if not has_green:
        return False
    executed = set().union(*(run.executed_phases for run in runs)) if runs else set()
    if not executed:
        return False
    # (1) Mid-list structural edit: an executed phase no longer exists in the current
    # definition (renamed or removed after the runs). Name evidence — exact where it speaks.
    if executed - set(spec_phases):
        return True
    # (2) Trailing append: the runs executed the whole current list except its final phase —
    # the fingerprint of ONE phase appended after the last full run. A strict prefix ALONE is
    # not proof of an edit (that is the f4 false-positive on partial-run corpora); only the
    # completion-shaped prefix missing exactly the trailing phase reads as an appended gate.
    return executed == set(spec_phases[:-1])


def _runs_of_current_revision(
    spec: ExperimentSpec, runs: list[RunSummary]
) -> tuple[list[RunSummary], bool]:
    """Split ``runs`` into those that certify the CURRENT spec revision.

    Returns ``(certifying, changed)``:

    * ``certifying`` — the subset of runs whose recorded ``workflow_revision_id`` equals the
      current spec digest. Only these may mark the current definition complete.
    * ``changed`` — True when runs EXIST but none of them certifies the current revision:
      the spec was edited after its last run (a gate appended, a phase changed), so the
      current revision has never been run and earlier completion does not carry over.

    Legacy runs (no recorded digest — the pre-w2 corpus) certify the current revision only
    when no definition change is detectable after them (see
    :func:`_is_definition_changed_after_runs`). Runs recording an older digest never certify.
    """
    if not runs:
        return [], False
    digest = spec.workflow_revision_id
    recorded = [r for r in runs if r.workflow_revision_id]
    if recorded:
        certifying = [r for r in recorded if r.workflow_revision_id == digest]
        return certifying, not certifying
    if _is_definition_changed_after_runs(spec, runs):
        return [], True
    return runs, False


def _certifying_families(certifying: list[RunSummary]) -> list[list[RunSummary]]:
    """Split certifying runs into run FAMILIES (engine_gaps_followups g1, F5).

    A family is the resume lineage: a parent run and every continuation run that records its
    ``parent_run_id``/``family_id`` link on the ledger. Every member of a family shares the
    family ROOT's ``family_id``, so grouping by that key re-unites the split run.

    A run with an empty ``family_id`` is its own family — a genuinely new attempt (unlinked)
    never unions with another run. That is the (b) invariant: two unlinked runs are two
    separate families, and their executed phases never combine to fake full coverage.

    Within a family, members keep the chronological order they appeared in ``certifying``
    (oldest first), so ``family[-1]`` is always the family's LATEST member. Families are
    returned ordered NEWEST-first — ordered by the position of their newest member in the
    chronological ``certifying`` list (the list order is the time order; unlinked singletons
    are ordered by their own position).
    """
    buckets: dict[str, list[RunSummary]] = {}
    order: list[str] = []
    newest_at: dict[str, int] = {}
    for index, run in enumerate(certifying):
        # A run with no family link is its own family: its group key is unique to its
        # position, so two unlinked runs never merge even if their summaries are equal.
        key = run.family_id or f"\x00self:{index}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(run)
        newest_at[key] = index
    return [buckets[key] for key in sorted(order, key=newest_at.__getitem__, reverse=True)]


def _family_executed_union(family: list[RunSummary]) -> set[str]:
    """The union of every phase name the family's members executed, across all of them."""
    union: set[str] = set()
    for run in family:
        union |= set(run.executed_phases)
    return union


def _family_status(spec: ExperimentSpec, family: list[RunSummary]) -> str | None:
    """One family's union verdict, or ``None`` when the family is not decisive.

    g1 split-run semantics (the family replaces the blunt any-failed block):

    * ``"failed"`` — any member is a definitive failure (ok False, not awaiting). A failed
      member means SOME phase in the family only ever failed — the union covering the phase
      list by NAME is not enough, because the failed phase was never re-executed to ok. The
      whole family reads failed: completion is NEVER derived from a later member alone when
      an earlier member failed.
    * ``"completed"`` — no member failed AND the family's executed-phase UNION covers the
      current revision's full phase list AND the family's LATEST member succeeded. The union
      is what lets a clean split certify: a resume parent (w1+w2, ok) + child (w3+w4, ok)
      together executed the full revision, where neither alone did.
    * ``None`` — no verdict (partial coverage with all-ok members, unresolved members, or
      awaiting-only): the family cannot certify completion and does not read failed.
    """
    if any(member.ok is False and not member.awaiting for member in family):
        return "failed"
    latest = family[-1]
    if latest.ok is not True:
        return None
    full_phases = set(_spec_phase_names(spec))
    if full_phases <= _family_executed_union(family):
        return "completed"
    return None


def _newest_decisive_family_status(
    spec: ExperimentSpec, certifying: list[RunSummary]
) -> str | None:
    """The spec's overall verdict under family-union semantics, or ``None``.

    Families are scanned NEWEST-first (see :func:`_certifying_families`) and the first
    family with a DECISIVE union verdict (``failed`` or ``completed``) decides the spec.
    Unresolved families — all members ok=None (started, never resolved), or an all-ok family
    whose union does not yet cover the full revision — are not decisive and are deferred, so
    a blocked attempt never erases an older decisive verdict:

    * a later FAILED family un-completes an earlier completed one (the guard's shape: a
      later failed re-run must not un-complete);
    * a later genuine full-coverage family completes even when an earlier SEPARATE family
      failed (the unlinked-second-run blind spot the guard could not see);
    * an unresolved family in between defers to the decisive evidence behind it.

    Returns ``None`` when no family is decisive (no verdict anywhere).
    """
    for family in _certifying_families(certifying):
        status = _family_status(spec, family)
        if status in ("failed", "completed"):
            return status
    return None


def derive_status(
    spec: ExperimentSpec,
    runs: list[RunSummary] | None = None,
    *,
    now: datetime | None = None,
    running_window: timedelta = RUNNING_WINDOW,
) -> str:
    """Resolve a spec's lifecycle status (review item 8 — current-execution evidence).

    The precedence is fixed by the spec-lifecycle design:

    1. an authored ``draft``/``tombstoned`` — a claim only a human can make, which no run
       can express (an explicit ``draft`` or ``tombstoned`` wins over every derivation);
    2. otherwise ``superseded`` when ``superseded_by`` is set — a spec that names its
       replacement has, by definition, been replaced;
    3. otherwise, **per-kind**:
       * a *repeatable* spec (an experiment, or an idempotent operation) is always
         ``runnable`` — it is re-runnable by construction;
       * a *non-repeatable* workflow derives its state from runs of its EXACT revision
         (w2 revision identity): ``running`` when a run is *currently* executing (an open
         run within ``running_window``), ``awaiting_approval`` when the LATEST run of the
         current revision stopped at a mechanical human checkpoint (the ledger carries
         ``awaiting: true``), ``completed`` when a run of the current revision succeeded,
         ``failed`` when a run of the current revision recorded a definitive failure,
         ``blocked`` when runs of the current revision exist but none resolved (no verdict
         and nothing in flight), and ``runnable`` when the current revision has never been
         run (never run at all, or edited after its last green run).

    **Authored ``status:`` no longer overrides run evidence for workflows** (w2). An
    authored ``completed``/``failed``/etc. on a WORKFLOW YAML is a legacy prose claim, not a
    measurement: it is reported only when the spec has NO run ledgers at all (nothing to
    override — the catalogue carries it as an explicit ``authored_status`` marker), and run
    evidence decides whenever it exists. ``draft``/``tombstoned`` are exempt: they are not
    run-evidence claims, they are operator lifecycle claims.

    **Completion follows the revision.** ``running`` requires positive evidence of current
    execution — a historical failed or abandoned run never stays ``running`` indefinitely
    (the P2 fix). A run ledger that records a ``workflow_revision_id`` certifies only its
    own digest: a completed run of revision A does NOT mark edited revision B completed; B
    shows its own run state or "never run of this revision" (a gate appended after the last
    green run leaves the current definition with a phase no run ever executed — those runs
    predate it and cannot certify it). Legacy ledgers written before the digest existed carry
    no revision id and are attributed to the current revision unless a definition change is
    detectable after them (see :func:`_runs_of_current_revision`).

    **Completion follows the family UNION, never the latest run alone** (engine_gaps_followups
    g1, F5). Certifying runs are grouped into families — the resume lineage a parent and its
    ``--resume`` children share via ``parent_run_id``/``family_id`` (see :func:`_certifying_families`).
    A spec is ``completed`` only when a family's *union* of executed phases covers the current
    revision's full phase list, its latest member succeeded, and NO member is a definitive
    failure. A family with any failed member reads ``failed`` — a failed member means some
    phase in the family only ever failed, and no union of names can certify it. An incomplete
    union (all-ok members that together did not execute the whole revision) is not completed.
    A run with no family link is its own family: a genuinely NEW attempt never unions with an
    older one, so a fresh full-coverage success can certify even after an earlier (separate)
    family failed, while a split parent+child never fakes completion from their joined phases.
    The overall status is the newest DECISIVE family's (newest-first scan, deferring past
    unresolved families) — a later failed re-run un-completes, a later genuine full run completes.

    The ``awaiting_approval`` state is the P1 fix: a correctly-paused run (``ok: false`` +
    ``awaiting: true`` on the ledger — a checkpoint stop, or a resume refused past an
    unsatisfied checkpoint) must read as "waiting for the operator", NOT as ``failed``. The
    check keys the LATEST run of the current revision only.

    Note what is deliberately *absent*: run history never demotes a *repeatable* spec to
    ``draft``. "Never run" and "draft" are different facts, and the table shows the first
    one directly (``n_runs``/``last_run``) rather than folding it into the status column.
    """
    # Authored human-only claims: draft/tombstoned are claims only a human can make, and no
    # run ledger can express them — they win over every derivation, on any spec kind.
    if spec.status in ("draft", "tombstoned"):
        return spec.status
    if spec.superseded_by:
        return "superseded"
    runs = runs or []
    if spec.repeatable:
        # A repeatable spec (experiment/idempotent operation) is re-runnable by
        # construction and never derives a work-order state from runs. Authored lifecycle
        # claims (draft/tombstone above, and any authored value) remain the report; the w2
        # demotion of authored ``status:`` targets WORKFLOW (non-repeatable) completion.
        return spec.status or "runnable"
    # ── Non-repeatable workflow — derive from runs of the EXACT current revision ──────────
    certifying, changed = _runs_of_current_revision(spec, runs)
    if _is_currently_running(certifying, now=now, window=running_window):
        return "running"
    # P1: the LATEST certifying run is awaiting operator approval — a designed pause.
    if certifying and certifying[-1].awaiting:
        return "awaiting_approval"
    # g1 (F5): completion is derived from the UNION of a run family's evidence, never from
    # any single run's `ok` flag alone. The split-run shape (parent failed at w2 + a --resume
    # child that ran w3+w4) must not read completed from the child's success: no single run
    # executed the full revision. _family_status resolves one family's union verdict; the
    # scan below walks families newest-first and returns the newest DECISIVE family (so a
    # later genuine full-coverage run can certify, and a later failed re-run un-completes).
    # A definitive failure anywhere in a family (any member ok False, not awaiting) blocks
    # that family from ever reading completed — a phase that failed in one member was never
    # re-executed to ok, and names alone cannot certify it. Awaiting members are designed
    # stops, never failures (a pause predating a later success is shadowed by that success).
    decisive = _newest_decisive_family_status(spec, certifying)
    if decisive is not None:
        return decisive
    if certifying:
        return "blocked"
    # No run certifies the current revision.
    if changed:
        # Runs exist but none is of the current revision — the definition changed after
        # the last run (a gate appended, a phase changed). The current revision has never
        # been run: it is runnable, and the catalogue's definition-changed marker explains
        # why a spec with historical runs reads as not-completed.
        return "runnable"
    if not runs:
        # Never run at all. A legacy authored run-evidence status (e.g. `completed` on a
        # consolidation spec with no ledger anywhere) is the ONLY record — report it as a
        # catalogue marker rather than silently erasing it; run evidence would override it.
        return spec.status or "runnable"
    return "runnable"


def build_entry(
    spec: ExperimentSpec, spec_path: Path, runs: list[RunSummary], *, root: Path
) -> SpecStatusEntry:
    """Join one spec with its run ledgers into an index entry.

    Seed-vs-evidence rule: where the YAML asserted ``last_run_at``/``results_pointer`` and
    a real run ledger also exists, the *measured* run wins; the YAML value survives only
    as the fallback for a spec whose runs live outside this checkout.

    w2 (revision identity — hard rule: *the index shows the new revision's run state, never
    the old one's*): for a non-repeatable workflow the run-evidence columns describe the
    latest run that certifies the CURRENT definition (see :func:`_runs_of_current_revision`),
    and ``workflow_revision_id`` records that digest. When the definition changed after the
    last green run (a gate appended), no run certifies the current revision: the columns
    report no current-revision evidence, ``status`` derives ``runnable`` (never run of this
    revision), and the YAML's authored ``status:`` — if any — is carried separately as the
    explicit ``authored_status`` marker rather than silently overriding the evidence.
    """
    if spec.repeatable:
        # Repeatable specs (experiments/operations) never derive a work-order state; the run
        # columns stay a plain record of the ledgers present.
        certifying = runs
    else:
        certifying, _changed = _runs_of_current_revision(spec, runs)
    latest = certifying[-1] if certifying else None
    return SpecStatusEntry(
        name=spec.name,
        version=spec.version,
        status=derive_status(spec, runs),
        spec_path=_relative_to(spec_path, root),
        artifact_kind=spec.artifact_kind,
        repeatable=spec.repeatable,
        supersedes=list(spec.supersedes),
        superseded_by=spec.superseded_by,
        completed_at=spec.completed_at,
        last_run_at=(latest.timestamp if latest and latest.timestamp else spec.last_run_at),
        latest_ok=latest.ok if latest else None,
        latest_model=latest.model if latest else None,
        latest_cost_usd=latest.cost_usd if latest else None,
        latest_git_sha=latest.git_sha if latest else None,
        results_pointer=(latest.path if latest else spec.results_pointer),
        # ``n_runs`` stays the count of run ledgers PRESENT for the spec (historical fact);
        # the derived status + the columns above reflect only runs that certify the current
        # revision, so a ledger of an edited older revision never reads as current evidence.
        n_runs=len(runs),
        workflow_revision_id=spec.workflow_revision_id,
        authored_status=spec.status or None,
    )


def sort_entries(entries: list[SpecStatusEntry]) -> list[SpecStatusEntry]:
    """Order rows by status rank (see :data:`STATUS_ORDER`) then by name."""

    def key(entry: SpecStatusEntry) -> tuple[int, str]:
        rank = (
            STATUS_ORDER.index(entry.status) if entry.status in STATUS_ORDER else len(STATUS_ORDER)
        )
        return (rank, entry.name)

    return sorted(entries, key=key)


def _spec_paths(root_path: Path) -> list[Path]:
    """Every committed ExperimentSpec YAML across the split spec layout (design §4).

    Delegates to :func:`experiment_spec.committed_spec_paths`, which excludes workflow-v1
    definitions (the Wave-3 authoring contract — the canonical examples under
    ``workflows/examples/`` are a different document kind, never ExperimentSpecs and never
    entries in this index).
    """
    return committed_spec_paths(root_path)


def collect_entries(*, root: Path | str = PROJECT_ROOT) -> list[SpecStatusEntry]:
    """Scan the spec corpus and the run ledgers; return sorted index entries.

    A spec YAML that fails to load (malformed, missing a required key) is warned about and
    skipped rather than aborting the scan — one broken spec must not hide the other 63.
    """
    root_path = Path(root).resolve()
    results_dir = root_path / WORKFLOW_RESULTS_DIR_REL

    entries: list[SpecStatusEntry] = []
    for spec_path in _spec_paths(root_path):
        try:
            spec = load_spec(spec_path)
        except Exception as exc:  # noqa: BLE001 — any load failure is a skip, never a crash
            warnings.warn(
                f"spec_status: skipping unloadable spec {spec_path}: {exc}",
                UserWarning,
                stacklevel=2,
            )
            continue
        runs = load_runs(spec.name, results_dir=results_dir, root=root_path)
        entries.append(build_entry(spec, spec_path, runs, root=root_path))

    return sort_entries(entries)


# ── The narrator (kb_finding_layer k5): a regeneration that shifts statuses narrates ──
#
# ``spec_catalog`` is derived — it is regenerated, never hand-edited — and a regeneration that
# SHIFTS statuses is itself an event a later reader should be able to retrieve ("why did 17
# specs change status? what moved?"). The pure derivation below turns a previous index + a
# freshly derived entry set into the per-spec status diff, and :func:`refresh_spec_status`
# emits ONE finding record narrating that shift (scoped, durable artifact + pointer event —
# the same producer path as phase findings). Derivation is pure and unit-testable without a
# knowledge stream; emission is a best-effort seam (a failed emit is a warning, never a failed
# regeneration).

#: Env var that disarms the narrator in the unit suite (set ``"0"``), mirroring the workflow-run
#: finding disarm (``FINOPS_EMIT_SELF`` — the same disable-flag pattern conftest applies).
NARRATOR_DISARM_ENV = "FINOPS_EMIT_SELF"


@dataclass(frozen=True)
class StatusShift:
    """One spec whose derived status changed between two index generations."""

    name: str
    from_status: str
    to_status: str


def _entry_name_and_status(raw: Any) -> tuple[str, str] | None:
    """``(name, status)`` from an index entry — a ``SpecStatusEntry`` or its ``index.json`` dict."""
    if isinstance(raw, SpecStatusEntry):
        return raw.name, raw.status
    if isinstance(raw, dict):
        name = raw.get("name")
        status = raw.get("status")
        if name and status:
            return str(name), str(status)
    return None


def diff_statuses(previous_specs: list[Any], current_entries: list[SpecStatusEntry]) -> list[StatusShift]:
    """The per-spec status diffs between a previous index's entries and a freshly derived set.

    A spec counts as a shift only when it exists in BOTH generations with a DIFFERENT status —
    a newly-added spec has no previous status to shift from, and a removed one has no current
    status to shift to. Sorted by name so the shift signature and the rendered text are
    deterministic.
    """
    previous: dict[str, str] = {}
    for raw in previous_specs:
        got = _entry_name_and_status(raw)
        if got:
            previous[got[0]] = got[1]
    shifts: list[StatusShift] = []
    for entry in current_entries:
        prev = previous.get(entry.name)
        if prev is not None and prev != entry.status:
            shifts.append(StatusShift(name=entry.name, from_status=prev, to_status=entry.status))
    shifts.sort(key=lambda s: s.name)
    return shifts


def shift_signature(shifts: list[StatusShift]) -> str:
    """Deterministic sha256 over the per-spec diffs — the ``shift signature`` half of
    the rerun-safe knowledge_id key (the regeneration timestamp is the other half).

    Sorted internally so the same shift SET always yields the same signature regardless of
    the order the caller passed (``diff_statuses`` returns name-sorted shifts, but a test or
    a producer should not have to rely on that).
    """
    ordered = sorted(shifts, key=lambda s: (s.name, s.from_status, s.to_status))
    canonical = "\n".join(f"{s.name}|{s.from_status}|{s.to_status}" for s in ordered)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def narrate_regeneration(
    shifts: list[StatusShift], *, generated_at: str
) -> str:
    """Render ONE derived narration of a status-shifting regeneration.

    The text is DERIVED from the actual per-spec diffs — direction counts grouped and summed —
    never a hand-written summary::

        spec-index regeneration <generated_at>: N specs changed (11 failed→completed; 6
        completed→blocked)

    Direction groups are listed in a deterministic order (descending count, then the arrow
    string) so the same diff always renders identically. An empty diff returns ``""`` — there
    is nothing to narrate (the regenerator emits nothing when no statuses shifted).
    """
    if not shifts:
        return ""
    counts: dict[tuple[str, str], int] = {}
    for s in shifts:
        key = (s.from_status, s.to_status)
        counts[key] = counts.get(key, 0) + 1
    groups = sorted(
        counts.items(), key=lambda item: (-item[1], f"{item[0][0]}→{item[0][1]}")
    )
    clauses = "; ".join(f"{count} {f}→{t}" for (f, t), count in groups)
    return f"spec-index regeneration {generated_at}: {len(shifts)} specs changed ({clauses})"


def _narrator_disarmed() -> bool:
    """True when the unit suite has disarmed finding emission (FINOPS_EMIT_SELF=0)."""
    return os.environ.get(NARRATOR_DISARM_ENV) == "0"


def _emit_index_shift_narration(
    previous_specs: list[Any],
    current_entries: list[SpecStatusEntry],
    *,
    generated_at: str,
    root: Path,
) -> str | None:
    """Best-effort narrator seam: emit ONE finding record when a regeneration shifts statuses.

    Returns the emitted record's ``knowledge_id`` (or ``None`` when nothing shifted / emission
    is disarmed / the emit failed). Never raises — a failed emit is a warning, never a failed
    regeneration. The KB work is delegated to ``knowledge.spec_ingestion.emit_index_shift`` so
    ``experiment`` does not own the producer path (the same seam pattern as
    ``workflow_runner._emit_self_finding``).
    """
    if _narrator_disarmed():
        return None
    shifts = diff_statuses(previous_specs, current_entries)
    if not shifts:
        return None
    text = narrate_regeneration(shifts, generated_at=generated_at)
    try:
        from agentic_dynamics.knowledge.spec_ingestion import emit_index_shift

        return emit_index_shift(
            shifts, text=text, generated_at=generated_at, root=root
        )
    except Exception as exc:  # noqa: BLE001 — best-effort seam, documented above
        warnings.warn(
            f"spec_status: narrator emit failed (regeneration unaffected): {exc}",
            UserWarning,
            stacklevel=2,
        )
        return None


# ── Rendering: index.json + STATUS.md ───────────────────────────


def build_index(
    entries: list[SpecStatusEntry], *, generated_at: str | None = None
) -> dict[str, Any]:
    """Assemble the ``index.json`` document: schema version, stamp, and the entries."""
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": generated_at or _iso(_now()),
        "n_specs": len(entries),
        "specs": [e.to_dict() for e in entries],
    }


def _fmt_bool(value: bool | None) -> str:
    """``ok``/``fail``/em-dash — never a bare ``False`` that could read as "not measured"."""
    if value is None:
        return MISSING
    return "ok" if value else "fail"


def _fmt_cost(value: float | None) -> str:
    return MISSING if value is None else f"${value:.4f}"


def _fmt_timestamp(value: str | None) -> str:
    """Shorten an ISO timestamp to ``YYYY-MM-DD HH:MM`` for the table; em-dash if absent."""
    moment = parse_timestamp(value)
    return moment.strftime("%Y-%m-%d %H:%M") if moment else MISSING


def _fmt_list(values: list[str]) -> str:
    return ", ".join(values) if values else MISSING


def _fmt_text(value: str | None) -> str:
    return value if value else MISSING


def _fmt_kind(value: str) -> str:
    """The artifact kind column — ``experiment``/``workflow``, or an em-dash when unset."""
    return value if value else MISSING


def _fmt_repeatable(value: bool | None) -> str:
    """The repeatable column — ``yes``/``no``, or an em-dash when unset (pre-backfill)."""
    if value is None:
        return MISSING
    return "yes" if value else "no"


#: The statuses an authoring agent treats as "still open" — work remaining, counted by the
#: summary line. ``awaiting_approval``/``failed``/``blocked`` are open (awaiting an operator
#: decision, a retry, or an unblock) but are not "runnable now"; the summary label below says
#: "open", not "runnable-now", for that reason.
OPEN_STATUSES = frozenset(
    {"runnable", "running", "awaiting_approval", "failed", "blocked", "draft"}
)

#: The statuses that mean "finished" — completed one-shots and retired lineage sink out of
#: the open view (refactor-repair P1-4 index).
DONE_STATUSES = frozenset({"completed", "superseded", "tombstoned"})


def render_status_md(entries: list[SpecStatusEntry], *, generated_at: str | None = None) -> str:
    """Render the agent-facing ``STATUS.md``: summary, table, legend.

    Columns are ``name | kind | repeatable | status | version | supersedes | last_run |
    ok | model | cost | n_runs`` — the ``kind``/``repeatable`` identity columns are new in
    the P1-4 index pass. A one-line summary above the table answers "what work remains?",
    and the sort order (see :data:`STATUS_ORDER`) separates the runnable-now group from the
    completed/retired group. The legend is part of the artifact rather than a doc elsewhere,
    so an agent that opens only this file still knows how to read it.
    """
    stamp = generated_at or _iso(_now())
    open_count = sum(1 for e in entries if e.status in OPEN_STATUSES)
    done = sum(1 for e in entries if e.status in DONE_STATUSES)
    lines: list[str] = [
        "# Spec status index",
        "",
        "**Generated — do not edit by hand.** Regenerate with `python scripts/spec_status.py`;",
        "`scripts/run_workflow.py` also refreshes it at the end of every run.",
        "",
        f"Generated at: `{stamp}`  ·  {len(entries)} spec(s)",
        f"**Work remaining:** {open_count} open · {done} completed/retired",
        "",
        "| name | kind | repeatable | status | version | supersedes | last_run | ok | model | cost | n_runs |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for e in entries:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{e.name}`",
                    _fmt_kind(e.artifact_kind),
                    _fmt_repeatable(e.repeatable),
                    e.status,
                    _fmt_text(e.version),
                    _fmt_list(e.supersedes),
                    _fmt_timestamp(e.last_run_at),
                    _fmt_bool(e.latest_ok),
                    _fmt_text(e.latest_model),
                    _fmt_cost(e.latest_cost_usd),
                    str(e.n_runs),
                ]
            )
            + " |"
        )

    lines += [
        "",
        "## Legend",
        "",
        "**Status** — authored in the spec YAML's `status:` only when the operator asserted one",
        "and no run evidence exists to decide otherwise (draft/tombstoned are claims only a",
        "human can make); otherwise derived: `superseded` when the spec names a",
        "`superseded_by:`; for a non-repeatable workflow, `completed`/`failed`/`blocked`/",
        "`running`/`awaiting_approval`/`runnable` come from runs of its EXACT revision",
        "(w2 revision identity). A completed run of revision A does NOT mark an edited",
        "revision B completed: editing a spec (a gate appended, a phase changed) changes its",
        "`workflow_revision_id`, and B shows its own run state — `runnable` (never run of",
        "this revision) until a run of B certifies it. `awaiting_approval` is the latest run",
        "of the current revision stopped at a mechanical human checkpoint (`awaiting: true`",
        "on the ledger — a designed pause, never a failure). `running` requires an open,",
        "recent run; `runnable` = never run of the current revision, or a repeatable spec.",
        "",
        "| status | meaning |",
        "|---|---|",
        "| `runnable` | never run (of the current revision — possibly edited after its last green run), or a repeatable spec — ready to run |",
        "| `running` | a non-repeatable workflow currently executing — an open run within the window |",
        "| `awaiting_approval` | the latest run of the current revision stopped at a human checkpoint (`awaiting: true`) — the operator must approve before it continues |",
        "| `failed` | a non-repeatable workflow whose run(s) of the current revision recorded a definitive failure |",
        "| `blocked` | a non-repeatable workflow with runs that started but never resolved |",
        "| `draft` | authored, not yet run to completion; not yet a claim about anything |",
        "| `completed` | a non-repeatable workflow whose current revision succeeded (derived from the "
        "run ledgers) |",
        "| `superseded` | a later spec took over its question (see that spec's "
        "`supersedes` column) |",
        "| `tombstoned` | retired; kept for lineage, never to be run again |",
        "",
        "**Columns**",
        "",
        "| column | derivation |",
        "|---|---|",
        "| `name` / `version` | the spec YAML's `name:` / `version:` |",
        "| `kind` | the spec YAML's `artifact_kind:` — `experiment` or `workflow` |",
        "| `repeatable` | the spec YAML's `repeatable:` — `yes` (re-runnable) or `no` (one-shot) |",
        "| `supersedes` | spec name(s) this spec replaces, from the YAML's `supersedes:` |",
        f"| `last_run` | latest run ledger's `ended_at` (UTC), over "
        f"`{WORKFLOW_RESULTS_DIR_REL}/<name>/*.json` |",
        "| `ok` | that latest run's `ok` — every phase succeeded (`ok`) or at least one "
        "failed (`fail`) |",
        "| `model` / `cost` | that latest run's `model` and `total_cost_usd` |",
        "| `n_runs` | how many run ledgers exist for the spec in this checkout |",
        "",
        f"`{MISSING}` means **no evidence**, not failure — the run-ledger directory",
        f"(`{WORKFLOW_RESULTS_DIR_REL}/`) is untracked, so a fresh checkout shows an em-dash",
        "for every run-derived column. The machine-readable form of this table, including",
        f"`results_pointer` (path to the latest run ledger), is `{INDEX_FILENAME}` beside",
        " this file.",
        "",
        "**Revision identity (w2)** — `index.json` entries carry the spec's current",
        "`workflow_revision_id` (sha256 of the canonicalized definition) and, when the spec's",
        "YAML authors a `status:` that run evidence did not confirm, the `authored_status`",
        "marker. A row whose status is `runnable` while older run columns exist means the",
        "definition changed after its last green run (a gate added, never run).",
        "",
    ]
    return "\n".join(lines)


# ── Writing + reading the artifacts ─────────────────────────────


@dataclass
class SpecStatusReport:
    """What a refresh did — returned so callers can log it without re-reading the files."""

    index_path: Path
    status_path: Path
    n_specs: int
    entries: list[SpecStatusEntry] = field(default_factory=list)

    def entry_for(self, spec_name: str) -> SpecStatusEntry | None:
        """The refreshed entry for one spec, if that spec is in the corpus."""
        return next((e for e in self.entries if e.name == spec_name), None)


def refresh_spec_status(
    spec_name: str | None = None,
    *,
    root: Path | str = PROJECT_ROOT,
    generated_at: str | None = None,
) -> SpecStatusReport:
    """Regenerate ``index.json`` + ``STATUS.md`` from the spec corpus and run ledgers.

    ``spec_name`` is advisory: both artifacts are whole-file documents, so refreshing one
    spec's entry means rewriting them from a full rescan (64 small YAMLs — cheap enough
    that an incremental path would only add a desync failure mode). The argument is kept
    because callers want the refreshed entry for *their* spec back, which
    :meth:`SpecStatusReport.entry_for` provides; it is never a filter on what is written.
    """
    root_path = Path(root).resolve()
    specs_dir = root_path / SPECS_DIR_REL
    specs_dir.mkdir(parents=True, exist_ok=True)

    stamp = generated_at or _iso(_now())
    # The PREVIOUS index (on disk, before this regeneration overwrites it) is the diff base
    # for the narrator — "diff the newly derived statuses against the previous index".
    previous_specs: list[Any] = []
    previous_payload = load_index(root=root_path)
    if previous_payload:
        previous_specs = list(previous_payload.get("specs") or [])
    entries = collect_entries(root=root_path)

    # The narrator (kb_finding_layer k5): when statuses SHIFT, emit ONE finding record
    # narrating the shift — BEFORE the index is written. Best-effort: a failed emit is a
    # warning, never a failed regeneration.
    _emit_index_shift_narration(
        previous_specs, entries, generated_at=stamp, root=root_path
    )

    index_path = specs_dir / INDEX_FILENAME
    status_path = specs_dir / STATUS_FILENAME
    index = build_index(entries, generated_at=stamp)
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    status_path.write_text(render_status_md(entries, generated_at=stamp))

    report = SpecStatusReport(
        index_path=index_path, status_path=status_path, n_specs=len(entries), entries=entries
    )
    if spec_name and report.entry_for(spec_name) is None:
        # Not an error: a spec can legitimately be run from a path outside the corpus.
        warnings.warn(
            f"spec_status: refreshed index does not contain spec {spec_name!r} "
            f"(not found in {SPECS_DIR_REL}/)",
            UserWarning,
            stacklevel=2,
        )
    return report


def load_index(*, root: Path | str = PROJECT_ROOT) -> dict[str, Any]:
    """Read ``index.json`` back. Returns ``{}`` when it is absent or unreadable.

    Read-side callers (the ``--resume`` fallback) treat "no index" and "unusable index"
    identically — they fall through to their prior behaviour — so this never raises.
    """
    path = Path(root).resolve() / SPECS_DIR_REL / INDEX_FILENAME
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def index_entry(spec_name: str, *, root: Path | str = PROJECT_ROOT) -> SpecStatusEntry | None:
    """Look one spec up in the on-disk index. ``None`` when absent or unreadable."""
    for raw in load_index(root=root).get("specs", []) or []:
        if isinstance(raw, dict) and raw.get("name") == spec_name:
            try:
                return SpecStatusEntry.from_dict(raw)
            except (KeyError, TypeError, ValueError):
                return None
    return None


# ── Helpers ─────────────────────────────────────────────────────


def _relative_to(path: Path, root: Path) -> str:
    """Repo-relative POSIX path, falling back to the absolute one when outside ``root``.

    Every path the index publishes is repo-relative so ``index.json`` is identical across
    checkouts (and therefore diffable); a path that genuinely lives elsewhere is emitted
    absolute rather than mangled into a chain of ``..`` segments.
    """
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()
