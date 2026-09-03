"""Tests for the belief record type (belief_ingestion) — s4a of the self_knowledge_layer wave.

Covers the record-type cases (the s4a scope fence — type ONLY, the update operation is s4b):
``derive_belief_record`` derives ONE ``source_type=belief`` record from a hypothesis dict,
carrying the deliverable's fixed content shape {hypothesis, prior_confidence,
n_confirmations, n_disconfirmations, last_updated, posterior_confidence, evidence_class,
domain, evidence_citations[]} plus actor + scope. The type cases assert: the registered
source_type (observation-family ADVISORY/[H]); the actor (``aio``) + org-root scope carriage
(structural + self-describing in the body, so a cell scope can never resolve a belief record);
the round trip through record_to_artifact / record_to_event / extract_record; the
deterministic posterior rule (a fresh hypothesis reproduces its prior, a confirmation raises,
a disconfirmation lowers — the well-formedness s4b's in-place update reads back through); the
evidence_class ladder ([P]/[M]/[C]/[H] — declared in the body, never self-elevating the
record's own ADVISORY tier); rerun-safe identity with the entity stable across an update
(the "updated in place, never duplicated" version chain s4b needs); the namespace separation
from the session/decision/wave_verdict families; and validation (missing required fields,
out-of-range confidences, fractional/negative counts, and out-of-ladder evidence classes all
refuse loudly).

The fixtures model the seeded hypotheses the s4c phase will mint from the measured history
(design §"the Bayesian–frequentist synthesis"), e.g. "flash converges in ~1 wave on in-process
work" — all synthetic, so the tests are hermetic.
"""

import hashlib
import json

import pytest

from agentic_dynamics.knowledge import belief_ingestion as bi
from agentic_dynamics.knowledge.knowledge import (
    SOURCE_TYPES,
    Authority,
    message_family,
)
from agentic_dynamics.knowledge.knowledge_ingestion import (
    REPOSITORY_ID,
    extract_record,
    record_to_artifact,
    record_to_event,
)
from agentic_dynamics.knowledge.session_ingestion import aio_acl_scope


def _belief(**overrides) -> dict:
    """A synthetic AIO hypothesis dict — the s4a DONE_WHEN fixture.

    Shaped like the measured-history seeds s4c will mint: a claim about how the machine
    converges, a declared [M] evidence class, and the wave names that bear on it as citations.
    """
    base = {
        "hypothesis": "flash converges in ~1 wave on in-process work",
        "prior_confidence": 0.5,
        "n_confirmations": 0,
        "n_disconfirmations": 0,
        "last_updated": "2026-09-04T08:00:00+00:00",
        "evidence_class": "[M]",
        "domain": "workstream-convergence",
        "evidence_citations": [
            "self_knowledge_layer wave verdict run-77f7b899f4f8",
            "kb_finding_layer wave verdict",
        ],
    }
    base.update(overrides)
    return base


def _payload(record) -> dict:
    return json.loads(record.text)


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert bi.SOURCE_TYPE == "belief"
    assert bi.EXTRACTOR_VERSION == "belief/v1"
    assert bi.ACTOR == "aio"
    assert bi.REVISION_FALLBACK == "belief/unrevisioned"
    assert bi.EVIDENCE_LADDER == ("[P]", "[M]", "[C]", "[H]")
    assert bi.DEFAULT_EVIDENCE_CLASS == "[H]"
    # The belief source_type is registered in the one vocabulary table, as an observation
    # family — a belief is a hypothesis the machine holds about itself operating, never an
    # actuation — with nominal ADVISORY/[H] provenance: self-reported like a session close or
    # a decision, so it can inform the AIO but never override a MEASURED row or pinned policy.
    assert bi.SOURCE_TYPE in SOURCE_TYPES
    assert SOURCE_TYPES["belief"].authority is Authority.ADVISORY
    assert SOURCE_TYPES["belief"].evidence_class == "[H]"
    assert message_family("belief") == "observation"


def test_belief_ingestion_is_exported_from_the_knowledge_package():
    from agentic_dynamics.knowledge import belief_ingestion

    assert belief_ingestion is bi


# ── Provenance + the actor/scope carriage ───────────────────────


