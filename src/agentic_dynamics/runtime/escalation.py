"""The cascade/escalation plan (step 9, G-27) — opt-in, ladder-bounded, validated.

The runner historically made EXACTLY one attempt per agent phase (the ``AttemptRecord``
docstring: "never retries a phase and never escalates a model mid-phase"), so
``escalation_from``/``escalation_to`` were always ``None`` on the ledger and the Control Room's
P9 escalation surface had to render ``armed: false``. This module defines the escalation CONFIG
the runner now honors — an ordered model ladder in the spec's workflow params::

    workflow:
      params:
        escalation:
          ladder: [<model>, <model>, ...]   # ordered; escalation walks forward
          max_attempts: 2                    # optional cap (default: the ladder length)

Semantics, pinned:

* a FAILED agent attempt escalates to the NEXT ladder model AFTER the one it ran;
* a model that is not on the ladder never escalates (nothing to escalate to);
* the attempt count is bounded by ``max_attempts``;
* malformed config raises ``ValueError`` — a silent no-op would look exactly like "escalation
  is disabled" when the operator asked for it, a load-bearing difference.

Default OFF: without the param, ``from_params`` returns ``None`` and the runner is byte-identical
to the pre-step-9 engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: The workflow-params key that carries the plan.
ESCALATION_PARAM = "escalation"


@dataclass(frozen=True)
class EscalationPlan:
    """An ordered model ladder walked on agent-attempt failure."""

    ladder: tuple[str, ...]
    max_attempts: int

    @classmethod
    def from_params(cls, params: dict[str, Any] | None) -> EscalationPlan | None:
        """Parse + validate the escalation config; ``None`` when absent (default OFF)."""
        raw = (params or {}).get(ESCALATION_PARAM)
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError(
                f"workflow.params.{ESCALATION_PARAM} must be a mapping with a 'ladder', "
                f"got {type(raw).__name__}"
            )
        ladder = raw.get("ladder")
        if not isinstance(ladder, list) or not ladder:
            raise ValueError(
                f"workflow.params.{ESCALATION_PARAM}.ladder must be a non-empty list of models"
            )
        models: list[str] = []
        for entry in ladder:
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(
                    f"workflow.params.{ESCALATION_PARAM}.ladder entries must be non-empty "
                    f"model strings, got {entry!r}"
                )
            models.append(entry.strip())
        if len(set(models)) != len(models):
            raise ValueError(
                f"workflow.params.{ESCALATION_PARAM}.ladder contains duplicate models "
                f"({models!r}) — a duplicate would escalate a model onto itself"
            )
        max_attempts = raw.get("max_attempts", len(models))
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError(
                f"workflow.params.{ESCALATION_PARAM}.max_attempts must be a positive integer, "
                f"got {max_attempts!r}"
            )
        return cls(ladder=tuple(models), max_attempts=max_attempts)

    def successor(self, model: str, *, attempts_made: int) -> str | None:
        """The model the NEXT attempt should run, or ``None`` (not on the ladder / capped).

        ``attempts_made`` is the number of attempts already completed for the phase; a plan
        whose cap is reached returns ``None`` even when the ladder has a successor.
        """
        if attempts_made >= self.max_attempts:
            return None
        try:
            index = self.ladder.index(model)
        except ValueError:
            return None
        if index + 1 >= len(self.ladder):
            return None
        return self.ladder[index + 1]
