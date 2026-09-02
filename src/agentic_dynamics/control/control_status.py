"""The ONE control packet — ``control-status/v1`` (``control_db_publication`` p4).

Why this module exists
----------------------
p1 gave the control plane ONE durable state (:mod:`agentic_dynamics.control.control_db`), p2
made emission atomic with that state (:mod:`agentic_dynamics.control.outbox`), and p3 made the
downstream projections visible (:mod:`agentic_dynamics.control.projection_watermarks`). What was
still missing is the *read* side: a single, small, machine-readable answer to "what is true right
now, and what may I safely do about it?".

Without it, every consumer reconstructed that answer differently. The Control Room read Redis,
the supervisor read flags and session files, and the master controller read *chat history* —
which is the worst source of all, because history describes what was true at the moment someone
typed it and silently keeps describing that forever. Three readers, three answers, and no way to
tell which was stale.

This module renders exactly one packet, from the control database, for all three. The doctrine
that goes with it (p5's job to write into the instruction surfaces) is:

    Reload the packet every turn. Act only on the ``run_id`` / ``gate_id`` / ``candidate_sha``
    values it returns. Never infer live state from conversation history.

The three rules the packet is built around
------------------------------------------
**1. ``safe_actions`` are DERIVED, never asserted.** Every entry is computed from the database's
own state plus :data:`~agentic_dynamics.control.control_db.ALLOWED_TRANSITIONS` — the same
transition graph the database *enforces*. A second, hand-written list of "things you may do"
would be a place for the two to drift, and the drift would be invisible until an actor proposed
an action the database then refused. Deriving from the exported graph makes that impossible by
construction: if the packet offers ``cancel``, the database accepts ``cancel``.

**2. The packet is a pure function of its inputs.** ``build_packet`` reads the database and the
values it is *given* (the repo head sha, the worker heartbeats, the clock). It never shells out,
never opens a socket, and never reads the wall clock itself. That is what makes the determinism
requirement testable and, more importantly, what makes the packet *diffable*: a master that
reloads it every turn needs "nothing changed" to be byte-identical, not merely equivalent. All
the impure collection lives in :func:`read_repo_head_sha` and :func:`read_worker_heartbeats`,
which the CLI seam (``scripts/control_status.py``) calls and passes in.

**3. Unknown is never rendered as good news.** The repo's null-not-zero discipline, applied to a
surface an actor takes decisions from. A projection whose lag cannot be computed is ``null``, not
``0`` (p3's rule, carried through verbatim). A surface that could not be *read at all* — Redis
down, git unavailable — is named in the additive :data:`DEGRADED_KEY` list rather than rendered
as an empty, healthy-looking result. An empty ``unhealthy_workers`` must mean "the workers were
observed and all are alive", never "nobody could look".

What this phase does NOT do
---------------------------
The phase scope fence is real. p4 owns this module, its CLI shell, and its tests. It does not
rewire the Control Room's routes onto it (they *may* wrap it — that is a later, additive change),
does not touch the instruction surfaces (p5), and does not publish (p6).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any

from agentic_dynamics.control import projection_watermarks as pwm
from agentic_dynamics.control.control_db import (
    ALLOWED_TRANSITIONS,
    TERMINAL_RUN_STATES,
    ControlDB,
    RunRecord,
    RunState,
)
from agentic_dynamics.core.paths import PROJECT_ROOT

# ── Schema identity ──────────────────────────────────────────────────────────────────────────

#: The packet's schema identifier, carried in the payload itself.
#:
#: Versioned in the *value*, not only in a filename, because the packet travels as bare JSON
#: through pipes, HTTP responses, and agent context windows — a consumer that receives it
#: out-of-band must still be able to tell what it is holding. A ``v2`` that changed a field's
#: meaning would be a different string here, and a strict consumer can refuse it.
SCHEMA_ID = "control-status/v1"

#: Top-level key naming the surfaces that could NOT be read on this pass.
#:
#: Additive beyond the keys the p4 mandate enumerates, and deliberately so: without it, "Redis
#: was unreachable" and "every worker is healthy" both render as ``unhealthy_workers: []``. The
#: mandate's own null-not-zero discipline demands that those two be distinguishable, and a list
#: of named degradations is the smallest honest way to do it.
DEGRADED_KEY = "degraded"


# ── The action vocabulary ────────────────────────────────────────────────────────────────────


class SafeAction(str, Enum):
    """What an actor may do about a run, per the mandated ``approve|cancel|promote`` vocabulary.

    Each member maps onto exactly one recorded control-plane operation, which is the point: an
    action the packet offers is an action some script can actually perform and the database will
    actually accept.

    ``APPROVE``
        Record an operator approval (``ControlDB.record_approval``) for a run stopped at a
        checkpoint. The run is in :attr:`~RunState.AWAITING_APPROVAL`; the approval binds an
        operator to a ``gate_id`` **and** a ``candidate_sha``.
    ``PROMOTE``
        Run the permanence gate (``scripts/promote.py``) against a run whose gates have passed.
        The run is in :attr:`~RunState.PROMOTABLE`.
    ``CANCEL``
        Transition a still-cancellable run to :attr:`~RunState.CANCELLED`. Legal only *before*
        the work reaches main — after a merge, cancelling is a lie and the honest terminal labels
        are ``failed`` or ``quarantined`` (see ``control_db._build_allowed_transitions``).
    """

    APPROVE = "approve"
    CANCEL = "cancel"
    PROMOTE = "promote"


#: Presentation order for ``safe_actions``: decisions that *advance* work before the destructive
#: one. Not alphabetical — an actor reading the list top-down should meet "approve this" and
#: "promote that" before "cancel the other", because the ordering is itself a weak prior about
#: what to do first. Ties break on ``run_id`` then ``gate_id``, which makes the order total (and
#: therefore the packet deterministic) even when two runs are in the same state.
_ACTION_ORDER: dict[str, int] = {
    SafeAction.APPROVE.value: 0,
    SafeAction.PROMOTE.value: 1,
    SafeAction.CANCEL.value: 2,
}

#: Every state a run can still move out of — i.e. everything that is not terminal.
#:
#: Derived by subtraction from the twelve-value vocabulary rather than listed by hand, so a
#: thirteenth state added to :class:`RunState` is automatically "active" unless it is explicitly
#: made terminal. A hand-written list would silently omit it, and a run in an unlisted state
#: would vanish from the packet — invisible work being the exact failure this whole wave exists
#: to delete.
ACTIVE_RUN_STATES: frozenset[RunState] = frozenset(RunState) - TERMINAL_RUN_STATES

#: How many ``failed`` runs the packet carries by default (newest first).
#:
#: Failures accumulate forever, and the packet is reloaded *every turn* by an actor with a finite
#: context window — an unbounded failure list would eventually crowd out the live state it exists
#: to carry. [H] 20: enough to see a burst of related failures (the shape that matters
#: operationally), few enough to stay small. Truncation is never silent: see
#: :data:`FAILED_TRUNCATED_KEY`.
DEFAULT_FAILED_LIMIT = 20

#: Worker heartbeat staleness threshold, in seconds.
#:
#: Mirrors ``scripts/fleet/fleet_manager.STALE_SECONDS`` (45s) — deliberately duplicated as a
#: named constant here rather than imported, because ``scripts/fleet/`` is a container-side
#: script package outside the importable ``src/`` tree; importing it from the control plane would
#: invert the layering. The heartbeat cadence is 10s (``scripts/fleet/heartbeat.DEFAULT_INTERVAL``),
#: so 45s tolerates four consecutive missed beats before calling a worker dead.
WORKER_STALE_AFTER_S = 45.0

#: Environment override for the worker staleness threshold (same shape as p3's
#: ``FINOPS_PROJECTION_STALE_S``): tighten it during a publication window without editing code.
WORKER_STALE_ENV = "FINOPS_WORKER_STALE_S"


def worker_stale_after_seconds() -> float:
    """The effective worker-staleness threshold, honouring :data:`WORKER_STALE_ENV`.

    A malformed or non-positive override falls back to the default rather than raising: an
    operator's typo in an environment variable must not be able to take down the surface that
    reports whether anything is alive.
    """
    raw = os.environ.get(WORKER_STALE_ENV, "").strip()
    if not raw:
        return WORKER_STALE_AFTER_S
    try:
        value = float(raw)
    except ValueError:
        return WORKER_STALE_AFTER_S
    return value if value > 0 else WORKER_STALE_AFTER_S


# ── The JSON Schema ──────────────────────────────────────────────────────────────────────────

#: A run reference as it appears in ``active_runs`` / ``promotable_runs`` / ``failed_runs``.
#:
#: Every entry carries ``candidate_sha`` alongside ``run_id``, because the doctrine tells actors
#: to act only on identifiers the packet returns — and an action against a run without naming the
#: tree it is about is exactly how a verdict gets re-attached to different code.
_RUN_REF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["run_id", "spec_name", "state", "candidate_sha", "model", "started_at"],
    "additionalProperties": False,
    "properties": {
        "run_id": {"type": "string", "minLength": 1},
        "spec_name": {"type": "string"},
        "state": {"type": "string", "enum": [s.value for s in RunState]},
        "candidate_sha": {"type": "string"},
        "model": {"type": "string"},
        "started_at": {"type": "string"},
        "workflow_revision_id": {"type": "string"},
    },
}

#: The full ``control-status/v1`` contract, as JSON Schema (draft 2020-12).
#:
#: Present as data, not prose, so the schema claim is *checkable*: the tests validate real
#: packets against this object with ``jsonschema``, and :func:`validate_packet` implements the
#: same contract without the dependency for callers that cannot take one. Two independent
#: encodings of one contract is the usual smell — here it is the point, because a packet that
#: passes only the checker written by the same hand as the builder proves very little.
CONTROL_STATUS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": SCHEMA_ID,
    "type": "object",
    "required": [
        "schema",
        "repo_head_sha",
        "control_epoch",
        "active_runs",
        "awaiting_approvals",
        "promotable_runs",
        "failed_runs",
        "unhealthy_workers",
        "projection_lag",
        "safe_actions",
        DEGRADED_KEY,
    ],
    "additionalProperties": False,
    "properties": {
        "schema": {"const": SCHEMA_ID},
        # Empty string is legal: "git could not be read" is reported in `degraded`, never as a
        # fabricated sha, and never as a hard failure of the whole packet.
        "repo_head_sha": {"type": "string"},
        "control_epoch": {"type": "integer", "minimum": 0},
        "active_runs": {"type": "array", "items": _RUN_REF_SCHEMA},
        "awaiting_approvals": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["run_id", "gate_id", "candidate_sha"],
                "additionalProperties": False,
                "properties": {
                    "run_id": {"type": "string", "minLength": 1},
                    # Empty when the run stopped for approval without a gate row naming it —
                    # `ControlDB.record_approval` accepts an empty gate_id for exactly this case.
                    "gate_id": {"type": "string"},
                    "candidate_sha": {"type": "string"},
                    "spec_name": {"type": "string"},
                },
            },
        },
        "promotable_runs": {"type": "array", "items": _RUN_REF_SCHEMA},
        "failed_runs": {"type": "array", "items": _RUN_REF_SCHEMA},
        "unhealthy_workers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["worker", "age_seconds", "reason"],
                "additionalProperties": False,
                "properties": {
                    "worker": {"type": "string", "minLength": 1},
                    "worker_type": {"type": "string"},
                    "worker_id": {"type": "string"},
                    "last_seen": {"type": ["number", "null"]},
                    # null when the heartbeat carried no usable `last_seen` — unknown age is
                    # unknown, never 0 (which would read as "beating right now").
                    "age_seconds": {"type": ["number", "null"]},
                    "jobs": {"type": ["integer", "null"]},
                    "pid": {"type": ["string", "null"]},
                    "reason": {"type": "string", "minLength": 1},
                },
            },
        },
        "projection_lag": {
            "type": "object",
            # One key per known projection, always present, `null` when the lag is unknown.
            "required": list(pwm.PROJECTIONS),
            "additionalProperties": False,
            "properties": {
                projection: {"type": ["integer", "null"], "minimum": 0}
                for projection in pwm.PROJECTIONS
            },
        },
        "safe_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action", "run_id", "gate_id"],
                "additionalProperties": False,
                "properties": {
                    "action": {"type": "string", "enum": [a.value for a in SafeAction]},
                    "run_id": {"type": "string", "minLength": 1},
                    "gate_id": {"type": "string"},
                    "candidate_sha": {"type": "string"},
                },
            },
        },
        DEGRADED_KEY: {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["surface", "reason"],
                "additionalProperties": False,
                "properties": {
                    "surface": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                },
            },
        },
    },
}


# ── Row → packet-entry renderers ─────────────────────────────────────────────────────────────


def run_ref(run: RunRecord) -> dict[str, Any]:
    """Render one :class:`RunRecord` as the packet's run reference.

    A deliberately *narrow* projection of the row. The packet is context an actor pays for on
    every turn, so it carries the identifiers needed to act (``run_id``, ``candidate_sha``), the
    labels needed to decide (``spec_name``, ``state``, ``model``, ``started_at``), and the spec
    pin needed to know *what mandate* the run is executing (``workflow_revision_id``) — and
    nothing else. Cost, ledger path, and end time are a query away via ``reconstruct_run`` for the
    one run an actor actually drills into.
    """
    return {
        "run_id": run.run_id,
        "spec_name": run.spec_name,
        "state": run.state.value,
        "candidate_sha": run.candidate_sha,
        "model": run.model,
        "started_at": run.started_at,
        "workflow_revision_id": run.workflow_revision_id,
    }


def awaiting_approval_entries(db: ControlDB, runs: Sequence[RunRecord]) -> list[dict[str, Any]]:
    """The ``awaiting_approvals`` block: one entry per decision an operator still owes.

    The derivation, and why each step is what it is:

    1. Only runs in :attr:`RunState.AWAITING_APPROVAL` are considered. The state is the *design's*
       stop — a run pauses there on purpose — so it, not a heuristic over attempts, is the signal.
    2. A run's pending gates are its ``gate_results`` **for the run's own candidate sha** that
       have no matching ``approvals`` row. Filtering on the sha is load-bearing: an approval
       recorded against an earlier tree must never satisfy a checkpoint on a rewritten one, which
       is precisely the stale-PASS reuse ``gate_results.candidate_sha`` exists to prevent.
    3. A run in ``awaiting_approval`` with **no** gate rows still yields one entry, with an empty
       ``gate_id``. The operator's decision binds to the candidate sha; ``record_approval``
       accepts an empty ``gate_id`` for exactly this shape. Dropping the run instead would hide a
       stopped run from the one surface that exists to show stopped runs.
    4. A run whose gates are **all** already approved yields nothing. The decision is recorded;
       what is outstanding is the orchestrator's transition, not a human's judgement, and asking
       an operator to approve twice is how duplicate approvals get manufactured.

    Ordered by ``(run_id, gate_id)`` so the block is stable for a fixed database.
    """
    entries: list[dict[str, Any]] = []
    for run in runs:
        if run.state is not RunState.AWAITING_APPROVAL:
            continue
        # (gate_id, candidate_sha) pairs already carrying an operator's signature.
        approved = {(a.gate_id, a.candidate_sha) for a in db.approvals(run.run_id)}
        gates = db.gate_results(run.run_id, candidate_sha=run.candidate_sha)
        pending = sorted(
            {g.gate_id for g in gates if (g.gate_id, g.candidate_sha) not in approved}
        )
        # Rule 3: stopped for approval with no gate row naming it — the run itself is the
        # subject, so the entry carries an empty gate_id. Skipped when a bare approval
        # (gate_id "") for this candidate sha has already been recorded.
        if not gates and ("", run.candidate_sha) not in approved:
            pending = [""]
        for gate_id in pending:
            entries.append(
                {
                    "run_id": run.run_id,
                    "gate_id": gate_id,
                    "candidate_sha": run.candidate_sha,
                    "spec_name": run.spec_name,
                }
            )
    entries.sort(key=lambda e: (e["run_id"], e["gate_id"]))
    return entries


def derive_safe_actions(
    *,
    awaiting: Sequence[Mapping[str, Any]],
    runs_by_state: Mapping[RunState, Sequence[RunRecord]],
) -> list[dict[str, Any]]:
    """Derive ``safe_actions`` from database state and the enforced transition graph.

    This function is the mandate's "never from chat or prose" made mechanical. Every entry is
    justified by a fact in the control database plus an edge in
    :data:`~agentic_dynamics.control.control_db.ALLOWED_TRANSITIONS` — the *same* graph
    ``ControlDB.transition_run`` checks. Consulting the exported graph rather than restating the
    rules means the packet can never offer an action the database would then refuse.

    The three derivations:

    ``approve``
        Exactly one per :func:`awaiting_approval_entries` entry. The 1:1 correspondence is an
        invariant worth stating out loud: every ``approve`` action names a decision that appears
        in ``awaiting_approvals``, and vice versa. Guarded by a test.
    ``promote``
        One per run in :attr:`RunState.PROMOTABLE`, gated on ``PROMOTING`` being a legal successor
        — read from the graph rather than assumed, so a future change to the lifecycle that
        removes the edge silently removes the offer too.
    ``cancel``
        One per active run for which ``CANCELLED`` is a legal successor. That is the pre-merge
        states only; the graph already encodes "you cannot cancel what is on main", so this
        function does not restate it.

    Note what "safe" means here: *legal and well-formed*, not *recommended*. The packet's job is
    to bound the action space to things the control plane will accept against identifiers that
    really exist. Choosing among them stays the controller's decision.
    """
    actions: list[dict[str, Any]] = []

    # approve — 1:1 with the awaiting_approvals block.
    for entry in awaiting:
        actions.append(
            {
                "action": SafeAction.APPROVE.value,
                "run_id": entry["run_id"],
                "gate_id": entry["gate_id"],
                "candidate_sha": entry["candidate_sha"],
            }
        )

    # promote — a promotable run, if the lifecycle still allows promoting one.
    if RunState.PROMOTING in ALLOWED_TRANSITIONS[RunState.PROMOTABLE]:
        for run in runs_by_state.get(RunState.PROMOTABLE, ()):  # noqa: B007 (explicit is clearer)
            actions.append(
                {
                    "action": SafeAction.PROMOTE.value,
                    "run_id": run.run_id,
                    # A promotion names no gate; the empty string keeps the entry shape uniform
                    # so a consumer never has to branch on key presence.
                    "gate_id": "",
                    "candidate_sha": run.candidate_sha,
                }
            )

    # cancel — every active run the graph still permits cancelling.
    for state, runs in runs_by_state.items():
        if RunState.CANCELLED not in ALLOWED_TRANSITIONS[state]:
            continue
        for run in runs:
            actions.append(
                {
                    "action": SafeAction.CANCEL.value,
                    "run_id": run.run_id,
                    "gate_id": "",
                    "candidate_sha": run.candidate_sha,
                }
            )

    # Total order: action priority, then run, then gate. Total (not merely stable) so the packet
    # is byte-identical across builds from the same database — the property that lets a master
    # diff turn N against turn N-1 and conclude "nothing changed".
    actions.sort(key=lambda a: (_ACTION_ORDER[a["action"]], a["run_id"], a["gate_id"]))
    return actions


# ── Worker health (pure over injected heartbeats) ────────────────────────────────────────────


def unhealthy_workers(
    heartbeats: Mapping[Any, Mapping[Any, Any]],
    *,
    now: float,
    stale_after_s: float | None = None,
) -> list[dict[str, Any]]:
    """Classify raw fleet heartbeats, returning only the workers that are NOT healthy.

    ``heartbeats`` is ``scripts/fleet/heartbeat.read_all``'s shape: ``{key: {last_seen, jobs, pid,
    started_at}}``, keyed ``worker:<type>:<id>``. Keys and values may arrive as ``bytes`` or
    ``str`` depending on how the caller configured its Redis client, so everything is decoded
    defensively here — a surface that reports whether anything is alive must not itself die on a
    client-configuration detail.

    Two unhealthy shapes, kept distinct because they call for different responses:

    ``stale``
        The worker beat, and then stopped. ``age_seconds`` says how long ago; the process is
        probably dead and its lease probably outlived it (see
        :mod:`agentic_dynamics.control.lease_watchdog`).
    ``no_heartbeat``
        A heartbeat key exists but carries no usable ``last_seen``. ``age_seconds`` is ``null``,
        not a large number: we do not know how long it has been silent, and inventing a number
        would be inventing evidence.

    A worker that has never registered at all is simply absent — it cannot appear here, and that
    gap is the fleet manager's to notice, not this function's to guess at.
    """
    threshold = worker_stale_after_seconds() if stale_after_s is None else stale_after_s
    out: list[dict[str, Any]] = []
    for raw_key, raw_value in heartbeats.items():
        key = _text(raw_key)
        fields = {_text(k): _text(v) for k, v in (raw_value or {}).items()}
        last_seen = _float_or_none(fields.get("last_seen"))
        if last_seen is None:
            age: float | None = None
            reason = "no_heartbeat"
        else:
            age = round(now - last_seen, 1)
            if age < threshold:
                continue  # alive — healthy workers are not the packet's business
            reason = "stale"
        # `worker:<type>:<id>` — split into at most 3 so an id containing ':' survives intact.
        parts = key.split(":", 2)
        out.append(
            {
                "worker": key,
                "worker_type": parts[1] if len(parts) > 2 else "",
                "worker_id": parts[2] if len(parts) > 2 else "",
                "last_seen": last_seen,
                "age_seconds": age,
                "jobs": _int_or_none(fields.get("jobs")),
                "pid": fields.get("pid") or None,
                "reason": reason,
            }
        )
    # Sorted by key: a total order over a set of unique Redis keys, so the block is deterministic.
    out.sort(key=lambda w: w["worker"])
    return out


def _text(value: Any) -> str:
    """Decode a Redis field that may be ``bytes`` or ``str`` into ``str`` (never raising)."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return "" if value is None else str(value)