def test_record_provenance_is_advisory_h_like_the_self_report_family():
    record = bi.derive_belief_record(_belief())
    assert record.source_type == "belief"
    assert record.authority is Authority.ADVISORY
    assert record.evidence_class == "[H]"


def test_record_carries_aio_actor_and_org_root_scope():
    record = bi.derive_belief_record(_belief())
    # Scope is structural on the record: the org id as repository_id, the AIO org-root scope as
    # acl_scope — the design actor table's "org:repo (AIO + controller visible)", distinct from
    # the corpus's "public" acl rows and from any self-* cell scope.
    assert record.repository_id == REPOSITORY_ID
    assert record.acl_scope == aio_acl_scope(REPOSITORY_ID)
    # And self-describing in the body: actor + scope keys are part of the hashed payload.
    payload = _payload(record)
    assert payload["actor"] == "aio"
    assert payload["scope"] == record.acl_scope


def test_cell_scoped_retrieval_excludes_the_belief_record():
    # Actor layering, deterministic at the type: the record's repository_id is the org id, so
    # the retrieval hard pre-filter (scope_excluded) excludes it from any cell/workload query —
    # a self-* cell scope or a foreign workload never equals the org id, so a cell agent cannot
    # resolve the AIO's private belief records. Only an explicit org-root read resolves them.
    from agentic_dynamics.knowledge.retrieval import scope_excluded

    record = bi.derive_belief_record(_belief())
    assert scope_excluded(record.repository_id, requested_scope="self-wt_beliefs")
    assert scope_excluded(
        record.repository_id,
        requested_scope="workload:other_spec/job:wf_other_spec_deepseek_deepseek_v4_flash",
    )
    # The AIO/controller at the org root resolves it (empty candidate scope semantics unchanged
    # and an explicit org-root requested scope matches the record's own repository id).
    assert not scope_excluded(record.repository_id, requested_scope="")
    assert not scope_excluded(record.repository_id, requested_scope="agentic-dynamics")


# ── The deliverable content fields round-trip ───────────────────


def test_content_fields_round_trip_through_artifact_and_event():
    record = bi.derive_belief_record(
        _belief(n_confirmations=3, n_disconfirmations=1)
    )

    artifact = record_to_artifact(record)
    event = record_to_event(record)
    extracted = extract_record(event, artifact)

    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash
    assert extracted.entity_id == record.entity_id
    assert extracted.acl_scope == record.acl_scope
    assert extracted.text == record.text

    payload = _payload(extracted)
    assert payload["hypothesis"] == "flash converges in ~1 wave on in-process work"
    assert payload["prior_confidence"] == 0.5
    assert payload["n_confirmations"] == 3
    assert payload["n_disconfirmations"] == 1
    assert payload["last_updated"] == "2026-09-04T08:00:00+00:00"
    assert payload["posterior_confidence"] == 0.666667
    assert payload["evidence_class"] == "[M]"
    assert payload["domain"] == "workstream-convergence"
    assert isinstance(payload["evidence_citations"], list) and len(payload["evidence_citations"]) == 2
    assert payload["actor"] == "aio"
    assert payload["scope"] == record.acl_scope

    # The standard pointer contract: content_hash covers the artifact, observed_at is the
    # belief's own last_updated (when it was last revised), not the producer clock.
    assert event.knowledge_id == record.knowledge_id
    assert event.operation == "upsert"
    assert event.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.observed_at == "2026-09-04T08:00:00+00:00"
    assert extracted.observed_at == "2026-09-04T08:00:00+00:00"


def test_full_dict_round_trip_is_lossless():
    from agentic_dynamics.knowledge.knowledge import KnowledgeRecord

    record = bi.derive_belief_record(_belief())
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record


def test_derive_and_build_delegate_to_the_same_record():
    a = bi.derive_belief_record(_belief())
    b = bi.build_belief_record(_belief())
    for attr in (
        "knowledge_id",
        "entity_id",
        "content_hash",
        "source_uri",
        "text",
        "logical_locator",
        "acl_scope",
        "repository_id",
    ):
        assert getattr(a, attr) == getattr(b, attr)


