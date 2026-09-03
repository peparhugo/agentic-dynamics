"""Tests for CAP I5 — fact contracts in the spec gate (``core/contracts.py``, refusals R1-R11).

Covers ``FactRequirement``/``normalize_requirement`` (shared with I4), ``RuleSpec.requires_facts``/
``decision_type`` (the ``experiment_spec.py`` wiring), each R1-R11 refusal in isolation (fixture
predicate/reducer/contract registries — ``core.contracts`` never imports the real ones, per
dependency direction), the compile-time/run-time split (this gate proves producibility, not
currency), and the REAL gate (``control.context_compiler.validate_spec_fact_contracts`` against
the actual ``FACT_PREDICATES``/``REDUCERS``/committed contracts) — including the "existing spec
corpus still validates with zero new refusals" gate (design §9 I5's own acceptance criterion).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

from agentic_dynamics.core.contracts import (
    ON_CONFLICT,
    ON_MISSING,
    ContractLike,
    FactRequirement,
    PredicateLike,
    ReducerLike,
    RuleLike,
    SpecLike,
    normalize_requirement,
    validate_fact_contracts,
)
from agentic_dynamics.experiment.experiment_spec import (
    ExperimentSpec,
    Factor,
    RuleSpec,
    Workflow,
    load_spec,
    validate_spec,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── Fixture registries (never the real FACT_PREDICATES/REDUCERS — core.contracts is tier 0) ─


class _Predicate(PredicateLike):
    def __init__(
        self,
        *,
        value_type="int",
        scope_type="job",
        abstraction_level="job",
        produced_by=("demo_reducer/v1",),
        volatile=False,
        inheritable=False,
        aggregates_from="",
    ):
        self.value_type = value_type
        self.scope_type = scope_type
        self.abstraction_level = abstraction_level
        self.produced_by = produced_by
        self.volatile = volatile
        self.inheritable = inheritable
        self.aggregates_from = aggregates_from


class _Reducer(ReducerLike):
    def __init__(self, *, version="demo_reducer/v1", level="job", consumes=(), produces=()):
        self.version = version
        self.level = level
        self.consumes = consumes
        self.produces = produces


class _Contract(ContractLike):
    def __init__(
        self,
        *,
        decision_type="demo_decision",
        contract_version="demo_decision/v1",
        allowed_actions=("route", "continue"),
        invariants=(),
        requires_facts=(),
        excludes=(),
    ):
        self.decision_type = decision_type
        self.contract_version = contract_version
        self.allowed_actions = allowed_actions
        self.invariants = invariants
        self.requires_facts = requires_facts
        self.excludes = excludes


class _Rule(RuleLike):
    def __init__(self, *, name="r1", plane="control", requires_facts=(), decision_type=""):
        self.name = name
        self.plane = plane
        self.requires_facts = requires_facts
        self.decision_type = decision_type


class _Spec(SpecLike):
    def __init__(self, rules):
        self.rules = rules


def _predicates() -> dict[str, _Predicate]:
    return {
        "demo_fact": _Predicate(),
        "unproduced_fact": _Predicate(produced_by=()),
        "volatile_fact": _Predicate(volatile=True),
        "workload_fact": _Predicate(scope_type="workload", abstraction_level="policy"),
        "aggregate_fact": _Predicate(
            scope_type="workflow", aggregates_from="demo_fact", produced_by=("agg_reducer/v1",)
        ),
        "orphan_consumer_fact": _Predicate(produced_by=("broken_reducer/v1",)),
    }


def _reducers() -> dict[str, _Reducer]:
    return {
        "demo_reducer/v1": _Reducer(consumes=("ledger_attempt",), produces=("demo_fact",)),
        "agg_reducer/v1": _Reducer(
            level="workflow", consumes=("demo_fact",), produces=("aggregate_fact",)
        ),
        "broken_reducer/v1": _Reducer(
            consumes=("unproduced_fact",), produces=("orphan_consumer_fact",)
        ),
    }


# ── FactRequirement / normalize_requirement (shared with I4) ────


def test_normalize_requirement_accepts_a_bare_string():
    req = normalize_requirement("confidence")
    assert req == FactRequirement(fact="confidence")
    assert req.scope == "self"
    assert req.on_missing == "halt"


def test_normalize_requirement_accepts_a_dict():
    req = normalize_requirement({"fact": "workflow_status", "scope": "parent", "on_missing": "classify"})
    assert req.fact == "workflow_status"
    assert req.scope == "parent"
    assert req.on_missing == "classify"


def test_normalize_requirement_passes_through_an_existing_instance():
    original = FactRequirement(fact="x")
    assert normalize_requirement(original) is original


def test_normalize_requirement_refuses_a_dict_with_no_fact_key():
    with pytest.raises(ValueError, match="missing required field"):
        normalize_requirement({"scope": "self"})


# ── RuleSpec.requires_facts / decision_type wiring ───────────────


def test_rulespec_round_trips_requires_facts_and_decision_type():
    rule = RuleSpec.from_dict({
        "name": "route_next_job",
        "plane": "control",
        "evidence_class": "[H]",
        "decision_type": "route_next_job",
        "requires_facts": [
            {"fact": "job_accumulated_cost_usd", "on_missing": "classify"},
            "workflow_phases_remaining",  # bare-string shorthand, per normalize_requirement
        ],
        "produces": ["route_decision"],
    })
    assert rule.decision_type == "route_next_job"
    assert [r.fact for r in rule.requires_facts] == [
        "job_accumulated_cost_usd", "workflow_phases_remaining",
    ]
    assert rule.requires_facts[1].scope == "self"  # the bare-string default

    d = rule.to_dict()
    assert d["decision_type"] == "route_next_job"
    assert d["requires_facts"][0]["fact"] == "job_accumulated_cost_usd"

    round_tripped = RuleSpec.from_dict(d)
    assert round_tripped == rule


def test_rulespec_defaults_are_backward_compatible():
    # Every RuleSpec authored before I5 (no requires_facts/decision_type keys) still parses.
    rule = RuleSpec.from_dict({"name": "r", "plane": "measurement", "evidence_class": "[C]"})
    assert rule.requires_facts == []
    assert rule.decision_type == ""


# ── R1-R8: per-requirement refusals ──────────────────────────────


def test_r1_undeclared_predicate():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="no_such_predicate")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert any("(R1)" in e and "no_such_predicate" in e for e in errors)


def test_r2_predicate_with_no_producer():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="unproduced_fact")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert any("(R2)" in e for e in errors)


def test_r3_incomplete_reduction_ladder():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="orphan_consumer_fact")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert any("(R3)" in e and "ladder is incomplete" in e for e in errors)


def test_r3_complete_ladder_is_not_refused():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="demo_fact")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert not any("(R3)" in e for e in errors)


def test_r4_scope_unreachable_without_an_aggregation():
    # demo_fact is job-scoped; requiring it at "workload" scope with no aggregates_from path.
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="demo_fact", scope="workload")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert any("(R4)" in e for e in errors)


def test_r4_relative_scopes_are_never_flagged():
    # self/parent are resolved at RUNTIME (I4) — R4 is the compile-time producibility twin only.
    for scope in ("self", "parent"):
        spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="demo_fact", scope=scope)])])
        errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
        assert not any("(R4)" in e for e in errors)


def test_r4_declared_aggregation_satisfies_the_ladder():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="aggregate_fact", scope="workflow")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert not any("(R4)" in e for e in errors)


def test_r5_advisory_min_authority_is_refused():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="demo_fact", min_authority="ADVISORY")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert any("(R5)" in e and "never consume an advisory value" in e for e in errors)


def test_r6_volatile_predicate_needs_max_age_seconds():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="volatile_fact")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert any("(R6)" in e for e in errors)

    spec_ok = _Spec(
        [_Rule(requires_facts=[FactRequirement(fact="volatile_fact", max_age_seconds=60)])]
    )
    errors_ok = validate_fact_contracts(spec_ok, predicates=_predicates(), reducers=_reducers())
    assert not any("(R6)" in e for e in errors_ok)


def test_r7_on_missing_and_on_conflict_vocabulary():
    spec = _Spec(
        [_Rule(requires_facts=[FactRequirement(fact="demo_fact", on_missing="retry")])]
    )
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert any("(R7)" in e and "on_missing" in e for e in errors)

    spec2 = _Spec(
        [_Rule(requires_facts=[FactRequirement(fact="demo_fact", on_conflict="ignore")])]
    )
    errors2 = validate_fact_contracts(spec2, predicates=_predicates(), reducers=_reducers())
    assert any("(R7)" in e and "on_conflict" in e for e in errors2)


def test_r8_value_type_disagrees_with_the_registry():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="demo_fact", value_type="usd")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert any("(R8)" in e for e in errors)


def test_r8_matching_value_type_is_not_refused():
    spec = _Spec([_Rule(requires_facts=[FactRequirement(fact="demo_fact", value_type="int")])])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers())
    assert not any("(R8)" in e for e in errors)


# ── R9/R10: contract binding ──────────────────────────────────────


def test_r9_decision_type_with_no_contract():
    spec = _Spec([_Rule(plane="control", decision_type="no_such_decision")])
    errors = validate_fact_contracts(spec, predicates=_predicates(), reducers=_reducers(), contracts={})
    assert any("(R9)" in e and "no_such_decision" in e for e in errors)


def test_r9_satisfied_when_the_contract_exists():
    contract = _Contract()
    spec = _Spec([_Rule(plane="control", decision_type="demo_decision")])
    errors = validate_fact_contracts(
        spec, predicates=_predicates(), reducers=_reducers(),
        contracts={"demo_decision": contract},
    )
    assert not any("(R9)" in e for e in errors)


def test_r10_rule_requires_a_fact_the_contract_excludes():
    contract = _Contract(excludes=("demo_fact",))
    spec = _Spec([
        _Rule(
            plane="control", decision_type="demo_decision",
            requires_facts=[FactRequirement(fact="demo_fact")],
        )
    ])
    errors = validate_fact_contracts(
        spec, predicates=_predicates(), reducers=_reducers(),
        contracts={"demo_decision": contract},
    )
    assert any("(R10)" in e for e in errors)


# ── R11: invariant on_missing/on_conflict must halt or escalate (F1) ─


def test_r11_invariant_that_classifies_is_refused():
    contract = _Contract(
        invariants=(FactRequirement(fact="workload_fact", on_missing="classify"),)
    )
    spec = _Spec([])  # R11 checks every LOADED contract, independent of any rule referencing it
    errors = validate_fact_contracts(
        spec, predicates=_predicates(), reducers=_reducers(),
        contracts={"demo_decision": contract},
    )
    assert any("(R11)" in e and "is not a constraint" in e for e in errors)


@pytest.mark.parametrize("handling", ["halt", "escalate"])
def test_r11_invariant_that_halts_or_escalates_is_not_refused(handling):
    contract = _Contract(
        invariants=(FactRequirement(fact="workload_fact", on_missing=handling),)
    )
    spec = _Spec([])
    errors = validate_fact_contracts(
        spec, predicates=_predicates(), reducers=_reducers(),
        contracts={"demo_decision": contract},
    )
    assert not any("(R11)" in e for e in errors)


def test_shipped_route_next_job_contract_never_fails_r11():
    # The route_next_job.yaml contract's own invariants (F1's fix, applied in I4).
    from agentic_dynamics.control.context_compiler import CONTRACTS_DIR, load_contract

    contract = load_contract("route_next_job", contracts_dir=CONTRACTS_DIR)
    spec = _Spec([])
    errors = validate_fact_contracts(
        spec, predicates=_predicates(), reducers=_reducers(),
        contracts={contract.decision_type: contract},
    )
    assert not any("(R11)" in e for e in errors)


# ── ON_MISSING / ON_CONFLICT vocabularies ─────────────────────────


def test_on_missing_and_on_conflict_vocabularies():
    assert {"halt", "escalate", "classify", "investigate"} == ON_MISSING
    assert {"halt", "escalate", "prefer_higher_authority", "classify"} == ON_CONFLICT


# ── The real gate: FACT_PREDICATES/REDUCERS/committed contracts ──


def test_real_gate_admits_the_route_next_job_control_rule():
    from agentic_dynamics.control.context_compiler import validate_spec_fact_contracts

    spec = ExperimentSpec(
        name="cap_i5_demo",
        question="does the real gate admit a well-formed route_next_job control rule?",
        version="0.1",
        workflow=Workflow(kind="agent_task", params={}),
        factors=[Factor(name="model", levels=["anthropic/claude-haiku-4-5"])],
        design="factorial",
        rules=[
            RuleSpec(
                name="route_next_job", plane="control", evidence_class="[H]",
                decision_type="route_next_job",
                requires_facts=[
                    {"fact": "job_accumulated_cost_usd", "scope": "self",
                     "max_age_seconds": 600, "min_authority": "MEASURED",
                     "on_missing": "classify"},
                    {"fact": "workflow_phases_remaining", "scope": "parent",
                     "max_age_seconds": 600, "min_authority": "DERIVED"},
                    {"fact": "phase_test_verified", "scope": "self",
                     "max_age_seconds": 3600, "min_authority": "MEASURED",
                     "on_missing": "classify"},
                ],
                produces=["route_decision"],
            ),
        ],
    )
    errors = validate_spec_fact_contracts(spec)
    assert errors == []


def test_real_gate_refuses_an_unproducible_predicate():
    from agentic_dynamics.control.context_compiler import validate_spec_fact_contracts

    spec = ExperimentSpec(
        name="cap_i5_demo_bad",
        question="does the real gate refuse a made-up predicate?",
        version="0.1",
        workflow=Workflow(kind="agent_task", params={}),
        factors=[Factor(name="model", levels=["anthropic/claude-haiku-4-5"])],
        design="factorial",
        rules=[
            RuleSpec(
                name="bogus_rule", plane="control", evidence_class="[H]",
                requires_facts=[{"fact": "deadline_slack"}],  # never declared (review §3d(iii))
            ),
        ],
    )
    errors = validate_spec_fact_contracts(spec)
    assert any("(R1)" in e and "deadline_slack" in e for e in errors)


def test_default_validate_spec_skips_the_i5_gate_when_no_registries_are_supplied():
    # experiment_spec.validate_spec (tier 1) cannot import control.facts/control.reducers — the
    # I5 gate is opt-in via explicit fact_predicates/fact_reducers, never on by default.
    spec = ExperimentSpec(
        name="cap_i5_demo_skip",
        question="an unproducible predicate is invisible without the real registries",
        version="0.1",
        workflow=Workflow(kind="agent_task", params={}),
        factors=[Factor(name="model", levels=["anthropic/claude-haiku-4-5"])],
        design="factorial",
        rules=[
            RuleSpec(
                name="bogus_rule", plane="control", evidence_class="[H]",
                requires_facts=[{"fact": "deadline_slack"}],
            ),
        ],
    )
    assert validate_spec(spec) == []


def test_committed_spec_corpus_gains_zero_new_refusals_from_the_i5_gate():
    """Design §9 I5's own acceptance criterion, restated: the I5 gate must not regress a single
    one of the ~88 committed specs, none of which declare requires_facts/decision_type yet."""
    from agentic_dynamics.control.context_compiler import validate_spec_fact_contracts
    from agentic_dynamics.experiment.experiment_spec import committed_spec_paths

    # A4 fix (authoring_product_aio, 2026-09-03): use the exclusion-aware discovery —
    # committed_spec_paths covers both definitions + workflows AND skips the workflow-v1
    # namespace (workflows/examples/*.yaml, workflows/schema/), which the raw rglob
    # below would feed to load_spec and fail on (workflow-v1 docs are NOT ExperimentSpecs).
    paths = sorted(committed_spec_paths(REPO_ROOT))
    assert len(paths) >= 63
    for path in paths:
        spec = load_spec(path)
        baseline = validate_spec(spec)
        with_gate = validate_spec_fact_contracts(spec)
        assert with_gate == baseline, f"{path}: I5 gate introduced new refusals: {with_gate}"