def _float_or_none(value: Any) -> float | None:
    """Parse a float, returning ``None`` for absent/blank/malformed input.

    ``None`` rather than ``0.0`` on purpose: a heartbeat timestamp of ``0`` is 1970, which would
    render as a spectacularly stale worker rather than as the unknown it actually is.
    """
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    """Parse an int, returning ``None`` for absent/blank/malformed input (same rule as above)."""
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


# ── Impure collectors (called by the CLI seam, never by build_packet) ────────────────────────


def read_repo_head_sha(root: str | Path | None = None) -> tuple[str, str]:
    """``git rev-parse HEAD`` for the checkout, as ``(sha, error)``.

    Returns ``("", "<reason>")`` when git cannot answer — a detached/absent/corrupt checkout, or
    no ``git`` binary. The caller turns that reason into a ``degraded`` note. It is emphatically
    not a fabricated sha and not an exception: a control packet that refuses to render because
    git is unavailable would take away the operator's view of the control plane at precisely the
    moment something is wrong with the machine.
    """
    cwd = Path(root) if root is not None else PROJECT_ROOT
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "", f"git_unavailable: {exc}"
    if proc.returncode != 0:
        return "", f"git_failed: {proc.stderr.strip() or proc.returncode}"
    return proc.stdout.strip(), ""