# ── The deterministic posterior rule (the type's well-formedness) ─


def test_a_fresh_hypothesis_posterior_equals_prior():
    # DONE_WHEN half — well-formedness: a hypothesis with no counted outcomes carries its prior
    # as its posterior (n_confirmations == n_disconfirmations == 0 by default).
    record = bi.derive_belief_record(_belief())
    payload = _payload(record)
    assert payload["n_confirmations"] == 0
    assert payload["n_disconfirmations"] == 0
    assert payload["posterior_confidence"] == payload["prior_confidence"] == 0.5


def test_a_confirmation_raises_the_posterior():
    # "posterior moves toward the evidence with the confirmation count": one confirm on a 0.5
    # prior moves the posterior to 2/3 (the Beta mean with a 2-pseudo-observation prior).
    payload = _payload(bi.derive_belief_record(_belief(n_confirmations=1)))
    assert payload["posterior_confidence"] == 0.666667
    assert payload["posterior_confidence"] > payload["prior_confidence"]


def test_a_disconfirmation_lowers_the_posterior():
    # "a disconfirm lowers it": one disconfirm on a 0.5 prior moves the posterior to 1/3.
    payload = _payload(bi.derive_belief_record(_belief(n_disconfirmations=1)))
    assert payload["posterior_confidence"] == 0.333333
    assert payload["posterior_confidence"] < payload["prior_confidence"]


def test_two_confirmations_yield_a_single_record_with_higher_posterior():
    # The s4b "two confirm updates yield ONE record with n=2" semantics are well-formed at the
    # type: a hypothesis whose counts read n=2 is ONE record whose posterior reflects both.
    payload = _payload(bi.derive_belief_record(_belief(n_confirmations=2)))
    assert payload["n_confirmations"] == 2
    assert payload["posterior_confidence"] == 0.75


def test_an_explicit_posterior_overrides_the_computed_default():
    # A caller with a hand-set posterior may record it without fighting the engine.
    payload = _payload(bi.derive_belief_record(_belief(posterior_confidence=0.9)))
    assert payload["posterior_confidence"] == 0.9


def test_compute_posterior_is_the_shared_deterministic_rule():
    # The pure function the derivation (and, later, s4b's in-place update) reads back through.
    assert bi.compute_posterior(0.5, 0, 0) == 0.5
    assert bi.compute_posterior(0.5, 1, 0) == 0.666667
    assert bi.compute_posterior(0.5, 0, 1) == 0.333333
    assert bi.compute_posterior(0.5, 2, 1) == 0.6  # (1+2)/(2+2+1)
    assert bi.compute_posterior(0.8, 0, 1) == 0.533333
    # An extreme prior is still revisable (a disconfirm pulls 1.0 down — never a dogma).
    assert bi.compute_posterior(1.0, 0, 1) == 0.666667
    with pytest.raises(ValueError, match="prior_confidence"):
        bi.compute_posterior(1.5, 0, 0)
    with pytest.raises(ValueError, match="n_confirmations"):
        bi.compute_posterior(0.5, -1, 0)
    with pytest.raises(ValueError, match="n_disconfirmations"):
        bi.compute_posterior(0.5, 0, True)  # type: ignore[arg-type]


# ── The evidence_class ladder ([P]/[M]/[C]/[H] — prior-authority) ─


def test_evidence_class_defaults_to_heuristic():
    # An undeclared hypothesis is a heuristic until evidence says otherwise — the honest base
    # of the ladder, never a fabricated measured claim.
    payload = _payload(bi.derive_belief_record(_belief(evidence_class=None)))
    assert payload["evidence_class"] == "[H]"


def test_evidence_class_rides_in_the_payload_but_does_not_self_elevate():
    # The declared class is REPORTED in the body (the [M] a measured-history seed carries) while
    # the record's own KB trust tier stays uniformly ADVISORY/[H]: a self-reported evidence
    # label describes the belief's backing, it never promotes the writer's authority tier.
    record = bi.derive_belief_record(_belief())
    payload = _payload(record)
    assert payload["evidence_class"] == "[M]"
    assert record.evidence_class == "[H]"
    assert record.authority is Authority.ADVISORY


