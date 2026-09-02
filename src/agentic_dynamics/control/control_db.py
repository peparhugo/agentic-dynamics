"""Control database — the ONE durable control state (``control_db_publication`` p1).

Why this module exists
----------------------
Before it, "the run is done" was a *conversational* claim reconciled from six carriers, none
of which was the unquestioned authority:

* the run ledger JSON under ``experiments/results/workflows/<spec>/<ts>.json`` (written by
  :mod:`agentic_dynamics.runtime.workflow_runner` at the *end* of a run — so a killed run
  leaves no record at all);
* Redis ``story_status`` (hot, lossy, and never written by a runner that died);
* the derived spec index (``experiments/specs/index.json`` — a projection of the ledgers);
* git itself (the commits exist, but "committed" ≠ "promoted" ≠ "projected");
* the knowledge registry (did the projectors consume the result?);
* the website (did it actually publish?).

The deep review's diagnosis was that the master session was asked to *reconcile* those from
chat context every turn. This module is the answer: a single SQLite database, owned by the
orchestrator, that records what happened. **Every other carrier becomes a projection of it** —
the ledger included. The ledger stops being the source and becomes a rendering.

The hard rules this module implements
-------------------------------------
1. **ONE durable state.** ``experiments/results/control/control.db`` is the authoritative
   record of run state, step attempts, gate results, approvals, promotions, outbox events, and
   projection watermarks.
2. **The state vocabulary is exact, and never a bool.** :class:`RunState` has exactly twelve
   values. There is deliberately no ``completed``/``done``/``ok`` member: those words collapse
   distinctions the control plane exists to keep (a run can be ``merged`` but not yet
   ``projecting``; ``published`` but built from a ``quarantined`` sibling). The database stores
   the *string*; a ``bool ok`` column would re-introduce exactly the overload this deletes.
3. **Terminal states are immutable.** Once a run reaches ``published``/``failed``/``cancelled``/
   ``quarantined`` it can never be edited again — enforced twice, in Python
   (:class:`TerminalStateError`) *and* in the schema (a ``BEFORE UPDATE`` trigger), so a writer
   that bypasses this module's API still cannot rewrite history through raw SQL.
4. **The evidence tables are append-only.** ``gate_results``/``approvals``/``promotions``/
   ``run_transitions`` refuse ``UPDATE`` and ``DELETE`` at the schema level. Evidence that can
   be edited after the fact is not evidence.
5. **One writer.** The orchestrator (the composition root in ``scripts/run_workflow.py``) is
   the only process that opens the database for writing; every other consumer — the control
   packet, the Control Room, the supervisor — opens it via :meth:`ControlDB.open_read_only`,
   which refuses writes with :class:`ReadOnlyControlDBError` *and* opens the SQLite file with
   ``mode=ro`` so the refusal is structural, not merely polite. **That wiring is p2/p4's
   deliverable, not this phase's** — this module supplies the contract it will be wired to.

What this phase does NOT do
---------------------------
The phase scope fence is real. This module owns the schema and the row-level API. It does not
wire the runner (p2's atomic parent write), does not implement the outbox *publisher* or its
retry policy (p2), does not refresh watermarks from Redis consumer groups (p3), and does not
render the control packet (p4). The outbox and watermark accessors here are the storage
primitives those phases will call — deliberately mechanism-only, with no policy baked in.

Design notes worth knowing before you edit
------------------------------------------
*Why SQLite.* The control plane needs transactions (the p2 outbox write must be atomic with the
state transition it accompanies), a single-file durable artifact an operator can copy, and zero
daemons — because the failure this database exists to survive is "Redis was down / the runner
was killed". A JSONL ledger cannot give an atomic multi-row write; a server database adds the
very dependency that must not be able to take the control plane down.

*Why not STRICT tables.* SQLite 3.37+ supports ``STRICT``, and this host has 3.37.2 — but the
gain (type rigidity) is small next to the portability cost, so the schema uses ``CHECK``
constraints for the parts that actually matter: the state vocabularies. A bad state string is
rejected by the *database*, not only by the Python enum.

*Why ``run_transitions`` exists although the mandate lists seven tables.* The mandate requires
that "a run's full lifecycle transitions are recorded immutably". ``runs.state`` holds the
*current* state; the history has to live somewhere, and an append-only transition log is the
only shape that survives a crash between two transitions. It is additive to the mandated
schema, never a replacement for it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from agentic_dynamics.core.paths import PROJECT_ROOT

# ── Location ─────────────────────────────────────────────────────────────────────────────────

#: Repo-root-RELATIVE control directory. Relative because the same string is what a
#: containerized cell (which mounts the checkout at a different absolute path) resolves
#: against its own root — the KB artifact paths in :mod:`agentic_dynamics.core.paths` are
#: relative for exactly this reason.
CONTROL_DIR_REL = "experiments/results/control"

#: Repo-root-RELATIVE path of the control database itself.
CONTROL_DB_REL = f"{CONTROL_DIR_REL}/control.db"

#: Absolute default path. Writers resolve through :func:`resolve_db_path`, never this constant
#: directly, so the environment override below always applies.
CONTROL_DB_PATH = PROJECT_ROOT / CONTROL_DB_REL

#: Environment override, honoured by :func:`resolve_db_path`. Two real uses: a test that wants
#: a ``tmp_path`` database, and a containerized orchestrator whose checkout is mounted
#: elsewhere. An explicit constructor argument still wins over it.
CONTROL_DB_ENV = "FINOPS_CONTROL_DB"

#: Bumped when the schema changes in a way a reader must know about. Stored in ``control_meta``
#: at creation and verified on open — an unknown (future) version is refused rather than
#: silently misread, because a control plane that half-understands its own state is worse than
#: one that stops.
#:
#: History:
#:
#: * ``1`` — the p1 mandate: runs / run_transitions / step_attempts / gate_results / approvals /
#:   promotions / outbox / projection_watermarks.
#: * ``2`` — p6 adds ``publication_receipts`` + ``publication_deployments``: the publication
#:   transaction's durable record. Purely ADDITIVE (two new tables, no column touched), which is
#:   what makes :meth:`ControlDB._ensure_schema`'s in-place forward migration safe — see there.
#: * ``3`` — control_db_evidence e2 adds ``run_heartbeats`` (one row per run: the last proof of
#:   life the zombie-run sweep judges staleness from). Purely ADDITIVE (one new table, no column
#:   touched), so the same in-place forward migration applies: ``CREATE TABLE IF NOT EXISTS`` is
#:   re-applied against a v2 database and the recorded version is bumped by the generic
#:   ``CAST(value AS INTEGER) < 3`` guard in :meth:`ControlDB._ensure_schema`.
SCHEMA_VERSION = 3


# ── The state vocabularies ───────────────────────────────────────────────────────────────────


class RunState(str, Enum):
    """The exact twelve-value run vocabulary mandated by ``control_db_publication``.

    Read the values as answers to *distinct* questions, which is precisely why a single
    ``completed`` boolean cannot carry them:

    ==================== ==========================================================
    ``queued``           admitted and recorded, no work started
    ``running``          the orchestrator is executing steps
    ``awaiting_approval`` stopped at a checkpoint — a designed stop, never a failure
    ``verifying``        work finished; gates (tests, review, adversarial) are running
    ``promotable``       gates passed; the branch is eligible for the permanence gate
    ``promoting``        ``scripts/promote.py`` is squash-merging to main
    ``merged``           on main — but nothing downstream has consumed it yet
    ``projecting``       the knowledge projectors are consuming the run's events
    ``published``        projections complete and the public surface reflects it
    ``failed``           terminal negative outcome
    ``cancelled``        terminal, by operator or orchestrator decision, before merge
    ``quarantined``      terminal; output exists but is unaccounted-for (see
                         :mod:`agentic_dynamics.control.quarantine`)
    ==================== ==========================================================

    Note the two distinctions the old vocabulary destroyed: ``merged`` is *not* ``published``
    (a run can be on main with stale projections), and ``awaiting_approval`` is *not*
    ``failed`` (the P1 awaiting-approval fix in ``workflow_runner`` made the same point for
    ledger labels — see :func:`run_state_from_ledger_state`).

    Inherits ``str`` so a value compares equal to its wire form: ``RunState.MERGED == "merged"``
    is True, which keeps SQL binding and JSON rendering free of conversions.
    """

    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    VERIFYING = "verifying"
    PROMOTABLE = "promotable"
    PROMOTING = "promoting"
    MERGED = "merged"
    PROJECTING = "projecting"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"


#: The states from which nothing may follow. An UPDATE of a run in one of these is refused by
#: :meth:`ControlDB.transition_run` *and* by the ``runs_terminal_immutable`` trigger.
TERMINAL_RUN_STATES: frozenset[RunState] = frozenset(
    {RunState.PUBLISHED, RunState.FAILED, RunState.CANCELLED, RunState.QUARANTINED}
)

#: The forward path through the lifecycle — the happy sequence, one hop at a time. Abnormal
#: exits are added programmatically below so the two concerns stay legible separately.
_FORWARD_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.QUEUED: {RunState.RUNNING},
    # A running run may pause for approval, go straight to verification, or (for a run with no
    # gates) be immediately promotable.
    RunState.RUNNING: {RunState.AWAITING_APPROVAL, RunState.VERIFYING, RunState.PROMOTABLE},
    # An approved checkpoint resumes execution; an approval that *was* the last gate can hand
    # straight to verification.
    RunState.AWAITING_APPROVAL: {RunState.RUNNING, RunState.VERIFYING},
    # Verification can send work back (a gate found something), stop for a human, or clear the
    # run for promotion.
    RunState.VERIFYING: {RunState.RUNNING, RunState.AWAITING_APPROVAL, RunState.PROMOTABLE},
    RunState.PROMOTABLE: {RunState.PROMOTING},
    RunState.PROMOTING: {RunState.MERGED},
    RunState.MERGED: {RunState.PROJECTING},
    RunState.PROJECTING: {RunState.PUBLISHED},
}


def _build_allowed_transitions() -> dict[RunState, frozenset[RunState]]:
    """Compose the full transition graph: forward edges + the abnormal exits.

    Two rules govern the abnormal exits, and both encode a real operational fact:

    * ``failed`` and ``quarantined`` are reachable from **every** non-terminal state. Anything
      can break, and anything can turn out to have run outside its lease.
    * ``cancelled`` is reachable only *before* the work reaches main. Once a run is ``merged``,
      cancelling it is a lie — the commits are on the mainline and the honest terminal labels
      are ``failed`` (the outcome was bad) or ``quarantined`` (the outcome is unaccounted-for).
      A revert is a new run, not a retroactive cancellation of this one.
    """
    allowed: dict[RunState, set[RunState]] = {
        state: set(_FORWARD_TRANSITIONS.get(state, set())) for state in RunState
    }
    #: Cancellation is legitimate only while the work has not yet landed on main.
    pre_merge = {
        RunState.QUEUED,
        RunState.RUNNING,
        RunState.AWAITING_APPROVAL,
        RunState.VERIFYING,
        RunState.PROMOTABLE,
        RunState.PROMOTING,
    }
    for state in RunState:
        if state in TERMINAL_RUN_STATES:
            # Terminal means terminal: no outgoing edges at all, not even self-edges.
            allowed[state] = set()
            continue
        allowed[state].update({RunState.FAILED, RunState.QUARANTINED})
        if state in pre_merge:
            allowed[state].add(RunState.CANCELLED)
    return {state: frozenset(targets) for state, targets in allowed.items()}


#: ``state -> the states it may transition to``. Consulted by :meth:`ControlDB.transition_run`
#: and exported so the control packet (p4) can derive *safe actions* from the same graph the
#: database enforces, rather than from a second hand-written list that could drift.
ALLOWED_TRANSITIONS: dict[RunState, frozenset[RunState]] = _build_allowed_transitions()


class AttemptState(str, Enum):
    """Per-step-attempt outcome vocabulary.

    Deliberately *not* the same enum as :class:`RunState`: a step attempt answers "did this one
    invocation of this one step produce its result?", which is a different question from "where
    is this run in its lifecycle?". Sharing one enum is how the old code ended up overloading
    ``completed`` in the first place.

    The values mirror the runner's per-phase ``status`` strings (``ok``/``failed``/``awaiting``)
    so :func:`attempt_state_from_phase_status` is a total, lossless mapping.
    """

    QUEUED = "queued"
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"
    #: The step ran to completion and *correctly stopped* for a human (a checkpoint phase).
    #: Terminal for the attempt: the invocation is over. The run, meanwhile, sits in
    #: ``awaiting_approval`` — the run-level and attempt-level facts are separate on purpose.
    AWAITING = "awaiting"
    #: Not executed (already satisfied on resume, or fenced out by ``--only-phase``). Recorded
    #: rather than omitted, because "we chose not to run it" and "it never existed" are
    #: different facts and only one of them is a gap.
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


#: An attempt in one of these has produced its outcome; a second finish is refused (the same
#: immutability rule as runs, applied one level down).
TERMINAL_ATTEMPT_STATES: frozenset[AttemptState] = frozenset(
    {
        AttemptState.OK,
        AttemptState.FAILED,
        AttemptState.AWAITING,
        AttemptState.SKIPPED,
        AttemptState.CANCELLED,
    }
)


class GateVerdict(str, Enum):
    """What a gate concluded about a candidate sha.

    ``ERROR`` is distinct from ``FAIL`` on purpose: "the gate ran and the work is bad" and "the
    gate could not run" must never be collapsed, because the second one is not evidence about
    the work at all. ``WAIVED`` records an operator override *as a verdict* so the waiver is in
    the evidence trail instead of being an absent row.
    """

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    WAIVED = "waived"


class OutboxStatus(str, Enum):
    """Lifecycle of one outbox row (the mandated ``pending|delivered|dead`` vocabulary).

    ``delivered`` is written **only** after the knowledge stream acknowledges the payload —
    that ordering is what makes delivery at-least-once (a crash between the ack and the mark
    re-delivers; it never loses). The publisher that enforces it is p2's deliverable; this
    module only guarantees the storage can express the states.
    """

    PENDING = "pending"
    DELIVERED = "delivered"
    DEAD = "dead"


def _csv(values: Sequence[str]) -> str:
    """Render a vocabulary as a SQL string list for a ``CHECK (col IN (...))`` constraint.

    Generated from the enums rather than hand-typed so the schema and the Python vocabulary can
    never disagree — a drift that would let a "valid" enum value be rejected by the database at
    3am mid-run.
    """
    return ", ".join(f"'{value}'" for value in values)


# ── Errors ───────────────────────────────────────────────────────────────────────────────────


class ControlDBError(Exception):
    """Base class for every refusal this module raises."""


class ReadOnlyControlDBError(ControlDBError):
    """A write was attempted through a handle opened for reading.

    Raised by the API before SQLite is even touched, so the error names the *contract* ("the
    orchestrator is the only writer") rather than leaking an ``attempt to write a readonly
    database`` from the driver.
    """


class UnknownStateError(ControlDBError):
    """A state string outside the exact vocabulary was supplied."""


class InvalidTransitionError(ControlDBError):
    """A transition not present in :data:`ALLOWED_TRANSITIONS` was attempted."""


class TerminalStateError(ControlDBError):
    """An attempt to modify a record that has already reached a terminal state."""


class ControlFieldError(ControlDBError):
    """A required field was missing or empty.

    Used where a silently-empty value would be a *false record* rather than a small gap — most
    importantly a gate result without its ``candidate_sha``, which would be a verdict about
    nothing in particular while looking exactly like a verdict about the work.
    """


class UnknownRunError(ControlDBError):
    """A row was addressed to a ``run_id`` that does not exist."""


# ── Small helpers ────────────────────────────────────────────────────────────────────────────


def _now() -> str:
    """UTC ISO-8601 with a ``Z`` suffix — the timestamp shape used across this repo."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    """A short, prefixed, collision-safe identifier (``gate-3f9a1c2d4e5b``).

    Prefixed because these ids end up in logs, control packets, and operator commands, where
    "which kind of thing is this?" should be readable without a lookup.
    """
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _require(value: str | None, field_name: str) -> str:
    """Return a non-empty stripped ``value`` or raise :class:`ControlFieldError`."""
    text = (value or "").strip()
    if not text:
        raise ControlFieldError(f"control_db: {field_name} is required and must be non-empty")
    return text


def _coerce_run_state(value: RunState | str) -> RunState:
    """Accept an enum member or its wire string; refuse anything else.

    The refusal is loud (:class:`UnknownStateError` naming the full vocabulary) because a typo
    in a state string is the exact class of bug that silently creates a thirteenth state.
    """
    if isinstance(value, RunState):
        return value
    try:
        return RunState(str(value))
    except ValueError as exc:
        vocabulary = ", ".join(s.value for s in RunState)
        raise UnknownStateError(
            f"control_db: {value!r} is not a run state — the vocabulary is exactly: {vocabulary}"
        ) from exc


def _coerce_attempt_state(value: AttemptState | str) -> AttemptState:
    """Enum-or-string coercion for attempt states (see :func:`_coerce_run_state`)."""
    if isinstance(value, AttemptState):
        return value
    try:
        return AttemptState(str(value))
    except ValueError as exc:
        vocabulary = ", ".join(s.value for s in AttemptState)
        raise UnknownStateError(
            f"control_db: {value!r} is not an attempt state — the vocabulary is: {vocabulary}"
        ) from exc


def _coerce_verdict(value: GateVerdict | str) -> GateVerdict:
    """Enum-or-string coercion for gate verdicts (see :func:`_coerce_run_state`)."""
    if isinstance(value, GateVerdict):
        return value
    try:
        return GateVerdict(str(value))
    except ValueError as exc:
        vocabulary = ", ".join(v.value for v in GateVerdict)
        raise UnknownStateError(
            f"control_db: {value!r} is not a gate verdict — the vocabulary is: {vocabulary}"
        ) from exc


def _loads(payload: str | None) -> Any:
    """Parse a stored JSON column, tolerating ``NULL``/empty as ``None``.

    Deliberately not tolerant of *malformed* JSON: a corrupt evidence blob raises, because
    silently returning ``None`` would present "we cannot read the evidence" as "there is no
    evidence" — the same coercion the quarantine ledger refuses for its own reads.
    """
    if payload is None or payload == "":
        return None
    return json.loads(payload)


# ── Records (the read model) ─────────────────────────────────────────────────────────────────
#
# Frozen dataclasses, per the repo convention (dataclasses over dicts). Frozen specifically:
# these are *readings* of durable rows, and a mutable reading invites code that "updates" an
# object and assumes the database followed.


@dataclass(frozen=True)
class RunRecord:
    """One row of ``runs`` — a workflow run's identity and current lifecycle position."""

    run_id: str
    spec_name: str
    #: Identifies the exact spec bytes/revision executed (the p0 pin's sha256, a git sha, or a
    #: ``<name>@<version>`` spec_id). Without it, a run's mandate is unrecoverable after the
    #: spec file changes — which it always does.
    workflow_revision_id: str
    #: The sha the run's work is *about* — the branch head under review. Gates and approvals
    #: carry their own copy so a verdict can never be silently re-attached to different code.
    candidate_sha: str
    state: RunState
    model: str
    started_at: str
    ended_at: str
    #: Path to the run ledger JSON, when one exists. A *pointer to a projection* — never a
    #: fallback source of truth. A run with no ledger is fully reconstructible from this db.
    ledger_path: str
    cost_usd: float

    @property
    def is_terminal(self) -> bool:
        """True when no further transition is possible (and no field may change)."""
        return self.state in TERMINAL_RUN_STATES


@dataclass(frozen=True)
class RunHeartbeat:
    """One row of ``run_heartbeats`` — a run's last proof of life.

    Read by the zombie-run sweep (control_db_evidence e2) to tell a genuinely-live ``running``
    run from a dangling one: the orchestrator's composition root beats this row while its
    process is alive, and a killed runner stops beating, so an expired ``last_seen_at`` is the
    positive evidence of death the sweep is allowed to act on.
    """

    run_id: str
    #: UTC ISO-8601 with a ``Z`` suffix — the same stamp shape as every other column, so the
    #: sweep's staleness comparison is a string compare over one format (see ``outbox._iso``).
    last_seen_at: str
    beat_count: int
    actor: str


@dataclass(frozen=True)
class StepAttemptRecord:
    """One row of ``step_attempts`` — a single invocation of a single step.

    "Attempt", not "phase": a retried phase produces two rows with the same ``step_id`` and
    different ``attempt_no``, which is how retry rate and escalation become measurable instead
    of being overwritten by the last attempt.
    """

    attempt_id: str
    run_id: str
    step_id: str
    attempt_no: int
    model: str
    state: AttemptState
    started_at: str
    ended_at: str
    tokens: int
    cost_usd: float
    #: The process exit code, when the step ran a process (the P0 exit-code contract).
    #: ``None`` means "not applicable / not observed" — never coerced to 0, which would read
    #: as success.
    exit_code: int | None
    error: str

    @property
    def is_terminal(self) -> bool:
        """True when the attempt has produced its outcome and may not be re-finished."""
        return self.state in TERMINAL_ATTEMPT_STATES


@dataclass(frozen=True)
class GateResultRecord:
    """One row of ``gate_results`` — a gate's verdict about a specific candidate sha.

    ``candidate_sha`` is mandatory (:class:`ControlFieldError` when empty): a verdict that does
    not name the code it judged is not evidence, and is exactly how a stale PASS gets reused
    for a different tree.
    """

    gate_id: str
    run_id: str
    step_id: str
    verdict: GateVerdict
    #: Free-form structured evidence (test counts, reviewer findings, tool output digests).
    #: Stored as JSON text; read back parsed by :attr:`evidence`.
    evidence_json: str
    #: What produced the verdict — ``pytest``, a reviewer model id, ``operator``. The
    #: independence conventions (an adversarial reviewer must be a different model) are only
    #: checkable if the executor is recorded.
    executor: str
    candidate_sha: str
    started_at: str
    ended_at: str

    @property
    def evidence(self) -> Any:
        """The parsed :attr:`evidence_json` (``None`` when absent)."""
        return _loads(self.evidence_json)


@dataclass(frozen=True)
class ApprovalRecord:
    """One row of ``approvals`` — a human decision, bound to a gate and a candidate sha."""

    approval_id: str
    run_id: str
    gate_id: str
    candidate_sha: str
    operator: str
    decided_at: str
    #: Where the signed artifact lives (a decision doc, a checkpoint contract file).
    artifact_path: str


@dataclass(frozen=True)
class PromotionRecord:
    """One row of ``promotions`` — the permanence gate's record of what reached main.

    Written by the promoter (``scripts/promote.py``, the only push-to-main path). ``base_sha``
    plus ``squash_sha`` make the merge independently re-derivable: you can check out the base,
    replay the squash, and compare.
    """

    run_id: str
    candidate_sha: str
    base_sha: str
    squash_sha: str
    pushed_at: str
    #: The actor that pushed — mapped from the mandated ``by`` column (a SQL keyword, so it is
    #: quoted in the DDL and renamed here for ergonomics).
    by: str


@dataclass(frozen=True)
class PublicationReceiptRecord:
    """One row of ``publication_receipts`` — what was published, from which tree, by whom (p6).

    The receipt is the site's evidence chain in one object: the tree (``repo_sha``), the two
    build artifacts it produced (``data_manifest_sha256``/``data_js_sha256``), the headline
    number those artifacts assert (``sessions_total``), and the projection frontier the data was
    derived from (inside :attr:`receipt_json`). Every public number on the website is supposed
    to trace to one of these rows, which is only meaningful because the row cannot be edited.
    """

    receipt_id: str
    repo_sha: str
    #: The full ``publication/v1`` document. The authority; the columns are a projection of it.
    receipt_json: str
    generated_at: str
    #: Empty when the publication was an operator action rather than a workflow run.
    run_id: str = ""
    data_manifest_sha256: str = ""
    data_js_sha256: str = ""
    #: ``None`` when the build could not report it — unknown, never a fabricated ``0`` (a zero
    #: session count that reads as measured is exactly the class of lie this table exists to end).
    sessions_total: int | None = None
    receipt_sha256: str = ""
    operator: str = ""

    @property
    def receipt(self) -> Any:
        """The parsed :attr:`receipt_json`."""
        return _loads(self.receipt_json)


@dataclass(frozen=True)
class DeploymentRecord:
    """One row of ``publication_deployments`` — one host's outcome for one receipt (p6).

    Two rows per healthy publication: the canonical host and the mirror. Recording them
    separately is the point — the dual-host rule is checkable ("does this receipt have a
    succeeded row for BOTH roles?") instead of being an instruction someone has to remember to
    follow twice.
    """

    deployment_id: str
    receipt_id: str
    #: ``canonical`` or ``mirror`` — the ROLE, so the pair is checkable without knowing today's
    #: project names.
    host_role: str
    firebase_project: str
    #: The provider's deployment identifier (a Firebase Hosting release/version id). Without it,
    #: "we deployed" is an assertion no one can check against the provider.
    release_id: str
    hosting_url: str
    #: ``succeeded`` or ``failed``. A failed host is RECORDED, not omitted: a publication that
    #: reached one host and not the other must be visible, and an absent row cannot say that.
    status: str
    deployed_at: str
    detail: str = ""


@dataclass(frozen=True)
class OutboxRecord:
    """One row of ``outbox`` — an event awaiting at-least-once delivery to the knowledge stream.

    The transactional-outbox pattern: the parent run writes its state transition *and* the
    events it wants emitted in ONE database transaction, so there is no window where the state
    moved but the emission was lost (today's failure: best-effort fire-and-forget from each
    child). A separate publisher then drains the table. **That publisher is p2's deliverable.**
    """

    event_id: str
    run_id: str
    payload_json: str
    status: OutboxStatus
    attempts: int
    #: Earliest time a retry may be attempted (ISO-8601). Empty means "eligible now".
    next_retry_at: str
    created_at: str
    #: Additive beyond the mandated columns, and honest about why: a ``dead`` row with no
    #: recorded cause is an alert with no diagnosis. Filled by the p2 publisher.
    delivered_at: str = ""
    last_error: str = ""

    @property
    def payload(self) -> Any:
        """The parsed :attr:`payload_json`."""
        return _loads(self.payload_json)


@dataclass(frozen=True)
class ProjectionWatermark:
    """One row of ``projection_watermarks`` — how far a downstream projector has consumed.

    One row per projection (``registry``/``chroma``/``neo4j``/``ledger``). The point is to make
    a *stale* projector visible: a consumer that stopped an hour ago has an old
    ``last_success_at`` and a growing ``lag_events``, instead of reading as "current" because
    nothing contradicted it. The consumer-loop wiring that refreshes these is p3's deliverable.
    """

    projection: str
    #: The last stream id this projection confirmed (XACKed).
    last_event_id: str
    #: The stream head at the time of the reading — the thing ``last_event_id`` lags behind.
    source_head_event_id: str
    #: Events between the two ids. ``None`` when not computed: unknown lag is recorded as
    #: unknown, never as ``0`` (the repo's null-not-zero discipline — a fabricated 0 would read
    #: as "fully caught up", the single most dangerous wrong answer this table can give).
    lag_events: int | None
    last_success_at: str
    last_error: str


@dataclass(frozen=True)
class StateTransition:
    """One row of ``run_transitions`` — an immutable edge in a run's lifecycle history."""

    transition_id: int
    run_id: str
    #: ``None`` for the creation edge (nothing → ``queued``).
    from_state: RunState | None
    to_state: RunState
    at: str
    #: Why the transition happened, in one line (a gate name, an operator note, an error head).
    reason: str
    #: Who/what caused it (``orchestrator``, ``promoter``, an operator handle).
    actor: str


@dataclass(frozen=True)
class ReconstructedRun:
    """A complete run, rebuilt from the control database ALONE.

    This type is the mandate's proof obligation made executable: "a run can be reconstructed
    from the db alone — the ledger becomes a projection, not the source". If this object can be
    built without reading ``experiments/results/workflows/**``, Redis, or the spec index, then
    the control database really is the authority and everything else really is a rendering.
    """

    run: RunRecord
    transitions: list[StateTransition] = field(default_factory=list)
    attempts: list[StepAttemptRecord] = field(default_factory=list)
    gate_results: list[GateResultRecord] = field(default_factory=list)
    approvals: list[ApprovalRecord] = field(default_factory=list)
    promotions: list[PromotionRecord] = field(default_factory=list)
    outbox_events: list[OutboxRecord] = field(default_factory=list)

    @property
    def state_path(self) -> list[str]:
        """The states the run passed through, in order — its lifecycle as a readable list."""
        return [t.to_state.value for t in self.transitions]

    @property
    def attempt_cost_usd(self) -> float:
        """Cost re-derived by summing attempts.

        Kept separate from :attr:`RunRecord.cost_usd` (which the orchestrator records at the
        run level) precisely so the two can be *compared*: a divergence means an attempt was
        never recorded, which is a measurement gap worth surfacing rather than averaging away.
        """
        return round(sum(a.cost_usd for a in self.attempts), 6)

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready rendering — the shape a ledger projection (or p4's packet) can build on."""
        return {
            "run": {
                "run_id": self.run.run_id,
                "spec_name": self.run.spec_name,
                "workflow_revision_id": self.run.workflow_revision_id,
                "candidate_sha": self.run.candidate_sha,
                "state": self.run.state.value,
                "model": self.run.model,
                "started_at": self.run.started_at,
                "ended_at": self.run.ended_at,
                "ledger_path": self.run.ledger_path,
                "cost_usd": self.run.cost_usd,
            },
            "state_path": self.state_path,
            "attempts": [
                {
                    "attempt_id": a.attempt_id,
                    "step_id": a.step_id,
                    "attempt_no": a.attempt_no,
                    "model": a.model,
                    "state": a.state.value,
                    "tokens": a.tokens,
                    "cost_usd": a.cost_usd,
                    "exit_code": a.exit_code,
                    "error": a.error,
                }
                for a in self.attempts
            ],
            "gate_results": [
                {
                    "gate_id": g.gate_id,
                    "step_id": g.step_id,
                    "verdict": g.verdict.value,
                    "executor": g.executor,
                    "candidate_sha": g.candidate_sha,
                    "evidence": g.evidence,
                }
                for g in self.gate_results
            ],
            "approvals": [
                {
                    "approval_id": ap.approval_id,
                    "gate_id": ap.gate_id,
                    "candidate_sha": ap.candidate_sha,
                    "operator": ap.operator,
                    "decided_at": ap.decided_at,
                }
                for ap in self.approvals
            ],
            "promotions": [
                {
                    "candidate_sha": p.candidate_sha,
                    "base_sha": p.base_sha,
                    "squash_sha": p.squash_sha,
                    "pushed_at": p.pushed_at,
                    "by": p.by,
                }
                for p in self.promotions
            ],
        }


# ── Schema ───────────────────────────────────────────────────────────────────────────────────
#
# One string, applied with executescript() inside a transaction. Every statement is
# IF NOT EXISTS so opening an existing database is a no-op — the orchestrator opens this file
# on every run and must never need a migration step for the current version.

SCHEMA_SQL = f"""
-- Housekeeping: the schema version and the monotonic control epoch. A key/value table rather
-- than PRAGMA user_version because the epoch needs to live somewhere transactional anyway.
-- The epoch counts EVERY durable state change (control_db_evidence e4): a run-level transition
-- (runs.state moving) OR a phase-level one (a step_attempt's start/end), each of which bumps it
-- inside its own transaction.
CREATE TABLE IF NOT EXISTS control_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- runs — the mandated columns, exactly. `state` is a string constrained to the twelve-value
-- vocabulary by the database itself: an invalid state cannot exist even if written by raw SQL.
CREATE TABLE IF NOT EXISTS runs (
    run_id               TEXT PRIMARY KEY,
    spec_name            TEXT NOT NULL,
    workflow_revision_id TEXT NOT NULL DEFAULT '',
    candidate_sha        TEXT NOT NULL DEFAULT '',
    state                TEXT NOT NULL CHECK (state IN ({_csv([s.value for s in RunState])})),
    model                TEXT NOT NULL DEFAULT '',
    started_at           TEXT NOT NULL DEFAULT '',
    ended_at             TEXT NOT NULL DEFAULT '',
    ledger_path          TEXT NOT NULL DEFAULT '',
    cost_usd             REAL NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_runs_state ON runs(state);
CREATE INDEX IF NOT EXISTS idx_runs_spec_name ON runs(spec_name);
CREATE INDEX IF NOT EXISTS idx_runs_candidate_sha ON runs(candidate_sha);

-- run_heartbeats — one row per run: the last time a LIVE orchestrator proved it was alive.
-- The runs table's `state = 'running'` means "the orchestrator started work", not "the
-- orchestrator is still alive": a killed runner leaves a dangling 'running' row (proven
-- 2026-09-02 — two killed runs needed manual cancellation). The zombie-run sweep
-- (control_db_evidence e2) cancels a 'running' run ONLY when this row's last_seen_at is old
-- enough — never a run whose heartbeat is fresh, and never a run with no heartbeat row at all
-- (no liveness information is not evidence of death). Heartbeats are NOT state transitions: a
-- beat upserts this row without touching `runs`, `run_transitions`, or the control epoch.
CREATE TABLE IF NOT EXISTS run_heartbeats (
    run_id       TEXT PRIMARY KEY REFERENCES runs(run_id),
    last_seen_at TEXT NOT NULL,
    beat_count   INTEGER NOT NULL DEFAULT 0,
    actor        TEXT NOT NULL DEFAULT ''
);

-- run_transitions — the append-only lifecycle history (additive to the mandate; see the module
-- docstring). AUTOINCREMENT so ids are strictly increasing even across deletes-that-cannot-
-- happen: ordering by transition_id is a total order on a run's history.
CREATE TABLE IF NOT EXISTS run_transitions (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    from_state    TEXT     CHECK (from_state IS NULL
                                  OR from_state IN ({_csv([s.value for s in RunState])})),
    to_state      TEXT NOT NULL CHECK (to_state IN ({_csv([s.value for s in RunState])})),
    at            TEXT NOT NULL,
    reason        TEXT NOT NULL DEFAULT '',
    actor         TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_run_transitions_run ON run_transitions(run_id, transition_id);

-- step_attempts — one row per invocation. The UNIQUE index is the retry contract: the same
-- (run, step, attempt_no) cannot be recorded twice, so a re-run must increment, never overwrite.
CREATE TABLE IF NOT EXISTS step_attempts (
    attempt_id TEXT PRIMARY KEY,
    run_id     TEXT NOT NULL REFERENCES runs(run_id),
    step_id    TEXT NOT NULL,
    attempt_no INTEGER NOT NULL,
    model      TEXT NOT NULL DEFAULT '',
    state      TEXT NOT NULL
               CHECK (state IN ({_csv([s.value for s in AttemptState])})),
    started_at TEXT NOT NULL DEFAULT '',
    ended_at   TEXT NOT NULL DEFAULT '',
    tokens     INTEGER NOT NULL DEFAULT 0,
    cost_usd   REAL NOT NULL DEFAULT 0.0,
    exit_code  INTEGER,
    error      TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_step_attempts_run_step_no
    ON step_attempts(run_id, step_id, attempt_no);
CREATE INDEX IF NOT EXISTS idx_step_attempts_run ON step_attempts(run_id);

-- gate_results — append-only verdicts. candidate_sha is NOT NULL *and* non-empty (the CHECK),
-- because a verdict about an unnamed tree is the stale-PASS bug waiting to happen.
CREATE TABLE IF NOT EXISTS gate_results (
    gate_id       TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    step_id       TEXT NOT NULL,
    verdict       TEXT NOT NULL
                  CHECK (verdict IN ({_csv([v.value for v in GateVerdict])})),
    evidence_json TEXT NOT NULL DEFAULT '',
    executor      TEXT NOT NULL DEFAULT '',
    candidate_sha TEXT NOT NULL CHECK (candidate_sha <> ''),
    started_at    TEXT NOT NULL DEFAULT '',
    ended_at      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_gate_results_run ON gate_results(run_id);
CREATE INDEX IF NOT EXISTS idx_gate_results_candidate_sha ON gate_results(candidate_sha);

-- approvals — append-only human decisions.
CREATE TABLE IF NOT EXISTS approvals (
    approval_id   TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    gate_id       TEXT NOT NULL DEFAULT '',
    candidate_sha TEXT NOT NULL CHECK (candidate_sha <> ''),
    operator      TEXT NOT NULL CHECK (operator <> ''),
    decided_at    TEXT NOT NULL,
    artifact_path TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_approvals_run ON approvals(run_id);

-- promotions — append-only. Keyed by (run_id, candidate_sha): one promotion per sha per run,
-- so a re-promotion of the SAME sha is refused as the duplicate it is, while promoting a
-- corrected sha remains possible. "by" is quoted throughout: it is a SQL keyword, and the
-- mandate names the column.
CREATE TABLE IF NOT EXISTS promotions (
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    candidate_sha TEXT NOT NULL CHECK (candidate_sha <> ''),
    base_sha      TEXT NOT NULL DEFAULT '',
    squash_sha    TEXT NOT NULL DEFAULT '',
    pushed_at     TEXT NOT NULL DEFAULT '',
    "by"          TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (run_id, candidate_sha)
);
CREATE INDEX IF NOT EXISTS idx_promotions_candidate_sha ON promotions(candidate_sha);

-- outbox — the transactional outbox. Rows here ARE mutable (status/attempts/next_retry_at are
-- the retry state machine), which is why no immutability trigger guards this table.
CREATE TABLE IF NOT EXISTS outbox (
    event_id      TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    payload_json  TEXT NOT NULL,
    status        TEXT NOT NULL
                  CHECK (status IN ({_csv([s.value for s in OutboxStatus])})),
    attempts      INTEGER NOT NULL DEFAULT 0,
    next_retry_at TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    delivered_at  TEXT NOT NULL DEFAULT '',
    last_error    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_outbox_run ON outbox(run_id);

-- projection_watermarks — one row per projection, upserted by its consumer loop (p3).
CREATE TABLE IF NOT EXISTS projection_watermarks (
    projection            TEXT PRIMARY KEY,
    last_event_id         TEXT NOT NULL DEFAULT '',
    source_head_event_id  TEXT NOT NULL DEFAULT '',
    lag_events            INTEGER,
    last_success_at       TEXT NOT NULL DEFAULT '',
    last_error            TEXT NOT NULL DEFAULT ''
);

-- publication_receipts — the publication transaction's durable record (p6). ONE row per
-- executed publication: the receipt document itself, plus the four fields a later reader most
-- often wants to filter on lifted out into columns. The receipt is the SINGLE source for every
-- public number on the site, so it is append-only: a receipt that could be edited after the
-- fact would let the record of what was published drift from what actually was.
CREATE TABLE IF NOT EXISTS publication_receipts (
    receipt_id           TEXT PRIMARY KEY,
    -- Nullable-by-convention (empty string): a publication is normally an operator action at
    -- the permanence gate, not a workflow run, so most receipts have no run to point at. When
    -- one does, the FK ties the release back to the run that produced the candidate.
    run_id               TEXT     REFERENCES runs(run_id),
    -- The exact tree that was published. Empty is refused: a receipt for an unnamed tree is
    -- the stale-PASS bug in publication form.
    repo_sha             TEXT NOT NULL CHECK (repo_sha <> ''),
    data_manifest_sha256 TEXT NOT NULL DEFAULT '',
    data_js_sha256       TEXT NOT NULL DEFAULT '',
    sessions_total       INTEGER,
    generated_at         TEXT NOT NULL,
    -- The whole publication/v1 document, verbatim. The columns above are a projection of it;
    -- this is the authority, so a future field added to the schema is not lost by this table.
    receipt_json         TEXT NOT NULL,
    receipt_sha256       TEXT NOT NULL DEFAULT '',
    operator             TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_publication_receipts_repo_sha
    ON publication_receipts(repo_sha);
CREATE INDEX IF NOT EXISTS idx_publication_receipts_run ON publication_receipts(run_id);

-- publication_deployments — one row per HOST per receipt. The dual-host rule (canonical
-- ai-finops-rulebook + mirror agentic-dynamics) is enforced by recording each host separately:
-- "both hosts deployed" becomes a countable fact rather than an assertion, so a publication
-- that reached one host and not the other is visible in the database instead of in someone's
-- memory of which of the two commands they ran.
CREATE TABLE IF NOT EXISTS publication_deployments (
    deployment_id    TEXT PRIMARY KEY,
    receipt_id       TEXT NOT NULL REFERENCES publication_receipts(receipt_id),
    -- The role this host plays: 'canonical' or 'mirror'. Stored as the role rather than only
    -- the project id so the pair can be checked without knowing today's project names.
    host_role        TEXT NOT NULL CHECK (host_role <> ''),
    firebase_project TEXT NOT NULL CHECK (firebase_project <> ''),
    -- The deployment identifier the provider returned (a Firebase Hosting release/version id).
    -- This is the thing the mandate asks to be recorded: without it, "we deployed" cannot be
    -- checked against the provider.
    release_id       TEXT NOT NULL DEFAULT '',
    hosting_url      TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
    deployed_at      TEXT NOT NULL,
    detail           TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_publication_deployments_receipt_host
    ON publication_deployments(receipt_id, host_role);
CREATE INDEX IF NOT EXISTS idx_publication_deployments_receipt
    ON publication_deployments(receipt_id);

-- ── Immutability triggers ───────────────────────────────────────────────────────────────────
-- Python-level checks protect callers who use this API. These triggers protect the database
-- from callers who do not — a sqlite3 shell, a future script, a well-meaning fix. History that
-- can be edited is not history.

CREATE TRIGGER IF NOT EXISTS runs_terminal_immutable
BEFORE UPDATE ON runs
WHEN OLD.state IN ({_csv([s.value for s in TERMINAL_RUN_STATES])})
BEGIN
    SELECT RAISE(ABORT, 'control_db: run is terminal — terminal runs are immutable');
END;

CREATE TRIGGER IF NOT EXISTS runs_no_delete
BEFORE DELETE ON runs
BEGIN
    SELECT RAISE(ABORT, 'control_db: runs are append-only — a run is never deleted');
END;

CREATE TRIGGER IF NOT EXISTS step_attempts_terminal_immutable
BEFORE UPDATE ON step_attempts
WHEN OLD.state IN ({_csv([s.value for s in TERMINAL_ATTEMPT_STATES])})
BEGIN
    SELECT RAISE(ABORT, 'control_db: attempt already finished — finished attempts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS step_attempts_no_delete
BEFORE DELETE ON step_attempts
BEGIN
    SELECT RAISE(ABORT, 'control_db: step_attempts are append-only');
END;

CREATE TRIGGER IF NOT EXISTS gate_results_no_update
BEFORE UPDATE ON gate_results
BEGIN
    SELECT RAISE(ABORT, 'control_db: gate results are append-only evidence');
END;

CREATE TRIGGER IF NOT EXISTS gate_results_no_delete
BEFORE DELETE ON gate_results
BEGIN
    SELECT RAISE(ABORT, 'control_db: gate results are append-only evidence');
END;

CREATE TRIGGER IF NOT EXISTS approvals_no_update
BEFORE UPDATE ON approvals
BEGIN
    SELECT RAISE(ABORT, 'control_db: approvals are append-only');
END;

CREATE TRIGGER IF NOT EXISTS approvals_no_delete
BEFORE DELETE ON approvals
BEGIN
    SELECT RAISE(ABORT, 'control_db: approvals are append-only');
END;

CREATE TRIGGER IF NOT EXISTS promotions_no_update
BEFORE UPDATE ON promotions
BEGIN
    SELECT RAISE(ABORT, 'control_db: promotions are append-only');
END;

CREATE TRIGGER IF NOT EXISTS promotions_no_delete
BEFORE DELETE ON promotions
BEGIN
    SELECT RAISE(ABORT, 'control_db: promotions are append-only');
END;

CREATE TRIGGER IF NOT EXISTS run_transitions_no_update
BEFORE UPDATE ON run_transitions
BEGIN
    SELECT RAISE(ABORT, 'control_db: the transition log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS run_transitions_no_delete
BEFORE DELETE ON run_transitions
BEGIN
    SELECT RAISE(ABORT, 'control_db: the transition log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS publication_receipts_no_update
BEFORE UPDATE ON publication_receipts
BEGIN
    SELECT RAISE(ABORT, 'control_db: publication receipts are append-only evidence');
END;

CREATE TRIGGER IF NOT EXISTS publication_receipts_no_delete
BEFORE DELETE ON publication_receipts
BEGIN
    SELECT RAISE(ABORT, 'control_db: publication receipts are append-only evidence');
END;

CREATE TRIGGER IF NOT EXISTS publication_deployments_no_update
BEFORE UPDATE ON publication_deployments
BEGIN
    SELECT RAISE(ABORT, 'control_db: deployment records are append-only evidence');
END;

CREATE TRIGGER IF NOT EXISTS publication_deployments_no_delete
BEFORE DELETE ON publication_deployments
BEGIN
    SELECT RAISE(ABORT, 'control_db: deployment records are append-only evidence');
END;
"""

#: The tables this schema guarantees — exported so the schema test asserts against a named
#: contract instead of a literal list copied into the test (which would drift).
CONTROL_TABLES: tuple[str, ...] = (
    "runs",
    "run_transitions",
    "step_attempts",
    "gate_results",
    "approvals",
    "promotions",
    "outbox",
    "projection_watermarks",
    "publication_receipts",
    "publication_deployments",
    "control_meta",
)


def resolve_db_path(path: str | Path | None = None) -> Path:
    """Resolve the control database path.

    Precedence, most specific first:

    1. an explicit ``path`` argument (tests, tools pointing at a copy);
    2. the :data:`CONTROL_DB_ENV` environment variable (a containerized orchestrator, or a
       whole test session redirected away from the real database);
    3. :data:`CONTROL_DB_PATH` — ``<repo>/experiments/results/control/control.db``.

    Returns an absolute path; the parent directory is *not* created here (opening for reading
    must never create anything — see :meth:`ControlDB.open_read_only`).
    """
    if path is not None:
        return Path(path).expanduser().resolve()
    override = os.environ.get(CONTROL_DB_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return CONTROL_DB_PATH


class ControlDB:
    """The control database handle — the orchestrator's writer, everyone else's reader.

    Typical writer use (the composition root, p2's wiring)::

        with ControlDB.open() as db:
            run = db.create_run(spec_name="control_db_publication", model="anthropic/claude-opus-5")
            db.transition_run(run.run_id, RunState.RUNNING, actor="orchestrator")
            attempt = db.start_attempt(run.run_id, step_id="p1_control_db", model=...)
            db.finish_attempt(attempt.attempt_id, AttemptState.OK, tokens=..., cost_usd=...)
            db.transition_run(run.run_id, RunState.VERIFYING)

    Typical reader use (the control packet, the Control Room)::

        with ControlDB.open_read_only() as db:
            for run in db.runs(state=RunState.AWAITING_APPROVAL):
                ...

    Concurrency. WAL journaling plus a busy timeout: many readers concurrent with the single
    writer, which is exactly the deployment shape (one orchestrator, N observers). WAL is not
    an optimisation here — in rollback-journal mode a reader would block the writer, letting a
    dashboard poll stall a run.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        read_only: bool = False,
        create: bool = True,
        busy_timeout_ms: int = 5000,
    ) -> None:
        """Open (and, for a writer, create + migrate) the database.

        :param path: explicit database path; see :func:`resolve_db_path` for the precedence.
        :param read_only: open with SQLite ``mode=ro``; every writer method then refuses with
            :class:`ReadOnlyControlDBError`. The single-writer contract, enforced two ways.
        :param create: create the parent directory and the schema when missing (writers only).
        :param busy_timeout_ms: how long a statement waits for a lock before raising.
        """
        self.path = resolve_db_path(path)
        self.read_only = read_only
        #: Nesting depth for :meth:`transaction`, so a writer method called *inside* a caller's
        #: transaction joins it rather than committing early and breaking the caller's atomicity.
        self._depth = 0

        if read_only:
            if not self.path.exists():
                # A reader must never conjure an empty database: "there are no runs" and "the
                # control state is missing" are different answers, and only one is safe to act on.
                raise ControlDBError(
                    f"control_db: no control database at {self.path} — "
                    "a reader never creates one (is the orchestrator running?)"
                )
            uri = f"file:{self.path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True, isolation_level=None)
        else:
            if create:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            elif not self.path.exists():
                raise ControlDBError(f"control_db: no control database at {self.path}")
            # isolation_level=None → autocommit; transactions are explicit (see transaction()).
            # Implicit BEGINs are what make "atomic" accidentally mean "whatever the driver did".
            self._conn = sqlite3.connect(str(self.path), isolation_level=None)

        self._conn.row_factory = sqlite3.Row
        self._conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
        # Foreign keys are OFF by default in SQLite — without this, an attempt could reference a
        # run that does not exist, which is precisely the orphan-state class this db deletes.
        self._conn.execute("PRAGMA foreign_keys = ON")
        if not read_only:
            self._conn.execute("PRAGMA journal_mode = WAL")
            # NORMAL (not FULL) synchronous: with WAL this is crash-safe for process death,
            # which is the failure mode here (a killed runner), while avoiding an fsync per
            # transition on a database written throughout every run.
            self._conn.execute("PRAGMA synchronous = NORMAL")
            if create:
                self._ensure_schema()
        self._verify_schema_version()

    # ── Construction helpers ─────────────────────────────────────────────────────────────

    @classmethod
    def open(cls, path: str | Path | None = None) -> ControlDB:
        """Open for writing — the ORCHESTRATOR's handle. Creates the database when missing."""
        return cls(path, read_only=False, create=True)

    @classmethod
    def open_read_only(cls, path: str | Path | None = None) -> ControlDB:
        """Open for reading — every consumer that is not the orchestrator."""
        return cls(path, read_only=True, create=False)

    def close(self) -> None:
        """Close the underlying connection (idempotent)."""
        self._conn.close()

    def __enter__(self) -> ControlDB:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ── Schema bootstrap ─────────────────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        """Apply :data:`SCHEMA_SQL` and seed ``control_meta`` (idempotent).

        ``executescript()`` issues an implicit COMMIT before it runs, so it deliberately does
        NOT live inside :meth:`transaction` — it would silently close the ``BEGIN`` and leave
        the matching ``COMMIT`` with no transaction to commit. Running it standalone is safe
        because every statement is ``IF NOT EXISTS``: a crash halfway through simply re-applies
        on the next open. The ``control_meta`` seeding that follows IS transactional, because
        those two rows must appear together or not at all.
        """
        self._conn.executescript(SCHEMA_SQL)
        with self.transaction():
            self._conn.execute(
                "INSERT OR IGNORE INTO control_meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO control_meta(key, value) VALUES ('control_epoch', '0')"
            )
            # Forward migration for an OLDER database, in place.
            #
            # Every statement in SCHEMA_SQL is CREATE ... IF NOT EXISTS, so executing it against
            # a v1 database has already added the v2 tables above — the database is now, in
            # fact, v2. What is left is to say so: the ``INSERT OR IGNORE`` cannot update the
            # existing row, so without this the recorded version would stay at 1 while the
            # tables were at 2, and a reader checking the version would draw the wrong
            # conclusion about what it may query.
            #
            # This is only sound because v1 → v2 is purely additive. A future version that
            # changes or drops a column must NOT extend this UPDATE; it needs a real migration
            # step (guarded per-version), because "re-apply the DDL" no longer reaches the
            # target shape. The ``< ?`` guard also keeps the write monotonic: a database from a
            # newer schema is never quietly downgraded — ``_verify_schema_version`` refuses it
            # outright a moment later.
            self._conn.execute(
                "UPDATE control_meta SET value = ? "
                "WHERE key = 'schema_version' AND CAST(value AS INTEGER) < ?",
                (str(SCHEMA_VERSION), SCHEMA_VERSION),
            )

    def _verify_schema_version(self) -> None:
        """Refuse a database written by a NEWER schema than this code understands.

        An older version is handled by :meth:`_ensure_schema`'s additive forward migration for
        a writer, and is harmless for a reader (v1 tables are a subset of v2's; a query against
        a missing publication table raises where it is used, rather than returning a wrong
        answer here). A *newer* version is the dangerous direction: this process would read
        columns it does not know about and write rows a newer reader considers malformed — so
        it stops instead.
        """
        row = self._conn.execute(
            "SELECT value FROM control_meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            return  # A read-only handle on a database mid-creation; nothing to verify yet.
        found = int(row["value"])
        if found > SCHEMA_VERSION:
            raise ControlDBError(
                f"control_db: {self.path} has schema version {found}, this code understands "
                f"{SCHEMA_VERSION} — upgrade before reading it"
            )

    # ── Transactions ─────────────────────────────────────────────────────────────────────

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block inside ONE database transaction (re-entrant).

        ``BEGIN IMMEDIATE`` — the write lock is taken up front rather than being upgraded
        mid-transaction, so two writers collide immediately and loudly instead of one failing
        halfway through a multi-row write.

        Re-entrancy matters for p2: the parent's terminal write is "transition the run + append
        the outbox events", composed from methods that each open a transaction. Nesting joins
        the outer transaction, so the whole composition commits or rolls back as one — the
        atomicity the outbox pattern depends on.
        """
        if self.read_only:
            raise ReadOnlyControlDBError(
                "control_db: this handle is read-only — the orchestrator is the only writer"
            )
        if self._depth:
            # Already inside a transaction: join it. No nested BEGIN (SQLite has no nested
            # transactions), and no COMMIT here — the outermost block owns the outcome.
            self._depth += 1
            try:
                yield self._conn
            finally:
                self._depth -= 1
            return

        self._conn.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")
        finally:
            self._depth = 0

    def _require_writable(self) -> None:
        """Refuse a write through a read-only handle, naming the contract."""
        if self.read_only:
            raise ReadOnlyControlDBError(
                "control_db: this handle is read-only — the orchestrator is the only writer"
            )

    def _bump_epoch(self) -> int:
        """Increment and return the monotonic control epoch.

        Bumped inside the same transaction as every durable state change, so an observer that
        caches a packet can tell "nothing changed" from "I have not looked" by comparing one
        integer — which is what lets the master controller diff turns instead of re-reading
        prose. p4 renders it; the database owns it, because only the database sees every
        transition.

        The epoch's meaning (control_db_evidence e4): **any durable state change, run-level or
        phase-level**. Run-level changes are the run-state transitions (:meth:`transition_run`,
        :meth:`create_run`'s creation edge); phase-level changes are a step attempt's *start*
        and *end* (:meth:`start_attempt`/:meth:`finish_attempt` — a phase moving into flight and
        then recording its outcome are both facts a turn-to-turn diff must see). A *heartbeat*
        is deliberately neither — :meth:`record_run_heartbeat` never bumps, because a beat every
        few seconds is not a state change and must not read as one.
        """
        self._conn.execute(
            "UPDATE control_meta SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
            "WHERE key = 'control_epoch'"
        )
        return self.control_epoch()

    def control_epoch(self) -> int:
        """The current control epoch (0 on a fresh database).

        Counts durable state changes: run-level (a run's state transitions) and phase-level (a
        step attempt's start/end). Two packets built at different times over an unchanged
        database carry the same value; any run-level or phase-level change moves it.
        """
        row = self._conn.execute(
            "SELECT value FROM control_meta WHERE key = 'control_epoch'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def schema_version(self) -> int:
        """The schema version recorded in the database."""
        row = self._conn.execute(
            "SELECT value FROM control_meta WHERE key = 'schema_version'"
        ).fetchone()
        return int(row["value"]) if row else 0

    # ── runs ─────────────────────────────────────────────────────────────────────────────

    def create_run(
        self,
        *,
        spec_name: str,
        run_id: str | None = None,
        workflow_revision_id: str = "",
        candidate_sha: str = "",
        model: str = "",
        state: RunState | str = RunState.QUEUED,
        started_at: str | None = None,
        ledger_path: str = "",
        cost_usd: float = 0.0,
        reason: str = "",
        actor: str = "orchestrator",
    ) -> RunRecord:
        """Record a new run and its creation transition.

        The initial state defaults to ``queued`` and may be ``running`` for an orchestrator that
        starts work immediately; anything else is refused, because a run cannot *begin* life
        already verified, merged, or failed — those are outcomes, and an outcome with no
        recorded path to it is an assertion, not evidence.

        The row and its first transition are written in one transaction: a run that exists with
        no history would be a hole in exactly the record this table is for.
        """
        self._require_writable()
        spec = _require(spec_name, "spec_name")
        initial = _coerce_run_state(state)
        if initial not in (RunState.QUEUED, RunState.RUNNING):
            raise InvalidTransitionError(
                f"control_db: a run may only be created in 'queued' or 'running', not "
                f"{initial.value!r} — every other state must be reached by a recorded transition"
            )
        rid = run_id or _new_id("run")
        now = started_at or _now()

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, spec_name, workflow_revision_id, candidate_sha,
                                  state, model, started_at, ended_at, ledger_path, cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?)
                """,
                (rid, spec, workflow_revision_id, candidate_sha, initial.value, model, now,
                 ledger_path, float(cost_usd)),
            )
            conn.execute(
                "INSERT INTO run_transitions (run_id, from_state, to_state, at, reason, actor) "
                "VALUES (?, NULL, ?, ?, ?, ?)",
                (rid, initial.value, now, reason, actor),
            )
            self._bump_epoch()

        record = self.get_run(rid)
        assert record is not None  # just inserted, inside the same connection
        return record

    def transition_run(
        self,
        run_id: str,
        new_state: RunState | str,
        *,
        reason: str = "",
        actor: str = "orchestrator",
        at: str | None = None,
        cost_usd: float | None = None,
        candidate_sha: str | None = None,
        ledger_path: str | None = None,
        ended_at: str | None = None,
    ) -> RunRecord:
        """Move a run to ``new_state``, appending an immutable transition row.

        Refusals, in the order checked — each one is a distinct error type so a caller can tell
        "you typo'd a state" from "that path does not exist" from "this run is over":

        * :class:`UnknownRunError` — no such run;
        * :class:`UnknownStateError` — the state string is outside the twelve;
        * :class:`TerminalStateError` — the run already ended (checked *before* the transition
          graph, so the message names the real problem);
        * :class:`InvalidTransitionError` — the edge is not in :data:`ALLOWED_TRANSITIONS`.

        The optional fields (``cost_usd``/``candidate_sha``/``ledger_path``) are updated in the
        same statement as the state. That is not a convenience: once the new state is terminal,
        the immutability trigger forbids any further UPDATE, so the terminal transition is the
        *last* moment a run's final cost and ledger pointer can be recorded. Passing them later
        would raise — correctly, but too late to keep the data.
        """
        self._require_writable()
        target = _coerce_run_state(new_state)
        now = at or _now()

        with self.transaction() as conn:
            current = self.get_run(run_id)
            if current is None:
                raise UnknownRunError(f"control_db: no run {run_id!r}")
            if current.is_terminal:
                raise TerminalStateError(
                    f"control_db: run {run_id} is terminal ({current.state.value}) — "
                    f"terminal states are immutable, refusing transition to {target.value}"
                )
            if target not in ALLOWED_TRANSITIONS[current.state]:
                legal = ", ".join(sorted(s.value for s in ALLOWED_TRANSITIONS[current.state]))
                raise InvalidTransitionError(
                    f"control_db: {current.state.value} → {target.value} is not a legal "
                    f"transition for run {run_id} (legal: {legal or 'none — terminal'})"
                )

            # A terminal transition stamps ended_at unless the caller supplied one, so "when did
            # this run end?" is answerable from the row without scanning the transition log.
            end_stamp = ended_at
            if end_stamp is None:
                end_stamp = now if target in TERMINAL_RUN_STATES else current.ended_at

            conn.execute(
                """
                UPDATE runs
                   SET state = ?,
                       ended_at = ?,
                       cost_usd = ?,
                       candidate_sha = ?,
                       ledger_path = ?
                 WHERE run_id = ?
                """,
                (
                    target.value,
                    end_stamp,
                    current.cost_usd if cost_usd is None else float(cost_usd),
                    current.candidate_sha if candidate_sha is None else candidate_sha,
                    current.ledger_path if ledger_path is None else ledger_path,
                    run_id,
                ),
            )
            conn.execute(
                "INSERT INTO run_transitions (run_id, from_state, to_state, at, reason, actor) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, current.state.value, target.value, now, reason, actor),
            )
            self._bump_epoch()

        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def update_run(
        self,
        run_id: str,
        *,
        candidate_sha: str | None = None,
        ledger_path: str | None = None,
        model: str | None = None,
        workflow_revision_id: str | None = None,
        cost_usd: float | None = None,
    ) -> RunRecord:
        """Update a NON-terminal run's mutable metadata (no state change, no transition row).

        For facts that become known mid-run: the branch head once the first commit lands, the
        ledger path once it is written, the running cost. Refuses on a terminal run — the same
        rule as :meth:`transition_run`, and the reason a terminal transition takes these fields
        directly.
        """
        self._require_writable()
        with self.transaction() as conn:
            current = self.get_run(run_id)
            if current is None:
                raise UnknownRunError(f"control_db: no run {run_id!r}")
            if current.is_terminal:
                raise TerminalStateError(
                    f"control_db: run {run_id} is terminal ({current.state.value}) — "
                    "its record can no longer be edited"
                )
            conn.execute(
                """
                UPDATE runs
                   SET candidate_sha = ?, ledger_path = ?, model = ?,
                       workflow_revision_id = ?, cost_usd = ?
                 WHERE run_id = ?
                """,
                (
                    current.candidate_sha if candidate_sha is None else candidate_sha,
                    current.ledger_path if ledger_path is None else ledger_path,
                    current.model if model is None else model,
                    (current.workflow_revision_id if workflow_revision_id is None
                     else workflow_revision_id),
                    current.cost_usd if cost_usd is None else float(cost_usd),
                    run_id,
                ),
            )
        updated = self.get_run(run_id)
        assert updated is not None
        return updated

    def get_run(self, run_id: str) -> RunRecord | None:
        """One run by id, or ``None`` when absent."""
        row = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _run_from_row(row) if row else None

    def runs(
        self,
        *,
        state: RunState | str | None = None,
        states: Sequence[RunState | str] | None = None,
        spec_name: str | None = None,
        limit: int | None = None,
    ) -> list[RunRecord]:
        """Runs, newest first, optionally filtered by state(s) and/or spec.

        ``states`` (plural) exists for the control packet's grouped questions — "everything
        still in flight" is one query over ``{queued, running, verifying, promoting,
        projecting}``, not five.
        """
        clauses: list[str] = []
        params: list[Any] = []
        wanted: list[str] = []
        if state is not None:
            wanted.append(_coerce_run_state(state).value)
        for extra in states or ():
            wanted.append(_coerce_run_state(extra).value)
        if wanted:
            clauses.append(f"state IN ({', '.join('?' for _ in wanted)})")
            params.extend(wanted)
        if spec_name:
            clauses.append("spec_name = ?")
            params.append(spec_name)
        sql = "SELECT * FROM runs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        # started_at DESC then run_id DESC: a stable total order even when two runs share a
        # timestamp, so a packet built twice from the same db is byte-identical (p4 needs the
        # determinism to diff turns).
        sql += " ORDER BY started_at DESC, run_id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return [_run_from_row(row) for row in self._conn.execute(sql, params).fetchall()]

    # ── run_heartbeats (control_db_evidence e2) ──────────────────────────────────────────

    def record_run_heartbeat(
        self,
        run_id: str,
        *,
        actor: str = "orchestrator",
        at: str | None = None,
    ) -> RunHeartbeat:
        """Upsert a run's heartbeat: this orchestrator process is alive, right now.

        The liveness proof the zombie-run sweep (``control_db_evidence`` e2) judges staleness
        from. Deliberately NOT a state transition: the beat upserts this row only — it does not
        touch ``runs``/``run_transitions`` and does not bump the control epoch, because a
        heartbeat every few seconds is not a durable state *change* and must not read as one to
        a master diffing packets.

        Refuses an unknown run (the foreign key is the backstop; the typed error is the point) —
        a beat for a run that was never recorded would be a proof of life for a phantom.
        """
        self._require_writable()
        if self.get_run(run_id) is None:
            raise UnknownRunError(f"control_db: no run {run_id!r} — cannot record a heartbeat")
        stamp = at or _now()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO run_heartbeats (run_id, last_seen_at, beat_count, actor)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    beat_count = beat_count + 1,
                    actor = excluded.actor
                """,
                (run_id, stamp, actor),
            )
        record = self.run_heartbeat(run_id)
        assert record is not None  # just upserted, inside the same connection
        return record

    def run_heartbeat(self, run_id: str) -> RunHeartbeat | None:
        """One run's heartbeat row, or ``None`` when the run has never been seen beating."""
        row = self._conn.execute(
            "SELECT * FROM run_heartbeats WHERE run_id = ?", (run_id,)
        ).fetchone()
        return _heartbeat_from_row(row) if row else None

    def transitions(self, run_id: str) -> list[StateTransition]:
        """A run's lifecycle history, oldest first."""
        rows = self._conn.execute(
            "SELECT * FROM run_transitions WHERE run_id = ? ORDER BY transition_id ASC",
            (run_id,),
        ).fetchall()
        return [
            StateTransition(
                transition_id=int(row["transition_id"]),
                run_id=row["run_id"],
                from_state=RunState(row["from_state"]) if row["from_state"] else None,
                to_state=RunState(row["to_state"]),
                at=row["at"],
                reason=row["reason"],
                actor=row["actor"],
            )
            for row in rows
        ]

    # ── step_attempts ────────────────────────────────────────────────────────────────────

    def next_attempt_no(self, run_id: str, step_id: str) -> int:
        """The next attempt number for a step (1-based).

        Derived from the stored rows rather than from a counter the caller keeps, so a resumed
        orchestrator that lost its memory still numbers attempts correctly.
        """
        row = self._conn.execute(
            "SELECT COALESCE(MAX(attempt_no), 0) AS n FROM step_attempts "
            "WHERE run_id = ? AND step_id = ?",
            (run_id, step_id),
        ).fetchone()
        return int(row["n"]) + 1

    def start_attempt(
        self,
        run_id: str,
        *,
        step_id: str,
        model: str = "",
        attempt_no: int | None = None,
        state: AttemptState | str = AttemptState.RUNNING,
        started_at: str | None = None,
        attempt_id: str | None = None,
    ) -> StepAttemptRecord:
        """Open a step attempt (recorded BEFORE the step runs).

        Before, not after, is the whole point: an attempt that crashes the orchestrator still
        leaves a ``running`` row, which is how a killed run becomes visible as *stuck at step X*
        instead of vanishing — today's failure, where the ledger is only written at the end.

        A phase moving from "not started" to "in flight" is a durable state change (e4): the
        row's existence is a fact a turn-to-turn packet diff must see, so the epoch bumps in the
        same transaction that inserts the ``running`` row.
        """
        self._require_writable()
        step = _require(step_id, "step_id")
        attempt_state = _coerce_attempt_state(state)
        with self.transaction() as conn:
            if self.get_run(run_id) is None:
                raise UnknownRunError(f"control_db: no run {run_id!r}")
            number = self.next_attempt_no(run_id, step) if attempt_no is None else int(attempt_no)
            aid = attempt_id or _new_id("att")
            conn.execute(
                """
                INSERT INTO step_attempts (attempt_id, run_id, step_id, attempt_no, model,
                                           state, started_at, ended_at, tokens, cost_usd,
                                           exit_code, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, '', 0, 0.0, NULL, '')
                """,
                (aid, run_id, step, number, model, attempt_state.value, started_at or _now()),
            )
            self._bump_epoch()
        record = self.get_attempt(aid)
        assert record is not None
        return record

    def finish_attempt(
        self,
        attempt_id: str,
        state: AttemptState | str,
        *,
        tokens: int = 0,
        cost_usd: float = 0.0,
        exit_code: int | None = None,
        error: str = "",
        ended_at: str | None = None,
    ) -> StepAttemptRecord:
        """Close a step attempt with its outcome.

        Refuses a second finish (:class:`TerminalStateError`): the first recorded outcome of an
        invocation is the outcome. A retry is a NEW attempt row with the next ``attempt_no`` —
        which is the difference between a measurable retry rate and an overwritten one.

        Recording the outcome is a durable state change (e4): the phase's result is exactly what
        a turn-to-turn packet diff must see move, so the epoch bumps in the same transaction.
        """
        self._require_writable()
        final = _coerce_attempt_state(state)
        with self.transaction() as conn:
            current = self.get_attempt(attempt_id)
            if current is None:
                raise ControlDBError(f"control_db: no attempt {attempt_id!r}")
            if current.is_terminal:
                raise TerminalStateError(
                    f"control_db: attempt {attempt_id} already finished "
                    f"({current.state.value}) — record a new attempt instead of editing this one"
                )
            conn.execute(
                """
                UPDATE step_attempts
                   SET state = ?, ended_at = ?, tokens = ?, cost_usd = ?,
                       exit_code = ?, error = ?
                 WHERE attempt_id = ?
                """,
                (final.value, ended_at or _now(), int(tokens), float(cost_usd),
                 exit_code, error, attempt_id),
            )
            self._bump_epoch()
        updated = self.get_attempt(attempt_id)
        assert updated is not None
        return updated

    def get_attempt(self, attempt_id: str) -> StepAttemptRecord | None:
        """One attempt by id, or ``None``."""
        row = self._conn.execute(
            "SELECT * FROM step_attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
        return _attempt_from_row(row) if row else None

    def attempts(self, run_id: str, *, step_id: str | None = None) -> list[StepAttemptRecord]:
        """A run's attempts in execution order (by step, then attempt number)."""
        sql = "SELECT * FROM step_attempts WHERE run_id = ?"
        params: list[Any] = [run_id]
        if step_id:
            sql += " AND step_id = ?"
            params.append(step_id)
        sql += " ORDER BY started_at ASC, step_id ASC, attempt_no ASC"
        return [_attempt_from_row(r) for r in self._conn.execute(sql, params).fetchall()]

    # ── gate_results ─────────────────────────────────────────────────────────────────────

    def record_gate_result(
        self,
        run_id: str,
        *,
        step_id: str,
        verdict: GateVerdict | str,
        candidate_sha: str,
        evidence: Any = None,
        executor: str = "",
        started_at: str = "",
        ended_at: str | None = None,
        gate_id: str | None = None,
    ) -> GateResultRecord:
        """Append a gate verdict — append-only, and never without its candidate sha.

        ``candidate_sha`` is required at the API level *and* by a schema ``CHECK``. A verdict
        that does not name the tree it judged is indistinguishable from a verdict about some
        other tree, which is how a PASS from yesterday's branch ends up authorising today's
        promotion.
        """
        self._require_writable()
        sha = _require(candidate_sha, "candidate_sha")
        step = _require(step_id, "step_id")
        decision = _coerce_verdict(verdict)
        gid = gate_id or _new_id("gate")
        payload = "" if evidence is None else json.dumps(evidence, sort_keys=True, default=str)
        with self.transaction() as conn:
            if self.get_run(run_id) is None:
                raise UnknownRunError(f"control_db: no run {run_id!r}")
            conn.execute(
                """
                INSERT INTO gate_results (gate_id, run_id, step_id, verdict, evidence_json,
                                          executor, candidate_sha, started_at, ended_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (gid, run_id, step, decision.value, payload, executor, sha,
                 started_at, ended_at or _now()),
            )
        record = self.get_gate_result(gid)
        assert record is not None
        return record

    def get_gate_result(self, gate_id: str) -> GateResultRecord | None:
        """One gate result by id, or ``None``."""
        row = self._conn.execute(
            "SELECT * FROM gate_results WHERE gate_id = ?", (gate_id,)
        ).fetchone()
        return _gate_from_row(row) if row else None

    def gate_results(
        self,
        run_id: str | None = None,
        *,
        candidate_sha: str | None = None,
        verdict: GateVerdict | str | None = None,
    ) -> list[GateResultRecord]:
        """Gate results, oldest first, filtered by run / candidate sha / verdict.

        The ``candidate_sha`` filter is the publication gate's question ("what has been proven
        about *this exact tree*?"), which is why the column is indexed.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if run_id:
            clauses.append("run_id = ?")
            params.append(run_id)
        if candidate_sha:
            clauses.append("candidate_sha = ?")
            params.append(candidate_sha)
        if verdict is not None:
            clauses.append("verdict = ?")
            params.append(_coerce_verdict(verdict).value)
        sql = "SELECT * FROM gate_results"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ended_at ASC, gate_id ASC"
        return [_gate_from_row(r) for r in self._conn.execute(sql, params).fetchall()]

    # ── approvals ────────────────────────────────────────────────────────────────────────

    def record_approval(
        self,
        run_id: str,
        *,
        gate_id: str = "",
        candidate_sha: str,
        operator: str,
        artifact_path: str = "",
        decided_at: str | None = None,
        approval_id: str | None = None,
    ) -> ApprovalRecord:
        """Append a human approval, bound to a gate and a candidate sha.

        ``operator`` is required: an approval with no approver is not an approval. It is also
        what makes "the machine approved itself" a detectable condition rather than an
        invisible one.
        """
        self._require_writable()
        sha = _require(candidate_sha, "candidate_sha")
        who = _require(operator, "operator")
        aid = approval_id or _new_id("apr")
        with self.transaction() as conn:
            if self.get_run(run_id) is None:
                raise UnknownRunError(f"control_db: no run {run_id!r}")
            conn.execute(
                """
                INSERT INTO approvals (approval_id, run_id, gate_id, candidate_sha, operator,
                                       decided_at, artifact_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (aid, run_id, gate_id, sha, who, decided_at or _now(), artifact_path),
            )
        rows = [a for a in self.approvals(run_id) if a.approval_id == aid]
        return rows[0]

    def approvals(self, run_id: str | None = None) -> list[ApprovalRecord]:
        """Approvals, oldest first, optionally for one run."""
        sql = "SELECT * FROM approvals"
        params: list[Any] = []
        if run_id:
            sql += " WHERE run_id = ?"
            params.append(run_id)
        sql += " ORDER BY decided_at ASC, approval_id ASC"
        return [
            ApprovalRecord(
                approval_id=row["approval_id"],
                run_id=row["run_id"],
                gate_id=row["gate_id"],
                candidate_sha=row["candidate_sha"],
                operator=row["operator"],
                decided_at=row["decided_at"],
                artifact_path=row["artifact_path"],
            )
            for row in self._conn.execute(sql, params).fetchall()
        ]

    # ── promotions ───────────────────────────────────────────────────────────────────────

    def record_promotion(
        self,
        run_id: str,
        *,
        candidate_sha: str,
        base_sha: str = "",
        squash_sha: str = "",
        by: str = "",
        pushed_at: str | None = None,
    ) -> PromotionRecord:
        """Append the permanence gate's record of a promotion (append-only).

        Written by the promoter after the push succeeds. Re-recording the same
        ``(run_id, candidate_sha)`` raises ``sqlite3.IntegrityError`` — a duplicate promotion
        record would misreport how many times work reached main.
        """
        self._require_writable()
        sha = _require(candidate_sha, "candidate_sha")
        with self.transaction() as conn:
            if self.get_run(run_id) is None:
                raise UnknownRunError(f"control_db: no run {run_id!r}")
            conn.execute(
                """
                INSERT INTO promotions (run_id, candidate_sha, base_sha, squash_sha,
                                        pushed_at, "by")
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, sha, base_sha, squash_sha, pushed_at or _now(), by),
            )
        return [p for p in self.promotions(run_id) if p.candidate_sha == sha][0]

    def promotions(self, run_id: str | None = None) -> list[PromotionRecord]:
        """Promotions, oldest first, optionally for one run."""
        sql = 'SELECT run_id, candidate_sha, base_sha, squash_sha, pushed_at, "by" FROM promotions'
        params: list[Any] = []
        if run_id:
            sql += " WHERE run_id = ?"
            params.append(run_id)
        sql += " ORDER BY pushed_at ASC, candidate_sha ASC"
        return [
            PromotionRecord(
                run_id=row["run_id"],
                candidate_sha=row["candidate_sha"],
                base_sha=row["base_sha"],
                squash_sha=row["squash_sha"],
                pushed_at=row["pushed_at"],
                by=row["by"],
            )
            for row in self._conn.execute(sql, params).fetchall()
        ]

    # ── publication (the p6 publication transaction's durable record) ────────────────────

    def record_publication_receipt(
        self,
        *,
        repo_sha: str,
        receipt: Mapping[str, Any] | str,
        receipt_id: str | None = None,
        run_id: str = "",
        operator: str = "",
        receipt_sha256: str = "",
    ) -> PublicationReceiptRecord:
        """Append a ``publication/v1`` receipt (append-only).

        The receipt document is stored verbatim in ``receipt_json``; the columns that callers
        filter on are *derived from it here* rather than accepted as separate arguments. That
        asymmetry is deliberate: two sources for one number is how a row comes to disagree with
        the document it summarises, and this table's whole job is to be the number nobody can
        argue with.

        :param repo_sha: the exact tree published. Empty is refused (by ``_require`` and again
            by the table's CHECK) — a receipt for an unnamed tree cannot be verified later.
        :param receipt: the ``publication/v1`` document, as a mapping or an already-serialised
            JSON string.
        :param run_id: the run that produced the candidate, when there is one. ``""`` is stored
            as SQL NULL so the foreign key is satisfied by absence rather than by a fake run.
        :param operator: who ran the publication. Deploying the site is a P0 (controller-only)
            action, so the record carries a name.
        """
        self._require_writable()
        sha = _require(repo_sha, "repo_sha")
        payload = receipt if isinstance(receipt, str) else json.dumps(receipt, sort_keys=True)
        parsed = _loads(payload) if isinstance(receipt, str) else receipt
        if not isinstance(parsed, Mapping):
            raise ControlFieldError(
                "control_db: publication receipt must be a JSON object (publication/v1)"
            )
        watermarks = parsed.get("source_event_watermarks")
        generated_at = str(parsed.get("generated_at") or _now())
        sessions_total = parsed.get("sessions_total")
        if sessions_total is not None and not isinstance(sessions_total, int):
            # A string "1,027" here would be recorded as an unqueryable number. Refuse loudly
            # rather than coerce: the coercion is where the corpus count would silently change.
            raise ControlFieldError(
                f"control_db: sessions_total must be an int or None, got {sessions_total!r}"
            )
        rid = receipt_id or _new_id("pub")
        with self.transaction() as conn:
            if run_id and self.get_run(run_id) is None:
                raise UnknownRunError(f"control_db: no run {run_id!r}")
            conn.execute(
                """
                INSERT INTO publication_receipts (
                    receipt_id, run_id, repo_sha, data_manifest_sha256, data_js_sha256,
                    sessions_total, generated_at, receipt_json, receipt_sha256, operator
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    run_id or None,
                    sha,
                    str(parsed.get("data_manifest_sha256") or ""),
                    str(parsed.get("data_js_sha256") or ""),
                    sessions_total,
                    generated_at,
                    payload,
                    receipt_sha256 or hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    operator,
                ),
            )
        del watermarks  # Carried inside receipt_json; no column duplicates it (see above).
        record = self.get_publication_receipt(rid)
        assert record is not None  # Just inserted inside this transaction.
        return record

    def record_deployment(
        self,
        receipt_id: str,
        *,
        host_role: str,
        firebase_project: str,
        release_id: str = "",
        hosting_url: str = "",
        status: str = "succeeded",
        detail: str = "",
        deployed_at: str | None = None,
        deployment_id: str | None = None,
    ) -> DeploymentRecord:
        """Append one host's deployment outcome for a receipt (append-only).

        Called once per host, so a publication that reached the canonical site but failed on the
        mirror leaves TWO rows — one ``succeeded``, one ``failed`` — rather than one row and a
        gap. The unique index on ``(receipt_id, host_role)`` makes re-recording the same host
        for the same receipt an ``IntegrityError``: a retry must produce a new receipt, because
        the tree it deploys has to be re-verified anyway.
        """
        self._require_writable()
        role = _require(host_role, "host_role")
        project = _require(firebase_project, "firebase_project")
        if status not in ("succeeded", "failed"):
            raise ControlFieldError(
                f"control_db: deployment status must be 'succeeded' or 'failed', got {status!r}"
            )
        did = deployment_id or _new_id("dep")
        with self.transaction() as conn:
            if self.get_publication_receipt(receipt_id) is None:
                raise ControlDBError(f"control_db: no publication receipt {receipt_id!r}")
            conn.execute(
                """
                INSERT INTO publication_deployments (
                    deployment_id, receipt_id, host_role, firebase_project, release_id,
                    hosting_url, status, deployed_at, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    did,
                    receipt_id,
                    role,
                    project,
                    release_id,
                    hosting_url,
                    status,
                    deployed_at or _now(),
                    detail,
                ),
            )
        return [d for d in self.deployments(receipt_id) if d.deployment_id == did][0]

    def get_publication_receipt(self, receipt_id: str) -> PublicationReceiptRecord | None:
        """One receipt by id, or ``None``."""
        row = self._conn.execute(
            "SELECT * FROM publication_receipts WHERE receipt_id = ?", (receipt_id,)
        ).fetchone()
        return _receipt_from_row(row) if row else None

    def publication_receipts(
        self, *, repo_sha: str | None = None, limit: int | None = None
    ) -> list[PublicationReceiptRecord]:
        """Receipts, NEWEST first (the useful order — "what is live?" is the common question)."""
        sql = "SELECT * FROM publication_receipts"
        params: list[Any] = []
        if repo_sha:
            sql += " WHERE repo_sha = ?"
            params.append(repo_sha)
        sql += " ORDER BY generated_at DESC, receipt_id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return [_receipt_from_row(row) for row in self._conn.execute(sql, params).fetchall()]

    def deployments(self, receipt_id: str | None = None) -> list[DeploymentRecord]:
        """Deployment rows, oldest first, optionally for one receipt."""
        sql = "SELECT * FROM publication_deployments"
        params: list[Any] = []
        if receipt_id:
            sql += " WHERE receipt_id = ?"
            params.append(receipt_id)
        sql += " ORDER BY deployed_at ASC, deployment_id ASC"
        return [_deployment_from_row(row) for row in self._conn.execute(sql, params).fetchall()]

    # ── outbox (storage primitives; the PUBLISHER is p2's deliverable) ───────────────────

    def enqueue_outbox_event(
        self,
        run_id: str,
        payload: Any,
        *,
        event_id: str | None = None,
        next_retry_at: str = "",
        created_at: str | None = None,
    ) -> OutboxRecord:
        """Append a ``pending`` outbox row.

        Call this INSIDE the same :meth:`transaction` as the state transition it accompanies —
        that co-commit is the entire outbox guarantee: the state never moves without the events
        being durably queued, and the events are never queued for a state change that rolled
        back.
        """
        self._require_writable()
        eid = event_id or _new_id("evt")
        body = json.dumps(payload, sort_keys=True, default=str)
        with self.transaction() as conn:
            if self.get_run(run_id) is None:
                raise UnknownRunError(f"control_db: no run {run_id!r}")
            conn.execute(
                """
                INSERT INTO outbox (event_id, run_id, payload_json, status, attempts,
                                    next_retry_at, created_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (eid, run_id, body, OutboxStatus.PENDING.value, next_retry_at,
                 created_at or _now()),
            )
        record = self.get_outbox_event(eid)
        assert record is not None
        return record

    def get_outbox_event(self, event_id: str) -> OutboxRecord | None:
        """One outbox row by id, or ``None``."""
        row = self._conn.execute(
            "SELECT * FROM outbox WHERE event_id = ?", (event_id,)
        ).fetchone()
        return _outbox_from_row(row) if row else None

    def pending_outbox_events(
        self, *, now: str | None = None, limit: int | None = None
    ) -> list[OutboxRecord]:
        """Pending rows whose ``next_retry_at`` has come, oldest first.

        Ordered by ``created_at`` so delivery preserves the order events were produced in;
        ``next_retry_at <= now`` (empty string sorts before every timestamp, so a never-retried
        row is always eligible) implements the backoff without any policy living here — the
        policy that *sets* ``next_retry_at`` is p2's.
        """
        stamp = now or _now()
        sql = (
            "SELECT * FROM outbox WHERE status = ? AND next_retry_at <= ? "
            "ORDER BY created_at ASC, event_id ASC"
        )
        params: list[Any] = [OutboxStatus.PENDING.value, stamp]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return [_outbox_from_row(r) for r in self._conn.execute(sql, params).fetchall()]

    def mark_outbox_delivered(
        self, event_id: str, *, delivered_at: str | None = None
    ) -> OutboxRecord:
        """Flip a row to ``delivered`` — call this ONLY after the stream acknowledges.

        The ordering (ack, then mark) is what makes delivery at-least-once: a crash in between
        leaves the row ``pending`` and the event is re-delivered. The opposite order would lose
        events silently, which is the failure the outbox exists to remove.
        """
        return self._update_outbox(
            event_id,
            status=OutboxStatus.DELIVERED,
            delivered_at=delivered_at or _now(),
            bump_attempts=True,
        )

    def mark_outbox_retry(
        self, event_id: str, *, next_retry_at: str, error: str = ""
    ) -> OutboxRecord:
        """Record a failed delivery: bump ``attempts``, schedule the next try, keep the error."""
        return self._update_outbox(
            event_id,
            status=OutboxStatus.PENDING,
            next_retry_at=next_retry_at,
            last_error=error,
            bump_attempts=True,
        )

    def mark_outbox_dead(self, event_id: str, *, error: str = "") -> OutboxRecord:
        """Give up on a row after the retry cap — ``dead`` is visible, not silent.

        A dead row stays in the table forever on purpose: an undelivered knowledge event is a
        gap in the projection chain, and the operator has to be able to find it.
        """
        return self._update_outbox(
            event_id, status=OutboxStatus.DEAD, last_error=error, bump_attempts=True
        )

    def _update_outbox(
        self,
        event_id: str,
        *,
        status: OutboxStatus,
        next_retry_at: str | None = None,
        delivered_at: str | None = None,
        last_error: str | None = None,
        bump_attempts: bool = False,
    ) -> OutboxRecord:
        """Shared row update for the three outbox marks above."""
        self._require_writable()
        with self.transaction() as conn:
            current = self.get_outbox_event(event_id)
            if current is None:
                raise ControlDBError(f"control_db: no outbox event {event_id!r}")
            if current.status is OutboxStatus.DELIVERED:
                # Delivered is final: re-marking would hide a double-delivery bug rather than
                # surface it. (Dead is NOT final — an operator may requeue after a fix.)
                raise TerminalStateError(
                    f"control_db: outbox event {event_id} is already delivered"
                )
            conn.execute(
                """
                UPDATE outbox
                   SET status = ?, attempts = ?, next_retry_at = ?, delivered_at = ?,
                       last_error = ?
                 WHERE event_id = ?
                """,
                (
                    status.value,
                    current.attempts + (1 if bump_attempts else 0),
                    current.next_retry_at if next_retry_at is None else next_retry_at,
                    current.delivered_at if delivered_at is None else delivered_at,
                    current.last_error if last_error is None else last_error,
                    event_id,
                ),
            )
        updated = self.get_outbox_event(event_id)
        assert updated is not None
        return updated

    def outbox_events(
        self, *, run_id: str | None = None, status: OutboxStatus | str | None = None
    ) -> list[OutboxRecord]:
        """Outbox rows, oldest first, filtered by run and/or status."""
        clauses: list[str] = []
        params: list[Any] = []
        if run_id:
            clauses.append("run_id = ?")
            params.append(run_id)
        if status is not None:
            value = status.value if isinstance(status, OutboxStatus) else str(status)
            if value not in {s.value for s in OutboxStatus}:
                raise UnknownStateError(f"control_db: {value!r} is not an outbox status")
            clauses.append("status = ?")
            params.append(value)
        sql = "SELECT * FROM outbox"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at ASC, event_id ASC"
        return [_outbox_from_row(r) for r in self._conn.execute(sql, params).fetchall()]

    # ── projection watermarks (storage primitives; the WIRING is p3's deliverable) ───────

    def record_watermark(
        self,
        projection: str,
        *,
        last_event_id: str = "",
        source_head_event_id: str = "",
        lag_events: int | None = None,
        last_success_at: str | None = None,
        last_error: str = "",
    ) -> ProjectionWatermark:
        """Upsert one projection's watermark.

        ``lag_events=None`` stores NULL — unknown lag is recorded as unknown. A fabricated ``0``
        would read as "fully caught up", which is the single most dangerous wrong answer this
        table can give a publication gate.

        ``last_success_at`` defaults to *now* only when the update carries no ``last_error``: a
        failed poll must not refresh the success stamp, or a broken projector would look healthy
        forever — precisely the invisibility p3 exists to remove.
        """
        self._require_writable()
        name = _require(projection, "projection")
        stamp = last_success_at
        if stamp is None:
            stamp = "" if last_error else _now()
        with self.transaction() as conn:
            existing = self.get_watermark(name)
            if existing is not None and not stamp:
                # Keep the previous success stamp on a failed poll — the whole point is that it
                # visibly ages.
                stamp = existing.last_success_at
            conn.execute(
                """
                INSERT INTO projection_watermarks (projection, last_event_id,
                                                   source_head_event_id, lag_events,
                                                   last_success_at, last_error)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(projection) DO UPDATE SET
                    last_event_id = excluded.last_event_id,
                    source_head_event_id = excluded.source_head_event_id,
                    lag_events = excluded.lag_events,
                    last_success_at = excluded.last_success_at,
                    last_error = excluded.last_error
                """,
                (name, last_event_id, source_head_event_id,
                 None if lag_events is None else int(lag_events), stamp, last_error),
            )
        record = self.get_watermark(name)
        assert record is not None
        return record

    def get_watermark(self, projection: str) -> ProjectionWatermark | None:
        """One projection's watermark, or ``None`` when it has never reported."""
        row = self._conn.execute(
            "SELECT * FROM projection_watermarks WHERE projection = ?", (projection,)
        ).fetchone()
        return _watermark_from_row(row) if row else None

    def watermarks(self) -> list[ProjectionWatermark]:
        """Every projection watermark, name-ordered (deterministic for the p4 packet)."""
        rows = self._conn.execute(
            "SELECT * FROM projection_watermarks ORDER BY projection ASC"
        ).fetchall()
        return [_watermark_from_row(r) for r in rows]

    # ── Reconstruction ───────────────────────────────────────────────────────────────────

    def reconstruct_run(self, run_id: str) -> ReconstructedRun:
        """Rebuild a complete run from the control database ALONE.

        The mandate's proof: no ledger JSON, no Redis, no spec index, no git — everything a
        reader needs about a run comes from these tables. Once this holds, the ledger is a
        *projection* (a convenient rendering) rather than the source, which is what lets a
        killed run still be fully described.
        """
        run = self.get_run(run_id)
        if run is None:
            raise UnknownRunError(f"control_db: no run {run_id!r}")
        return ReconstructedRun(
            run=run,
            transitions=self.transitions(run_id),
            attempts=self.attempts(run_id),
            gate_results=self.gate_results(run_id),
            approvals=self.approvals(run_id),
            promotions=self.promotions(run_id),
            outbox_events=self.outbox_events(run_id=run_id),
        )


# ── Row → record adapters ────────────────────────────────────────────────────────────────────
#
# Module-level (not methods) so a reader with a raw sqlite3.Row — a migration script, a debug
# session — can build the same typed records without constructing a ControlDB.


def _run_from_row(row: sqlite3.Row) -> RunRecord:
    """Build a :class:`RunRecord` from a ``runs`` row."""
    return RunRecord(
        run_id=row["run_id"],
        spec_name=row["spec_name"],
        workflow_revision_id=row["workflow_revision_id"],
        candidate_sha=row["candidate_sha"],
        state=RunState(row["state"]),
        model=row["model"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        ledger_path=row["ledger_path"],
        cost_usd=float(row["cost_usd"]),
    )


def _heartbeat_from_row(row: sqlite3.Row) -> RunHeartbeat:
    """Build a :class:`RunHeartbeat` from a ``run_heartbeats`` row."""
    return RunHeartbeat(
        run_id=row["run_id"],
        last_seen_at=row["last_seen_at"],
        beat_count=int(row["beat_count"]),
        actor=row["actor"],
    )


def _attempt_from_row(row: sqlite3.Row) -> StepAttemptRecord:
    """Build a :class:`StepAttemptRecord` from a ``step_attempts`` row."""
    return StepAttemptRecord(
        attempt_id=row["attempt_id"],
        run_id=row["run_id"],
        step_id=row["step_id"],
        attempt_no=int(row["attempt_no"]),
        model=row["model"],
        state=AttemptState(row["state"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        tokens=int(row["tokens"]),
        cost_usd=float(row["cost_usd"]),
        # NULL stays None — an unobserved exit code must never read as 0 ("clean exit").
        exit_code=None if row["exit_code"] is None else int(row["exit_code"]),
        error=row["error"],
    )


def _gate_from_row(row: sqlite3.Row) -> GateResultRecord:
    """Build a :class:`GateResultRecord` from a ``gate_results`` row."""
    return GateResultRecord(
        gate_id=row["gate_id"],
        run_id=row["run_id"],
        step_id=row["step_id"],
        verdict=GateVerdict(row["verdict"]),
        evidence_json=row["evidence_json"],
        executor=row["executor"],
        candidate_sha=row["candidate_sha"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
    )


def _outbox_from_row(row: sqlite3.Row) -> OutboxRecord:
    """Build an :class:`OutboxRecord` from an ``outbox`` row."""
    return OutboxRecord(
        event_id=row["event_id"],
        run_id=row["run_id"],
        payload_json=row["payload_json"],
        status=OutboxStatus(row["status"]),
        attempts=int(row["attempts"]),
        next_retry_at=row["next_retry_at"],
        created_at=row["created_at"],
        delivered_at=row["delivered_at"],
        last_error=row["last_error"],
    )


def _receipt_from_row(row: sqlite3.Row) -> PublicationReceiptRecord:
    """Map a ``publication_receipts`` row to its record (NULL run_id → ``""``)."""
    return PublicationReceiptRecord(
        receipt_id=row["receipt_id"],
        run_id=row["run_id"] or "",
        repo_sha=row["repo_sha"],
        data_manifest_sha256=row["data_manifest_sha256"],
        data_js_sha256=row["data_js_sha256"],
        sessions_total=row["sessions_total"],
        generated_at=row["generated_at"],
        receipt_json=row["receipt_json"],
        receipt_sha256=row["receipt_sha256"],
        operator=row["operator"],
    )


def _deployment_from_row(row: sqlite3.Row) -> DeploymentRecord:
    """Map a ``publication_deployments`` row to its record."""
    return DeploymentRecord(
        deployment_id=row["deployment_id"],
        receipt_id=row["receipt_id"],
        host_role=row["host_role"],
        firebase_project=row["firebase_project"],
        release_id=row["release_id"],
        hosting_url=row["hosting_url"],
        status=row["status"],
        deployed_at=row["deployed_at"],
        detail=row["detail"],
    )


def _watermark_from_row(row: sqlite3.Row) -> ProjectionWatermark:
    """Build a :class:`ProjectionWatermark` from a ``projection_watermarks`` row."""
    return ProjectionWatermark(
        projection=row["projection"],
        last_event_id=row["last_event_id"],
        source_head_event_id=row["source_head_event_id"],
        lag_events=None if row["lag_events"] is None else int(row["lag_events"]),
        last_success_at=row["last_success_at"],
        last_error=row["last_error"],
    )


# ── Ledger → control-state mappings (the ledger becomes a projection) ────────────────────────


def run_state_from_ledger_state(ledger_state: str) -> RunState:
    """Map a run ledger's terminal label onto the control vocabulary.

    ``workflow_runner.RunState`` (four values: ``succeeded``/``awaiting_approval``/``failed``/
    ``cancelled``) is the *ledger's* label — the answer to "how did this run's phases end?".
    This function translates it into the control plane's answer to a different question: "where
    is this run in its lifecycle?".

    The only non-obvious row is ``succeeded → promotable``. There is deliberately no control
    state meaning "the phases passed", because that fact alone authorises nothing: work whose
    phases all passed sits on a branch, gates green, awaiting the permanence decision — which
    is exactly ``promotable``. Mapping it to ``merged`` or ``published`` would assert a
    promotion and a projection that have not happened, the precise conflation the twelve-state
    vocabulary exists to prevent.

    Used when back-filling the control db from existing ledgers, so historic runs enter the
    database with honest states rather than a guessed ``completed``.
    """
    mapping = {
        "succeeded": RunState.PROMOTABLE,
        "awaiting_approval": RunState.AWAITING_APPROVAL,
        "failed": RunState.FAILED,
        "cancelled": RunState.CANCELLED,
    }
    try:
        return mapping[str(ledger_state)]
    except KeyError as exc:
        known = ", ".join(sorted(mapping))
        raise UnknownStateError(
            f"control_db: {ledger_state!r} is not a ledger run state (known: {known})"
        ) from exc


def attempt_state_from_phase_status(status: str) -> AttemptState:
    """Map a ledger phase ``status`` (``ok``/``failed``/``awaiting``/``skipped``) to an attempt.

    Total and lossless by construction — :class:`AttemptState` reuses the runner's own strings,
    so back-filling attempts from ledger phases invents nothing. An unknown status raises
    rather than defaulting: silently folding an unrecognised status into ``failed`` would
    fabricate outcomes, and into ``ok`` would fabricate successes.
    """
    try:
        return AttemptState(str(status))
    except ValueError as exc:
        known = ", ".join(s.value for s in AttemptState)
        raise UnknownStateError(
            f"control_db: {status!r} is not a phase status (known: {known})"
        ) from exc


def summarize_states(records: Sequence[RunRecord]) -> Mapping[str, int]:
    """Count runs per state — the shape the p4 control packet and the Control Room render.

    Every one of the twelve states is present in the result, including zeros: a state that
    disappears from a summary when empty makes "no failed runs" and "the failed count was not
    computed" look identical to whatever reads it next.
    """
    counts = {state.value: 0 for state in RunState}
    for record in records:
        counts[record.state.value] += 1
    return counts


__all__ = [
    "ALLOWED_TRANSITIONS",
    "AttemptState",
    "ApprovalRecord",
    "CONTROL_DB_ENV",
    "CONTROL_DB_PATH",
    "CONTROL_DB_REL",
    "CONTROL_DIR_REL",
    "CONTROL_TABLES",
    "ControlDB",
    "ControlDBError",
    "ControlFieldError",
    "GateResultRecord",
    "GateVerdict",
    "InvalidTransitionError",
    "OutboxRecord",
    "OutboxStatus",
    "ProjectionWatermark",
    "PromotionRecord",
    "ReadOnlyControlDBError",
    "ReconstructedRun",
    "RunRecord",
    "RunState",
    "SCHEMA_SQL",
    "SCHEMA_VERSION",
    "StateTransition",
    "StepAttemptRecord",
    "TERMINAL_ATTEMPT_STATES",
    "TERMINAL_RUN_STATES",
    "TerminalStateError",
    "UnknownRunError",
    "UnknownStateError",
    "attempt_state_from_phase_status",
    "resolve_db_path",
    "run_state_from_ledger_state",
    "summarize_states",
]
