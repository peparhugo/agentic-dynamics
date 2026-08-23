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

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

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


# ── validate_fact_contracts (design §7.3, refusals R1-R11) ───────
#
# Structural (duck-typed) protocols, never a concrete import of `control.facts.PredicateSpec` /
# `control.facts.ReducerSpec` / `experiment.experiment_spec.RuleSpec` — see the module docstring:
# `core` may not import `experiment` or `control`. The real objects (which already satisfy these
# shapes — PredicateSpec/ReducerSpec/RuleSpec's own attributes match verbatim) are threaded in by
# a caller in a tier that may see both, e.g. `control.context_compiler.validate_spec_fact_contracts`.


class PredicateLike(Protocol):
    value_type: str
    scope_type: str
    abstraction_level: str
    produced_by: tuple[str, ...]
    volatile: bool
    inheritable: bool
    aggregates_from: str


class ReducerLike(Protocol):
    version: str
    level: str
    consumes: tuple[str, ...]
    produces: tuple[str, ...]


class ContractLike(Protocol):
    decision_type: str
    contract_version: str
    allowed_actions: tuple[str, ...]
    invariants: Iterable[FactRequirement]
    requires_facts: Iterable[FactRequirement]
    excludes: tuple[str, ...]


class RuleLike(Protocol):
    name: str
    plane: str
    requires_facts: Iterable[FactRequirement]
    decision_type: str


class SpecLike(Protocol):
    rules: Iterable[RuleLike]


def _validate_one_requirement(
    rule_name: str,
    req: FactRequirement,
    *,
    predicates: Mapping[str, PredicateLike],
    reducers: Mapping[str, ReducerLike],
) -> list[str]:
    """Refusals R1-R8 for one :class:`FactRequirement` (design §7.3's per-requirement rows)."""
    errors: list[str] = []
    row = predicates.get(req.fact)
    if row is None:
        errors.append(
            f'rule "{rule_name}" requires fact {req.fact!r} — no such predicate is declared. '
            f"Declare it with a producing reducer first. (R1)"
        )
        return errors  # nothing further is checkable without a predicate row

    produced_by = tuple(row.produced_by or ())
    if not produced_by:
        errors.append(
            f'rule "{rule_name}" requires {req.fact!r} — declared but produced by no reducer. '
            f"Instrument it first. (R2)"
        )

    # R3 — the reduction ladder: every predicate a producing reducer's `consumes` names must
    # itself be produced by SOME registered reducer. A `consumes` entry not in `predicates` is
    # assumed to be an evidence source_type (design §4.1: "consumes" mixes both), not checked
    # further here — there is no evidence-source registry to check it against.
    for reducer_version in produced_by:
        reducer = reducers.get(reducer_version)
        if reducer is None:
            continue  # the reducer itself is unregistered — a different failure, not R3
        for consumed in reducer.consumes:
            consumed_spec = predicates.get(consumed)
            if consumed_spec is not None and not consumed_spec.produced_by:
                errors.append(
                    f'rule "{rule_name}" requires {req.fact!r} — its reducer {reducer_version} '
                    f"consumes {consumed!r}, which no reducer produces. The ladder is "
                    f"incomplete. (R3)"
                )

    # R4 — scope reachability: an EXPLICIT requirement scope narrower/other than the predicate's
    # own declared scope_type needs a declared aggregation (`aggregates_from`) to roll up to it.
    # Relative keywords (self/parent) are resolved at RUNTIME against the decision's own scope
    # (I4) and are not checkable here — this is the compile-time twin design §7.3 describes, not
    # a re-implementation of scope_visible().
    if req.scope not in RELATIVE_SCOPES and req.scope != row.scope_type and not row.aggregates_from:
        errors.append(
            f'rule "{rule_name}" requires {req.fact!r} at scope {req.scope!r} from a '
            f"{row.scope_type!r}-scoped fact — no aggregation reducer exists. Declare one or "
            f"raise the requirement's scope. (R4)"
        )

    if req.min_authority == "ADVISORY":
        errors.append(
            f'rule "{rule_name}" requires {req.fact!r} at min_authority ADVISORY — a control '
            f"rule may never consume an advisory value. (R5)"
        )

    if row.volatile and req.max_age_seconds is None:
        errors.append(
            f'rule "{rule_name}" requires volatile fact {req.fact!r} with no max_age_seconds '
            f"— a control rule may not consume a volatile fact with unbounded age. (R6)"
        )

    if req.on_missing not in ON_MISSING:
        errors.append(
            f'rule "{rule_name}": on_missing {req.on_missing!r} is not one of '
            f"{sorted(ON_MISSING)} (R7)"
        )
    if req.on_conflict not in ON_CONFLICT:
        errors.append(
            f'rule "{rule_name}": on_conflict {req.on_conflict!r} is not one of '
            f"{sorted(ON_CONFLICT)} (R7)"
        )

    if req.value_type is not None and req.value_type != row.value_type:
        errors.append(
            f'rule "{rule_name}" requires {req.fact!r} as {req.value_type!r}; the registry '
            f"declares {row.value_type!r}. (R8)"
        )
    return errors


def validate_fact_contracts(
    spec: SpecLike,
    *,
    predicates: Mapping[str, PredicateLike],
    reducers: Mapping[str, ReducerLike],
    contracts: Mapping[str, ContractLike] | None = None,
) -> list[str]:
    """Compile-time refusals R1-R11 (design §7.3 + the F1/implementation_notes.md resolution).

    Composed into the spec gate ALONGSIDE ``experiment_spec.validate_rules`` — never instead of
    it (a bare-string legacy ``requires`` entry is untouched by this function). Returns error
    strings in the house style (``experiment_spec.py``'s ``rule "<name>": ...`` prefix) so a
    failing spec reads the same regardless of which gate refused it.

    "Compile time proves PRODUCIBILITY. Run time proves CURRENCY." (design §7.3) — the five
    remaining runtime-only conditions (absent / stale / conflicted / out-of-scope / broken
    derivation chain) are the I4 Context Compiler's job (``compile_context``), every time, per
    decision; they are NOT re-implemented here.
    """
    errors: list[str] = []
    contracts = contracts or {}

    # R11 (F1's resolution, implementation_notes.md §2): an invariant with on_missing outside
    # {halt, escalate} silently disables a safety constraint — checked for every loaded
    # contract, independent of whether a rule in THIS spec references it, because the property
    # is of the CONTRACT, not of the reference.
    for contract in contracts.values():
        for inv in contract.invariants:
            if inv.on_missing not in ("halt", "escalate"):
                errors.append(
                    f"contract {contract.decision_type!r}/{contract.contract_version} "
                    f"invariant {inv.fact!r}: on_missing {inv.on_missing!r} is not one of "
                    f"('halt', 'escalate') — an invariant that classifies is not a "
                    f"constraint. (R11)"
                )

    for rule in spec.rules:
        if rule.plane == "control" and rule.decision_type:
            contract = contracts.get(rule.decision_type)
            if contract is None:
                errors.append(
                    f'rule "{rule.name}": decision_type {rule.decision_type!r} has no contract '
                    f"in experiments/contexts/ (R9)"
                )
            else:
                excluded = set(contract.excludes)
                for req in rule.requires_facts:
                    if req.fact in excluded:
                        errors.append(
                            f'rule "{rule.name}" requires {req.fact!r}; contract '
                            f"{contract.decision_type!r}/{contract.contract_version} excludes "
                            f"it. (R10)"
                        )

        for req in rule.requires_facts:
            errors.extend(
                _validate_one_requirement(
                    rule.name, req, predicates=predicates, reducers=reducers
                )
            )

    return errors
