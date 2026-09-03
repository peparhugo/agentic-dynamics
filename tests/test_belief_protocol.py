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

The s4b UPDATE cases (the bottom sections) cover the belief protocol's missing half
(``knowledge/belief_update.py`` — the scope fence "the update operation + its trigger ONLY"):
the pure in-place update (one count +1, posterior recomputed through the SAME rule, prior
anchor preserved, never a duplicate entity); the version-chain record seam (entity stable,
``supersedes`` = the current version, two confirm updates yield ONE record with n=2); the
belief index (the durable latest-per-entity pool resolved from the ``belief/v1`` artifacts); and
the TRIGGER — a wave verdict (the s3b emission's payload) consults the index and updates the
hypotheses it bears on, an unrelated outcome updates nothing, and a re-applied same-run
verdict is never double-counted. The final section drives the REAL run-completion wiring in
``scripts/run_workflow.py`` hermetically (importlib + redirected control db/KB dir + fake
stream, the test_wave_verdicts technique): a completed run whose verdict bears on a durable
belief updates it in the same terminal transaction that emits the verdict.

The fixtures model the seeded hypotheses the s4c phase will mint from the measured history
(design §"the Bayesian–frequentist synthesis"), e.g. "flash converges in ~1 wave on in-process
work" — all synthetic, so the tests are hermetic.
"""

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentic_dynamics.knowledge import belief_ingestion as bi
from agentic_dynamics.knowledge import belief_update as bu
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


# ════════════════════════════════════════════════════════════════════════════════════════════
# s4b — the UPDATE operation (knowledge/belief_update.py): the belief protocol's missing half
# ════════════════════════════════════════════════════════════════════════════════════════════
#
# DONE_WHEN (s4b): two confirm updates yield ONE record with n=2 (assert); a disconfirm lowers
# the posterior; an unrelated outcome updates nothing. The scope fence is the update operation +
# its trigger ONLY — the seeded corpus is s4c, so every fixture below is a hand-built belief
# dict/record (the s4a ``_belief`` shape), hermetic, no live KB.


def _write_artifact(artifact_dir, record) -> Path:
    """Durably write one record's artifact under ``artifact_dir`` (the belief-index read path)."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{record.knowledge_id}.json"
    path.write_bytes(record_to_artifact(record))
    return path


def _verdict(**overrides) -> dict:
    """A synthetic s3a wave-verdict payload (the fields the trigger reads)."""
    base = {
        "spec_name": "self_knowledge_layer",
        "run_id": "run-99aaaa1111",
        "verdict": "merge-ready",
        "cost": 1.0,
        "phases_total": 8,
        "merge_state": "promotable",
        "residuals": [],
    }
    base.update(overrides)
    return base


#: The run-completion instant the trigger tests stamp their updates with. Deliberately LATER
#: than the ``_belief`` fixture's ``last_updated`` (2026-09-04T08:00Z) so the belief index
#: resolves the updated version over the seed — the machine clock may predate the fixture.
_VERDICT_AT = "2026-09-04T12:00:00+00:00"


def _apply(verdict, tmp_path, **kwargs):
    """Drive the trigger with the fixture's pinned observed_at (the run's completion instant)."""
    kwargs.setdefault("observed_at", _VERDICT_AT)
    return bu.apply_wave_verdict(verdict, artifact_dir=tmp_path, **kwargs)


def _body(record) -> dict:
    return json.loads(record.text)


def _index(artifact_dir) -> dict:
    """Convenience: current belief index as {locator: (knowledge_id, payload)}."""
    current, warnings = bu.belief_index(artifact_dir=artifact_dir)
    assert warnings == []
    return {payload["domain"] + "|" + payload["hypothesis"]: (kid, payload) for kid, payload in current}


# ── the pure update rule ─────────────────────────────────────────


def test_a_confirm_update_increments_and_raises_the_posterior():
    payload = _body(bi.derive_belief_record(_belief()))
    assert payload["n_confirmations"] == 0 and payload["posterior_confidence"] == 0.5
    updated = bu.update_belief(payload, signal="confirm")
    assert updated["n_confirmations"] == 1
    assert updated["n_disconfirmations"] == 0
    assert updated["posterior_confidence"] == 0.666667  # (1+1)/(2+1) — the s4a rule
    assert updated["posterior_confidence"] > payload["posterior_confidence"]


def test_a_disconfirm_update_increments_and_lowers_the_posterior():
    # DONE_WHEN half: "a disconfirm lowers it".
    payload = _body(bi.derive_belief_record(_belief()))
    updated = bu.update_belief(payload, signal="disconfirm")
    assert updated["n_disconfirmations"] == 1
    assert updated["n_confirmations"] == 0
    assert updated["posterior_confidence"] == 0.333333  # (0+1)/(2+1)
    assert updated["posterior_confidence"] < payload["posterior_confidence"]


def test_the_prior_anchor_is_preserved_across_updates():
    # The record's prior is the confidence BEFORE the recorded evidence; an update accumulates
    # counts against it (Beta-binomial pseudo-observations), it never re-anchors to the last
    # posterior. Two confirms on a 0.5 prior -> n=2 -> posterior 0.75, exactly the s4a fixture.
    payload = _body(bi.derive_belief_record(_belief(prior_confidence=0.4)))
    once = bu.update_belief(payload, signal="confirm")
    twice = bu.update_belief(once, signal="confirm")
    for step in (payload, once, twice):
        assert step["prior_confidence"] == 0.4
    assert twice["n_confirmations"] == 2
    assert twice["posterior_confidence"] == bi.compute_posterior(0.4, 2, 0)


def test_a_confirm_then_a_disconfirm_moves_the_posterior_back_toward_the_prior():
    # Symmetric counting: one confirm + one disconfirm is a wash (1/1 -> the prior itself).
    payload = _body(bi.derive_belief_record(_belief()))
    after_confirm = bu.update_belief(payload, signal="confirm")
    after_both = bu.update_belief(after_confirm, signal="disconfirm")
    assert after_both["n_confirmations"] == 1 and after_both["n_disconfirmations"] == 1
    assert after_both["posterior_confidence"] == 0.5
    assert after_both["prior_confidence"] == payload["prior_confidence"] == 0.5


def test_update_belief_is_pure_and_appends_a_citation_once():
    payload = _body(bi.derive_belief_record(_belief()))
    updated = bu.update_belief(
        payload, signal="confirm", citation="self_knowledge_layer wave verdict run-zz9999"
    )
    assert payload["n_confirmations"] == 0  # the input dict is never mutated
    assert updated["evidence_citations"] == payload["evidence_citations"] + [
        "self_knowledge_layer wave verdict run-zz9999"
    ]
    again = bu.update_belief(updated, signal="confirm", citation="self_knowledge_layer wave verdict run-zz9999")
    assert again["evidence_citations"].count("self_knowledge_layer wave verdict run-zz9999") == 1
    assert again["n_confirmations"] == 2  # the count advanced; the citation did not duplicate


def test_an_unknown_signal_is_refused_loudly():
    payload = _body(bi.derive_belief_record(_belief()))
    with pytest.raises(ValueError, match="signal"):
        bu.update_belief(payload, signal="maybe")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="signal"):
        bu.update_belief(payload, signal=None)  # type: ignore[arg-type]


