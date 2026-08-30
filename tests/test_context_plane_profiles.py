"""Tests for CAP addendum I8 — ``control/profiles.py`` (``DomainProfile``/``ChallengeProfile``).

Covers design §2.5's three obligations: (1) profile facts resolve — a declared
``DomainProfile``/``ChallengeProfile`` mints a well-formed, ``verify_chain``-clean, canonical
POLICY fact through the registered ``profiles/v1`` reducer; (2) a profile cannot widen a
contract — ``compose_requirements``/``tighten`` never relax a contract's ``requires_facts`` and
refuse an excluded fact, both as a pure function and through the real ``compile_context`` entry
point; (3) versioning/supersession behaves — bumping ``profile_version`` for the same
domain/challenge re-keys the fact VALUE under the SAME ``fact_entity_id`` slot, never a new one.

No L4 workload-fact claims: every predicate this module declares is ``abstraction_level=
"policy"`` (checked explicitly below) — the design §2.1 honesty rule this increment must not
violate.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from agentic_dynamics.control.context_compiler import (
    CONTRACTS_DIR,
    ContextRequest,
    InMemoryFactStore,
    compile_context,
    load_contract,
)
from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    Authority,
    CanonicalFact,
    is_canonical,
    recompute_inputs_digest,
    verify_chain,
)
from agentic_dynamics.control.profiles import (
    CHALLENGES,
    DELIBERATION_STAGES,
    DOMAIN_SOFTWARE_DELIVERY,
    PROFILES,
    PROFILES_V1,
    ChallengeProfile,
    ProfileCompositionError,
    SessionPolicy,
    compose_requirements,
    declare_challenge_profile,
    declare_domain_profile,
    domain_profile_predicates_known,
    migrate_static_filing,
    profiles_v1,
    resolve_profile,
    tighten,
)
from agentic_dynamics.control.reducers import REDUCERS, get_reducer
from agentic_dynamics.core.contracts import FactRequirement

NOW = "2026-08-24T00:00:00+00:00"
REPO = "agentic-dynamics"


# ── §2.1 — the dataclasses themselves ─────────────────────────────


def test_domain_profile_fields_match_design_2_1():
    profile = DOMAIN_SOFTWARE_DELIVERY
    assert profile.domain == "software_delivery"
    assert profile.profile_version == "software_delivery/v1"
    assert isinstance(profile.canonical_sources, tuple)
    assert isinstance(profile.predicates, tuple)
    assert isinstance(profile.policies, tuple)
    assert isinstance(profile.patterns, tuple)
    assert isinstance(profile.verification, tuple)
    with pytest.raises(FrozenInstanceError):
        profile.domain = "other"  # type: ignore[misc]


def test_challenge_profile_fields_match_design_2_1_and_2_6():
    profile = PROFILES[("challenge", "greenfield")]
    assert profile.challenge == "greenfield"
    assert profile.profile_version == "challenge/greenfield/v1"
    assert isinstance(profile.context_requirements, tuple)
    assert profile.deliberation == DELIBERATION_STAGES["greenfield"]
    assert isinstance(profile.session_policy, SessionPolicy)
    assert isinstance(profile.verification_policy, tuple)
    with pytest.raises(FrozenInstanceError):
        profile.challenge = "other"  # type: ignore[misc]


def test_session_policy_defaults_shadow_only_true():
    # A4/§4.3: no session action may be applied until real evidence exists. shadow_only=True is
    # the safe default every seeded ChallengeProfile inherits without having to say so explicitly.
    policy = SessionPolicy(policy="continue_default")
    assert policy.shadow_only is True
    assert policy.fork_when == ()
    assert policy.max_fork_depth == 1
    assert policy.compress_threshold_tokens == 0


def test_deliberation_table_covers_all_six_archetypes():
    assert {
        "greenfield",
        "cross_cutting",
        "small_change",
        "research",
        "incident",
        "migration",
    } == CHALLENGES
    for challenge in CHALLENGES:
        assert len(DELIBERATION_STAGES[challenge]) >= 4  # every archetype has a real sequence


def test_profiles_registry_seeds_one_domain_and_six_challenges():
    assert PROFILES[("domain", "software_delivery")] is DOMAIN_SOFTWARE_DELIVERY
    for challenge in CHALLENGES:
        assert isinstance(PROFILES[("challenge", challenge)], ChallengeProfile)
    assert resolve_profile("domain", "does_not_exist") is None
    assert resolve_profile("challenge", "does_not_exist") is None


def test_domain_profile_predicates_are_all_real_l5_predicates():
    # The honesty rule (§2.1): every predicate a DomainProfile claims must actually be declared.
    assert domain_profile_predicates_known(DOMAIN_SOFTWARE_DELIVERY) == ()
    fake = replace(DOMAIN_SOFTWARE_DELIVERY, predicates=("not_a_real_predicate",))
    assert domain_profile_predicates_known(fake) == ("not_a_real_predicate",)


def test_migrate_static_filing_resolves_the_provisional_workflow_yaml_filing():
    # workflows/repository/cap_addendum_implement.yaml's own PROVISIONAL prose names domain
    # "software_delivery" — this is the structured entry point that supersedes it (see the
    # module docstring's MIGRATION section).
    domain, challenge = migrate_static_filing(challenge="greenfield")
    assert domain is DOMAIN_SOFTWARE_DELIVERY
    assert challenge is PROFILES[("challenge", "greenfield")]
    domain2, missing = migrate_static_filing(domain="no_such_domain", challenge="greenfield")
    assert domain2 is None
    assert missing is PROFILES[("challenge", "greenfield")]


# ── (1) profile facts resolve ─────────────────────────────────────


def test_profiles_v1_is_registered_and_declares_only_l4_never_l4_workload():
    assert REDUCERS[PROFILES_V1.version] is PROFILES_V1
    assert get_reducer(PROFILES_V1.version) is profiles_v1
    assert PROFILES_V1.level == "policy"
    assert PROFILES_V1.scope_type == "workload"
    assert set(PROFILES_V1.produces) == {"domain_profile_version", "challenge_profile_version"}
    # Deviation D6 — every predicate profiles.py's reducer may emit is abstraction_level="policy".
    for predicate in PROFILES_V1.produces:
        assert FACT_PREDICATES[predicate].abstraction_level == "policy"
        assert FACT_PREDICATES[predicate].scope_type == "workload"


def test_declare_domain_profile_mints_a_clean_canonical_policy_fact():
    fact = declare_domain_profile(DOMAIN_SOFTWARE_DELIVERY, now=NOW, repository_id=REPO)
    assert fact.predicate == "domain_profile_version"
    assert fact.value == "software_delivery/v1"
    assert fact.subject_id == "software_delivery"
    assert fact.scope_type == "workload"
    assert fact.abstraction_level == "policy"
    assert fact.epistemic_status == "declared"
    assert fact.authority is Authority.POLICY
    assert fact.evidence_class == "[P]"
    assert EPISTEMIC_MAP[fact.epistemic_status] == (fact.authority, fact.evidence_class)
    assert fact.evidence_ids == ()  # declared, not reduced from evidence
    assert verify_chain(fact, REDUCERS) == []
    assert is_canonical(fact)


def test_declare_challenge_profile_mints_a_clean_canonical_policy_fact():
    profile = PROFILES[("challenge", "research")]
    fact = declare_challenge_profile(profile, now=NOW, repository_id=REPO)
    assert fact.predicate == "challenge_profile_version"
    assert fact.value == "challenge/research/v1"
    assert fact.subject_id == "research"
    assert fact.epistemic_status == "declared"
    assert fact.authority is Authority.POLICY
    assert verify_chain(fact, REDUCERS) == []
    assert is_canonical(fact)


def test_profiles_v1_ignores_non_profile_evidence_payloads():
    from agentic_dynamics.control.facts import EvidenceItem, ReducerInput

    inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=(EvidenceItem(source_type="profile", evidence_id="x", payload={"not": "a profile"}),),
        facts=(),
        now=NOW,
        source_revision="",
    )
    assert profiles_v1(inp) == []


def test_a_fact_from_an_unregistered_reducer_version_fails_verify_chain():
    # Sanity check that verify_chain is actually exercising the registry, not vacuously passing.
    fact = declare_domain_profile(DOMAIN_SOFTWARE_DELIVERY, now=NOW, repository_id=REPO)
    tampered = replace(fact, reducer_version="not_a_real_reducer/v1")
    tampered = replace(tampered, inputs_digest=recompute_inputs_digest(tampered))
    errors = verify_chain(tampered, REDUCERS)
    assert any("not_a_real_reducer/v1" in e and "not registered" in e for e in errors)


# ── (3) versioning / supersession behaves ─────────────────────────


def test_bumping_profile_version_supersedes_under_the_same_entity_id():
    v1 = DOMAIN_SOFTWARE_DELIVERY
    v2 = replace(v1, profile_version="software_delivery/v2")
    fact_v1 = declare_domain_profile(v1, now=NOW, repository_id=REPO)
    fact_v2 = declare_domain_profile(v2, now=NOW, repository_id=REPO)
    # Same slot (same domain -> same fact_entity_id): a v2 declaration is a NEW VALUE under the
    # SAME entity, i.e. a supersession — never a second, independent slot.
    assert fact_v1.fact_entity_id == fact_v2.fact_entity_id
    assert fact_v1.value != fact_v2.value
    assert fact_v1.value == "software_delivery/v1"
    assert fact_v2.value == "software_delivery/v2"


def test_a_different_domain_gets_a_different_entity_id():
    other = replace(DOMAIN_SOFTWARE_DELIVERY, domain="investing")
    fact_a = declare_domain_profile(DOMAIN_SOFTWARE_DELIVERY, now=NOW, repository_id=REPO)
    fact_b = declare_domain_profile(other, now=NOW, repository_id=REPO)
    assert fact_a.fact_entity_id != fact_b.fact_entity_id


def test_challenge_profile_versioning_mirrors_domain_profile_versioning():
    base = PROFILES[("challenge", "incident")]
    bumped = replace(base, profile_version="challenge/incident/v2")
    fact_1 = declare_challenge_profile(base, now=NOW, repository_id=REPO)
    fact_2 = declare_challenge_profile(bumped, now=NOW, repository_id=REPO)
    assert fact_1.fact_entity_id == fact_2.fact_entity_id
    assert fact_1.value != fact_2.value


# ── (2) a profile cannot widen a contract — the pure tighten()/compose_requirements gate ──


def _req(**overrides) -> FactRequirement:
    base = dict(fact="x", scope="self", max_age_seconds=600, min_authority="DERIVED",
                on_missing="halt", on_conflict="halt")
    base.update(overrides)
    return FactRequirement(**base)


class _Contract:
    """Minimal ``ContractLike`` fixture — pure data, no context_compiler dependency needed."""

    def __init__(self, *, requires_facts=(), excludes=(), decision_type="test_decision"):
        self.decision_type = decision_type
        self.contract_version = "test_decision/v1"
        self.allowed_actions = ()
        self.invariants = ()
        self.requires_facts = requires_facts
        self.excludes = excludes


def test_compose_requirements_is_a_noop_when_challenge_is_none():
    contract = _Contract(requires_facts=(_req(fact="a"),))
    assert compose_requirements(contract, None) == contract.requires_facts


def test_compose_requirements_adds_a_new_fact_the_contract_did_not_require():
    # NOTE: the profile's OWN entry ("workflow_phases_remaining") must be a REAL, registered
    # predicate — see _validate_context_requirement's R1/R2 mirror, added after an adversarial
    # pass found a profile's context_requirements never passed through the R1-R8 spec gate at
    # all (docs/designs/implemented/implementation_notes.md §17). The CONTRACT's own fictional
    # "a" is untouched by that check (only PROFILE-supplied requirements are validated here).
    contract = _Contract(requires_facts=(_req(fact="a"),))
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        context_requirements=(_req(fact="workflow_phases_remaining"),),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    merged = compose_requirements(contract, challenge)
    assert {r.fact for r in merged} == {"a", "workflow_phases_remaining"}


def test_compose_requirements_refuses_an_excluded_fact():
    contract = _Contract(requires_facts=(), excludes=("live_telemetry",))
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        context_requirements=(_req(fact="live_telemetry"),),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    with pytest.raises(ProfileCompositionError):
        compose_requirements(contract, challenge)


def test_compose_requirements_never_loosens_min_authority():
    # "checkpoint_present" (job-scoped, produced_by=("checkpoint/v1",)) stands in for the
    # fictional "a" used elsewhere in this file — here the SAME fact must be REAL because it
    # appears in the profile's own context_requirements, which _validate_context_requirement
    # now checks (R1/R2/R5 mirror; see the note on the "adds_a_new_fact" test above).
    contract = _Contract(
        requires_facts=(_req(fact="checkpoint_present", min_authority="POLICY"),)
    )
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        # profile asks for a WEAKER floor — must not win.
        context_requirements=(_req(fact="checkpoint_present", min_authority="DERIVED"),),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    merged = compose_requirements(contract, challenge)
    assert merged[0].min_authority == "POLICY"


def test_compose_requirements_never_loosens_max_age_or_on_missing():
    contract = _Contract(
        requires_facts=(_req(fact="checkpoint_present", max_age_seconds=60, on_missing="halt"),)
    )
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        # profile asks for a LOOSER age bound and a non-halting degrade — must not win.
        context_requirements=(
            _req(fact="checkpoint_present", max_age_seconds=6000, on_missing="classify"),
        ),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    merged = compose_requirements(contract, challenge)
    assert merged[0].max_age_seconds == 60
    assert merged[0].on_missing == "halt"


def test_compose_requirements_does_tighten_when_the_profile_is_stricter():
    contract = _Contract(
        requires_facts=(_req(fact="checkpoint_present", max_age_seconds=6000),)
    )
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        context_requirements=(_req(fact="checkpoint_present", max_age_seconds=60),),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    merged = compose_requirements(contract, challenge)
    assert merged[0].max_age_seconds == 60  # the tighter of the two wins


# ── Adversarial release verdict (implementation_notes.md §17): attack 1 — a profile widening a
# controller's view past its contract via an ILLEGAL FactRequirement field, not merely a looser
# value for a field the contract already governs. tighten()'s rank-based defense (above) only
# activates when the SAME fact is already present in the contract's own requires_facts; a
# BRAND-NEW fact a profile introduces skips tighten() entirely (compose_requirements does
# `merged[req.fact] = req` directly) — so nothing previously validated that req itself is
# well-formed. _validate_context_requirement closes that gap; these tests prove it end to end. ──


def test_compose_requirements_refuses_an_advisory_min_authority_on_a_new_fact():
    """The concrete exploit found in this pass: a profile requiring a BRAND-NEW fact (the
    contract does not already require it, so tighten()'s comparison never runs) with
    ``min_authority="ADVISORY"``. Before the fix, this composed cleanly and — verified by hand
    against the real ``compile_context`` — let an ADVISORY-graded fact resolve into
    ``ControlContext.job`` (the "citable" bucket), duplicated into ``ControlContext.advisory``
    too. A decision citing it was still refused by check C5 (which independently re-derives
    advisory-ness from the fact's own epistemic_status), but nothing stopped a control RULE from
    reading the wrongly-admitted value out of ``ctx.job`` to inform its branching without ever
    citing the fact_id — a silent, untraceable influence path. Now refused at composition time."""
    contract = _Contract(requires_facts=())
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        context_requirements=(
            _req(fact="checkpoint_present", min_authority="ADVISORY", on_missing="classify"),
        ),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    with pytest.raises(ProfileCompositionError, match="min_authority"):
        compose_requirements(contract, challenge)


def test_compose_requirements_refuses_an_unknown_predicate_on_a_new_fact():
    """R1's mirror: a profile may not require a fact FACT_PREDICATES has never heard of — that
    name can never resolve to anything, canonical or otherwise, so silently accepting it would
    only defer the failure to a confusing runtime "Unknown" rather than a clear composition-time
    refusal naming the actual problem."""
    contract = _Contract(requires_facts=())
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        context_requirements=(_req(fact="totally_made_up_predicate_xyz"),),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    with pytest.raises(ProfileCompositionError, match="no such predicate"):
        compose_requirements(contract, challenge)


def test_compose_requirements_refuses_an_illegal_on_missing_on_a_new_fact():
    contract = _Contract(requires_facts=())
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        context_requirements=(_req(fact="checkpoint_present", on_missing="retry_forever"),),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    with pytest.raises(ProfileCompositionError, match="on_missing"):
        compose_requirements(contract, challenge)


def test_advisory_fact_cannot_be_smuggled_into_ctx_job_via_a_profile_end_to_end():
    """The full end-to-end proof, through the REAL ``compile_context`` (not just the pure
    ``compose_requirements`` unit above): with the fix, the malformed profile is refused before
    ``compile_context`` ever runs, so an ADVISORY fact can never appear in ``ctx.job``. This is
    the "concrete path" attack 1's own charge asks for — found, reproduced, and now closed."""
    advisory_fact = CanonicalFact(
        fact_entity_id="e_advisory_present", fact_id="f_advisory_present",
        subject_type="job", subject_id=CELL, predicate="checkpoint_present",
        value="true", value_type="bool", unit="",
        scope_type="job", scope_id=CELL, scope_path=JOB_SCOPE,
        abstraction_level="job", epistemic_status="advisory",
        authority=Authority.ADVISORY, evidence_class="[H]",
        observed_at=NOW, valid_from=NOW, valid_to=None, expires_at=None,
        reducer="checkpoint", reducer_version="checkpoint/v1",
        evidence_ids=(), inputs_digest="",
        supersedes=None, source_revision="abc123", repository_id=REPO,
    )
    advisory_fact = replace(advisory_fact, inputs_digest=recompute_inputs_digest(advisory_fact))
    store = InMemoryFactStore(facts=(advisory_fact,))

    # The REAL route_next_job contract (module-level CONTRACT, defined below — Python resolves
    # module globals at call time, not definition order, so this forward reference is safe).
    # It does not already require checkpoint_present, so this is a genuinely NEW requirement —
    # exactly the path that skips tighten()'s rank-comparison defense.
    challenge = ChallengeProfile(
        challenge="research", profile_version="challenge/research/v1",
        context_requirements=(
            _req(fact="checkpoint_present", min_authority="ADVISORY", on_missing="classify"),
        ),
        deliberation=DELIBERATION_STAGES["research"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    request = ContextRequest(
        decision_type="route_next_job", scope_type="job", scope_id=CELL, scope_path=JOB_SCOPE,
        repository_id=REPO,
    )
    with pytest.raises(ProfileCompositionError):
        compile_context(request, store=store, now=NOW, contract=CONTRACT, challenge=challenge)


def test_tighten_raises_on_scope_mismatch():
    with pytest.raises(ProfileCompositionError):
        tighten(_req(fact="a", scope="self"), _req(fact="a", scope="parent"))


def test_tighten_raises_on_value_type_mismatch():
    with pytest.raises(ProfileCompositionError):
        tighten(_req(fact="a", value_type="str"), _req(fact="a", value_type="int"))


def test_tighten_raises_on_different_facts():
    with pytest.raises(ProfileCompositionError):
        tighten(_req(fact="a"), _req(fact="b"))


# ── (2) again — through the REAL compile_context entry point ──────

CONTRACT = load_contract("route_next_job", contracts_dir=CONTRACTS_DIR)
CELL = "wf_demo_spec_anthropic_claude_haiku"
JOB_SCOPE = f"org:{REPO}/workload:demo_spec/job:{CELL}"
WORKFLOW_SCOPE = f"org:{REPO}/workload:demo_spec/workflow:{CELL}"
WORKLOAD_SCOPE = f"org:{REPO}/workload:demo_spec"


def _fact(*, predicate, value, scope_type, scope_id, scope_path, fact_id,
          reducer_version="workflow_facts/v1", epistemic_status="derived") -> CanonicalFact:
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


def _base_facts() -> tuple[CanonicalFact, ...]:
    return (
        _fact(predicate="job_accumulated_cost_usd", value="1.25", scope_type="job",
              scope_id=CELL, scope_path=JOB_SCOPE, reducer_version="job_facts/v1",
              epistemic_status="observed", fact_id="fact_cost"),
        _fact(predicate="workflow_phases_remaining", value="2", scope_type="workflow",
              scope_id=CELL, scope_path=WORKFLOW_SCOPE, reducer_version="workflow_facts/v1",
              fact_id="fact_remaining"),
        _fact(predicate="allowed_models", value="anthropic/claude-sonnet-5", scope_type="workload",
              scope_id="demo_spec", scope_path=WORKLOAD_SCOPE, reducer_version="policy_facts/v1",
              epistemic_status="declared", fact_id="fact_allowed_models"),
        _fact(predicate="max_spend_usd", value="50.0", scope_type="workload",
              scope_id="demo_spec", scope_path=WORKLOAD_SCOPE, reducer_version="policy_facts/v1",
              epistemic_status="declared", fact_id="fact_max_spend"),
    )


def _request() -> ContextRequest:
    return ContextRequest(
        decision_type="route_next_job", scope_type="job", scope_id=CELL, scope_path=JOB_SCOPE,
        repository_id=REPO,
    )


def test_compile_context_with_no_challenge_matches_pre_i8_behavior():
    store = InMemoryFactStore(facts=_base_facts())
    ctx = compile_context(_request(), store=store, now=NOW, contract=CONTRACT)
    ctx_with_none = compile_context(
        _request(), store=store, now=NOW, contract=CONTRACT, challenge=None
    )
    assert ctx.snapshot_id == ctx_with_none.snapshot_id
    assert ctx.admissible == ctx_with_none.admissible


def test_compile_context_refuses_a_challenge_that_requires_an_excluded_fact():
    # route_next_job.yaml excludes live_telemetry (design §10.4) — a challenge profile may not
    # smuggle it in through context_requirements.
    challenge = ChallengeProfile(
        challenge="incident", profile_version="challenge/incident/v1",
        context_requirements=(FactRequirement(fact="live_telemetry"),),
        deliberation=DELIBERATION_STAGES["incident"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    store = InMemoryFactStore(facts=_base_facts())
    with pytest.raises(ProfileCompositionError):
        compile_context(_request(), store=store, now=NOW, contract=CONTRACT, challenge=challenge)


def test_compile_context_composes_a_new_required_fact_and_can_refuse_on_it():
    # max_attempts is a real, producible predicate the base contract does NOT require — the
    # challenge profile legitimately ADDS visibility into it (§2.3's "may add" half).
    challenge = ChallengeProfile(
        challenge="incident", profile_version="challenge/incident/v1",
        context_requirements=(
            FactRequirement(fact="max_attempts", scope="workload", on_missing="halt"),
        ),
        deliberation=DELIBERATION_STAGES["incident"],
        session_policy=SessionPolicy(policy="continue_default"), verification_policy=(),
    )
    # Not in the store yet -> the ADDED requirement halts admission (the contract's own
    # requires_facts are otherwise fully satisfied).
    store = InMemoryFactStore(facts=_base_facts())
    ctx = compile_context(_request(), store=store, now=NOW, contract=CONTRACT, challenge=challenge)
    assert ctx.admissible is False
    assert "max_attempts" in ctx.refusal

    # Now satisfy it -> admissible, and the added fact shows up in the workload bucket.
    store2 = InMemoryFactStore(
        facts=_base_facts()
        + (
            _fact(predicate="max_attempts", value="5", scope_type="workload",
                  scope_id="demo_spec", scope_path=WORKLOAD_SCOPE,
                  reducer_version="policy_facts/v1", epistemic_status="declared",
                  fact_id="fact_max_attempts"),
        )
    )
    ctx2 = compile_context(_request(), store=store2, now=NOW, contract=CONTRACT, challenge=challenge)
    assert ctx2.admissible is True
    assert any(f.predicate == "max_attempts" for f in ctx2.workload)


def test_compile_context_accepts_a_domain_profile_without_changing_resolution():
    # §2.1's honesty rule: a DomainProfile carries no context_requirements, so passing one must
    # not silently change what gets resolved relative to passing none.
    store = InMemoryFactStore(facts=_base_facts())
    ctx_without = compile_context(_request(), store=store, now=NOW, contract=CONTRACT)
    ctx_with = compile_context(
        _request(), store=store, now=NOW, contract=CONTRACT, domain=DOMAIN_SOFTWARE_DELIVERY
    )
    assert ctx_without.snapshot_id == ctx_with.snapshot_id