def read_worker_heartbeats() -> tuple[dict[Any, Mapping[Any, Any]], str]:
    """Read the fleet's worker heartbeats from Redis, as ``(heartbeats, error)``.

    Returns ``({}, "<reason>")`` when Redis cannot be reached. That distinction is the whole
    reason this returns a tuple: ``({}, "")`` means *observed, and every worker is alive*, while
    ``({}, "connection refused")`` means *nobody could look* — and only the first is safe to read
    as good news.

    The heartbeat keys live on the framework Redis (6380 db1), never the story-agent sandbox on
    6379 — the same isolation rule the whole control plane observes (story agents call
    ``flushdb()`` on 6379 while testing).
    """
    try:
        import redis  # local import: a socket library the packet must not require to render
    except ImportError as exc:  # pragma: no cover — redis is a declared dependency
        return {}, f"redis_import_failed: {exc}"

    host = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
    db = int(os.environ.get("FINOPS_REDIS_DB", "1"))
    try:
        client = redis.Redis(
            host=host, port=port, db=db, decode_responses=True, socket_connect_timeout=2
        )
        out: dict[Any, Mapping[Any, Any]] = {}
        for key in client.scan_iter(match="worker:*", count=100):
            if client.type(key) in (b"hash", "hash"):
                out[key] = client.hgetall(key)
        return out, ""
    except Exception as exc:  # noqa: BLE001 — every redis failure mode is "could not observe"
        return {}, f"redis_unavailable: {exc}"


