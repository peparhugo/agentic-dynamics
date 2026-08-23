"""Tests for CAP I6 — the shadow controller + validator (``control/{rules,validator,decisions}.py``).

Covers ``route_next_job_v1`` (the fact-based rule's admissible/inadmissible/no-phases-remaining
branches), ``AUTOMATABLE_ACTIONS`` immutability, each C1-C10 refusal in ``validate_decision``
(one mutation per test, everything else held valid), the F2 (empty ``facts_used``) and F3
(``decision_calibration``) resolutions, and the shadow-recording hook end to end (never changes
the routed model; records without arming actuation).
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agentic_dynamics.control.context_compiler import (
    CONTRACTS_DIR,
    ContextRequest,
    InMemoryFactStore,
    compile_context,
    load_contract,
)
from agentic_dynamics.control.decisions import (
    AUTOMATABLE_ACTIONS,
    PROPOSABLE_ACTIONS,
    ControlDecision,
)
from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    CanonicalFact,
    recompute_inputs_digest,
)
from agentic_dynamics.control.rules import (
    decision_payload,
    make_shadow_router,
    record_shadow_decision,
    route_next_job_v1,
)
from agentic_dynamics.control.validator import ValidationResult, validate_decision
from agentic_dynamics.experiment.compile_experiment import decision_calibration
from agentic_dynamics.knowledge.knowledge import Authority

NOW = "2026-08-23T00:00:00+00:00"
REPO = "agentic-dynamics"
WORKLOAD = "demo_spec"
CELL = "wf_demo_spec_anthropic_claude_haiku"
JOB_SCOPE = f"org:{REPO}/workload:{WORKLOAD}/job:{CELL}"
WORKFLOW_SCOPE = f"org:{REPO}/workload:{WORKLOAD}/workflow:{CELL}"
WORKLOAD_SCOPE = f"org:{REPO}/workload:{WORKLOAD}"


def _fact(
    *,
    predicate: str,
    value: str,
    scope_type: str,
    scope_id: str,
    scope_path: str,
    fact_id: str,
    reducer_version: str = "workflow_facts/v1",
    epistemic_status: str = "derived",
) -> CanonicalFact:
    spec = FACT_PREDICATES[predicate]
    authority, evidence_class = EPISTEMIC_MAP[epistemic_status]
    fact = CanonicalFact(
        fact_entity_id=f"entity_{predicate}_{scope_id}",
        fact_id=fact_id,
        subject_type=spec.subject_type,
        subject_id=scope_id,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type=scope_type,
        scope_id=scope_id,
        scope_path=scope_path,
        abstraction_level=spec.abstraction_level,
        epistemic_status=epistemic_status,
        authority=authority,
        evidence_class=evidence_class,
        observed_at=NOW,
        valid_from=NOW,
        valid_to=None,
        expires_at=None,
        reducer=reducer_version.split("/")[0],
        reducer_version=reducer_version,
        evidence_ids=(),
        inputs_digest="",
        supersedes=None,
        source_revision="abc123",
        repository_id=REPO,
        lifecycle_state="current",
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def _base_store(remaining: str = "2", cost: str = "1.25") -> InMemoryFactStore:
    return InMemoryFactStore(
        facts=(
            _fact(
                predicate="job_accumulated_cost_usd", value=cost, scope_type="job",
                scope_id=CELL, scope_path=JOB_SCOPE, reducer_version="job_facts/v1",
                epistemic_status="observed", fact_id="fact_cost",
            ),
            _fact(
                predicate="workflow_phases_remaining", value=remaining, scope_type="workflow",
                scope_id=CELL, scope_path=WORKFLOW_SCOPE, reducer_version="workflow_facts/v1",
                fact_id="fact_remaining",
            ),
            _fact(
                predicate="allowed_models",
                value="anthropic/claude-sonnet-5,anthropic/claude-haiku-4-5",
                scope_type="workload", scope_id=WORKLOAD, scope_path=WORKLOAD_SCOPE,
                reducer_version="policy_facts/v1", epistemic_status="declared",
                fact_id="fact_allowed_models",
            ),
            _fact(
                predicate="max_spend_usd", value="50.0", scope_type="workload",
                scope_id=WORKLOAD, scope_path=WORKLOAD_SCOPE, reducer_version="policy_facts/v1",
                epistemic_status="declared", fact_id="fact_max_spend",
            ),
        )
    )


def _request() -> ContextRequest:
    return ContextRequest(
        decision_type="route_next_job", scope_type="job", scope_id=CELL, scope_path=JOB_SCOPE,
        repository_id=REPO,
    )


def _admissible_ctx(**store_kwargs):
    return compile_context(_request(), store=_base_store(**store_kwargs), now=NOW)


CONTRACT = load_contract("route_next_job", contracts_dir=CONTRACTS_DIR)


# ── AUTOMATABLE_ACTIONS (design §8.3, "CODE, never config") ──────


def test_automatable_actions_is_exactly_continue_and_route():
    assert frozenset({"continue", "route"}) == AUTOMATABLE_ACTIONS
    assert AUTOMATABLE_ACTIONS < PROPOSABLE_ACTIONS  # a strict, documented subset


def test_automatable_actions_is_frozen():
    with pytest.raises(AttributeError):
        AUTOMATABLE_ACTIONS.add("stop")  # type: ignore[attr-defined]


# ── route_next_job_v1 (the fact-based rule) ───────────────────────


def test_route_next_job_v1_routes_when_phases_remain():
    ctx = _admissible_ctx()
    decision = route_next_job_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "route"
    assert decision.parameters["model"] == "anthropic/claude-haiku-4-5"  # lexicographically first
    assert decision.facts_used  # F2: non-empty for any action other than continue
    assert {e.predicate for e in decision.expected_effect} == {
        "workflow_phases_remaining", "job_accumulated_cost_usd",
    }
    assert decision.snapshot_id == ctx.snapshot_id
    assert decision.decision_type == ctx.decision_type


def test_route_next_job_v1_continues_when_no_phases_remain():
    ctx = _admissible_ctx(remaining="0")
    decision = route_next_job_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "continue"


def test_route_next_job_v1_continues_when_the_snapshot_is_inadmissible():
    store = InMemoryFactStore(
        facts=tuple(f for f in _base_store().facts if f.predicate != "allowed_models")
    )
    ctx = compile_context(_request(), store=store, now=NOW)
    assert ctx.admissible is False
    decision = route_next_job_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "continue"
    assert decision.facts_used == ()
    assert "inadmissible" in decision.rationale


def test_route_next_job_v1_is_deterministic():
    ctx = _admissible_ctx()
    a = route_next_job_v1(ctx, target_id=CELL, proposed_at=NOW)
    b = route_next_job_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert a == b


# ── validate_decision: each C-code refusal, one mutation at a time ─


def _valid_decision(ctx) -> ControlDecision:
    return route_next_job_v1(ctx, target_id=CELL, proposed_at=NOW)


def test_c1_snapshot_binding_wrong_snapshot_id():
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), snapshot_id="wrong")
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result == ValidationResult(admitted=False, check="C1", reason=result.reason)


def test_c2_snapshot_not_admissible():
    store = InMemoryFactStore(
        facts=tuple(f for f in _base_store().facts if f.predicate != "allowed_models")
    )
    ctx = compile_context(_request(), store=store, now=NOW)
    decision = ControlDecision(
        decision_id="d1", snapshot_id=ctx.snapshot_id, decision_type=ctx.decision_type,
        contract_version=ctx.contract_version, action="continue", target_type="job",
        target_id=CELL, proposed_by="policy_rule:route_next_job", proposed_at=NOW,
    )
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C2"


def test_c3_action_outside_allowed_actions():
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), action="stop")
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C3"


def test_c4_target_not_within_scope_path():
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), target_id="some_other_cell")
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C4"


def test_c5_cites_a_fact_not_in_the_snapshot():
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), facts_used=("not_a_real_fact_id",))
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C5"


def test_c5_cites_an_advisory_fact():
    store = _base_store()
    advisory_cost = replace(
        [f for f in store.facts if f.predicate == "job_accumulated_cost_usd"][0],
        epistemic_status="advisory", authority=Authority.ADVISORY, evidence_class="[H]",
    )
    other = tuple(f for f in store.facts if f.predicate != "job_accumulated_cost_usd")
    ctx = compile_context(
        _request(), store=InMemoryFactStore(facts=other + (advisory_cost,)), now=NOW
    )
    decision = replace(_valid_decision(ctx), facts_used=("fact_cost",))
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C5"


def test_c5_f2_empty_facts_used_for_a_non_continue_action():
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), facts_used=())
    assert decision.action == "route"
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C5"
    assert "F2" in result.reason


def test_c5_continue_with_empty_facts_used_is_fine():
    # F2 requires non-empty facts_used only for actions OTHER than continue; continue's own
    # citation (if any) is exempt.
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), action="continue", facts_used=())
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check != "C5"


def test_c6_broken_derivation_chain_with_a_store():
    store = _base_store()
    ctx = compile_context(_request(), store=store, now=NOW)
    decision = _valid_decision(ctx)
    tampered_cost = replace(
        [f for f in store.facts if f.predicate == "job_accumulated_cost_usd"][0],
        inputs_digest="deadbeef",
    )
    other = tuple(f for f in store.facts if f.predicate != "job_accumulated_cost_usd")
    tampered_store = InMemoryFactStore(facts=other + (tampered_cost,))
    result = validate_decision(
        decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW,
        store=tampered_store,
    )
    assert result.check == "C6"


def test_c6_without_a_store_degrades_to_a_pass():
    ctx = _admissible_ctx()
    decision = _valid_decision(ctx)
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check != "C6"


def test_c7_snapshot_too_old():
    ctx = _admissible_ctx()
    decision = _valid_decision(ctx)
    far_future = "2030-01-01T00:00:00+00:00"  # >> contract.max_snapshot_age_seconds (300s)
    result = validate_decision(
        decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=far_future
    )
    assert result.check == "C7"


def test_c7_precondition_fails_against_a_fresh_snapshot():
    ctx = _admissible_ctx()
    decision = _valid_decision(ctx)
    fresh_ctx = _admissible_ctx(remaining="0")  # phases finished between compile and apply
    result = validate_decision(
        decision, snapshot=ctx, fresh_snapshot=fresh_ctx, contract=CONTRACT, now=NOW
    )
    assert result.check == "C7"


def test_c8_model_not_in_allowed_models():
    ctx = _admissible_ctx()
    decision = replace(
        _valid_decision(ctx), parameters={"model": "openai/gpt-5.6-sol"}
    )
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C8"


def test_c8_cost_already_exceeds_max_spend():
    ctx = _admissible_ctx(cost="9999.0")
    decision = _valid_decision(ctx)
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C8"


def test_c9_non_automatable_action_from_an_automated_proposer():
    ctx = _admissible_ctx()
    decision = replace(
        _valid_decision(ctx), action="retry", proposed_by="policy_rule:route_next_job"
    )
    # retry is PROPOSABLE but not AUTOMATABLE — an automated proposer may not have it applied.
    # Route around C3 by widening the contract's allowed_actions for this one check.
    contract = replace(CONTRACT, allowed_actions=(*CONTRACT.allowed_actions, "retry"))
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=contract, now=NOW)
    assert result.check == "C9"


def test_c9_non_automatable_action_from_a_human_operator_passes_c9():
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), action="retry", proposed_by="operator:alice")
    contract = replace(CONTRACT, allowed_actions=(*CONTRACT.allowed_actions, "retry"))
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=contract, now=NOW)
    assert result.check != "C9"


def test_c10_missing_decision_id():
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), decision_id="")
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C10"


def test_fully_valid_decision_is_admitted():
    ctx = _admissible_ctx()
    decision = _valid_decision(ctx)
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result == ValidationResult(admitted=True, check="", reason="")


def test_checks_are_ordered_c1_before_c3():
    # A decision that fails BOTH C1 (wrong snapshot_id) and C3 (bad action) must report C1 —
    # first failure short-circuits (design §8.3).
    ctx = _admissible_ctx()
    decision = replace(_valid_decision(ctx), snapshot_id="wrong", action="bogus_action")
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.check == "C1"


# ── decision_payload / record_shadow_decision (never arms actuation) ─


def test_decision_payload_is_json_safe():
    ctx = _admissible_ctx()
    decision = _valid_decision(ctx)
    payload = decision_payload(decision)
    json.dumps(payload)  # must not raise
    assert payload["action"] == "route"
    assert payload["facts_used"] == list(decision.facts_used)


def test_record_shadow_decision_never_publishes_to_the_stream(tmp_path, monkeypatch):
    # The whole point of §8.6's "never arms actuation": writing the artifact must succeed even
    # when the knowledge stream / Redis is entirely unavailable, because it is never contacted.
    ctx = _admissible_ctx()
    decision = _valid_decision(ctx)
    record = record_shadow_decision(
        decision, repository_id=REPO, causes="deadbeef" * 4, artifact_dir=tmp_path
    )
    assert record is not None
    assert record.source_type == "actuation"
    artifact_path = tmp_path / f"{record.knowledge_id}.json"
    assert artifact_path.is_file()


def test_record_shadow_decision_requires_causes():
    ctx = _admissible_ctx()
    decision = _valid_decision(ctx)
    # derive_actuation_record raises ValueError on empty causes — record_shadow_decision must
    # swallow it (best-effort, never blocks) and return None.
    assert record_shadow_decision(decision, repository_id=REPO, causes="") is None


# ── decision_calibration (F3) ──────────────────────────────────────


def test_decision_calibration_zero_regret_on_full_agreement():
    decisions = [
        {"action": "route", "baseline_action": "route", "model": "m1", "baseline_model": "m1"},
        {"action": "continue", "baseline_action": "continue"},
    ]
    result = decision_calibration(decisions)
    assert result.rule == "decision_calibration"
    assert result.produces["decision_regret"] == 0.0
    assert result.produces["n_decisions"] == 2


def test_decision_calibration_scores_model_divergence():
    decisions = [
        {"action": "route", "baseline_action": "route", "model": "m1", "baseline_model": "m2"},
        {"action": "route", "baseline_action": "route", "model": "m1", "baseline_model": "m1"},
    ]
    result = decision_calibration(decisions)
    assert result.produces["decision_regret"] == 0.5


def test_decision_calibration_unmeasured_when_no_decisions():
    result = decision_calibration([])
    assert result.metric != result.metric  # NaN != NaN — the explicit "unmeasured" convention
    assert result.uncertainty == 1.0


# ── make_shadow_router: end to end, never changes the route ───────


def test_shadow_router_never_changes_the_routing_decision(monkeypatch):
    import agentic_dynamics.control.rules as rules_mod
    from agentic_dynamics.control import step_routing

    monkeypatch.setattr(step_routing, "route_step", lambda *a, **k: "anthropic/claude-haiku-4-5")

    def _boom(*a, **k):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(rules_mod, "compile_context", _boom)
    router = make_shadow_router(workload=WORKLOAD, cell_id=CELL, repository_id=REPO)
    from agentic_dynamics.runtime.routing import RouteState, RoutingPreferences

    result = router(
        {}, RouteState(pool=["anthropic/claude-haiku-4-5"]), RoutingPreferences(), signals={}
    )
    assert result == "anthropic/claude-haiku-4-5"


def test_shadow_router_recording_disabled_still_routes():
    from agentic_dynamics.runtime.routing import RouteState, RoutingPreferences

    router = make_shadow_router(
        workload=WORKLOAD, cell_id=CELL, repository_id=REPO, record=False
    )
    result = router(
        {"model": "anthropic/claude-sonnet-5"}, RouteState(pool=["anthropic/claude-sonnet-5"]),
        RoutingPreferences(),
    )
    assert result == "anthropic/claude-sonnet-5"