# ── the version-chain record seam (in place, never duplicated) ──


def _dt(hour: int) -> datetime:
    return datetime(2026, 9, 4, hour, 0, 0, tzinfo=timezone.utc)


def test_two_confirm_updates_yield_one_record_with_n2(tmp_path):
    # DONE_WHEN: two confirm updates on the same hypothesis produce ONE belief entity whose
    # current version carries n_confirmations == 2 — never two hypotheses, never a duplicate.
    rec0 = bi.derive_belief_record(_belief(n_confirmations=0, n_disconfirmations=0))
    rec1 = bu.version_from_record(rec0, signal="confirm", now=_dt(9))
    rec2 = bu.version_from_record(rec1, signal="confirm", now=_dt(12))

    # The version chain: one entity, three versions, each superseding the last.
    assert rec1.entity_id == rec0.entity_id
    assert rec2.entity_id == rec0.entity_id
    assert rec2.logical_locator == rec0.logical_locator
    assert rec1.knowledge_id != rec0.knowledge_id
    assert rec2.knowledge_id != rec1.knowledge_id
    assert rec1.supersedes == rec0.knowledge_id
    assert rec2.supersedes == rec1.knowledge_id

    # The final version IS the one record: n=2, posterior recomputed (0.75), prior anchor intact.
    body = _body(rec2)
    assert body["n_confirmations"] == 2
    assert body["n_disconfirmations"] == 0
    assert body["posterior_confidence"] == 0.75
    assert body["prior_confidence"] == 0.5

    # And as a durable corpus, the belief index resolves exactly ONE current record with n=2
    # (the two older versions are history, not duplicates).
    for record in (rec0, rec1, rec2):
        _write_artifact(tmp_path, record)
    current = _index(tmp_path)
    assert len(current) == 1  # one belief entity, however many versions accumulated
    (knowledge_id, payload) = next(iter(current.values()))
    assert knowledge_id == rec2.knowledge_id  # the newest version is the one the index resolves
    assert payload["n_confirmations"] == 2
    assert payload["posterior_confidence"] == 0.75


