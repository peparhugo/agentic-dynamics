"""CAP I6 — the decision record types: ``ControlDecision``, ``Precondition``, ``ExpectedEffect``.

A typed, validated, provenance-carrying proposal to change the future (design §1's thesis,
§8.2). Deliberately just the SHAPE — no I/O, no policy, no validation logic — so both the
fact-based control rule (``control/rules.py``, which CONSTRUCTS decisions) and the validator
(``control/validator.py``, which ADMITS or REFUSES them) import the same types without either
depending on the other.

Persisted as ``source_type="actuation"`` (REUSE — ``knowledge.py``, ``actuation_ingestion.py``),
NOT a new record family: the review found the envelope, identity, POLICY authority, action
vocabulary, ``causes`` lineage requirement, and the armed gate already exist with zero call
sites (design §8.2). ``ControlDecision`` is the TYPED PAYLOAD that travels in that record's body.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: The ONLY actions an automated proposer may have APPLIED (design §8.3). Both `continue` and
#: `route` are pre-execution, in-process, reversible choices the system already makes
#: deterministically today (step_routing.route_step). Everything else a controller proposes is
#: recorded + surfaced, never applied. Widening this set is a deliberate, reviewable code edit —
#: never a config value, never an env var (design's own emphasis, verbatim).
AUTOMATABLE_ACTIONS: frozenset[str] = frozenset({"continue", "route"})

#: The full action vocabulary a decision may ever propose (design §8.1's table) — a superset of
#: AUTOMATABLE_ACTIONS. `retry`/`escalate`/`stop` are "proposal only": constructed, validated,
#: durably recorded, and surfaced as a flag for a human — never applied by an automated path.
#: `fork`/`compress_and_fork` are CAP addendum I10 additions (design §4.2/§4.3,
#: `experiments/contexts/session_routing.yaml`'s `allowed_actions`) — widened explicitly here,
#: the same "each increment grows this vocabulary, never silently" discipline
#: `control/facts.py`'s own predicate/allowlist tables already follow. Both are proposal-only,
#: same as `retry`/`stop`: `AUTOMATABLE_ACTIONS` (above) is UNCHANGED by this addition.
#: `escalate` was already present (I6) — the session-routing `escalate` REUSES that same action
#: name (a real actuation: a model change), never a second name for the same concept.
PROPOSABLE_ACTIONS: frozenset[str] = frozenset(
    {"continue", "route", "retry", "escalate", "stop", "fork", "compress_and_fork"}
)

#: `Precondition.op` — the comparison vocabulary a TOCTOU re-check may use (design §8.2).
PRECONDITION_OPS: frozenset[str] = frozenset(
    {"eq", "ne", "lt", "lte", "gt", "gte", "in", "is_true", "is_false"}
)


@dataclass(frozen=True)
class Precondition:
    """A condition re-checked against a FRESH snapshot at apply time (validator check C7) —
    the TOCTOU guard: between compile and apply, a phase may finish, a cost may cross a
    ceiling, a policy may change. Without re-checking, the plane would apply decisions derived
    from a world that no longer exists (design §8.2)."""

    fact: str
    scope: str
    op: str  # PRECONDITION_OPS
    value: Any
    max_age_seconds: int


@dataclass(frozen=True)
class ExpectedEffect:
    """The falsifiable prediction a decision makes. Recording it BEFORE execution is what turns
    control into an experiment: the same ``compare_arms``-style machinery can score predicted
    against measured (design §8.2) — see ``compile_experiment.decision_calibration`` (I6, F3)."""

    predicate: str
    direction: str  # "increase" | "decrease" | "unchanged"
    magnitude: float | None
    horizon: str  # "next_phase" | "end_of_workflow"


@dataclass(frozen=True)
class ControlDecision:
    """A typed, validated, provenance-carrying proposal to change the future (design §8.2).

    Persisted as ``source_type="actuation"`` — NOT a new record family (design §8.2's own
    emphasis: the review found this envelope already exists with zero call sites). This
    dataclass is the typed payload; ``rules.decision_to_actuation_candidate`` maps it onto the
    existing ``actuation_ingestion.derive_actuation_record`` candidate shape.
    """

    decision_id: str
    snapshot_id: str
    """The snapshot this decision was made from — also the resolution of the actuation record's
    ``causes`` (a single knowledge_id is sufficient because the snapshot itself carries the full
    evidence set — design §8.2)."""
    decision_type: str
    contract_version: str

    action: str  # PROPOSABLE_ACTIONS
    target_type: str  # job | workflow | attempt
    target_id: str
    parameters: dict[str, Any] = field(default_factory=dict)  # e.g. {"model": "..."}

    facts_used: tuple[str, ...] = ()
    """fact_ids actually consumed. MUST be a subset of the snapshot's canonical facts (check
    C5) — the audit trail for "which facts, at which values, led to this decision"."""

    expected_effect: tuple[ExpectedEffect, ...] = ()
    preconditions: tuple[Precondition, ...] = ()
    proposed_by: str = ""  # "policy_rule:route_next_job" | "operator:<id>" | "advisor:<model>"
    proposed_at: str = ""
    rationale: str = ""  # free text; NEVER load-bearing — validators ignore it
