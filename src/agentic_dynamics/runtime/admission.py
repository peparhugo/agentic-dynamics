"""The admission *contract* — the per-phase spend-gate seam (the Debt-2 pattern, again).

``runtime.workflow_runner`` must not start a paid phase that was never admitted, but it may not
import ``control`` (``tests/test_dependency_direction.py`` pins the complete tier-1 → tier-2 edge
set to the two adapter telemetry edges). So this module does for admission exactly what
``runtime/routing.py`` does for routing and ``runtime/telemetry.py`` for telemetry:

* **runtime owns the contract** — the :class:`PhaseAdmission` protocol below, plus the
  :func:`phase_admission_scope` helper that makes "no gate injected" a no-op rather than a
  branch at every call site.
* **control supplies the decision** — ``control.admission.make_phase_admission`` builds a
  matching callable, and ``scripts/run_workflow.py`` (the composition root) injects it.

Runtime depends on the protocol; control supplies the implementation; the dependency arrow
never points from a plane into control.

Failure semantics
-----------------
A refused phase raises ``core.admission_context.AdmissionRefused`` (tier 0, importable here —
``control.admission.AdmissionDenied`` inherits from it). The runner's per-phase handler catches
it like any other phase failure: the phase is marked ``failed`` with the refusal on the ledger
and **the agent is never invoked**. That is the direction the work order asks to be proven —
"each entry point's tests prove refusal (no invocation happens) when a lease fails".
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Protocol


class PhaseAdmission(Protocol):
    """The per-phase spend gate a workflow run reserves through.

    Matched structurally by ``control.admission.make_phase_admission``'s return value. The
    returned context manager holds the leases for the duration of the phase and releases them
    on exit (including on an exception); the yielded value is the ``Admission`` when the gate is
    armed and ``None`` when it is disarmed, so a caller can record the admission without having
    to know whether the gate is on.
    """

    def __call__(self, phase_name: str, model: str) -> AbstractContextManager[Any]:
        """Admit one phase of ``model``, or raise ``AdmissionRefused``."""


@contextmanager
def _no_gate() -> Iterator[None]:
    """The inert gate: yields ``None`` and reserves nothing."""
    yield None


def phase_admission_scope(
    gate: PhaseAdmission | None, phase_name: str, model: str
) -> AbstractContextManager[Any]:
    """Return the context manager guarding one phase — inert when no gate was injected.

    Exists so the runner's phase loop reads as a single unconditional ``with`` rather than as a
    pair of duplicated branches. Without an injected gate the returned manager does nothing at
    all, so a run's behaviour is byte-identical to the pre-admission runner.
    """
    if gate is None:
        return _no_gate()
    return gate(phase_name, model)