def test_an_update_is_a_superseding_version_not_a_new_entity(tmp_path):
    # "Updated in place ... NEVER duplicated": the durable corpus after an update holds ONE
    # entity across its versions, and the artifact the new version writes carries the
    # supersedes link the registry closes the predecessor out with.
    seed = bi.derive_belief_record(_belief())
    updated = bu.version_from_record(seed, signal="confirm", now=_dt(9))
    seed_path = _write_artifact(tmp_path, seed)
    updated_path = _write_artifact(tmp_path, updated)

    from agentic_dynamics.knowledge.knowledge import KnowledgeRecord

    restored = KnowledgeRecord.from_dict(json.loads(updated_path.read_text()))
    assert restored.supersedes == seed.knowledge_id
    assert updated_path.name != seed_path.name  # distinct versions, same entity
    assert _index(tmp_path)[next(iter(_index(tmp_path)))][1]["n_confirmations"] == 1


def test_version_from_record_preserves_the_actor_and_org_root_scope():
    seed = bi.derive_belief_record(_belief())
    updated = bu.version_from_record(seed, signal="disconfirm", now=_dt(9))
    assert updated.source_type == "belief"
    assert updated.repository_id == REPOSITORY_ID
    assert updated.acl_scope == aio_acl_scope(REPOSITORY_ID)
    assert updated.authority is Authority.ADVISORY
    body = _body(updated)
    assert body["actor"] == "aio"
    assert body["scope"] == updated.acl_scope


# ── the belief index (the durable current-belief pool) ───────────


