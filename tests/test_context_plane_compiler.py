"""Tests for CAP I4 — the read-only Context Compiler (``control/context_compiler.py``).

Covers contract loading (the ``route_next_job/v1`` YAML), scope addressing (``parse_scope_path``,
``resolve_requirement_scope``'s job/workflow-sibling reconciliation, ``scope_visible``'s
ancestor-prefix generalization), requirement classification (satisfied / unknown / stale /
conflicted), halt-vs-degrade per ``on_missing``/``on_conflict``, ``snapshot_id`` determinism
(content-addressed, ``compiled_at``-independent), and the ``InMemoryFactStore`` fixture.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from agentic_dynamics.control.context_compiler import (
    CONTRACTS_DIR,
    ContextRequest,
    InMemoryFactStore,
    compile_context,
    compute_snapshot_id,
    load_contract,
    make_snapshotting_router,
    parse_scope_path,
    resolve_requirement_scope,
    scope_visible,
)
from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    CanonicalFact,
    recompute_inputs_digest,
)
from agentic_dynamics.core.contracts import FactRequirement
from agentic_dynamics.knowledge.knowledge import Authority

pytestmark = pytest.mark.fast

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
    subject_type: str = "",
    subject_id: str = "",
    fact_id: str = "fact_0001",
    reducer_version: str = "workflow_facts/v1",
    epistemic_status: str = "derived",
    observed_at: str = NOW,
    expires_at: str | None = None,
    lifecycle_state: str = "current",
    evidence_ids: tuple[str, ...] = (),
) -> CanonicalFact:
    spec = FACT_PREDICATES[predicate]
    authority, evidence_class = EPISTEMIC_MAP[epistemic_status]
    fact = CanonicalFact(
        fact_entity_id=f"entity_{predicate}_{scope_id}",
        fact_id=fact_id,
        subject_type=subject_type or spec.subject_type,
        subject_id=subject_id or scope_id,
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
        observed_at=observed_at,
        valid_from=observed_at,
        valid_to=None,
        expires_at=expires_at,
        reducer=reducer_version.split("/")[0],
        reducer_version=reducer_version,
        evidence_ids=evidence_ids,
        inputs_digest="",
        supersedes=None,
        source_revision="abc123",
        repository_id=REPO,
        lifecycle_state=lifecycle_state,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


# ── Contract loading ─────────────────────────────────────────────


def test_route_next_job_contract_loads_and_matches_the_design():
    contract = load_contract("route_next_job", contracts_dir=CONTRACTS_DIR)
    assert contract.decision_type == "route_next_job"
    assert contract.contract_version == "route_next_job/v1"
    assert contract.decision_scope == "job"
    assert set(contract.allowed_actions) == {"route", "continue"}
    assert contract.max_snapshot_age_seconds == 300
    assert {req.fact for req in contract.requires_facts} == {
        "job_accumulated_cost_usd",
        "workflow_phases_remaining",
        "phase_test_verified",
    }
    assert {req.fact for req in contract.invariants} == {"allowed_models", "max_spend_usd"}


def test_invariants_never_use_on_missing_classify():
    # F1 (implementation_notes.md §2): an invariant with on_missing=classify silently disables a
    # safety constraint. The shipped contract must not regress this.
    contract = load_contract("route_next_job", contracts_dir=CONTRACTS_DIR)
    for inv in contract.invariants:
        assert inv.on_missing in ("halt", "escalate"), inv


def test_load_contract_refuses_unknown_decision_type():
    with pytest.raises(ValueError, match="no context contract"):
        load_contract("no_such_decision_type", contracts_dir=CONTRACTS_DIR)


# ── Scope addressing (design §10) ────────────────────────────────


def test_parse_scope_path_splits_into_ordered_segments():
    assert parse_scope_path(JOB_SCOPE) == [
        ("org", REPO),
        ("workload", WORKLOAD),
        ("job", CELL),
    ]


def test_resolve_self_is_the_decision_path_verbatim():
    assert resolve_requirement_scope("self", JOB_SCOPE) == JOB_SCOPE


def test_resolve_parent_of_job_is_the_workflow_view_of_the_same_cell():
    # The reducers' own convention (job_facts.py / workflow_facts.py): job and workflow are
    # SIBLING labels over the SAME cell id, not a nested pair — "parent" of a job-scoped
    # decision is the workflow view of that SAME cell (design §10.3), not a dropped segment.
    assert resolve_requirement_scope("parent", JOB_SCOPE) == WORKFLOW_SCOPE


def test_resolve_parent_of_attempt_drops_the_run_segment_to_its_job():
    attempt_scope = f"{JOB_SCOPE}/attempt:phase1/run:deadbeef"
    assert resolve_requirement_scope("parent", attempt_scope) == JOB_SCOPE


def test_resolve_parent_of_workflow_is_the_workload():
    assert resolve_requirement_scope("parent", WORKFLOW_SCOPE) == WORKLOAD_SCOPE


def test_resolve_parent_at_the_root_is_none():
    assert resolve_requirement_scope("parent", f"org:{REPO}") is None


def test_resolve_explicit_scope_type_truncates_at_that_segment():
    assert resolve_requirement_scope("workload", JOB_SCOPE) == WORKLOAD_SCOPE


def test_resolve_explicit_scope_type_not_reached_is_none():
    assert resolve_requirement_scope("attempt", WORKLOAD_SCOPE) is None


def test_scope_visible_equal_scope_is_always_visible():
    assert scope_visible(JOB_SCOPE, JOB_SCOPE) is True


def test_scope_visible_ancestor_requires_inheritable_or_policy():
    allowed_models = FACT_PREDICATES["allowed_models"]  # inheritable=True
    current_commit = FACT_PREDICATES["current_commit"]  # inheritable=False
    assert scope_visible(JOB_SCOPE, WORKLOAD_SCOPE, allowed_models) is True
    assert scope_visible(JOB_SCOPE, WORKLOAD_SCOPE, current_commit) is False
    assert scope_visible(JOB_SCOPE, WORKLOAD_SCOPE, None) is False


def test_scope_visible_forbids_descendant_peek():
    assert scope_visible(WORKLOAD_SCOPE, JOB_SCOPE, FACT_PREDICATES["allowed_models"]) is False


def test_scope_visible_forbids_lateral_reads():
    other_job = f"org:{REPO}/workload:{WORKLOAD}/job:some_other_cell"
    assert scope_visible(JOB_SCOPE, other_job, FACT_PREDICATES["current_commit"]) is False


def test_scope_visible_empty_scope_is_never_a_wildcard():
    assert scope_visible("", JOB_SCOPE) is False
    assert scope_visible(JOB_SCOPE, "") is False


# ── compile_context: satisfied / unknown / stale / conflicted ────


def _base_store() -> InMemoryFactStore:
    return InMemoryFactStore(
        facts=(
            _fact(
                predicate="job_accumulated_cost_usd",
                value="1.25",
                scope_type="job",
                scope_id=CELL,
                scope_path=JOB_SCOPE,
                reducer_version="job_facts/v1",
                epistemic_status="observed",
                fact_id="fact_cost",
            ),
            _fact(
                predicate="workflow_phases_remaining",
                value="2",
                scope_type="workflow",
                scope_id=CELL,
                scope_path=WORKFLOW_SCOPE,
                reducer_version="workflow_facts/v1",
                fact_id="fact_remaining",
            ),
            _fact(
                predicate="phase_test_verified",
                value="true",
                scope_type="attempt",
                scope_id=f"{CELL}:phase1:runhash",
                scope_path=f"{JOB_SCOPE}/attempt:phase1/run:runhash",
                reducer_version="attempt_facts/v1",
                epistemic_status="verified",
                fact_id="fact_test_verified",
            ),
            _fact(
                predicate="allowed_models",
                value="anthropic/claude-haiku-4-5,anthropic/claude-sonnet-5",
                scope_type="workload",
                scope_id=WORKLOAD,
                scope_path=WORKLOAD_SCOPE,
                reducer_version="policy_facts/v1",
                epistemic_status="declared",
                fact_id="fact_allowed_models",
            ),
            _fact(
                predicate="max_spend_usd",
                value="50.0",
                scope_type="workload",
                scope_id=WORKLOAD,
                scope_path=WORKLOAD_SCOPE,
                reducer_version="policy_facts/v1",
                epistemic_status="declared",
                fact_id="fact_max_spend",
            ),
        )
    )


def _request(scope_path: str = JOB_SCOPE) -> ContextRequest:
    return ContextRequest(
        decision_type="route_next_job",
        scope_type="job",
        scope_id=CELL,
        scope_path=scope_path,
        repository_id=REPO,
    )


def test_compile_context_admits_a_fully_satisfied_snapshot():
    ctx = compile_context(_request(), store=_base_store(), now=NOW)
    assert ctx.admissible is True
    assert ctx.refusal == ""
    assert ctx.unknowns == ()
    assert ctx.conflicts == ()
    assert ctx.stale == ()
    # attempt-scoped facts (phase_test_verified) fall under the `job` bucket — the design's
    # §6.3 ControlContext has no separate attempt bucket.
    assert {f.predicate for f in ctx.job} == {"job_accumulated_cost_usd", "phase_test_verified"}
    assert {f.predicate for f in ctx.workflow} == {"workflow_phases_remaining"}
    assert {f.predicate for f in ctx.invariants} == {"allowed_models", "max_spend_usd"}
    assert "fact_cost" in ctx.evidence_ids
    assert "fact_allowed_models" in ctx.evidence_ids


def test_compile_context_refuses_a_scope_mismatch():
    request = ContextRequest(
        decision_type="route_next_job",
        scope_type="workflow",  # contract is decision_scope: job
        scope_id=CELL,
        scope_path=WORKFLOW_SCOPE,
        repository_id=REPO,
    )
    with pytest.raises(ValueError, match="scoped at"):
        compile_context(request, store=_base_store(), now=NOW)


def test_missing_required_fact_halts_admissibility():
    store = InMemoryFactStore(
        facts=tuple(f for f in _base_store().facts if f.predicate != "workflow_phases_remaining")
    )
    ctx = compile_context(_request(), store=store, now=NOW)
    assert ctx.admissible is False
    assert any(u.predicate == "workflow_phases_remaining" for u in ctx.unknowns)
    assert any(u.reason == "no_fact" for u in ctx.unknowns)
    assert "workflow_phases_remaining" in ctx.refusal


def test_missing_optional_fact_classifies_without_blocking_admissibility():
    # job_accumulated_cost_usd: on_missing=classify — a first phase legitimately has none.
    store = InMemoryFactStore(
        facts=tuple(f for f in _base_store().facts if f.predicate != "job_accumulated_cost_usd")
    )
    ctx = compile_context(_request(), store=store, now=NOW)
    assert ctx.admissible is True
    assert any(u.predicate == "job_accumulated_cost_usd" for u in ctx.unknowns)


def test_missing_invariant_halts_even_though_it_is_not_a_requires_facts_entry():
    store = InMemoryFactStore(
        facts=tuple(f for f in _base_store().facts if f.predicate != "allowed_models")
    )
    ctx = compile_context(_request(), store=store, now=NOW)
    assert ctx.admissible is False
    assert any(u.predicate == "allowed_models" for u in ctx.unknowns)


def test_stale_by_requirement_max_age_seconds():
    store = _base_store()
    stale_cost = replace(
        [f for f in store.facts if f.predicate == "job_accumulated_cost_usd"][0],
        observed_at="2020-01-01T00:00:00+00:00",
        valid_from="2020-01-01T00:00:00+00:00",
    )
    other = tuple(f for f in store.facts if f.predicate != "job_accumulated_cost_usd")
    ctx = compile_context(
        _request(), store=InMemoryFactStore(facts=other + (stale_cost,)), now=NOW
    )
    assert any(s.fact.predicate == "job_accumulated_cost_usd" for s in ctx.stale)
    assert ctx.admissible is True  # on_missing=classify for this requirement


def test_stale_by_predicate_expires_at_cascade():
    store = _base_store()
    expired = replace(
        [f for f in store.facts if f.predicate == "workflow_phases_remaining"][0],
        expires_at="2020-01-01T00:00:00+00:00",
    )
    other = tuple(f for f in store.facts if f.predicate != "workflow_phases_remaining")
    ctx = compile_context(
        _request(), store=InMemoryFactStore(facts=other + (expired,)), now=NOW
    )
    assert any(s.fact.predicate == "workflow_phases_remaining" for s in ctx.stale)
    assert ctx.admissible is False  # on_missing=halt for this requirement


def test_conflicted_two_current_facts_same_entity_disagree():
    store = _base_store()
    remaining = [f for f in store.facts if f.predicate == "workflow_phases_remaining"][0]
    conflicting = replace(remaining, fact_id="fact_remaining_conflict", value="9")
    other = tuple(f for f in store.facts if f.predicate != "workflow_phases_remaining")
    ctx = compile_context(
        _request(), store=InMemoryFactStore(facts=other + (remaining, conflicting)), now=NOW
    )
    assert any(c.predicate == "workflow_phases_remaining" for c in ctx.conflicts)
    assert ctx.admissible is False  # on_conflict=halt for this requirement
    assert len(ctx.conflicts[0].candidates) == 2


def test_below_min_authority_is_unknown_not_satisfied():
    store = _base_store()
    advisory_cost = replace(
        [f for f in store.facts if f.predicate == "job_accumulated_cost_usd"][0],
        epistemic_status="advisory",
        authority=Authority.ADVISORY,
        evidence_class="[H]",
    )
    other = tuple(f for f in store.facts if f.predicate != "job_accumulated_cost_usd")
    ctx = compile_context(
        _request(), store=InMemoryFactStore(facts=other + (advisory_cost,)), now=NOW
    )
    assert any(
        u.predicate == "job_accumulated_cost_usd" and u.reason == "below_min_authority"
        for u in ctx.unknowns
    )
    assert any(f.predicate == "job_accumulated_cost_usd" for f in ctx.advisory)


def test_broken_derivation_chain_demotes_to_unknown():
    store = _base_store()
    tampered = replace(
        [f for f in store.facts if f.predicate == "job_accumulated_cost_usd"][0],
        inputs_digest="deadbeef",
    )
    other = tuple(f for f in store.facts if f.predicate != "job_accumulated_cost_usd")
    ctx = compile_context(
        _request(), store=InMemoryFactStore(facts=other + (tampered,)), now=NOW
    )
    assert any(
        u.predicate == "job_accumulated_cost_usd" and u.reason == "broken_chain"
        for u in ctx.unknowns
    )


# ── snapshot_id (design §6.4) ─────────────────────────────────────


def test_snapshot_id_is_stable_across_recompilation_of_identical_state():
    # A few seconds later — well inside every requirement's max_age_seconds/predicate TTL, so
    # nothing crosses a staleness boundary and only `compiled_at` differs between the two
    # compiles.
    a = compile_context(_request(), store=_base_store(), now=NOW)
    b = compile_context(_request(), store=_base_store(), now="2026-08-23T00:00:10+00:00")
    assert a.snapshot_id == b.snapshot_id  # compiled_at excluded — content-addressed only


def test_snapshot_id_changes_when_the_fact_set_changes():
    a = compile_context(_request(), store=_base_store(), now=NOW)
    store = _base_store()
    changed = replace(
        [f for f in store.facts if f.predicate == "job_accumulated_cost_usd"][0],
        fact_id="fact_cost_v2",
        value="9.99",
    )
    other = tuple(f for f in store.facts if f.predicate != "job_accumulated_cost_usd")
    b = compile_context(_request(), store=InMemoryFactStore(facts=other + (changed,)), now=NOW)
    assert a.snapshot_id != b.snapshot_id


def test_compute_snapshot_id_is_a_pure_function_of_its_inputs():
    a = compute_snapshot_id(
        contract_version="v1", decision_type="d", scope_path="s",
        fact_ids=["b", "a"], unknowns=(), conflicts=(), stale=(),
    )
    b = compute_snapshot_id(
        contract_version="v1", decision_type="d", scope_path="s",
        fact_ids=["a", "b"], unknowns=(), conflicts=(), stale=(),
    )
    assert a == b  # sorted fact_ids — order-independent


# ── FactRequirement normalization (core.contracts, shared with I5) ─


def test_normalize_requirement_from_dict_in_the_contract():
    contract = load_contract("route_next_job", contracts_dir=CONTRACTS_DIR)
    req = next(r for r in contract.requires_facts if r.fact == "job_accumulated_cost_usd")
    assert isinstance(req, FactRequirement)
    assert req.on_missing == "classify"
    assert req.min_authority == "MEASURED"
    assert req.max_age_seconds == 600


# ── make_snapshotting_router (the composition-root seam) ──────────


def test_snapshotting_router_never_changes_the_routing_decision(monkeypatch):
    # route_step itself is untouched (design §8.4): the wrapper must return EXACTLY what
    # route_step chose, and never raise, even when snapshot compilation/recording fails
    # end to end — recording is read-only measurement, never a gate on the phase.
    import agentic_dynamics.control.context_compiler as cc
    from agentic_dynamics.control import step_routing
    from agentic_dynamics.runtime.routing import RouteState, RoutingPreferences

    monkeypatch.setattr(step_routing, "route_step", lambda *a, **k: "anthropic/claude-haiku-4-5")

    def _boom(*a, **k):
        raise RuntimeError("simulated Redis outage")

    monkeypatch.setattr(cc, "compile_context", _boom)
    router = make_snapshotting_router(workload="demo", cell_id=CELL, repository_id=REPO)
    result = router(
        {}, RouteState(pool=["anthropic/claude-haiku-4-5"]), RoutingPreferences(), signals={}
    )
    assert result == "anthropic/claude-haiku-4-5"


def test_snapshotting_router_recording_disabled_still_routes():
    from agentic_dynamics.runtime.routing import RouteState, RoutingPreferences

    router = make_snapshotting_router(
        workload="demo", cell_id=CELL, repository_id=REPO, record=False
    )
    result = router(
        {"model": "anthropic/claude-sonnet-5"}, RouteState(pool=["anthropic/claude-sonnet-5"]),
        RoutingPreferences(),
    )
    assert result == "anthropic/claude-sonnet-5"
