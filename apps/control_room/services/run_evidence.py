"""Shared per-run evidence derivations for the Control Room's read surfaces.

The glance projection (``routes/glance.py``) and the per-run drawer
(``services/operations.run_detail``) answer the SAME questions about a run: what did it
cost and how was that cost measured, did independent verification run, is a decision
receipt on record, what was narrated, where did its work live, which knowledge was
selected into the prepared prompt, where is that prepared step, and which timings were
actually recorded. Before this module existed those answers were derived once inside
``glance.py`` and the drawer could only show the raw blocks — so the two surfaces could
drift, and a "same run, same answer" property could not be stated.

This module owns the derivations ONCE. ``glance.py`` imports the private helpers it has
always used (the leading-underscore names are preserved so existing importers and tests
keep working); ``operations.run_detail`` calls them plus the public block builders below.
The dependency direction is route -> service, never service -> route.

Every function here is pure given its inputs and encodes the same truthfulness rules the
rest of the control plane enforces:

* a measured zero stays a measured zero (``$0.0000 · metered``), never collapsed to
  ``unknown``;
* an absent cost stays ``unknown`` — never a fabricated ``$0.0000``;
* mixed contributors stay ``mixed``;
* a missing ledger or a missing phase key is a NAMED absence, never fabricated;
* selection/delivery of knowledge is shown as exactly that — ``use`` is never claimed;
* timings carry a ``measured``/``unknown`` state and no fabricated ``0``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── path resolution + the recorded ledger ────────────────────────────────────────────────────


def _resolve_recorded_path(path: str) -> Path:
    """Resolve a recorded artifact path to THIS host's checkout.

    Runs execute in containers where the repo is mounted at ``/repo``; the ledger pointer they
    stamp is spelled ``/repo/experiments/...``. The room runs on the host, where the same file
    lives under the checkout — a raw ``Path(...)`` read therefore failed and every
    ledger-derived field silently rendered ``unknown`` (the fixed defect). The mapping is
    explicit: a leading ``/repo/`` resolves against the project root; anything else is used
    as written.
    """
    prefix = "/repo/"
    if path.startswith(prefix):
        from agentic_dynamics.core.paths import PROJECT_ROOT  # lazy: host checkout root

        return PROJECT_ROOT / path[len(prefix) :]
    return Path(path)


def recorded_ledger(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    """Read the run's recorded ledger artifact, or ``None`` when there is none/unreadable.

    The ledger pointer lives on the run row (``ledger_path``, stamped by the CLI's terminal
    write). It is the run's own artifact and the only place a workspace binding, prose
    narration, the independent test verdict, and the delivered-knowledge provenance are
    recorded today; a missing or unreadable file stays ``None`` so every field derived from
    it renders ``unknown`` rather than a fabricated value.
    """
    if not detail:
        return None
    path = str((detail.get("run") or {}).get("ledger_path") or "").strip()
    if not path:
        return None
    try:
        payload = json.loads(_resolve_recorded_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


# Backwards-compatible private alias (``glance.py`` imported ``_recorded_ledger``).
_recorded_ledger = recorded_ledger


# ── the shared labels ─────────────────────────────────────────────────────────────────────────


def _token(value: Any) -> str:
    """Render a control-record token as its string value (Enums via ``.value``)."""
    if value is None:
        return "unknown"
    raw = getattr(value, "value", value)
    return str(raw)


_TRUSTED_COST_SOURCES = frozenset({"metered", "estimated", "reconciled"})


def _cost_provenance(
    run: dict[str, Any], detail: dict[str, Any] | None, ledger: dict[str, Any] | None
) -> str:
    """The AGGREGATE's recorded spend with the AGGREGATE's own provenance.

    The label must describe the aggregate, never the first phase that happens to carry one
    (review finding P2): per-phase contributors (cost > 0) decide it — one uniform recorded
    source, ``mixed`` when contributors disagree, ``source unknown`` when none is recorded.

    A measured zero is a value (review finding P3): when the ledger records a recognized
    source for any phase, an explicit $0 is surfaced (``$0.0000 · metered``), never collapsed
    to ``unknown``; an absent amount with no recorded source still renders ``unknown`` —
    an absent measurement is not $0.
    """
    phases = [phase for phase in (ledger or {}).get("phases") or [] if isinstance(phase, dict)]
    contributors: list[str] = []
    for phase in phases:
        try:
            cost = float(phase.get("cost_usd"))
        except (TypeError, ValueError):
            cost = 0.0
        if cost > 0:
            contributors.append(str(phase.get("cost_source") or "").strip().lower())
    sources = [
        str(phase.get("cost_source") or "").strip().lower()
        for phase in phases
        if str(phase.get("cost_source") or "").strip().lower() in _TRUSTED_COST_SOURCES
    ]

    total: float | None = None
    candidates = (
        ((detail or {}).get("run") or {}).get("cost_usd"),
        run.get("cost_usd"),
        (ledger or {}).get("total_cost_usd"),
    )
    for candidate in candidates:
        try:
            value = float(candidate)
        except (TypeError, ValueError):
            continue
        if value > 0:
            total = value
            break
    if total is None:
        # A provenance LABEL cannot establish an amount. Accept a zero only when it is
        # EXPLICITLY recorded as the run total (the key is present and numeric), or when a
        # COMPLETE aggregate is derivable — every phase carries a numeric cost. Otherwise the
        # amount is unknown, never an invented $0.00 (review finding P2, second correction).
        recorded_total = None
        if isinstance(ledger, dict) and ledger.get("total_cost_usd") is not None:
            try:
                recorded_total = float(ledger["total_cost_usd"])
            except (TypeError, ValueError):
                recorded_total = None
        if recorded_total is not None and recorded_total >= 0:
            total = recorded_total
        else:
            amounts = []
            complete = bool(phases)
            for phase in phases:
                raw = phase.get("cost_usd")
                if raw is None:
                    complete = False
                    break
                try:
                    amounts.append(float(raw))
                except (TypeError, ValueError):
                    complete = False
                    break
            if complete:
                total = sum(amounts)
            else:
                return "unknown"

    if contributors:
        known = [source for source in contributors if source in _TRUSTED_COST_SOURCES]
        if not known:
            label = "source unknown"
        elif len(known) == len(contributors) and len(set(known)) == 1:
            label = known[0]
        else:
            label = "mixed"
    elif len(set(sources)) == 1:
        label = sources[0]
    elif sources:
        label = "mixed"
    else:
        label = "source unknown"
    return f"${total:.4f} · {label}"


def _attempt_number(detail: dict[str, Any] | None) -> str:
    """The run's current attempt number from its ``step_attempts`` rows, or ``unknown``.

    ``attempt_no`` is per step; the highest number any step reached is the run's current attempt
    depth (a retried phase records 1, then 2). No rows is ``unknown`` — never a hard-coded 1.
    """
    numbers: list[int] = []
    for attempt in (detail or {}).get("attempts") or []:
        try:
            numbers.append(int(attempt.get("attempt_no") or 0))
        except (TypeError, ValueError):
            continue
    current = max(numbers, default=0)
    return str(current) if current > 0 else "unknown"


def _workspace_target(detail: dict[str, Any] | None, ledger: dict[str, Any] | None) -> str:
    """The recorded workspace binding (the ledger's ``workdir``), or ``unknown``.

    Never ``wt/<run_id>``: a fabricated path pretends to name where the run's work lives and
    misdirects every downstream use of the row (including the dock's event binding).
    """
    if isinstance(ledger, dict):
        workdir = str(ledger.get("workdir") or "").strip()
        if workdir:
            return workdir
    return "unknown"


def _cell_binding(ledger: dict[str, Any] | None) -> str:
    """The recorded executor cell binding, or ``unknown``.

    The runner does not currently stamp its publish cell id (``FINOPS_CELL_ID`` or the
    deterministic ``wf_<spec>_<model>`` fallback) into the run ledger or the control database,
    so no explicit binding exists to read for most runs. When a recorded ledger DOES carry one
    (``cell_id``), the row exposes exactly that value; otherwise the field is ``unknown`` and
    the dock refuses to subscribe rather than guessing an id it would then mislabel live.
    """
    if isinstance(ledger, dict):
        cell = str(ledger.get("cell_id") or "").strip()
        if cell:
            return cell
    return "unknown"


def _narration_state(detail: dict[str, Any] | None, ledger: dict[str, Any] | None) -> str:
    """Whether recorded prose narration exists — never claimed without the record."""
    if ledger is None:
        return "narration unknown"
    for phase in ledger.get("phases") or []:
        if isinstance(phase, dict) and str(phase.get("final_response") or "").strip():
            return "narration recorded"
    for attempt in ledger.get("attempts") or []:
        if isinstance(attempt, dict) and attempt.get("confidence") is not None:
            return "narration recorded"
    return "no narration recorded"


def _measured_state(detail: dict[str, Any] | None, ledger: dict[str, Any] | None) -> str:
    """The recorded measured verdict — per TEST PHASE, never mixed across phases.

    Success and independence are properties of the SAME phase/attempt (review finding P1):
    a passing non-independent test alongside a failing independent one is a FAILURE, and an
    independent pending result is not a pass. Any failure wins; then any non-True outcome is
    pending; a pass requires every test outcome True, and only then may independence be
    claimed (all recorded-independent -> "independent tests passed"; otherwise the weaker
    "tests passed (independence unrecorded)").
    """
    if ledger is not None:
        tests = [
            phase
            for phase in ledger.get("phases") or []
            if isinstance(phase, dict) and str(phase.get("kind") or "") == "test"
        ]
        if tests:
            outcomes = [phase.get("test_executed_success") for phase in tests]
            if any(outcome is False for outcome in outcomes):
                failing = [phase for phase in tests if phase.get("test_executed_success") is False]
                independent_fail = any(
                    phase.get("evaluator_independent") is True for phase in failing
                )
                return "independent tests failed" if independent_fail else "tests failed"
            if any(outcome is not True for outcome in outcomes):
                return "test result pending"
            all_independent = all(phase.get("evaluator_independent") is True for phase in tests)
            if all_independent:
                return "independent tests passed"
            return "tests passed (independence unrecorded)"
    verdicts = [_token(gate.get("verdict")) for gate in (detail or {}).get("gates") or []]
    if "fail" in verdicts:
        return "gate failed"
    if "pass" in verdicts:
        return "gate passed"
    return "test result unknown" if ledger is None else "no test recorded"


def _receipt_state(detail: dict[str, Any] | None) -> str:
    """Whether a decision receipt is on record — an awaiting run implies nothing.

    ``recorded`` requires an approval row or a completed command carrying a receipt; a bare
    intent is ``pending``; a fully readable run with neither is ``missing``; an unreadable
    detail block is ``unknown``.
    """
    if not detail:
        return "unknown"
    if detail.get("approvals"):
        return "recorded"
    for command in detail.get("commands") or []:
        if (
            _token(command.get("state")) == "completed"
            and str(command.get("receipt_json") or "").strip()
        ):
            return "recorded"
    if detail.get("commands"):
        return "pending"
    return "missing"


# ── the additive derived blocks the run drawer consumes ───────────────────────────────────────


def cost_block(
    run: dict[str, Any], detail: dict[str, Any] | None, ledger: dict[str, Any] | None
) -> dict[str, Any]:
    """The run's aggregate cost with its own provenance label.

    ``provenance`` is the exact label ``glance`` emits: a measured zero is
    ``$0.0000 · metered``, an absent amount is ``unknown``, disagreeing contributors are
    ``mixed``. The amount never appears without the provenance that qualifies it.
    """
    return {"provenance": _cost_provenance(run, detail, ledger)}


def evidence_block(detail: dict[str, Any] | None, ledger: dict[str, Any] | None) -> dict[str, Any]:
    """The three evidence labels, exactly as the glance row emits them.

    ``measured`` is the independent verification verdict; ``narration`` is the agent's own
    claim; ``receipt`` is the decision record. Keeping them separate is the point — a process
    or agent claim is never shown as independent acceptance.
    """
    return {
        "measured": _measured_state(detail, ledger),
        "receipt": _receipt_state(detail),
        "narration": _narration_state(detail, ledger),
    }


def recorded_block(detail: dict[str, Any] | None, ledger: dict[str, Any] | None) -> dict[str, Any]:
    """The run's ledger pointer and whether that pointer actually resolved.

    ``ledger_path`` is the recorded pointer (``None`` when none was stamped);
    ``present`` is True only when the artifact was read. A pointer that does not resolve is
    ``present: false`` — a named gap, never a fabricated ledger.
    """
    path = str((detail or {}).get("run", {}).get("ledger_path") or "").strip()
    return {"ledger_path": path or None, "present": ledger is not None}


def _normalized_evidence(value: Any) -> list[dict[str, Any]] | None:
    """Normalize an ``augmentation_evidence`` list to the four provenance fields.

    ``None`` (the key is absent) is a named absence and stays ``None``; a present-but-empty
    list is a recorded zero and stays ``[]``. Entries are restricted to
    ``id``/``revision``/``source_type``/``locator`` so the drawer cannot accidentally render
    an unrecorded field as if it were measured.
    """
    if not isinstance(value, list):
        return None
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {key: item.get(key) for key in ("id", "revision", "source_type", "locator")}
        )
    return normalized


def delivered_knowledge_block(ledger: dict[str, Any] | None) -> dict[str, Any]:
    """What was SELECTED and DELIVERED into each phase's prepared prompt.

    Per phase, from the recorded ledger: the selected evidence ids, the per-evidence
    provenance (id/revision/source_type/locator), the fallback mode, retrieval leg errors,
    and the augmentation versions/tokens/cost. This is selection + delivery ONLY —
    ``use`` is fixed to ``not_established`` because an id proves neither relevance nor use;
    that is a separate, later judgement this surface does not make.

    A missing ledger is a named absence (``state: absent``); a key the ledger does not carry
    stays ``None`` rather than an empty list that would read as "recorded nothing".
    """
    if ledger is None:
        return {
            "state": "absent",
            "reason": "no ledger recorded",
            "use": "not_established",
            "phases": [],
        }
    phases: list[dict[str, Any]] = []
    for phase in ledger.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        raw_versions = phase.get("augmentation_versions")
        raw_tokens = phase.get("augmentation_tokens")
        raw_leg_errors = phase.get("retrieval_leg_errors")
        raw_cost = phase.get("augmentation_cost_usd")
        phases.append(
            {
                "phase": str(phase.get("phase") or phase.get("name") or "?"),
                "selected_evidence_ids": (
                    list(phase["selected_evidence_ids"])
                    if isinstance(phase.get("selected_evidence_ids"), list)
                    else None
                ),
                "augmentation_evidence": _normalized_evidence(phase.get("augmentation_evidence")),
                "fallback_mode": (
                    str(phase["fallback_mode"])
                    if isinstance(phase.get("fallback_mode"), str)
                    and str(phase.get("fallback_mode")).strip()
                    else None
                ),
                "retrieval_leg_errors": (
                    dict(raw_leg_errors) if isinstance(raw_leg_errors, dict) else None
                ),
                "augmentation_versions": (
                    dict(raw_versions) if isinstance(raw_versions, dict) else None
                ),
                "augmentation_tokens": (dict(raw_tokens) if isinstance(raw_tokens, dict) else None),
                "augmentation_cost_usd": (
                    float(raw_cost)
                    if isinstance(raw_cost, (int, float)) and not isinstance(raw_cost, bool)
                    else None
                ),
            }
        )
    return {"state": "recorded", "reason": None, "use": "not_established", "phases": phases}


def prepared_block(ledger: dict[str, Any] | None) -> dict[str, Any]:
    """The prepared-step transport reference per phase, or a named missing.

    The parent readies the EXACT step it hands a sibling child (``prepared-step/v1``) and
    records the clone-relative path + the prompt's sha256 on its phase result (which the run
    ledger serializes). This block surfaces that recorded reference so the drawer can point at
    the exact instruction that was delivered; a phase (or ledger) without one is a named
    ``missing``/``absent``, never an inferred path.
    """
    if ledger is None:
        return {"state": "absent", "reason": "no ledger recorded", "phases": []}
    phases: list[dict[str, Any]] = []
    for phase in ledger.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        path = phase.get("prepared_step_path")
        sha = phase.get("prepared_step_prompt_sha256")
        path_text = str(path).strip() if isinstance(path, str) else ""
        sha_text = str(sha).strip() if isinstance(sha, str) else ""
        phases.append(
            {
                "phase": str(phase.get("phase") or phase.get("name") or "?"),
                "state": "recorded" if path_text and sha_text else "missing",
                "prepared_step_path": path_text or None,
                "prompt_sha256": sha_text or None,
            }
        )
    return {"state": "recorded", "reason": None, "phases": phases}


def _timing_row(
    field: str, value: Any, *, scope: str | None = None, numeric: bool = False
) -> dict[str, Any]:
    """One timing row: ``measured`` only when the record actually carries a value.

    ``numeric`` fields (a duration in seconds) accept a real ``0.0`` as measured — a measured
    zero is not the same as an absent one. Everything else requires a non-empty string; a
    blank or missing value renders ``unknown`` with a null value (never a fabricated ``0``).
    """
    state = "unknown"
    if numeric:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            value = None
        else:
            state = "measured"
    elif value is not None and str(value).strip():
        state = "measured"
    else:
        value = None
    row: dict[str, Any] = {"field": field, "value": value, "state": state}
    if scope is not None:
        row["scope"] = scope
    return row


def timings_block(
    detail: dict[str, Any] | None, ledger: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """One row per timing field the records actually carry, each with its measured state.

    The exact declared set is read from the run/attempt control records and the run ledger:

    * the run record's ``started_at`` / ``ended_at``;
    * each attempt record's ``started_at`` / ``ended_at``;
    * each ledger phase's ``duration_s`` / ``leased_at`` / ``first_token_at``.

    No queue-wait or first-token value is invented: a field the record does not carry stays
    ``state: unknown`` with a null value, and a recorded ``0.0`` duration stays a measured
    zero.
    """
    detail = detail or {}
    rows: list[dict[str, Any]] = []
    run = detail.get("run") or {}
    rows.append(_timing_row("run.started_at", run.get("started_at")))
    rows.append(_timing_row("run.ended_at", run.get("ended_at")))
    for attempt in detail.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        scope = str(attempt.get("attempt_id") or attempt.get("step_id") or "?")
        rows.append(_timing_row("attempt.started_at", attempt.get("started_at"), scope=scope))
        rows.append(_timing_row("attempt.ended_at", attempt.get("ended_at"), scope=scope))
    for phase in (ledger or {}).get("phases") or []:
        if not isinstance(phase, dict):
            continue
        scope = str(phase.get("phase") or phase.get("name") or "?")
        rows.append(
            _timing_row("phase.duration_s", phase.get("duration_s"), scope=scope, numeric=True)
        )
        rows.append(_timing_row("phase.leased_at", phase.get("leased_at"), scope=scope))
        rows.append(_timing_row("phase.first_token_at", phase.get("first_token_at"), scope=scope))
    return rows