def test_the_index_resolves_the_latest_version_per_entity_and_ignores_foreign_artifacts(
    tmp_path,
):
    # The durable dir accumulates every producer's rows; the index must resolve ONE current
    # payload per belief entity, by the belief's OWN revision content, and never mistake a
    # foreign artifact (a session record, a wave verdict) for a belief.
    from agentic_dynamics.knowledge.session_ingestion import derive_session_record
    from agentic_dynamics.knowledge.wave_verdict_ingestion import derive_wave_verdict

    seed = bi.derive_belief_record(_belief())
    updated = bu.version_from_record(seed, signal="confirm", now=_dt(9))
    other_belief = bi.derive_belief_record(
        _belief(hypothesis="container seams take ~4 waves", domain="workstream-convergence")
    )
    session = derive_session_record(
        {"session_date": "2026-09-04", "slug": "s4b", "waves_run": []}
    )
    verdict = derive_wave_verdict(
        {
            "spec_name": "self_knowledge_layer",
            "run_id": "run-zzz",
            "state": "succeeded",
            "ok": True,
            "total_cost_usd": 1.0,
        },
        None,
    )
    for record in (seed, updated, other_belief, session, verdict):
        _write_artifact(tmp_path, record)

    current = _index(tmp_path)
    assert len(current) == 2  # the two belief entities; the session + verdict are foreign
    anchor = "workstream-convergence|flash converges in ~1 wave on in-process work"
    kid, payload = current[anchor]
    assert kid == updated.knowledge_id  # the newest version of the SAME entity
    assert payload["n_confirmations"] == 1
    # Entity-scope: the belief index only ever resolves AIO org-root belief/v1 artifacts.
    assert bu.scan_belief_payloads(artifact_dir=tmp_path)[0]  # no anomaly warnings


# ── the trigger: a verdict consults the belief index ─────────────


def test_a_verdict_updates_the_hypothesis_it_bears_on(tmp_path):
    # A verdict for a wave a belief's citations name BEARS ON that belief: the trigger updates
    # it in place (confirm for a green verdict — the positive-form default) and never duplicates
    # the entity.
    seed = bi.derive_belief_record(_belief())
    _write_artifact(tmp_path, seed)

    result = _apply(_verdict(), tmp_path)

    assert result.spec_name == "self_knowledge_layer"
    assert result.consulted == 1
    assert result.bearing == 1
    assert result.unrelated == 0
    assert len(result.updated) == 1
    updated = result.updated[0]
    assert updated.entity_id == seed.entity_id  # in place
    assert updated.supersedes == seed.knowledge_id
    body = _body(updated)
    assert body["n_confirmations"] == 1
    assert body["posterior_confidence"] == 0.666667
    assert body["evidence_citations"][-1] == "self_knowledge_layer wave verdict run-99aaaa1111"
    # The durable corpus then holds ONE entity whose current version is the update (the seed's
    # own bytes are untouched — it is the predecessor, not a duplicate).
    _write_artifact(tmp_path, updated)
    current = _index(tmp_path)
    assert len(current) == 1
    assert next(iter(current.values()))[1]["n_confirmations"] == 1


def test_an_unrelated_outcome_updates_nothing(tmp_path):
    # DONE_WHEN half: an outcome NO belief cites (a wave whose name appears in no hypothesis's
    # evidence_citations) consults the index and updates NOTHING — the durable belief is
    # byte-identical before and after, and no new version is written.
    seed = bi.derive_belief_record(_belief())  # cites self_knowledge_layer + kb_finding_layer
    seed_path = _write_artifact(tmp_path, seed)
    before = seed_path.read_bytes()

    result = _apply(
        _verdict(spec_name="some_other_wave", run_id="run-other0000", verdict="merge-ready"), tmp_path
    )

    assert result.consulted == 1
    assert result.bearing == 0
    assert result.unrelated == 1
    assert result.updated == []
    assert seed_path.read_bytes() == before  # nothing updated, nothing rewritten
    assert _index(tmp_path)[next(iter(_index(tmp_path)))][1]["n_confirmations"] == 0


def test_a_disconfirming_verdict_lowers_the_posterior_via_the_trigger(tmp_path):
    # "a disconfirm lowers the posterior" — through the trigger: a ``not`` verdict on a wave the
    # belief cites applies a DISCONFIRM (the default positive-form polarity).
    seed = bi.derive_belief_record(_belief())
    _write_artifact(tmp_path, seed)

    result = _apply(_verdict(verdict="not", run_id="run-99aaaa1111"), tmp_path)
    assert len(result.updated) == 1
    body = _body(result.updated[0])
    assert body["n_disconfirmations"] == 1
    assert body["posterior_confidence"] == 0.333333
    assert body["posterior_confidence"] < 0.5