def test_every_ladder_class_is_accepted():
    for ladder_class in bi.EVIDENCE_LADDER:
        payload = _payload(bi.derive_belief_record(_belief(evidence_class=ladder_class)))
        assert payload["evidence_class"] == ladder_class


def test_an_evidence_class_outside_the_ladder_raises():
    # The belief ladder is closed: [X] (external) and any invented tag refuse loudly — a belief
    # record must never carry an evidence class the design's ladder does not define.
    with pytest.raises(ValueError, match="evidence_class"):
        bi.derive_belief_record(_belief(evidence_class="[X]"))
    with pytest.raises(ValueError, match="evidence_class"):
        bi.derive_belief_record(_belief(evidence_class="measured"))


# ── The DONE_WHEN ───────────────────────────────────────────────


def test_a_synthetic_hypothesis_derives_a_complete_belief_record():
    # DONE_WHEN: a synthetic hypothesis derives a belief record with ALL fields + its citations.
    record = bi.derive_belief_record(
        _belief(
            n_confirmations=1,
            n_disconfirmations=0,
            evidence_citations=[
                "self_knowledge_layer wave verdict run-77f7b899f4f8",
                "kb_finding_layer wave verdict",
            ],
        )
    )
    payload = _payload(record)
    for field in bi.CONTENT_FIELDS:
        assert field in payload, f"missing content field {field!r}"
    assert payload["hypothesis"] == "flash converges in ~1 wave on in-process work"
    assert payload["domain"] == "workstream-convergence"
    assert payload["last_updated"] == "2026-09-04T08:00:00+00:00"
    assert payload["evidence_citations"] == [
        "self_knowledge_layer wave verdict run-77f7b899f4f8",
        "kb_finding_layer wave verdict",
    ]
    # The posterior is the deterministic consequence of the recorded counts (a self-consistent
    # record, never a field left to the reader to guess).
    assert payload["posterior_confidence"] == 0.666667
    # A single citation string is treated as one item; absent citations render as [].
    single = _payload(bi.derive_belief_record(_belief(evidence_citations="self_knowledge_layer")))
    assert single["evidence_citations"] == ["self_knowledge_layer"]
    none = _payload(bi.derive_belief_record(_belief(evidence_citations=None)))
    assert none["evidence_citations"] == []


# ── Identity + rerun safety ─────────────────────────────────────


def test_knowledge_id_is_rerun_safe_same_inputs_same_id():
    first = bi.derive_belief_record(_belief())
    second = bi.derive_belief_record(_belief())
    assert second.knowledge_id == first.knowledge_id
    assert second.entity_id == first.entity_id
    assert second.content_hash == first.content_hash


def test_a_different_hypothesis_is_a_different_entity():
    first = bi.derive_belief_record(_belief())
    other = bi.derive_belief_record(_belief(hypothesis="container seams take ~4 waves"))
    assert other.entity_id != first.entity_id
    assert other.knowledge_id != first.knowledge_id
    assert other.logical_locator != first.logical_locator


def test_the_same_words_in_a_different_domain_are_a_different_entity():
    # Domain is part of the identity: the same claim under a different domain is a different
    # belief (the controller model's org-root class vs a workstream-convergence claim), and the
    # domain is the s4c retrieval axis.
    first = bi.derive_belief_record(_belief())
    other = bi.derive_belief_record(_belief(domain="controller-model"))
    assert other.entity_id != first.entity_id
    assert other.knowledge_id != first.knowledge_id


def test_an_update_rekeys_knowledge_id_but_not_entity_id():
    # The s4b "updated in place, NEVER duplicated" precondition: confirming the same hypothesis
    # (count +1, last_updated advanced) is a NEW VERSION of the SAME belief slot — content
    # changes (n_confirmations, posterior, last_updated) so knowledge_id re-keys while
    # entity_id holds, the supersede-capable spine an in-place update writes.
    confirmed = bi.derive_belief_record(
        _belief(n_confirmations=1, last_updated="2026-09-04T08:00:00+00:00")
    )
    re_confirmed = bi.derive_belief_record(
        _belief(n_confirmations=2, last_updated="2026-09-04T12:00:00+00:00")
    )
    assert re_confirmed.entity_id == confirmed.entity_id
    assert re_confirmed.logical_locator == confirmed.logical_locator
    assert re_confirmed.knowledge_id != confirmed.knowledge_id
    assert re_confirmed.content_hash != confirmed.content_hash
    assert _payload(re_confirmed)["n_confirmations"] == 2
    assert _payload(re_confirmed)["posterior_confidence"] == 0.75


