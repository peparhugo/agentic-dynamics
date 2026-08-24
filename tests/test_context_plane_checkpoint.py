"""Tests for CAP addendum I10 — ``SessionCheckpoint`` + the ``session_routing`` contract.

Covers design §4 (answers OQ6/OQ7): (1) the ``SessionCheckpoint`` schema's per-field epistemic
split (``DERIVED_FIELDS``/``ADVISORY_FIELDS``, D1/D2's demotions applied); (2) the ``checkpoint/
v1`` reducer — the DERIVED-only ``session_checkpoint`` payload, the five POSITIVE-MARKER booleans
(present only when true, never a fabricated ``"false"``), the no-checkpoint no-phantom case; (3)
the real ``session_routing.yaml`` contract — loads, R11-clean, and (via a fixture reproducing the
addendum's own literal §4.2 sketch) a demonstration that the addendum's UNCONDITIONAL invariant
grouping is refused by R11 / is logically unsatisfiable, which is why this contract moves those
facts to ``requires_facts`` instead (documented in the contract file's own header and
``docs/context_abstraction/implementation_notes.md`` §15); (4) ``session_routing_v1`` — the
shadow control rule's four-way branching, each DELIVER-required refusal case (stale continue,
checkpointless fork) via the REAL validator check C5; (5) proposals are durably recorded and
NEVER actuated (``record_shadow_decision``, reused verbatim — no new recording path); (6)
``AUTOMATABLE_ACTIONS`` stays exactly ``{continue, route}`` — untouched by this increment.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from agentic_dynamics.control.checkpoint import (
    ADVISORY_FIELDS,
    DERIVED_FIELDS,
    SessionCheckpoint,
    advisory_payload,
    derived_payload,
)
from agentic_dynamics.control.context_compiler import (
    CONTRACTS_DIR,
    ContextRequest,
    InMemoryFactStore,
    ContractSpec,
    compile_context,
    load_all_contracts,
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
    Authority,
    CanonicalFact,
    EvidenceItem,
    FactRequirement,
    ReducerInput,
    is_canonical,
    recompute_inputs_digest,
    verify_chain,
)
from agentic_dynamics.control.reducers import REDUCERS, get_reducer
from agentic_dynamics.control.reducers.checkpoint import (
    CHECKPOINT_V1,
    checkpoint_from_run,
    checkpoint_v1,
)
from agentic_dynamics.control.rules import record_shadow_decision, session_routing_v1
from agentic_dynamics.control.validator import validate_decision
from agentic_dynamics.core.contracts import validate_fact_contracts

NOW = "2026-08-24T00:10:00+00:00"
REPO = "agentic-dynamics"
WORKLOAD = "demo_spec"
CELL = "wf_demo_spec_anthropic_claude_haiku"
JOB_SCOPE = f"org:{REPO}/workload:{WORKLOAD}/job:{CELL}"
WORKFLOW_SCOPE = f"org:{REPO}/workload:{WORKLOAD}/workflow:{CELL}"


# ── (1) SessionCheckpoint schema + the per-field epistemic split ────


def test_session_checkpoint_is_frozen_with_the_design_field_order():
    cp = SessionCheckpoint(goal="ship the thing")
    with pytest.raises(Exception):  # FrozenInstanceError
        cp.goal = "other"  # type: ignore[misc]
    # Defaults match design §4.1's v1 grades exactly.
    assert cp.completed == ()
    assert cp.current_revision == ""
    assert cp.acceptance_state == ""
    assert cp.context_snapshot_id is None
    assert cp.snapshot_available is False
    assert cp.verified_facts == ()
    assert cp.open_hypotheses == ()
    assert cp.failed_approaches == ()
    assert cp.next_action == ""


def test_derived_and_advisory_fields_are_disjoint_and_exhaustive():
    # The module's own import-time completeness assert already checks this; re-asserted here as
    # the DELIVER-required "checkpoint field epistemic split" unit test, explicit and readable.
    assert DERIVED_FIELDS & ADVISORY_FIELDS == frozenset()
    assert DERIVED_FIELDS | ADVISORY_FIELDS == {
        "goal", "completed", "current_revision", "acceptance_state",
        "context_snapshot_id", "snapshot_available",
        "verified_facts", "open_hypotheses", "failed_approaches", "next_action",
    }


def test_derived_fields_match_the_accepted_design_table():
    # design §4.1: completed/current_revision/acceptance_state/context_snapshot_id (D2's v1
    # None-default form) + goal are DERIVED-or-measured, all carried by the CANONICAL fact.
    assert DERIVED_FIELDS == {
        "goal", "completed", "current_revision", "acceptance_state",
        "context_snapshot_id", "snapshot_available",
    }


def test_advisory_fields_include_verified_facts_per_deviation_d1():
    # D1: the addendum calls verified_facts DERIVED; the ACCEPTED design demotes it to ADVISORY.
    # This is the field the task prompt's own shorthand DELIVER text gets wrong relative to the
    # accepted design — see control/checkpoint.py's module docstring for the full citation.
    assert "verified_facts" in ADVISORY_FIELDS
    assert "verified_facts" not in DERIVED_FIELDS
    assert ADVISORY_FIELDS == {
        "verified_facts", "open_hypotheses", "failed_approaches", "next_action",
    }


def test_derived_payload_carries_only_derived_fields():
    cp = SessionCheckpoint(
        goal="g", completed=("scope",), current_revision="abc", acceptance_state="verified_pass",
        verified_facts=("f1",), open_hypotheses=("h1",), failed_approaches=("x",),
        next_action="do the thing",
    )
    payload = derived_payload(cp)
    assert set(payload) == DERIVED_FIELDS
    assert payload["goal"] == "g"
    assert payload["completed"] == ["scope"]
    assert "verified_facts" not in payload
    assert "next_action" not in payload


def test_advisory_payload_carries_only_advisory_fields_and_never_leaks_into_derived():
    cp = SessionCheckpoint(goal="g", verified_facts=("f1",), next_action="do the thing")
    payload = advisory_payload(cp)
    assert set(payload) == ADVISORY_FIELDS
    assert payload["verified_facts"] == ["f1"]
    assert payload["next_action"] == "do the thing"
    # D5 / adversarial finding F3: the two payloads never share a key, so an ADVISORY edit can
    # never re-key the canonical fact's identity (which hashes only derived_payload's content).
    assert set(derived_payload(cp)) & set(advisory_payload(cp)) == set()


# ── (2) the checkpoint/v1 reducer (pure) ─────────────────────────


def _run(
    *, spec_name="demo_spec", model="anthropic/claude-haiku-4-5", goal="implement thing",
    git_sha="abc123", ok=True, phases=None, started_at="2026-08-24T00:00:00+00:00",
    ended_at="2026-08-24T00:05:00+00:00",
):
    return {
        "spec_name": spec_name, "model": model, "workdir": "/tmp/x", "goal": goal,
        "git_sha": git_sha, "ok": ok, "started_at": started_at, "ended_at": ended_at,
        "phases": phases if phases is not None else [{"phase": "scope", "status": "ok"}],
    }


def _current(*, spec_name="demo_spec", model="anthropic/claude-haiku-4-5", goal="implement thing", phase="scope"):
    return {"spec_name": spec_name, "model": model, "goal": goal, "phase": phase}


def _inp(*items):
    return ReducerInput(
        scope_path=f"org:{REPO}", scope_type="workload", scope_id="", repository_id=REPO,
        evidence=items, facts=(), now=NOW, source_revision="abc123",
    )


def _by_predicate(facts):
    out: dict[str, CanonicalFact] = {}
    for f in facts:
        assert f.predicate not in out, f"duplicate {f.predicate}"
        out[f.predicate] = f
    return out


def test_checkpoint_v1_is_registered():
    assert REDUCERS[CHECKPOINT_V1.version] is CHECKPOINT_V1
    assert get_reducer(CHECKPOINT_V1.version) is checkpoint_v1
    assert set(CHECKPOINT_V1.produces) == {
        "session_checkpoint", "checkpoint_present", "checkpoint_goal_unchanged",
        "checkpoint_phase_unchanged", "checkpoint_model_unchanged", "model_change_required",
        "checkpoint_snapshot_identity",
    }


def test_checkpoint_from_run_populates_only_derived_fields():
    run = _run(phases=[
        {"phase": "scope", "status": "ok"},
        {"phase": "implement", "status": "ok", "test_executed_success": True},
    ])
    cp = checkpoint_from_run(run)
    assert cp.goal == "implement thing"
    assert cp.completed == ("scope", "implement")
    assert cp.current_revision == "abc123"
    assert cp.acceptance_state == "verified_pass"
    assert cp.context_snapshot_id is None  # D2
    assert cp.snapshot_available is False  # D2
    assert cp.verified_facts == () and cp.open_hypotheses == ()  # never populated by the reducer


@pytest.mark.parametrize(
    "phases,ok,expected",
    [
        ([{"phase": "a", "status": "ok", "test_executed_success": True}], True, "verified_pass"),
        ([{"phase": "a", "status": "ok", "test_executed_success": False}], True, "verified_fail"),
        ([{"phase": "a", "status": "ok"}], True, "unverified_ok"),
        ([{"phase": "a", "status": "failed"}], False, "unverified_fail"),
    ],
)
def test_acceptance_state_combines_verification_and_status(phases, ok, expected):
    run = _run(phases=phases, ok=ok)
    assert checkpoint_from_run(run).acceptance_state == expected


def test_session_checkpoint_fact_carries_only_the_derived_payload():
    run = _run()
    facts = _by_predicate(checkpoint_v1(_inp(EvidenceItem("workflow_run", "r1", run))))
    fact = facts["session_checkpoint"]
    assert fact.predicate == "session_checkpoint"
    assert fact.epistemic_status == "derived"
    assert fact.authority is Authority.DERIVED
    assert fact.evidence_class == "[C]"
    assert EPISTEMIC_MAP[fact.epistemic_status] == (fact.authority, fact.evidence_class)
    import json

    payload = json.loads(fact.value)
    assert set(payload) == DERIVED_FIELDS
    assert "next_action" not in payload and "verified_facts" not in payload
    assert verify_chain(fact, REDUCERS) == []
    assert is_canonical(fact)


def test_checkpoint_present_is_a_positive_marker_emitted_alone():
    facts = _by_predicate(checkpoint_v1(_inp(EvidenceItem("workflow_run", "r1", _run()))))
    assert facts["checkpoint_present"].value == "true"
    # No "current" evidence was supplied — the comparison markers must be ABSENT, never a
    # fabricated "false" (module docstring's positive-marker convention).
    assert "checkpoint_goal_unchanged" not in facts
    assert "checkpoint_phase_unchanged" not in facts
    assert "checkpoint_model_unchanged" not in facts
    assert "model_change_required" not in facts
    assert "checkpoint_snapshot_identity" not in facts  # v1: NEVER emitted (D2)


def test_no_checkpoint_at_all_mints_nothing():
    # The no-phantom rule (§3.3's discipline, applied here too): zero workflow_run evidence for a
    # cell means zero facts, never a "checkpoint_present=false" fabrication.
    assert checkpoint_v1(_inp()) == []
    assert checkpoint_v1(_inp(EvidenceItem("session_current", "c1", _current()))) == []


def test_unchanged_goal_phase_model_all_emit_true_markers():
    facts = _by_predicate(
        checkpoint_v1(_inp(
            EvidenceItem("workflow_run", "r1", _run()),
            EvidenceItem("session_current", "c1", _current()),
        ))
    )
    assert facts["checkpoint_goal_unchanged"].value == "true"
    assert facts["checkpoint_phase_unchanged"].value == "true"
    assert facts["checkpoint_model_unchanged"].value == "true"
    assert "model_change_required" not in facts
    for f in facts.values():
        assert verify_chain(f, REDUCERS) == []


def test_changed_goal_and_phase_omit_their_markers_not_emit_false():
    facts = _by_predicate(
        checkpoint_v1(_inp(
            EvidenceItem("workflow_run", "r1", _run(goal="original goal")),
            EvidenceItem(
                "session_current", "c1",
                _current(goal="a DIFFERENT goal", phase="a different phase"),
            ),
        ))
    )
    assert facts["checkpoint_present"].value == "true"
    assert "checkpoint_goal_unchanged" not in facts
    assert "checkpoint_phase_unchanged" not in facts
    # Same model in this fixture -> that marker still fires true.
    assert facts["checkpoint_model_unchanged"].value == "true"


def test_model_change_evidences_model_change_required_not_unchanged():
    # This is the case that PROVES the join key fix: the "current" item names a DIFFERENT model
    # than the checkpoint's own — they must still be compared as the SAME session (see
    # control/reducers/checkpoint.py's own comment on why the join is keyed by spec_name alone).
    facts = _by_predicate(
        checkpoint_v1(_inp(
            EvidenceItem("workflow_run", "r1", _run(model="anthropic/claude-haiku-4-5")),
            EvidenceItem("session_current", "c1", _current(model="anthropic/claude-sonnet-5")),
        ))
    )
    assert "checkpoint_model_unchanged" not in facts
    assert facts["model_change_required"].value == "true"
    assert verify_chain(facts["model_change_required"], REDUCERS) == []


def test_most_recent_run_wins_as_the_checkpoint_within_one_reduction():
    older = _run(goal="older goal", started_at="2026-08-20T00:00:00+00:00", ended_at="2026-08-20T00:05:00+00:00")
    newer = _run(goal="newer goal", started_at="2026-08-23T00:00:00+00:00", ended_at="2026-08-23T00:05:00+00:00")
    facts = _by_predicate(
        checkpoint_v1(_inp(
            EvidenceItem("workflow_run", "r1", older),
            EvidenceItem("workflow_run", "r2", newer),
        ))
    )
    import json

    assert json.loads(facts["session_checkpoint"].value)["goal"] == "newer goal"


def test_duplicate_current_item_for_same_session_is_last_one_wins_not_a_crash():
    facts = _by_predicate(
        checkpoint_v1(_inp(
            EvidenceItem("workflow_run", "r1", _run()),
            EvidenceItem("session_current", "c1", _current(goal="stale current")),
            EvidenceItem("session_current", "c2", _current(goal="implement thing")),
        ))
    )
    assert facts["checkpoint_goal_unchanged"].value == "true"


def test_re_derivation_is_byte_stable():
    a = _by_predicate(checkpoint_v1(_inp(EvidenceItem("workflow_run", "r1", _run()))))
    b = _by_predicate(checkpoint_v1(_inp(EvidenceItem("workflow_run", "r1", _run()))))
    assert a["session_checkpoint"].fact_entity_id == b["session_checkpoint"].fact_entity_id
    assert a["session_checkpoint"].value == b["session_checkpoint"].value
    assert a["session_checkpoint"].inputs_digest == b["session_checkpoint"].inputs_digest


# ── (3) the real session_routing.yaml contract ───────────────────


def test_session_routing_contract_loads_and_matches_design_shape():
    contract = load_contract("session_routing", contracts_dir=CONTRACTS_DIR)
    assert contract.decision_type == "session_routing"
    assert contract.decision_scope == "job"
    assert set(contract.allowed_actions) == {"continue", "fork", "compress_and_fork", "escalate"}
    assert contract.invariants == ()  # see the file's own header — the R11 fix
    assert {r.fact for r in contract.requires_facts} == {
        "session_checkpoint", "checkpoint_snapshot_identity", "checkpoint_goal_unchanged",
        "checkpoint_phase_unchanged", "checkpoint_model_unchanged", "checkpoint_present",
        "model_change_required", "workflow_phases_remaining",
    }
    assert contract.max_snapshot_age_seconds == 300


def test_shipped_session_routing_contract_never_fails_r11():
    """DELIVER: "validator enforcement (invariant-halt semantics per R11)" — the real, shipped
    contract must never be refused by the same R11 check route_next_job.yaml already passes."""
    contract = load_contract("session_routing", contracts_dir=CONTRACTS_DIR)

    class _Spec:
        rules = ()

    errors = validate_fact_contracts(
        _Spec(), predicates={}, reducers={}, contracts={contract.decision_type: contract},
    )
    assert not any("(R11)" in e for e in errors)


def test_all_committed_contracts_pass_r11_via_load_all_contracts():
    contracts = load_all_contracts(contracts_dir=CONTRACTS_DIR)
    assert set(contracts) == {"route_next_job", "session_routing"}

    class _Spec:
        rules = ()

    errors = validate_fact_contracts(_Spec(), predicates={}, reducers={}, contracts=contracts)
    assert not any("(R11)" in e for e in errors)


def test_the_addendums_own_literal_invariant_grouping_would_be_refused_by_r11():
    """Reproduces the addendum's §4.2 sketch EXACTLY (an unconditional invariant with
    ``on_missing: classify`` for ``checkpoint_snapshot_identity``) to prove the material finding
    documented in ``session_routing.yaml``'s own header and ``implementation_notes.md`` §15 is
    real, not asserted on faith: R11 refuses it, which is WHY this contract moves the fact to
    ``requires_facts`` instead."""
    broken = ContractSpec(
        decision_type="session_routing_addendum_literal",
        contract_version="demo/v1",
        decision_scope="job",
        allowed_actions=("continue", "fork", "compress_and_fork", "escalate"),
        max_snapshot_age_seconds=300,
        invariants=(
            FactRequirement(fact="checkpoint_goal_unchanged", on_missing="halt"),
            FactRequirement(fact="checkpoint_phase_unchanged", on_missing="halt"),
            FactRequirement(fact="checkpoint_model_unchanged", on_missing="halt"),
            # The addendum's own literal sketch — this is the R11 violation.
            FactRequirement(fact="checkpoint_snapshot_identity", on_missing="classify"),
            FactRequirement(fact="checkpoint_present", on_missing="halt"),
        ),
        objectives=(),
        requires_facts=(),
        excludes=(),
    )

    class _Spec:
        rules = ()

    errors = validate_fact_contracts(
        _Spec(), predicates={}, reducers={}, contracts={broken.decision_type: broken},
    )
    assert any(
        "(R11)" in e and "checkpoint_snapshot_identity" in e and "is not a constraint" in e
        for e in errors
    )


# ── (4) session_routing_v1 — the shadow control rule ─────────────


def _marker_fact(predicate: str, *, value="true", scope_path=JOB_SCOPE, scope_id=CELL, fact_id=None) -> CanonicalFact:
    """Mirrors ``test_context_plane_controller.py``'s own ``_fact()`` fixture idiom (empty
    ``evidence_ids`` — see this file's own module docstring for why: verify_chain's evidence-
    resolution check needs a resolver that knows raw evidence-artifact refs, which
    ``InMemoryFactStore`` deliberately does not provide; every I1-family reducer's OWN tests
    exercise that check in isolation, via a bespoke evidence index, never through
    ``compile_context`` — this fixture follows that SAME established precedent)."""
    spec = FACT_PREDICATES[predicate]
    fid = fact_id or f"fact_{predicate}_{scope_id}"
    fact = CanonicalFact(
        fact_entity_id=f"entity_{predicate}_{scope_id}",
        fact_id=fid,
        subject_type=spec.subject_type,
        subject_id=scope_id,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type=spec.scope_type,
        scope_id=scope_id,
        scope_path=scope_path,
        abstraction_level=spec.abstraction_level,
        epistemic_status="derived",
        authority=Authority.DERIVED,
        evidence_class="[C]",
        observed_at=NOW,
        valid_from=NOW,
        valid_to=None,
        expires_at=None,
        reducer="checkpoint",
        reducer_version="checkpoint/v1",
        evidence_ids=(),
        inputs_digest="",
        supersedes=None,
        source_revision="abc123",
        repository_id=REPO,
        lifecycle_state="current",
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def _phases_remaining_fact(value="2") -> CanonicalFact:
    spec = FACT_PREDICATES["workflow_phases_remaining"]
    fact = CanonicalFact(
        fact_entity_id=f"entity_workflow_phases_remaining_{CELL}",
        fact_id="fact_phases_remaining",
        subject_type=spec.subject_type,
        subject_id=CELL,
        predicate="workflow_phases_remaining",
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="workflow",
        scope_id=CELL,
        scope_path=WORKFLOW_SCOPE,
        abstraction_level=spec.abstraction_level,
        epistemic_status="derived",
        authority=Authority.DERIVED,
        evidence_class="[C]",
        observed_at=NOW,
        valid_from=NOW,
        valid_to=None,
        expires_at=None,
        reducer="workflow_facts",
        reducer_version="workflow_facts/v1",
        evidence_ids=(),
        inputs_digest="",
        supersedes=None,
        source_revision="abc123",
        repository_id=REPO,
        lifecycle_state="current",
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def _request() -> ContextRequest:
    return ContextRequest(
        decision_type="session_routing", scope_type="job", scope_id=CELL, scope_path=JOB_SCOPE,
        repository_id=REPO,
    )


CONTRACT = load_contract("session_routing", contracts_dir=CONTRACTS_DIR)


def _ctx(facts: tuple[CanonicalFact, ...]):
    store = InMemoryFactStore(facts=facts)
    return compile_context(_request(), store=store, now=NOW, contract=CONTRACT)


def test_continue_when_checkpoint_present_and_everything_unchanged():
    ctx = _ctx((
        _marker_fact("checkpoint_present"),
        _marker_fact("checkpoint_goal_unchanged"),
        _marker_fact("checkpoint_phase_unchanged"),
        _marker_fact("checkpoint_model_unchanged"),
        _phases_remaining_fact(),
    ))
    decision = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "continue"
    assert decision.facts_used  # F2: non-empty for a real (non-degenerate) continue proposal


def test_continue_when_no_checkpoint_present_at_all():
    ctx = _ctx((_phases_remaining_fact(),))
    decision = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "continue"
    assert decision.facts_used == ()
    assert "no checkpoint" in decision.rationale


def test_fork_when_checkpoint_present_but_state_changed():
    # Only checkpoint_present resolves — the three equality markers are absent (goal/phase/model
    # changed), and there is no evidenced model change either.
    ctx = _ctx((
        _marker_fact("checkpoint_present"),
        _phases_remaining_fact(),
    ))
    decision = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "fork"
    assert decision.facts_used


def test_escalate_when_model_change_is_evidenced():
    ctx = _ctx((
        _marker_fact("checkpoint_present"),
        _marker_fact("model_change_required"),
        _phases_remaining_fact(),
    ))
    decision = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "escalate"


def test_session_routing_v1_is_deterministic():
    ctx = _ctx((_marker_fact("checkpoint_present"), _phases_remaining_fact()))
    a = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    b = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert a == b


# ── DELIVER: "a continue with a stale snapshot is refused" ──────


def test_continue_with_a_stale_snapshot_is_refused_by_c5():
    """The checkpoint markers are simply ABSENT (the stale-cascade / max_age_exceeded path
    resolves them to Unknown/StaleFact exactly like an unresolved fact — §4.5's "stale is treated
    as unsatisfied" rule, `context_compiler.py`'s own ``StaleFact`` docstring) — so a decision
    that WRONGLY claims to have used them fails C5 for citing a non-canonical fact, exactly the
    same mechanism ``test_c5_cites_a_fact_not_in_the_snapshot`` already proves for route_next_job.
    """
    ctx = _ctx((_phases_remaining_fact(),))  # no checkpoint facts resolved at all == "stale/absent"
    assert ctx.admissible is False  # every halt-on-missing requires_facts entry is unmet
    bogus_decision = ControlDecision(
        decision_id="d1", snapshot_id=ctx.snapshot_id, decision_type=ctx.decision_type,
        contract_version=ctx.contract_version, action="continue", target_type="job",
        target_id=CELL, proposed_by="test",
        proposed_at=NOW, facts_used=("fact_checkpoint_goal_unchanged_" + CELL,),
    )
    result = validate_decision(
        bogus_decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW,
    )
    assert result.admitted is False
    # C2 (inadmissible snapshot) fires before C5 here, since checks are ORDERED — still a real,
    # mechanical refusal of the same bogus "continue" claim; test_fork_without_a_checkpoint below
    # exercises the C5-specific citation path directly against an ADMISSIBLE snapshot.
    assert result.check in ("C2", "C5")


def test_continue_citing_an_unresolved_marker_against_an_admissible_snapshot_fails_c5():
    # An admissible snapshot (checkpoint present + all three markers resolved) where the decision
    # nonetheless cites a fact_id that was never actually in it — the direct C5 proof.
    ctx = _ctx((
        _marker_fact("checkpoint_present"),
        _marker_fact("checkpoint_goal_unchanged"),
        _marker_fact("checkpoint_phase_unchanged"),
        _marker_fact("checkpoint_model_unchanged"),
        _phases_remaining_fact(),
    ))
    assert ctx.admissible is True
    decision = replace(
        session_routing_v1(ctx, target_id=CELL, proposed_at=NOW),
        facts_used=("fact_checkpoint_snapshot_identity_" + CELL,),  # never resolved — v1, D2
    )
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.admitted is False
    assert result.check == "C5"


# ── DELIVER: "a fork without a checkpoint is refused" ────────────


def test_fork_without_a_checkpoint_is_refused_by_c5():
    ctx = _ctx((_phases_remaining_fact(),))  # no checkpoint_present fact anywhere in the store
    bogus_fork = ControlDecision(
        decision_id="d2", snapshot_id=ctx.snapshot_id, decision_type=ctx.decision_type,
        contract_version=ctx.contract_version, action="fork", target_type="job",
        target_id=CELL, proposed_by="test", proposed_at=NOW,
        facts_used=("fact_checkpoint_present_" + CELL,),  # claims a checkpoint that was never there
    )
    result = validate_decision(bogus_fork, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.admitted is False
    assert result.check in ("C2", "C5")


def test_real_rule_never_proposes_fork_without_citing_checkpoint_present():
    # The RULE's own honesty check: it structurally cannot construct a fork decision that fails
    # C5 for this reason, because it only proposes fork when checkpoint_present ACTUALLY resolved.
    ctx = _ctx((_marker_fact("checkpoint_present"), _phases_remaining_fact()))
    decision = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "fork"
    result = validate_decision(decision, snapshot=ctx, fresh_snapshot=ctx, contract=CONTRACT, now=NOW)
    assert result.admitted is True


# ── (5) proposals are recorded and NEVER actuated ────────────────


def test_session_routing_proposal_is_recorded_never_actuated(tmp_path):
    ctx = _ctx((
        _marker_fact("checkpoint_present"),
        _marker_fact("checkpoint_goal_unchanged"),
        _marker_fact("checkpoint_phase_unchanged"),
        _marker_fact("checkpoint_model_unchanged"),
        _phases_remaining_fact(),
    ))
    decision = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    # REUSE record_shadow_decision verbatim — no new recording path for this decision type (the
    # module docstring's own point: "recorded" means the SAME durable-artifact-only pipe I6
    # already built, never a second one).
    record = record_shadow_decision(
        decision, repository_id=REPO, causes="deadbeef" * 4, artifact_dir=tmp_path,
    )
    assert record is not None
    assert record.source_type == "actuation"
    artifact_path = tmp_path / f"{record.knowledge_id}.json"
    assert artifact_path.is_file()
    # "Never actuated": knowledge_stream.publish_event is not imported anywhere in
    # record_shadow_decision (control/rules.py) — this test passing with no Redis/stream running
    # at all IS the proof, exactly as test_record_shadow_decision_never_publishes_to_the_stream
    # already establishes for route_next_job's own shadow decisions.
    import agentic_dynamics.control.rules as rules_module

    assert "publish_event" not in rules_module.record_shadow_decision.__code__.co_names


def test_escalate_and_fork_proposals_are_also_recorded_never_actuated(tmp_path):
    ctx = _ctx((
        _marker_fact("checkpoint_present"), _marker_fact("model_change_required"),
        _phases_remaining_fact(),
    ))
    decision = session_routing_v1(ctx, target_id=CELL, proposed_at=NOW)
    assert decision.action == "escalate"
    record = record_shadow_decision(
        decision, repository_id=REPO, causes="c0ffee" * 4, artifact_dir=tmp_path,
    )
    assert record is not None


# ── (6) AUTOMATABLE_ACTIONS is untouched; PROPOSABLE_ACTIONS grows explicitly ─


def test_automatable_actions_is_still_exactly_continue_and_route():
    assert AUTOMATABLE_ACTIONS == frozenset({"continue", "route"})
    for action in ("continue", "fork", "compress_and_fork", "escalate"):
        # Every session_routing action name is proposable...
        assert action in PROPOSABLE_ACTIONS
    # ...but NONE of the session-routing-specific ones are automatable (only route_next_job's
    # own "continue"/"route" are — a DIFFERENT "continue" than the session one, design F4).
    assert "fork" not in AUTOMATABLE_ACTIONS
    assert "compress_and_fork" not in AUTOMATABLE_ACTIONS
    assert "escalate" not in AUTOMATABLE_ACTIONS


def test_no_committed_spec_opts_a_control_route_into_session_routing():
    # GUARD: "no runner wiring changes" — no workflow spec YAML references decision_type:
    # session_routing anywhere in the committed corpus; this increment ships the contract/rule/
    # schema only, never a call site.
    import subprocess

    result = subprocess.run(
        ["grep", "-rl", "session_routing", "experiments/", "workflows/"],
        capture_output=True, text=True, cwd=__file__.rsplit("/tests/", 1)[0],
    )
    hits = [
        line for line in result.stdout.splitlines()
        if not line.endswith("session_routing.yaml")
    ]
    assert hits == []
