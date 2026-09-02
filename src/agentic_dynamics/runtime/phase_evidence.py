"""The per-phase evidence *contract* — the step_attempts + gate_results write seam (Debt-2).

``runtime.workflow_runner`` owns the phase loop, and the loop is where per-phase evidence must
be recorded (``control_db_evidence`` e1): every executed phase is one ``step_attempts`` row plus
one ``gate_results`` row per gate verdict the phase produced. But the writer that persists those
rows is the control database, and ``runtime`` may not import ``control``
(``tests/test_dependency_direction.py`` pins the complete tier-1 → tier-2 edge set). So this
module does for phase evidence exactly what ``runtime/routing.py`` does for routing,
``runtime/telemetry.py`` for telemetry, ``runtime/admission.py`` for the spend gate, and
``runtime/change_analyzer.py`` for phase-boundary evidence:

* **runtime owns the contract** — the :class:`PhaseEvidence` value object (everything one
  executed phase contributes to the control db), the :func:`phase_gate_verdicts` derivation from
  a :class:`~agentic_dynamics.runtime.workflow_runner.PhaseResult`, and the
  :class:`PhaseEvidenceRecorder` protocol. This module is pure data + one protocol; it touches
  no database.
* **control supplies the writer** — ``control.phase_evidence.record_phase_evidence`` maps a
  :class:`PhaseEvidence` onto the control db's existing writers (``start_attempt`` /
  ``finish_attempt`` / ``record_gate_result``), and ``scripts/run_workflow.py`` (the composition
  root) injects the bound recorder.

The dependency arrow never points from a plane into control. Runtime produces the facts about
the phase it just executed; control decides how those facts become rows.

Best-effort is the engine's guarantee, not this module's: the recorder call in the phase loop is
wrapped so a control-db failure can never fail the phase — but a failed write is loud (a named
warning), never silent, which is the e1 contract ("a successful write is the norm and a failure
is loud").

What a gate verdict IS here. A phase produces a gate-result row only when a gate actually FIRED —
the gate left its verdict on the :class:`PhaseResult` (``commit_gate`` / ``relabel_gate`` /
``deploy_gate`` become non-``None``). A gate that ran cleanly leaves nothing behind, and the
absence of a row is the honest statement "this gate did not flag this phase": recording a
fabricated ``pass`` for a gate that never ran (or never applied to a test phase) would be the
exact null-not-zero violation the evidence tables exist to prevent. The verdict maps from the
fired evidence's ``reason``: ``APPROVED`` (an operator-approved relabel reuse) is a ``pass``;
every other reason names a violation the gate detected and is a ``fail``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

#: Wire values of the control db's ``GateVerdict`` vocabulary, spelled here so runtime owns its
#: contract without importing ``control.control_db``. The control-side writer coerces them back
#: onto the enum (a total mapping — both directions are lossless).
GATE_VERDICT_PASS = "pass"
GATE_VERDICT_FAIL = "fail"

#: The per-phase gates whose fired verdicts ride on :class:`PhaseResult`. The attribute names on
#: the result are the row's ``gate`` identifier, so the control db's ``step_id``/evidence can
#: name which gate produced the verdict.
GATE_FIELDS: tuple[str, ...] = ("commit_gate", "relabel_gate", "deploy_gate")

#: The one fired-gate reason that records a PASS: an operator-approved tree reuse. Everything
#: else (``COMMIT_PREFIX`` / ``COMMIT_PREFIX_CANONICALIZED`` / ``NO_CHANGES`` / ``DEPLOY_GATE`` /
#: ``RELABEL``) names a violation the gate detected.
GATE_REASON_APPROVED = "APPROVED"


def iso_now() -> str:
    """UTC ISO-8601 with a ``Z`` suffix — the control db's own timestamp shape (``control_db._now``).

    Phase evidence rows carry start/end stamps that are compared and ordered alongside control
    db rows written by the database's own helpers, so they use the same wire shape rather than
    the workflow ledger's offset form.
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_from_epoch(epoch_seconds: float) -> str:
    """Render a ``time.time()`` epoch as the control db's ``Z`` ISO string."""
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class PhaseGateEvidence:
    """One gate verdict a phase produced.

    Exists only when the gate FIRED — see the module docstring for why clean gates produce no
    row. ``verdict`` is the :data:`GATE_VERDICT_PASS`/:data:`GATE_VERDICT_FAIL` wire value;
    ``reason`` is the fired evidence's ``reason`` field (``COMMIT_PREFIX``, ``DEPLOY_GATE``,
    ``RELABEL``, ``APPROVED``, …); ``evidence`` is the gate's full verdict object verbatim, so
    the append-only gate_results row carries the same proof the PhaseResult carried.
    """

    gate: str
    verdict: str
    reason: str
    evidence: Any = None
    executor: str = "orchestrator"


def phase_gate_verdicts(result: Any) -> tuple[PhaseGateEvidence, ...]:
    """The gate verdicts a finished phase produced, in a fixed gate order.

    ``result`` is duck-typed (a :class:`PhaseResult`, or any object exposing the three gate
    attributes) so this stays a pure derivation over the result's surface. A gate attribute that
    is ``None`` (never fired) contributes nothing; a non-``None`` dict contributes one verdict.
    """
    verdicts: list[PhaseGateEvidence] = []
    for gate in GATE_FIELDS:
        evidence = getattr(result, gate, None)
        if not evidence:
            continue
        reason = str(evidence.get("reason", "")) if isinstance(evidence, dict) else ""
        verdict = GATE_VERDICT_PASS if reason == GATE_REASON_APPROVED else GATE_VERDICT_FAIL
        verdicts.append(
            PhaseGateEvidence(gate=gate, verdict=verdict, reason=reason, evidence=evidence)
        )
    return tuple(verdicts)


@dataclass(frozen=True)
class PhaseEvidence:
    """Everything the control db needs to record ONE executed phase.

    One instance per executed phase of the loop, built by the engine from the phase's
    :class:`~agentic_dynamics.runtime.workflow_runner.PhaseResult` + the timing/git facts the
    loop holds. ``status`` is the ledger vocabulary (``ok``/``failed``/``awaiting`` — an
    ``awaiting`` checkpoint phase is a designed stop, mapped losslessly onto the control db's
    ``AttemptState`` by the writer). ``candidate_sha`` is the phase-boundary commit the gates
    judged (empty only when the worktree had no commit at all — in which case no gate can have
    fired, so no gate row needs a candidate).
    """

    step_id: str
    status: str
    started_at: str
    ended_at: str
    candidate_sha: str
    kind: str = "agent"
    model: str = ""
    tokens: int = 0
    cost_usd: float = 0.0
    exit_code: int | None = None
    error: str = ""
    gates: tuple[PhaseGateEvidence, ...] = ()


class PhaseEvidenceRecorder(Protocol):
    """The per-phase write seam a workflow run records evidence through.

    A callable protocol (matched structurally by ``control.phase_evidence.
    make_phase_evidence_recorder``'s return value — a function bound to an open control db
    handle and the run's id), mirroring the ``Router``/``PhaseAdmission`` seams. Implementations
    are best-effort by construction: a writer that raises is caught by the engine, which prints
    a named warning and lets the phase stand.
    """

    def __call__(self, evidence: PhaseEvidence) -> None:
        """Record one executed phase's step attempt + gate verdicts (or raise; never a gate)."""
