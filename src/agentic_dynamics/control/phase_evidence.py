"""The control implementation of the per-phase evidence seam (``control_db_evidence`` e1).

``runtime.workflow_runner`` produces a :class:`PhaseEvidence` per executed phase and hands it to
the injected :class:`PhaseEvidenceRecorder`. This module is the control-plane half of that
Debt-2 seam: it turns one :class:`PhaseEvidence` into the control db's real rows, reusing the
database's existing writers — :meth:`ControlDB.start_attempt` + :meth:`ControlDB.finish_attempt`
for the one ``step_attempts`` row, and :meth:`ControlDB.record_gate_result` for each gate
verdict — exactly the "INSERT path transition_run uses", composed inside ONE transaction so a
phase's attempt and its gate verdicts appear together or not at all (a phase is one unit of
evidence; a half-recorded phase would read as a different phase).

Before e1 these two evidence tables were code-complete but data-empty (a run that executed 8
phases recorded 0 step_attempts and 0 gate_results; ``record_gate_result`` had zero production
callers). The write side that fills them lives here and in the engine's loop.

Best-effort is the ENGINE's guarantee (a recorder failure must never fail the phase, and the
failure is a named warning) — so this module deliberately does NOT swallow errors. A control-db
outage raises ``ControlDBError``/``OSError`` out of :func:`record_phase_evidence`, and the engine
catches it loudly. Swallowing here would hide which half of the write failed.

Child mode (``--only-phase``) stays inert by construction: the composition root mints NO run row
for a sibling cell, so :func:`make_phase_evidence_recorder` is handed ``run_id=None`` and returns
``None`` — the engine's seam then does nothing, and the PARENT's run records every phase its
children executed. "Children never emit; the parent aggregates" (P0-2) is thus held in exactly
one place: the run row's existence.
"""

from __future__ import annotations

from agentic_dynamics.control.control_db import (
    AttemptState,
    ControlDB,
    GateResultRecord,
    StepAttemptRecord,
    attempt_state_from_phase_status,
)
from agentic_dynamics.runtime.phase_evidence import PhaseEvidence, PhaseEvidenceRecorder


def record_phase_evidence(
    db: ControlDB, run_id: str, evidence: PhaseEvidence
) -> tuple[StepAttemptRecord, tuple[GateResultRecord, ...]]:
    """Record one executed phase: a step attempt + every gate verdict it produced.

    The attempt row's ``attempt_no`` is derived from the rows already stored for ``(run, step)``
    (:meth:`ControlDB.next_attempt_no`, applied inside :meth:`ControlDB.start_attempt`), so a
    retried phase records attempt 1, then 2, never a duplicate — the schema's
    ``uq_step_attempts_run_step_no`` UNIQUE contract is satisfied by reusing the writer that
    enforces it, rather than by the engine guessing a number.

    The whole phase is one transaction: the attempt's ``start``/``finish`` and every gate result
    commit together, so a reader never sees a phase whose gate verdicts exist but whose attempt
    does not (or vice versa). ``record_gate_result`` enforces the non-empty ``candidate_sha``
    itself — a verdict the engine cannot bind to a commit raises, the transaction rolls back,
    and the engine's named warning reports it; evidence that cannot name its tree is never
    written half-heartedly.

    Returns the committed attempt and gate records (re-read after commit, mirroring the db's own
    writer pattern).
    """
    # ``started_at``/``ended_at`` default to the db's clock when a caller has none; the engine
    # always supplies both so a phase's duration is its own, not the writer's.
    with db.transaction():
        attempt = db.start_attempt(
            run_id,
            step_id=evidence.step_id,
            model=evidence.model,
            state=AttemptState.RUNNING,
            started_at=evidence.started_at or None,
        )
        attempt = db.finish_attempt(
            attempt.attempt_id,
            attempt_state_from_phase_status(evidence.status),
            tokens=evidence.tokens,
            cost_usd=evidence.cost_usd,
            exit_code=evidence.exit_code,
            error=evidence.error,
            ended_at=evidence.ended_at or None,
        )
        gates = tuple(
            db.record_gate_result(
                run_id,
                step_id=evidence.step_id,
                verdict=gate.verdict,
                candidate_sha=evidence.candidate_sha,
                evidence=gate.evidence,
                executor=gate.executor,
                started_at=evidence.started_at,
                ended_at=evidence.ended_at,
            )
            for gate in evidence.gates
        )
    return attempt, gates


def make_phase_evidence_recorder(
    db: ControlDB | None, run_id: str | None
) -> PhaseEvidenceRecorder | None:
    """Bind the per-phase writer to an open control db + run id; ``None`` when there is no run row.

    ``run_id`` is ``None`` in child mode (``--only-phase`` — the composition root never mints a
    run row for a sibling cell) and when the database was unavailable at run start. In both cases
    the returned ``None`` makes the engine's seam inert, which is the entire child-mode contract:
    the parent aggregates, and a sibling records nothing. The bound writer raises through on a
    control-db failure (the engine catches and warns) — it never silently drops a phase.
    """
    if db is None or not run_id:
        return None

    def _record(evidence: PhaseEvidence) -> None:
        record_phase_evidence(db, run_id, evidence)

    return _record