def test_reapplying_the_same_runs_verdict_is_not_double_counted(tmp_path):
    # Rerun-safe: once a run's verdict has updated a belief (its citation now names the run), a
    # re-application of the SAME outcome — a re-drain, a re-run of the terminal write — must
    # not increment the same hypothesis twice.
    seed = bi.derive_belief_record(_belief())
    _write_artifact(tmp_path, seed)

    first = _apply(_verdict(), tmp_path)
    assert len(first.updated) == 1
    for record in first.updated:
        _write_artifact(tmp_path, record)  # the update lands durably

    second = _apply(_verdict(), tmp_path)
    assert second.updated == []
    assert second.already_counted == 1
    assert _index(tmp_path)[next(iter(_index(tmp_path)))][1]["n_confirmations"] == 1


def test_a_new_run_of_the_same_wave_bears_on_the_belief_again(tmp_path):
    # Wave-level citations (no run id) leave the door open for a NEW run of the same spec: each
    # distinct run's verdict is one more observation in the evidence series.
    seed = bi.derive_belief_record(
        _belief(evidence_citations=["self_knowledge_layer wave verdict", "kb_finding_layer wave verdict"])
    )
    _write_artifact(tmp_path, seed)

    first = _apply(_verdict(run_id="run-aaaa0000"), tmp_path)
    assert len(first.updated) == 1
    for record in first.updated:
        _write_artifact(tmp_path, record)  # the first update is durable before the second lands
    # A second run of the same wave completes at a LATER instant — a distinct outcome, stamped
    # at its own completion time (never the same last_updated as the first).
    second = _apply(
        _verdict(run_id="run-bbbb0000"), tmp_path, observed_at="2026-09-04T13:00:00+00:00"
    )
    assert len(second.updated) == 1
    assert second.updated[0].supersedes == first.updated[0].knowledge_id  # chained in place
    for record in second.updated:
        _write_artifact(tmp_path, record)
    payload = _index(tmp_path)[next(iter(_index(tmp_path)))][1]
    assert payload["n_confirmations"] == 2  # ONE record with n=2, two distinct outcomes
    assert payload["posterior_confidence"] == 0.75


def test_signal_fn_overrides_the_default_polarity(tmp_path):
    # Polarity is the AIO's judgment: a negatively-phrased hypothesis inverts the default (a
    # green verdict can DISCONFIRM a pessimist seed) via signal_fn.
    seed = bi.derive_belief_record(_belief())
    _write_artifact(tmp_path, seed)

    result = _apply(
        _verdict(), tmp_path, signal_fn=lambda payload, verdict: "disconfirm"
    )
    assert len(result.updated) == 1
    body = _body(result.updated[0])
    assert body["n_disconfirmations"] == 1
    assert body["posterior_confidence"] == 0.333333


def test_verdict_signal_maps_the_verdict_vocabulary():
    assert bu.verdict_signal("merge-ready") == "confirm"
    assert bu.verdict_signal("clean") == "confirm"
    assert bu.verdict_signal("not") == "disconfirm"


# ── s4b — the run-completion wiring (scripts/run_workflow.py's terminal write) ──
# ════════════════════════════════════════════════════════════════════════════════════════════
#
# The trigger's home is the s3b emission path: at run completion the emitted wave verdict
# consults the belief index and updates the hypotheses it bears on, in the SAME atomic
# terminal transaction that emits the verdict. These cases drive the REAL
# ``scripts/run_workflow._control_terminal_write`` hermetically (the test_wave_verdicts
# technique — importlib, redirected control db + KB dir + registry index, fake stream, stubbed
# spec index), with a durable belief seeded in the redirected KB dir.

EMIT_NOW = "2026-09-04T12:00:00+00:00"