def test_identity_is_namespace_distinct_from_decision_session_and_wave_verdict():
    from agentic_dynamics.knowledge.decision_ingestion import derive_decision_record
    from agentic_dynamics.knowledge.session_ingestion import derive_session_record
    from agentic_dynamics.knowledge.wave_verdict_ingestion import derive_wave_verdict

    belief = bi.derive_belief_record(_belief())
    decision = derive_decision_record(
        {
            "what": "park the fleet",
            "why": "dormant lane",
            "alternatives": [],
            "category": "park",
            "decided_at": "2026-09-03T12:00:00+00:00",
        }
    )
    session = derive_session_record(
        {
            "session_date": "2026-09-03",
            "slug": belief.logical_locator,  # same locator string, different family
            "waves_run": [],
        }
    )
    verdict = derive_wave_verdict(
        {
            "spec_name": "some_spec",
            "run_id": belief.logical_locator,
            "state": "succeeded",
            "ok": True,
            "total_cost_usd": 1.0,
        },
        None,
    )
    assert belief.source_uri.startswith("belief:")
    assert belief.extractor_version == "belief/v1"
    assert decision.source_uri.startswith("decision:")
    assert session.source_uri.startswith("session:")
    assert verdict.source_uri.startswith("wave_verdict:")
    assert belief.entity_id != decision.entity_id
    assert belief.entity_id != session.entity_id
    assert belief.entity_id != verdict.entity_id
    assert belief.knowledge_id != decision.knowledge_id
    assert belief.knowledge_id != session.knowledge_id
    assert belief.knowledge_id != verdict.knowledge_id


# ── Validation ──────────────────────────────────────────────────


def test_missing_hypothesis_raises_value_error():
    with pytest.raises(ValueError, match="hypothesis"):
        bi.derive_belief_record(_belief(hypothesis=""))


def test_missing_domain_raises_value_error():
    with pytest.raises(ValueError, match="domain"):
        bi.derive_belief_record(_belief(domain=None))


def test_missing_last_updated_raises_value_error():
    with pytest.raises(ValueError, match="last_updated"):
        bi.derive_belief_record(_belief(last_updated=""))


def test_missing_prior_confidence_raises_value_error():
    with pytest.raises(ValueError, match="prior_confidence"):
        bi.derive_belief_record(_belief(prior_confidence=None))


def test_prior_confidence_out_of_range_raises_value_error():
    with pytest.raises(ValueError, match="prior_confidence"):
        bi.derive_belief_record(_belief(prior_confidence=1.5))
    with pytest.raises(ValueError, match="prior_confidence"):
        bi.derive_belief_record(_belief(prior_confidence=-0.1))


def test_prior_confidence_non_numeric_raises_value_error():
    with pytest.raises(ValueError, match="prior_confidence"):
        bi.derive_belief_record(_belief(prior_confidence="high"))
    with pytest.raises(ValueError, match="prior_confidence"):
        bi.derive_belief_record(_belief(prior_confidence=True))  # type: ignore[arg-type]


def test_posterior_out_of_range_raises_when_provided():
    with pytest.raises(ValueError, match="posterior_confidence"):
        bi.derive_belief_record(_belief(posterior_confidence=1.01))


def test_negative_or_fractional_counts_raise_value_error():
    with pytest.raises(ValueError, match="n_confirmations"):
        bi.derive_belief_record(_belief(n_confirmations=-1))
    with pytest.raises(ValueError, match="n_disconfirmations"):
        bi.derive_belief_record(_belief(n_disconfirmations=-1))
    with pytest.raises(ValueError, match="n_confirmations"):
        bi.derive_belief_record(_belief(n_confirmations=1.5))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="n_disconfirmations"):
        bi.derive_belief_record(_belief(n_disconfirmations=True))  # type: ignore[arg-type]
