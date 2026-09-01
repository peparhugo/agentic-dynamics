"""Tests for CAP addendum I9 — the ``pattern`` fact kind (``control/reducers/pattern.py``, D7).

Covers the design's own obligations (§3, D7): (1) ``pattern`` is a FACT KIND carried by
``FACT_PREDICATES``, not a new ``EPISTEMIC_MAP`` row — every pattern fact's epistemic status is
the EXISTING ``"derived"`` row; (2) the ``pattern/v1`` reducer mines real ``finding`` records
from the canonical corpus into a well-formed, ``verify_chain``-clean, canonical DERIVED fact,
never fabricating support for an empty slice; (3) an LLM-proposed pattern is ADVISORY and
therefore structurally uncitable (``is_canonical()`` False, validator check C5 refuses it); (4)
re-deriving the same evidence set is byte-for-byte stable, regardless of input order.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.context_compiler import ContractSpec, ControlContext
from agentic_dynamics.control.decisions import ControlDecision
from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    Authority,
    CanonicalFact,
    EvidenceItem,
    FactRef,
    PatternPayload,
    ReducerInput,
    is_canonical,
    recompute_inputs_digest,
    verify_chain,
)
from agentic_dynamics.control.reducers import REDUCERS, get_reducer
from agentic_dynamics.control.reducers.pattern import (
    MIN_SUPPORT_FOR_UNCERTAINTY,
    PATTERN_V1,
    decode_pattern_payload,
    pattern_v1,
)
from agentic_dynamics.control.validator import validate_decision
from agentic_dynamics.reporting import canonical_corpus

pytestmark = pytest.mark.fast

NOW = "2026-08-24T00:00:00+00:00"
REPO = "agentic-dynamics"
WORKLOAD = "task_manager"
CELL = "wf_task_manager_deepseek_v4_pro"


# ── fixtures: synthetic-but-real-shaped finding rows ────────────────
#
# Mirrors canonical_corpus.resolve_findings' actual output shape (verified against
# experiments/results/task_manager_deepseek-v4-pro.json): `_table`/`_registry` (the
# lab_contract.record_id provenance), `_experiment` (the task), `perturbation_class` (the
# operator family), `test_executed_success` (the measured outcome).


def _finding(
    *,
    knowledge_id: str,
    experiment: str = "task_manager",
    perturbation_class: str = "objective_mutation",
    test_executed_success: bool | None,
) -> dict:
    return {
        "_table": "finding",
        "_registry": {"entity_id": f"entity_{knowledge_id}", "knowledge_id": knowledge_id},
        "_experiment": experiment,
        "perturbation_class": perturbation_class,
        "operator": "invert_constraint",
        "test_executed_success": test_executed_success,
        "confidence": 0.5,
        "perturbation_strength": 0.5,
    }


def _evidence(rows: list[dict]) -> tuple[EvidenceItem, ...]:
    return tuple(
        EvidenceItem(source_type="finding", evidence_id=r["_registry"]["knowledge_id"], payload=r)
        for r in rows
    )


def _reducer_input(rows: list[dict], *, source_revision: str = "abc123") -> ReducerInput:
    return ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=_evidence(rows),
        facts=(),
        now=NOW,
        source_revision=source_revision,
    )


# ── (0) `pattern` is a fact KIND, not an EPISTEMIC_MAP row (D7) ─────


def test_no_new_epistemic_map_row_was_added():
    assert set(EPISTEMIC_MAP) == {"observed", "verified", "derived", "declared", "advisory"}


def test_pattern_predicate_uses_the_existing_derived_row():
    spec = FACT_PREDICATES["pattern"]
    assert spec.produced_by == ("pattern/v1",)
    assert spec.abstraction_level == "workload"
    assert spec.scope_type == "workload"
    assert spec.value_type == "str"
    assert spec.inheritable is True


def test_pattern_v1_is_registered():
    assert REDUCERS[PATTERN_V1.version] is PATTERN_V1
    assert get_reducer(PATTERN_V1.version) is pattern_v1
    assert PATTERN_V1.produces == ("pattern",)
    assert PATTERN_V1.level == "workload"


def test_pattern_projection_is_a_scoped_typed_view_of_the_registered_fact():
    rows = [
        _finding(knowledge_id="k1", test_executed_success=True),
        _finding(knowledge_id="k2", test_executed_success=False),
        _finding(knowledge_id="k3", test_executed_success=True),
    ]
    fact = pattern_v1(_reducer_input(rows))[0]
    fact_record = fi.build_fact_record(fact)
    projection = fi.build_pattern_projection_record(
        fact,
        source_fact_id=fact_record.knowledge_id,
        now=None,
    )

    assert projection.source_type == "pattern"
    assert projection.authority is Authority.DERIVED
    assert projection.evidence_class == "[C]"
    assert projection.source_fact_id == fact_record.knowledge_id
    assert projection.evidence_ids == tuple(fact.evidence_ids)
    assert projection.pattern_payload == decode_pattern_payload(fact.value)
    assert projection.entity_id == f"pattern-projection:{fact.fact_entity_id}"
    assert "predicate" not in projection.text
    replay = fi.build_pattern_projection_record(fact, source_fact_id=fact_record.knowledge_id)
    assert replay.knowledge_id == projection.knowledge_id
    assert replay.content_hash == projection.content_hash


# ── (1) a pattern derived from real campaign records ────────────────


def test_pattern_derived_from_real_records():
    rows = [
        _finding(knowledge_id="k1", test_executed_success=True),
        _finding(knowledge_id="k2", test_executed_success=True),
        _finding(knowledge_id="k3", test_executed_success=True),
        _finding(knowledge_id="k4", test_executed_success=False),
    ]
    facts = pattern_v1(_reducer_input(rows))
    assert len(facts) == 1
    fact = facts[0]

    assert fact.predicate == "pattern"
    assert fact.subject_type == "workload"
    assert fact.scope_type == "workload"
    assert fact.abstraction_level == "workload"
    assert fact.epistemic_status == "derived"
    assert fact.authority is Authority.DERIVED
    assert fact.evidence_class == "[C]"
    assert EPISTEMIC_MAP[fact.epistemic_status] == (fact.authority, fact.evidence_class)
    assert fact.reducer_version == "pattern/v1"
    assert len(fact.evidence_ids) == 4  # every real record cited

    payload = decode_pattern_payload(fact.value)
    assert payload.claim == "recovers_under_objective_mutation"
    assert payload.population == "finding:task=task_manager,perturbation_class=objective_mutation"
    assert payload.conditions == ("test_executed_success=true",)
    assert payload.support == 3  # a real COUNT — 3 of the 4 rows measured True
    assert payload.validity_window == "abc123"
    assert payload.source_experiment in fact.evidence_ids
    assert payload.source_experiment == min(fact.evidence_ids)  # deterministic pick

    # 4 real observations >= MIN_SUPPORT_FOR_UNCERTAINTY -> a real, bounded statistic.
    assert payload.uncertainty is not None
    assert 0.0 <= payload.uncertainty <= 1.0

    # Only a registered deterministic reducer minted this fact (hard rule 3, D3) — both gates.
    assert is_canonical(fact)
    assert verify_chain(fact, REDUCERS) == []


def test_pattern_groups_by_task_and_perturbation_class_independently():
    rows = [
        _finding(knowledge_id="k1", experiment="task_manager", test_executed_success=True),
        _finding(knowledge_id="k2", experiment="static_site_gen", test_executed_success=False),
        _finding(
            knowledge_id="k3",
            experiment="task_manager",
            perturbation_class="specification_corruption",
            test_executed_success=True,
        ),
    ]
    facts = pattern_v1(_reducer_input(rows))
    populations = {decode_pattern_payload(f.value).population for f in facts}
    assert populations == {
        "finding:task=task_manager,perturbation_class=objective_mutation",
        "finding:task=static_site_gen,perturbation_class=objective_mutation",
        "finding:task=task_manager,perturbation_class=specification_corruption",
    }


# ── (1b) integration — mined from the REAL canonical corpus, not a fixture ──


def test_pattern_derived_from_the_real_canonical_corpus():
    """The corpus door this reducer actually reads (design §3.3/review constraint 4): the SAME
    ``canonical_corpus.load_canonical_tables("finding")`` every lab uses, never the retired
    ``_results_summary.json``. Skips (never fails) when the local registry has unresolved rows —
    a resolution gap is an environment fact, not a defect in this reducer."""
    tables = canonical_corpus.load_canonical_tables("finding")
    if tables.resolution.missing or tables.resolution.unreadable or tables.is_empty:
        pytest.skip("canonical corpus finding rows not resolvable in this environment")

    inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=tuple(
            EvidenceItem(
                source_type="finding",
                evidence_id=row["_registry"]["knowledge_id"],
                payload=row,
            )
            for row in tables.findings
        ),
        facts=(),
        now=NOW,
        source_revision="real-corpus-test",
    )
    facts = pattern_v1(inp)
    assert facts, "the real corpus has measured finding rows; at least one pattern must mint"
    for fact in facts:
        assert fact.predicate == "pattern"
        assert is_canonical(fact)
        assert verify_chain(fact, REDUCERS) == []
        payload = decode_pattern_payload(fact.value)
        assert payload.support >= 0
        assert payload.support <= len(fact.evidence_ids)
        assert payload.population.startswith("finding:task=")
        assert payload.source_experiment in fact.evidence_ids


# ── (2) uncertainty is None below the estimability floor ────────────


def test_uncertainty_is_none_below_min_support():
    rows = [
        _finding(knowledge_id="k1", test_executed_success=True),
        _finding(knowledge_id="k2", test_executed_success=False),
    ]
    assert len(rows) < MIN_SUPPORT_FOR_UNCERTAINTY
    facts = pattern_v1(_reducer_input(rows))
    assert len(facts) == 1
    payload = decode_pattern_payload(facts[0].value)
    assert payload.support == 1  # still a real count — support=0/1 is not "no data"
    assert payload.uncertainty is None


# ── (3) a pattern with no real support cannot be minted ─────────────


def test_empty_population_mints_no_fact():
    # No finding evidence at all.
    assert pattern_v1(_reducer_input([])) == []


def test_unmeasured_outcomes_alone_mint_no_fact():
    # Every row present, but none carries a REAL measured test_executed_success (the coverage
    # invariant: an unmeasured row is null, never coerced into a "non-match" or a phantom slice).
    rows = [
        _finding(knowledge_id="k1", test_executed_success=None),
        _finding(knowledge_id="k2", test_executed_success=None),
    ]
    assert pattern_v1(_reducer_input(rows)) == []


def test_rows_missing_slice_keys_mint_no_fact():
    row = _finding(knowledge_id="k1", test_executed_success=True)
    row["_experiment"] = ""  # unaddressable task
    assert pattern_v1(_reducer_input([row])) == []


def test_pattern_v1_ignores_non_finding_evidence():
    inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=(
            EvidenceItem(source_type="review", evidence_id="r1", payload={"story_id": "x"}),
            EvidenceItem(source_type="analysis", evidence_id="a1", payload={"foo": "bar"}),
        ),
        facts=(),
        now=NOW,
        source_revision="abc123",
    )
    assert pattern_v1(inp) == []


# ── duplicate records never double-count (r4-style dedup precedent) ─


def test_duplicate_finding_records_are_deduped_not_double_counted():
    row = _finding(knowledge_id="k1", test_executed_success=True)
    facts_once = pattern_v1(_reducer_input([row]))
    facts_dup = pattern_v1(_reducer_input([row, dict(row)]))  # the SAME record, handed in twice
    assert len(facts_dup) == 1
    payload_once = decode_pattern_payload(facts_once[0].value)
    payload_dup = decode_pattern_payload(facts_dup[0].value)
    assert payload_dup.support == payload_once.support == 1
    assert len(facts_dup[0].evidence_ids) == 1


# ── (4) re-derivation stability ──────────────────────────────────────


def test_re_derivation_from_the_same_evidence_is_byte_stable_regardless_of_order():
    rows = [
        _finding(knowledge_id="k1", test_executed_success=True),
        _finding(knowledge_id="k2", test_executed_success=True),
        _finding(knowledge_id="k3", test_executed_success=False),
    ]
    forward = pattern_v1(_reducer_input(rows))
    backward = pattern_v1(_reducer_input(list(reversed(rows))))
    assert len(forward) == len(backward) == 1
    a, b = forward[0], backward[0]
    assert a.fact_entity_id == b.fact_entity_id
    assert a.value == b.value
    assert a.evidence_ids == b.evidence_ids
    assert a.inputs_digest == b.inputs_digest


def test_re_deriving_the_same_slot_twice_is_idempotent():
    rows = [
        _finding(knowledge_id="k1", test_executed_success=True),
        _finding(knowledge_id="k2", test_executed_success=False),
        _finding(knowledge_id="k3", test_executed_success=True),
    ]
    a = pattern_v1(_reducer_input(rows))[0]
    b = pattern_v1(_reducer_input(rows))[0]
    assert a == b


# ── verify_chain: a tampered pattern fails the mandatory chain check (D3) ─


def test_verify_chain_refuses_a_pattern_from_an_unregistered_reducer():
    rows = [_finding(knowledge_id="k1", test_executed_success=True) for _ in range(1)]
    fact = pattern_v1(_reducer_input(rows))[0]
    tampered = replace(fact, reducer_version="not_a_real_reducer/v1")
    tampered = replace(tampered, inputs_digest=recompute_inputs_digest(tampered))
    errors = verify_chain(tampered, REDUCERS)
    assert any("not registered" in e for e in errors)


# ── (5) an ADVISORY (LLM-proposed) pattern is structurally uncitable ─


def _advisory_pattern_fact() -> CanonicalFact:
    """An LLM's own proposal for a pattern — never minted by ``pattern_v1`` (hard rule 3's
    "an LLM may propose a pattern only as ADVISORY", design §3.4 rule 2)."""
    payload = PatternPayload(
        claim="llm_guessed_pattern",
        population="finding:task=task_manager,perturbation_class=objective_mutation",
        conditions=("test_executed_success=true",),
        support=999,  # an LLM's unverified assertion — never counted against real rows
        uncertainty=None,
        validity_window="unrevisioned",
        source_experiment="finding:entity_x:k1",
    )
    from agentic_dynamics.control.reducers.pattern import _payload_to_json  # test-only peek

    spec = FACT_PREDICATES["pattern"]
    fact = CanonicalFact(
        fact_entity_id="entity_pattern_advisory",
        fact_id="fact_pattern_advisory",
        subject_type="workload",
        subject_id="pattern/task_manager/objective_mutation",
        predicate="pattern",
        value=_payload_to_json(payload),
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="workload",
        scope_id="pattern/task_manager/objective_mutation",
        scope_path=f"org:{REPO}/workload:{WORKLOAD}",
        abstraction_level=spec.abstraction_level,
        epistemic_status="advisory",
        authority=Authority.ADVISORY,
        evidence_class="[H]",
        observed_at=NOW,
        valid_from=NOW,
        valid_to=None,
        expires_at=None,
        reducer="advisor",
        reducer_version="advisor:claude/v1",  # NOT a registered reducer — an LLM's own proposal
        evidence_ids=(),
        inputs_digest="",
        supersedes=None,
        source_revision="abc123",
        repository_id=REPO,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def test_advisory_pattern_is_never_canonical():
    fact = _advisory_pattern_fact()
    assert not is_canonical(fact)


def test_advisory_pattern_fails_verify_chain_too():
    # Belt and braces (design D3): even if something mistakenly treated it as canonical,
    # verify_chain refuses it too — its reducer_version is not in REDUCERS.
    errors = verify_chain(_advisory_pattern_fact(), REDUCERS)
    assert any("not registered" in e for e in errors)


def test_advisory_pattern_proposal_is_uncitable_by_validate_decision_c5():
    fact = _advisory_pattern_fact()
    advisory_ref = FactRef(
        fact_id=fact.fact_id,
        predicate=fact.predicate,
        subject_id=fact.subject_id,
        scope_path=fact.scope_path,
        value=fact.value,
        value_type=fact.value_type,
        authority=fact.authority.name,
        epistemic_status=fact.epistemic_status,
        observed_at=fact.observed_at,
        age_seconds=0,
        reducer_version=fact.reducer_version,
        evidence_ids=fact.evidence_ids,
    )
    scope_path = f"org:{REPO}/workload:{WORKLOAD}/job:{CELL}"
    contract = ContractSpec(
        decision_type="pattern_citation_test",
        contract_version="test/v1",
        decision_scope="job",
        allowed_actions=("route",),
        max_snapshot_age_seconds=None,
        invariants=(),
        objectives=(),
        requires_facts=(),
        excludes=(),
    )
    ctx = ControlContext(
        snapshot_id="snap_pattern_test",
        decision_type="pattern_citation_test",
        contract_version="test/v1",
        scope_path=scope_path,
        compiled_at=NOW,
        invariants=(),
        objectives=(),
        workload=(),
        workflow=(),
        job=(),
        resource=(),
        unknowns=(),
        conflicts=(),
        stale=(),
        advisory=(advisory_ref,),
        evidence_ids=(),
        admissible=True,
        refusal="",
    )
    decision = ControlDecision(
        decision_id="d_pattern_cite",
        snapshot_id=ctx.snapshot_id,
        decision_type=ctx.decision_type,
        contract_version=ctx.contract_version,
        action="route",
        target_type="job",
        target_id=CELL,
        parameters={"model": "anthropic/claude-haiku-4-5"},
        facts_used=(fact.fact_id,),  # citing the ADVISORY pattern proposal
        proposed_by="advisor:claude",
        proposed_at=NOW,
    )
    result = validate_decision(
        decision, snapshot=ctx, fresh_snapshot=ctx, contract=contract, now=NOW
    )
    assert result.admitted is False
    assert result.check == "C5"
    assert "ADVISORY" in result.reason


# ── ACCEPTED LIMITATION (adversarial release verdict, attack 2 — implementation_notes.md §17):
# verify_chain never re-derives a fact's VALUE from its cited evidence, so a fabricated
# support/uncertainty riding on genuine evidence_ids/reducer_version passes every structural
# check. This is an INHERITED I0 property (`facts.recompute_inputs_digest`'s own docstring: "the
# design's formula is sha256(evidence_ids | reducer_version | input VALUES)... I0 hashes [only]
# the input IDENTITIES... the 'input values' term... is not part of this self-contained check"),
# not something D3's mandatory-verify_chain rule closes — D3 only makes verify_chain MANDATORY
# for the pattern class, it does not change what verify_chain itself checks. Documented here,
# not fixed: closing it needs a resolver that returns full evidence PAYLOADS (not just registry
# metadata) so pattern_v1 could be re-run and compared — that resolver doesn't exist anywhere in
# this plane yet (the same producer-wiring gap already noted for pattern_v1 itself, module
# docstring's "Deliberately NOT done" section) — building one is out of I9's reserved home
# (`control/reducers/pattern.py`, `control/facts.py`'s additive rows) and would touch shared I0
# infrastructure (`facts.verify_chain`/`recompute_inputs_digest`) well beyond this review's scope.


def test_known_limitation_verify_chain_does_not_catch_a_fabricated_value_on_real_evidence_ids():
    """Pins the gap so a future fix to ``verify_chain``/``recompute_inputs_digest`` is forced to
    either update this test or close the gap on purpose — never silently regress it further.

    Builds a REAL pattern fact via ``pattern_v1`` (support=1 of 4, per the reducer's own honest
    count), then constructs a FABRICATED sibling that keeps the real fact's ``evidence_ids``/
    ``reducer_version``/``epistemic_status``/``authority`` verbatim (so every structural check
    that ``verify_chain``/``is_canonical`` actually performs stays internally consistent) but
    swaps in a claim of ``support=4`` (all four records "succeeded") — the opposite of what the
    cited evidence shows. If this assertion ever starts FAILING (i.e. ``verify_chain`` starts
    reporting errors, or ``is_canonical`` starts returning ``False``), the limitation has been
    closed — update this test's docstring/assertions to match, do not just delete it.
    """
    from agentic_dynamics.control.reducers.pattern import _payload_to_json

    rows = [
        _finding(knowledge_id="k1", test_executed_success=True),
        _finding(knowledge_id="k2", test_executed_success=False),
        _finding(knowledge_id="k3", test_executed_success=False),
        _finding(knowledge_id="k4", test_executed_success=False),
    ]
    real_fact = pattern_v1(_reducer_input(rows))[0]
    real_payload = decode_pattern_payload(real_fact.value)
    assert real_payload.support == 1  # the honest count: 1 of 4 rows measured True

    fabricated_payload = PatternPayload(
        claim=real_payload.claim,
        population=real_payload.population,
        conditions=real_payload.conditions,
        support=4,  # FABRICATED — claims all 4 succeeded; the real count is 1
        uncertainty=0.01,  # FABRICATED — a suspiciously tight interval to match the false claim
        validity_window=real_payload.validity_window,
        source_experiment=real_payload.source_experiment,
    )
    fabricated = replace(real_fact, value=_payload_to_json(fabricated_payload))
    # evidence_ids/reducer_version were NEVER touched, so the digest — which hashes only those,
    # never `value` — still "reproduces": the tamper is invisible to check 3.
    assert recompute_inputs_digest(fabricated) == fabricated.inputs_digest

    # KNOWN LIMITATION: both of these SHOULD ideally refuse the fabricated fact; neither does.
    assert verify_chain(fabricated, REDUCERS) == []
    assert is_canonical(fabricated) is True