def _load_script(rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent.parent / rel_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _emit_spec(name: str = "wave_emit_test") -> "object":
    from agentic_dynamics.experiment.experiment_spec import (
        ExperimentSpec,
        StopSpec,
        Workflow,
    )

    return ExperimentSpec(
        name=name,
        question="does the s4b belief trigger fire at the terminal write",
        version="0.1",
        workflow=Workflow(
            kind="agent_task", params={"model_pool": ["deepseek/deepseek-v4-flash"]}
        ),
        factors=[],
        design="factorial",
        stop=StopSpec(budget_usd=10.0, max_attempts=1),
    )


def _emit_result(*, spec_name: str = "wave_emit_test", ok: bool = True) -> "object":
    from agentic_dynamics.runtime.workflow_runner import PhaseResult, WorkflowRunResult

    n_phases = 8
    statuses = ["ok"] * n_phases
    if not ok:
        statuses[-1] = "failed"
    phases = [
        PhaseResult(
            phase=f"p{i}",
            kind="agent",
            status=statuses[i],
            model="deepseek/deepseek-v4-flash",
            commit_hash=f"c{i}",
            cost_usd=1.0 / n_phases,
        )
        for i in range(n_phases)
    ]
    return WorkflowRunResult(
        spec_name=spec_name,
        spec_id=f"{spec_name}@0.1",
        model="deepseek/deepseek-v4-flash",
        workdir="/tmp/x",
        goal="build it",
        git_sha="c7",
        started_at=EMIT_NOW,
        ended_at=EMIT_NOW,
        run_id="run-77f7b899f4f8",
        parent_run_id="",
        family_id="run-77f7b899f4f8",
        awaiting=False,
        phases=phases,
    )


class _EmitArgs:
    """The argparse namespace the terminal write reads (facts off — verdict + beliefs only)."""

    workdir = "/tmp/x"
    model = "deepseek/deepseek-v4-flash"
    only_phase = None
    no_fact_emit = True
    resume = False


class _FakeRedis:
    """The minimal handle the publisher's checkpoint reads need."""

    def __init__(self):
        self._checkpoint: dict[str, str] = {}

    def hget(self, key, field):
        return self._checkpoint.get(field)

    def hset(self, key, field, value):
        self._checkpoint[field] = value


@pytest.fixture
def emit_env(tmp_path, monkeypatch):
    """Redirect every durable path the terminal write touches, and stub the spec-index read."""
    rw = _load_script("scripts/run_workflow.py", "run_workflow_under_test_belief")
    monkeypatch.setattr(rw, "ROOT", tmp_path)
    monkeypatch.setenv("FINOPS_CONTROL_DB", str(tmp_path / "control" / "control.db"))
    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setattr(
        "agentic_dynamics.core.paths.REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl"
    )
    monkeypatch.setattr(rw.si, "load_index_entries", lambda **kw: [])
    return rw, tmp_path


def _mint_run(rw, spec) -> str:
    run_id, db = rw._control_open_run(spec, _EmitArgs())
    if db is not None:
        db.close()
    return run_id


def _seed_belief(kb_dir, *, spec_name: str) -> "object":
    """Write a durable org-root belief citing ``spec_name``'s wave into the redirected KB dir."""
    seed = bi.derive_belief_record(
        _belief(
            evidence_citations=[f"{spec_name} wave verdict"],
        )
    )
    _write_artifact(kb_dir, seed)
    return seed


def _belief_artifacts(kb_dir) -> list[Path]:
    out = []
    for path in sorted((kb_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("extractor_version") == bi.EXTRACTOR_VERSION:
            out.append(path)
    return out


def _outbox_delivered(tmp_path, run_id) -> tuple:
    from agentic_dynamics.control.control_db import ControlDB
    from agentic_dynamics.control.outbox import summarize

    db = ControlDB.open_read_only(tmp_path / "control" / "control.db")
    try:
        summary = summarize(db, run_id=run_id)
        state = db.get_run(run_id).state
    finally:
        db.close()
    return state, summary


def _drive_terminal_write(rw, tmp_path, monkeypatch, spec, result, *, run_id) -> list:
    """Run the real terminal write against the hermetic env; return the captured events."""
    from agentic_dynamics.knowledge import knowledge_stream as real_ks

    fake_redis = _FakeRedis()
    published: list = []
    monkeypatch.setattr(real_ks, "connect", lambda *a, **kw: fake_redis)
    monkeypatch.setattr(real_ks, "publish_event", lambda r, e, **kw: published.append(e) or "1-0")
    rw._control_terminal_write(
        spec, _EmitArgs(), result, run_id=run_id, ledger_path=Path("/tmp/ledger.json")
    )
    return published


def test_a_completed_run_updates_the_belief_its_verdict_bears_on(emit_env, monkeypatch):
    # The DONE_WHEN at the emission seam: a completed run whose emitted wave verdict bears on a
    # durable belief (its citations name this wave) updates that belief in the SAME terminal
    # transaction that emits the verdict — ONE entity, n=1, superseding the seed — default-on.
    rw, tmp_path = emit_env
    kb_dir = tmp_path / "kb"
    spec = _emit_spec()
    seed = _seed_belief(kb_dir, spec_name=spec.name)
    result = _emit_result()
    run_id = _mint_run(rw, spec)
    result.run_id = run_id

    published = _drive_terminal_write(rw, tmp_path, monkeypatch, spec, result, run_id=run_id)

    artifacts = _belief_artifacts(kb_dir)
    assert len(artifacts) == 2  # the seed + one superseding version — never a duplicate entity
    supersede = [p for p in artifacts if p.name != f"{seed.knowledge_id}.json"]
    assert len(supersede) == 1
    payload = json.loads(json.loads(supersede[0].read_text())["text"])
    assert payload["n_confirmations"] == 1  # the green verdict confirmed the hypothesis
    assert payload["posterior_confidence"] == 0.666667
    assert payload["evidence_citations"][-1] == f"{spec.name} wave verdict {run_id}"
    # The emitted supersede event is in the transaction's stream (operation supersede).
    supersede_events = [e for e in published if e.operation == "supersede"]
    assert len(supersede_events) == 1
    assert supersede_events[0].knowledge_id == supersede[0].stem
    # The index now resolves the updated version (n=1) as the ONE current record.
    current = _index(kb_dir)
    assert len(current) == 1
    assert next(iter(current.values()))[1]["n_confirmations"] == 1

    from agentic_dynamics.control.control_db import RunState

    state, summary = _outbox_delivered(tmp_path, run_id)
    assert state is RunState.PROMOTABLE
    assert summary.delivered == 2 and summary.pending == 0  # the verdict + the belief update


def test_an_unrelated_run_emits_its_verdict_but_updates_no_belief(emit_env, monkeypatch):
    # An outcome no belief cites updates NOTHING — the run still emits its verdict (s3b), the
    # belief index is consulted, and the durable belief stays byte-identical.
    rw, tmp_path = emit_env
    kb_dir = tmp_path / "kb"
    spec = _emit_spec()
    seed = _seed_belief(kb_dir, spec_name="some_other_wave")  # cites a DIFFERENT wave
    seed_path = kb_dir / f"{seed.knowledge_id}.json"
    before = seed_path.read_bytes()
    result = _emit_result()
    run_id = _mint_run(rw, spec)
    result.run_id = run_id

    published = _drive_terminal_write(rw, tmp_path, monkeypatch, spec, result, run_id=run_id)

    assert seed_path.read_bytes() == before
    assert _belief_artifacts(kb_dir) == [seed_path]  # no new belief version written
    assert [e for e in published if e.operation == "supersede"] == []

    from agentic_dynamics.control.control_db import RunState

    state, summary = _outbox_delivered(tmp_path, run_id)
    assert state is RunState.PROMOTABLE
    assert summary.delivered == 1 and summary.pending == 0  # the verdict only