# ── The packet ───────────────────────────────────────────────────────────────────────────────


def build_packet(
    db: ControlDB,
    *,
    repo_head_sha: str = "",
    heartbeats: Mapping[Any, Mapping[Any, Any]] | None = None,
    now: float | None = None,
    failed_limit: int = DEFAULT_FAILED_LIMIT,
    degraded: Iterable[Mapping[str, str]] = (),
    projections: Sequence[str] = pwm.PROJECTIONS,
) -> dict[str, Any]:
    """Render the ``control-status/v1`` packet from the control database.

    :param db: an open control database handle — read-only in every real caller.
    :param repo_head_sha: the checkout's HEAD, from :func:`read_repo_head_sha`. Injected rather
        than read here so the function stays pure (and therefore deterministic and testable).
    :param heartbeats: raw fleet heartbeats from :func:`read_worker_heartbeats`. ``None`` means
        *not collected* — distinct from ``{}`` ("collected; nobody is registered"), and recorded
        as a ``degraded`` note so an empty ``unhealthy_workers`` can never be mistaken for health.
    :param now: epoch seconds used for worker-age arithmetic. Injected for the same reason.
        Defaults to :func:`time.time` only when heartbeats were actually supplied.
    :param failed_limit: how many recent ``failed`` runs to carry (see
        :data:`DEFAULT_FAILED_LIMIT`). Truncation is reported in ``degraded``.
    :param degraded: notes contributed by the *caller's* collectors (git, Redis). Merged with the
        ones this function derives.
    :param projections: which projections to report lag for; defaults to the four known ones.

    Determinism. Every list is totally ordered and every value comes from the database or from an
    injected argument; the dict is built with a fixed key order. Two calls with the same database
    and the same arguments produce byte-identical JSON — which is what lets an actor diff turn N
    against turn N-1 instead of re-reading the whole packet.
    """
    notes: list[dict[str, str]] = [dict(n) for n in degraded]

    # ── runs, grouped once and reused ────────────────────────────────────────────────────
    # One query for every non-terminal run, then grouped in memory. Not one query per state:
    # a single `runs(states=...)` call gives a single consistent read, whereas eight separate
    # queries could interleave with the orchestrator's writes and render a run twice (or never).
    active = db.runs(states=sorted(s.value for s in ACTIVE_RUN_STATES))
    runs_by_state: dict[RunState, list[RunRecord]] = {}
    for run in active:
        runs_by_state.setdefault(run.state, []).append(run)

    awaiting = awaiting_approval_entries(db, active)

    # `failed` is terminal, so it is queried separately and capped: unlike the active set, it
    # only ever grows.
    failed = db.runs(state=RunState.FAILED, limit=failed_limit + 1)
    if len(failed) > failed_limit:
        failed = failed[:failed_limit]
        notes.append(
            {
                "surface": "failed_runs",
                "reason": f"truncated to the {failed_limit} most recent failures",
            }
        )

    # ── workers ──────────────────────────────────────────────────────────────────────────
    if heartbeats is None:
        workers: list[dict[str, Any]] = []
        notes.append({"surface": "unhealthy_workers", "reason": "workers were not observed"})
    else:
        workers = unhealthy_workers(heartbeats, now=time.time() if now is None else now)

    # ── projections ──────────────────────────────────────────────────────────────────────
    # p3's compact block. A projection's lag is carried ONLY when the health verdict says the
    # number is believable *now*: `CURRENT` (0) and `LAGGING` (>0) are live readings; `STALE`
    # and `FAILING` describe old reality — p3's own rule is that a stale recorded zero must not
    # be believed — so their lag renders as `null` (the consumer's "do not proceed on this")
    # rather than as a reassuring 0. `UNKNOWN` (never reported / lag not computable) is already
    # `null` by construction. The block the packet carries is therefore exactly the compact
    # answer the mandate names, with the one correction that prevents a lagging-or-stale
    # consumer from reading as "current".
    lag = pwm.projection_lag(db, projections=projections)
    report = pwm.projection_report(db, projections=projections)
    health_by_projection = {entry["projection"]: entry["health"] for entry in report}
    projection_lag = {
        projection: (
            lag.get(projection)
            if health_by_projection.get(projection) == pwm.ProjectionHealth.CURRENT.value
            or health_by_projection.get(projection) == pwm.ProjectionHealth.LAGGING.value
            else None
        )
        for projection in projections
    }
    unknown = sorted(p for p, v in projection_lag.items() if v is None)
    if unknown:
        notes.append(
            {"surface": "projection_lag", "reason": f"lag unknown for: {', '.join(unknown)}"}
        )

    notes.sort(key=lambda n: (n["surface"], n["reason"]))

    # Key order is fixed by construction (Python dicts preserve insertion order, and json.dumps
    # writes them in that order) — part of the byte-identical determinism guarantee.
    return {
        "schema": SCHEMA_ID,
        "repo_head_sha": repo_head_sha,
        "control_epoch": db.control_epoch(),
        "active_runs": [run_ref(r) for r in active],
        "awaiting_approvals": awaiting,
        "promotable_runs": [run_ref(r) for r in runs_by_state.get(RunState.PROMOTABLE, [])],
        "failed_runs": [run_ref(r) for r in failed],
        "unhealthy_workers": workers,
        "projection_lag": projection_lag,
        "safe_actions": derive_safe_actions(awaiting=awaiting, runs_by_state=runs_by_state),
        DEGRADED_KEY: notes,
    }


