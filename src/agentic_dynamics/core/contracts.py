"""CAP I5's reserved home — ``FactRequirement`` is introduced here in I4, ahead of the I5 gate.

``ARCHITECTURE.md`` §4 reserves this module for I5 (``FactRequirement``,
``validate_fact_contracts``). The design's own contract sketch (§6.1) uses the
``FactRequirement`` *shape* (``fact``/``scope``/``max_age_seconds``/``min_authority``/
``on_missing``/``on_conflict``) inside the I4 decision-type contract YAML before §7 formalizes
it as a type — so the dataclass is defined here now, and I4's Context Compiler
(``control/context_compiler.py``) imports it to parse ``experiments/contexts/*.yaml``. I5 adds
``validate_fact_contracts`` (refusals R1-R11) and wires ``RuleSpec.requires_facts`` to it.

Dependency direction (``tests/test_dependency_direction.py``): ``core`` is tier 0 and may import
only the standard library plus core siblings — nothing from ``experiment``/``control``. So this
module never imports ``agentic_dynamics.control.facts`` (``FACT_PREDICATES``/``REDUCERS``) or
``agentic_dynamics.experiment.experiment_spec`` (``RuleSpec``): the predicate/reducer registries
and the rule objects the I5 gate inspects are passed in as plain data (``Mapping``/``Iterable`` of
loosely-typed rows), never imported. The real registries are threaded in by a caller in a tier
that may see both ``core`` and ``control`` (``control.context_compiler``, tier 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── Closed vocabularies (design §7.1) ────────────────────────────

#: ``on_missing`` — how the compiler degrades when a required fact cannot be resolved.
ON_MISSING = frozenset({"halt", "escalate", "classify", "investigate"})

#: ``on_conflict`` — how the compiler degrades when two current facts disagree.
ON_CONFLICT = frozenset({"halt", "escalate", "prefer_higher_authority", "classify"})

#: ``min_authority`` — the ``Authority`` enum NAMEs a requirement may demand. ``ADVISORY`` is
#: deliberately absent: R5 refuses a control rule that would consume an advisory value, so
#: ``min_authority`` can never legally be set to it in the first place.
MIN_AUTHORITY_LEVELS = frozenset({"DERIVED", "SOURCE", "MEASURED", "POLICY"})

#: ``scope`` — either a relative keyword (resolved against the decision's own scope at compile
#: time, design §10.2) or an explicit ancestor scope_type name.
RELATIVE_SCOPES = frozenset({"self", "parent"})
EXPLICIT_SCOPES = frozenset({"workload", "organization", "workflow", "job", "attempt", "resource"})
SCOPE_KEYWORDS = RELATIVE_SCOPES | EXPLICIT_SCOPES


# ── FactRequirement (design §7.1) ────────────────────────────────


@dataclass(frozen=True)
class FactRequirement:
    """One fact a rule (or contract entry) consumes, with its currency and failure semantics.

    Generalizes the legacy bare-string ``RuleSpec.requires`` entry: a bare string means the
    legacy contract, made explicit by :func:`normalize_requirement` (``"confidence"`` ==
    ``FactRequirement(fact="confidence")``) — one validator, one set of error messages, and
    every spec committed before this design keeps validating unchanged.
    """

    fact: str
    scope: str = "self"
    max_age_seconds: int | None = None
    min_authority: str = "DERIVED"
    on_missing: str = "halt"
    on_conflict: str = "halt"
    value_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact": self.fact,
            "scope": self.scope,
            "max_age_seconds": self.max_age_seconds,
            "min_authority": self.min_authority,
            "on_missing": self.on_missing,
            "on_conflict": self.on_conflict,
            "value_type": self.value_type,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FactRequirement:
        if "fact" not in d:
            raise ValueError(f"FactRequirement missing required field: fact ({d})")
        return cls(
            fact=str(d["fact"]),
            scope=str(d.get("scope", "self")),
            max_age_seconds=d.get("max_age_seconds"),
            min_authority=str(d.get("min_authority", "DERIVED")),
            on_missing=str(d.get("on_missing", "halt")),
            on_conflict=str(d.get("on_conflict", "halt")),
            value_type=d.get("value_type"),
        )


def normalize_requirement(entry: str | dict | FactRequirement) -> FactRequirement:
    """Normalize one ``requires_facts``/contract entry to a :class:`FactRequirement`.

    A bare string is the legacy shorthand for ``FactRequirement(fact=<name>)`` — self,
    unbounded age, ``DERIVED`` minimum authority, halt on missing/conflict (design §7.1).
    """
    if isinstance(entry, FactRequirement):
        return entry
    if isinstance(entry, str):
        return FactRequirement(fact=entry)
    return FactRequirement.from_dict(entry)