def packet_json(packet: Mapping[str, Any], *, indent: int | None = 2) -> str:
    """Serialise a packet to JSON.

    ``sort_keys=False`` deliberately: the builder's insertion order is the *documented* order
    (identity, then state, then derived actions, then degradations), and it reads top-down the way
    an operator scans. Determinism does not require sorted keys — it requires a fixed order, and
    the builder fixes one.
    """
    return json.dumps(packet, indent=indent, ensure_ascii=False, sort_keys=False)


# ── Validation (dependency-free twin of the JSON Schema) ─────────────────────────────────────


def validate_packet(packet: Any) -> list[str]:
    """Structurally validate a packet, returning a list of human-readable errors (empty = valid).

    A hand-written checker beside :data:`CONTROL_STATUS_SCHEMA` rather than a call into
    ``jsonschema``, because the consumers that most need to validate — a container-side worker,
    a minimal orchestrator image — are exactly the ones that may not carry the dependency. The
    tests run *both* against the same packets, so the two encodings of the contract are pinned to
    each other.

    Returns errors instead of raising: a caller may want to render a malformed packet *and* say
    what is wrong with it, which an exception makes awkward.
    """
    errors: list[str] = []
    if not isinstance(packet, Mapping):
        return [f"packet is {type(packet).__name__}, expected an object"]

    required = list(CONTROL_STATUS_SCHEMA["required"])
    for key in required:
        if key not in packet:
            errors.append(f"missing required key: {key}")
    for key in packet:
        if key not in CONTROL_STATUS_SCHEMA["properties"]:
            errors.append(f"unknown key: {key}")

    if packet.get("schema") != SCHEMA_ID:
        errors.append(f"schema is {packet.get('schema')!r}, expected {SCHEMA_ID!r}")
    if not isinstance(packet.get("repo_head_sha"), str):
        errors.append("repo_head_sha must be a string")
    epoch = packet.get("control_epoch")
    # `bool` is an `int` subclass in Python; excluded explicitly so `True` cannot pass as an epoch.
    if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
        errors.append("control_epoch must be a non-negative integer")

    run_states = {s.value for s in RunState}
    for block in ("active_runs", "promotable_runs", "failed_runs"):
        value = packet.get(block)
        if not isinstance(value, list):
            errors.append(f"{block} must be an array")
            continue
        for i, entry in enumerate(value):
            errors.extend(
                _check_object(
                    entry,
                    where=f"{block}[{i}]",
                    required=_RUN_REF_SCHEMA["required"],
                    allowed=set(_RUN_REF_SCHEMA["properties"]),
                )
            )
            if isinstance(entry, Mapping) and entry.get("state") not in run_states:
                errors.append(f"{block}[{i}].state is not a known run state: {entry.get('state')!r}")

    awaiting = packet.get("awaiting_approvals")
    if not isinstance(awaiting, list):
        errors.append("awaiting_approvals must be an array")
    else:
        for i, entry in enumerate(awaiting):
            errors.extend(
                _check_object(
                    entry,
                    where=f"awaiting_approvals[{i}]",
                    required=["run_id", "gate_id", "candidate_sha"],
                    allowed={"run_id", "gate_id", "candidate_sha", "spec_name"},
                )
            )

    workers = packet.get("unhealthy_workers")
    if not isinstance(workers, list):
        errors.append("unhealthy_workers must be an array")
    else:
        for i, entry in enumerate(workers):
            errors.extend(
                _check_object(
                    entry,
                    where=f"unhealthy_workers[{i}]",
                    required=["worker", "age_seconds", "reason"],
                    allowed=set(
                        CONTROL_STATUS_SCHEMA["properties"]["unhealthy_workers"]["items"][
                            "properties"
                        ]
                    ),
                )
            )

    lag = packet.get("projection_lag")
    if not isinstance(lag, Mapping):
        errors.append("projection_lag must be an object")
    else:
        for projection in pwm.PROJECTIONS:
            if projection not in lag:
                errors.append(f"projection_lag is missing {projection}")
        for projection, value in lag.items():
            if projection not in pwm.PROJECTIONS:
                errors.append(f"projection_lag has unknown projection {projection!r}")
            elif value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                errors.append(f"projection_lag.{projection} must be an integer or null")

    actions = packet.get("safe_actions")
    known_actions = {a.value for a in SafeAction}
    if not isinstance(actions, list):
        errors.append("safe_actions must be an array")
    else:
        for i, entry in enumerate(actions):
            errors.extend(
                _check_object(
                    entry,
                    where=f"safe_actions[{i}]",
                    required=["action", "run_id", "gate_id"],
                    allowed={"action", "run_id", "gate_id", "candidate_sha"},
                )
            )
            if isinstance(entry, Mapping) and entry.get("action") not in known_actions:
                errors.append(f"safe_actions[{i}].action is not in the vocabulary: {entry.get('action')!r}")

    notes = packet.get(DEGRADED_KEY)
    if not isinstance(notes, list):
        errors.append(f"{DEGRADED_KEY} must be an array")
    else:
        for i, entry in enumerate(notes):
            errors.extend(
                _check_object(
                    entry,
                    where=f"{DEGRADED_KEY}[{i}]",
                    required=["surface", "reason"],
                    allowed={"surface", "reason"},
                )
            )

    return errors


def _check_object(
    entry: Any, *, where: str, required: Iterable[str], allowed: set[str]
) -> list[str]:
    """Shared shape check for a packet sub-object: is a mapping, has required keys, no extras."""
    if not isinstance(entry, Mapping):
        return [f"{where} is {type(entry).__name__}, expected an object"]
    errors = [f"{where} is missing {key}" for key in required if key not in entry]
    errors += [f"{where} has unknown key {key!r}" for key in entry if key not in allowed]
    return errors


# ── Human rendering ──────────────────────────────────────────────────────────────────────────


def format_packet(packet: Mapping[str, Any]) -> str:
    """A compact operator-readable rendering of the packet (the CLI's default output).

    Deliberately terse and lossy — it is the glance, not the record. Anything that acts on the
    packet reads ``--json``; this exists so a human running the command in a terminal is not made
    to parse JSON by eye. The counts and the action list are what an operator actually scans for.
    """
    lines: list[str] = [
        f"{packet.get('schema', '?')}  epoch {packet.get('control_epoch', '?')}  "
        f"head {(packet.get('repo_head_sha') or '(unknown)')[:12]}",
        f"  active {len(packet.get('active_runs', []))}"
        f" · awaiting {len(packet.get('awaiting_approvals', []))}"
        f" · promotable {len(packet.get('promotable_runs', []))}"
        f" · failed {len(packet.get('failed_runs', []))}"
        f" · unhealthy workers {len(packet.get('unhealthy_workers', []))}",
    ]

    lag = packet.get("projection_lag", {}) or {}
    rendered_lag = ", ".join(
        f"{name}={'?' if value is None else value}" for name, value in lag.items()
    )
    lines.append(f"  projection lag: {rendered_lag or '(none)'}")

    for run in packet.get("active_runs", []):
        lines.append(
            f"  [{run['state']}] {run['run_id']}  {run['spec_name']}  "
            f"{(run.get('candidate_sha') or '(no sha)')[:12]}"
        )

    actions = packet.get("safe_actions", [])
    lines.append(f"  safe actions ({len(actions)}):")
    for action in actions:
        gate = f" gate={action['gate_id']}" if action.get("gate_id") else ""
        lines.append(f"    {action['action']} {action['run_id']}{gate}")
    if not actions:
        lines.append("    (none)")

    for note in packet.get(DEGRADED_KEY, []):
        lines.append(f"  ! degraded: {note['surface']} — {note['reason']}")

    return "\n".join(lines)


__all__ = [
    "ACTIVE_RUN_STATES",
    "CONTROL_STATUS_SCHEMA",
    "DEFAULT_FAILED_LIMIT",
    "DEGRADED_KEY",
    "SCHEMA_ID",
    "WORKER_STALE_AFTER_S",
    "WORKER_STALE_ENV",
    "SafeAction",
    "awaiting_approval_entries",
    "build_packet",
    "derive_safe_actions",
    "format_packet",
    "packet_json",
    "read_repo_head_sha",
    "read_worker_heartbeats",
    "run_ref",
    "unhealthy_workers",
    "validate_packet",
    "worker_stale_after_seconds",
]
