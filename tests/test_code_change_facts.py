"""Tests for code_change_facts/v1 (design §5.6 — e5 of cap_evidence_integrity).

Covers the reducer's ten predicates: status enums, defined denominators, zero-change behavior,
null-not-zero omission (unavailable analyzers never yield fabricated zero counts), the DEFERRED
TESTED_BY ratio, the [P]-weighted renormalized risk formula, and the verify_code_change/v1
contract (loads, passes the R1-R11 gate, and compiles admissible through the real
``compile_context``).
"""

from dataclasses import replace

import pytest

from agentic_dynamics.control.context_compiler import (
    CONTRACTS_DIR,
    ContextRequest,
    InMemoryFactStore,
    compile_context,
    load_contract,
    validate_spec_fact_contracts,
)
from agentic_dynamics.control.facts import (
    FACT_PREDICATES,
    CanonicalFact,
    EvidenceItem,
    ReducerInput,
    compute_fact_entity_id,
    recompute_inputs_digest,
)
from agentic_dynamics.control.reducers import REDUCERS, get_reducer
from agentic_dynamics.control.reducers.code_change_facts import (
    CODE_CHANGE_FACTS_V1,
    code_change_facts_v1,
)
from agentic_dynamics.core.language import (
    _PROFILES,
    build_code_snapshot,
    compute_code_delta,
)

PY = _PROFILES["python"]
NOW = "2026-08-25T00:10:00+00:00"
REPO = "agentic-dynamics"
CELL = "wf_evidence_integrity_flash"
JOB_SCOPE = f"org:{REPO}/workload:cap_evidence_integrity/job:{CELL}"


def _inp(*items) -> ReducerInput:
    return ReducerInput(
        scope_path=JOB_SCOPE,
        scope_type="job",
        scope_id=CELL,
        repository_id=REPO,
        evidence=items,
        facts=(),
        now=NOW,
        source_revision="rev-2",
    )


def _delta():
    before = build_code_snapshot(
        {
            "math_utils.py": b"def add(a, b):\n    return a + b\n",
            "test_math_utils.py": b"def test_add():\n    assert True\n",
        },
        revision="rev-1",
        profile=PY,
    )
    after = build_code_snapshot(
        {
            "math_utils.py": b"def add(a, b):\n    return a * b\n\ndef top():\n    return add(1, 2)\n",
            "test_math_utils.py": b"def test_add():\n    assert True\n",
        },
        revision="rev-2",
        profile=PY,
    )
    return compute_code_delta(before, after)


def _full_evidence():
    delta = _delta()
    return (
        EvidenceItem(source_type="code_delta", evidence_id="delta-1", payload=delta),
        EvidenceItem(
            source_type="sonar_analysis", evidence_id="sonar-1",
            payload={"status": "available", "revision_matches": True,
                     "new_critical_count": 2, "analyzed_sha": "rev-2"},
        ),
        EvidenceItem(
            source_type="lsp_analysis", evidence_id="lsp-1",
            payload={"status": "available", "new_error_count": 3, "tool": "pyright"},
        ),
        EvidenceItem(source_type="impacted_symbols", evidence_id="imp-1", payload={"count": 5}),
    )


def _facts_by_predicate(facts):
    return {f.predicate: f for f in facts}


# ── The reducer: full fixture ───────────────────────────────────


def test_full_fixture_produces_all_measurable_facts():
    facts = code_change_facts_v1(_inp(*_full_evidence()))
    by = _facts_by_predicate(facts)

    assert by["sonar_analysis_status"].value == "available"
    assert by["lsp_analysis_status"].value == "available"
    assert by["analysis_revision_matches"].value == "true"
    # changed: add (edited) + top (added) = 2; test_add unchanged.
    assert by["changed_symbol_count"].value == "2"
    assert by["impacted_symbol_count"].value == "5"
    assert by["new_lsp_error_count"].value == "3"
    assert by["new_sonar_critical_count"].value == "2"
    # add/top are in math_utils.py, which has a matching test file → ratio = 2/2 = 1.0.
    assert float(by["changed_symbols_with_tests_ratio"].value) == 1.0
    # ast_parse_coverage: 1 changed file, fully parsed.
    assert float(by["ast_parse_coverage"].value) == 1.0
    # risk = 0.35*.2 + 0.25*.3 + 0.20*(1-1.0) + 0.20*.5 = 0.245
    assert float(by["code_change_risk"].value) == pytest.approx(0.245)

    # Every fact is DERIVED ([C]) and job-scoped.
    for fact in facts:
        assert fact.epistemic_status == "derived"
        assert fact.evidence_class == "[C]"
        assert fact.scope_type == "job"
        assert fact.reducer_version == CODE_CHANGE_FACTS_V1.version


def test_all_facts_registered_and_produced_by_reducer():
    from agentic_dynamics.control.reducers.code_change_facts import CODE_CHANGE_PREDICATES

    for predicate in CODE_CHANGE_PREDICATES:
        assert predicate in FACT_PREDICATES
        assert "code_change_facts/v1" in FACT_PREDICATES[predicate].produced_by
    assert REDUCERS[CODE_CHANGE_FACTS_V1.version].produces == CODE_CHANGE_PREDICATES
    assert get_reducer(CODE_CHANGE_FACTS_V1.version) is code_change_facts_v1


# ── Unavailable analyzers omit counts (null-not-zero) ───────────


def test_unavailable_lsp_omits_counts_and_renormalizes_risk():
    items = list(_full_evidence())
    items[2] = EvidenceItem(
        source_type="lsp_analysis", evidence_id="lsp-1",
        payload={"status": "unavailable", "new_error_count": None, "tool": "pyright"},
    )
    facts = code_change_facts_v1(_inp(*items))
    by = _facts_by_predicate(facts)

    assert by["lsp_analysis_status"].value == "unavailable"
    assert "new_lsp_error_count" not in by  # OMITTED — never a fabricated zero
    assert "code_change_risk" in by
    # Terms: sonar (w .35) + tests (w .20) + impacted (w .20); sum w = .75.
    # (0.35*.2 + 0.20*0 + 0.20*.5) / .75 = (0.07 + 0.1)/.75 = 0.226666...
    assert float(by["code_change_risk"].value) == pytest.approx(0.2267, abs=1e-3)


def test_stale_refused_sonar_emits_status_and_marks_revision_mismatch():
    items = list(_full_evidence())
    items[1] = EvidenceItem(
        source_type="sonar_analysis", evidence_id="sonar-1",
        payload={"status": "stale-refused", "revision_matches": False,
                 "new_critical_count": None, "analyzed_sha": "deadbeef"},
    )
    facts = code_change_facts_v1(_inp(*items))
    by = _facts_by_predicate(facts)

    assert by["sonar_analysis_status"].value == "stale-refused"
    assert by["analysis_revision_matches"].value == "false"
    assert "new_sonar_critical_count" not in by  # refused -> omitted, never zero


def test_no_measurable_risk_terms_yields_no_risk_fact():
    items = (
        EvidenceItem(source_type="code_delta", evidence_id="delta-1", payload=_delta()),
        EvidenceItem(
            source_type="sonar_analysis", evidence_id="sonar-1",
            payload={"status": "unavailable", "new_critical_count": None},
        ),
        EvidenceItem(
            source_type="lsp_analysis", evidence_id="lsp-1",
            payload={"status": "unavailable", "new_error_count": None},
        ),
        # No impacted set (graph unavailable), and no test file for the changed module would
        # defer the ratio — but here the delta HAS a test file, so the ratio is measurable.
    )
    # Drop the impacted evidence so only the tests-ratio term could remain; force deferral by
    # using a changed module with NO test file.
    before = build_code_snapshot({"m.py": b"def f():\n    pass\n"}, revision="rev-1", profile=PY)
    after = build_code_snapshot({"m.py": b"def f():\n    return 1\n"}, revision="rev-2", profile=PY)
    delta = compute_code_delta(before, after)  # no test file -> ratio deferred
    items = (EvidenceItem(source_type="code_delta", evidence_id="delta-1", payload=delta),) + items[1:]
    facts = code_change_facts_v1(_inp(*items))
    by = _facts_by_predicate(facts)

    assert "code_change_risk" not in by  # NO term measurable -> risk omitted (None), never 0
    assert "changed_symbols_with_tests_ratio" not in by  # deferred


# ── Deferred TESTED_BY ratio + zero-change behavior ─────────────


def test_ratio_deferred_when_no_test_file_links():
    before = build_code_snapshot({"m.py": b"def f():\n    pass\n"}, revision="rev-1", profile=PY)
    after = build_code_snapshot({"m.py": b"def f():\n    return 1\n"}, revision="rev-2", profile=PY)
    delta = compute_code_delta(before, after)
    items = (
        EvidenceItem(source_type="code_delta", evidence_id="delta-1", payload=delta),
        EvidenceItem(
            source_type="sonar_analysis", evidence_id="sonar-1",
            payload={"status": "available", "revision_matches": True, "new_critical_count": 1},
        ),
        EvidenceItem(
            source_type="lsp_analysis", evidence_id="lsp-1",
            payload={"status": "available", "new_error_count": 1},
        ),
    )
    facts = code_change_facts_v1(_inp(*items))
    by = _facts_by_predicate(facts)
    assert "changed_symbols_with_tests_ratio" not in by  # DEFERRED, never 0.0


def test_zero_change_omits_parse_coverage_denominator():
    before = build_code_snapshot({"m.py": b"def f():\n    pass\n"}, revision="rev-1", profile=PY)
    after = build_code_snapshot({"m.py": b"def f():\n    pass\n"}, revision="rev-2", profile=PY)
    delta = compute_code_delta(before, after)
    items = (EvidenceItem(source_type="code_delta", evidence_id="delta-1", payload=delta),)
    facts = code_change_facts_v1(_inp(*items))
    by = _facts_by_predicate(facts)
    assert "ast_parse_coverage" not in by  # changed_files == 0 -> no denominator, omitted
    assert by["changed_symbol_count"].value == "0"  # a real measured zero, not a fabricated one


def test_changed_but_unparseable_file_degrades_parse_coverage():
    before = build_code_snapshot({"m.py": b"def f():\n    pass\n"}, revision="rev-1", profile=PY)
    after = build_code_snapshot({"m.py": b"def f(:\n"}, revision="rev-2", profile=PY)
    delta = compute_code_delta(before, after)
    items = (EvidenceItem(source_type="code_delta", evidence_id="delta-1", payload=delta),)
    facts = code_change_facts_v1(_inp(*items))
    by = _facts_by_predicate(facts)
    # The delta tracks the unparseable file as changed (content hash differs), so the fact is
    # EMITTED with a degraded value — never omitted, never a structural 1.0 (review F1).
    assert float(by["ast_parse_coverage"].value) == 0.0
    assert by["changed_symbol_count"].value == "1"  # f is removed from the parseable surface


def test_parse_coverage_mixed_parsed_and_unparseable():
    before = build_code_snapshot(
        {"a.py": b"def f():\n    pass\n", "b.py": b"def g():\n    pass\n"},
        revision="rev-1", profile=PY,
    )
    after = build_code_snapshot(
        {"a.py": b"def f():\n    pass\n", "b.py": b"def g(:\n"},
        revision="rev-2", profile=PY,
    )
    delta = compute_code_delta(before, after)
    items = (EvidenceItem(source_type="code_delta", evidence_id="delta-1", payload=delta),)
    facts = code_change_facts_v1(_inp(*items))
    by = _facts_by_predicate(facts)
    # a.py unchanged; b.py changed + unparseable -> 0 parsed / 1 changed file.
    assert delta.changed_files == ["b.py"]
    assert float(by["ast_parse_coverage"].value) == 0.0


# ── The verify_code_change/v1 contract ──────────────────────────


def _fact(predicate: str, value: str) -> CanonicalFact:
    spec = FACT_PREDICATES[predicate]
    from agentic_dynamics.control.facts import EPISTEMIC_MAP

    authority, evidence_class = EPISTEMIC_MAP["derived"]
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=REPO, scope_type="job", scope_id=CELL,
            predicate=predicate, subject_type="job", subject_id=CELL,
        ),
        fact_id="", subject_type="job", subject_id=CELL, predicate=predicate, value=value,
        value_type=spec.value_type, unit=spec.unit, scope_type="job", scope_id=CELL,
        scope_path=JOB_SCOPE, abstraction_level=spec.abstraction_level,
        epistemic_status="derived", authority=authority, evidence_class=evidence_class,
        observed_at=NOW, valid_from=NOW, valid_to=None, expires_at=None,
        reducer="code_change_facts", reducer_version="code_change_facts/v1",
        evidence_ids=(), inputs_digest="", supersedes=None,
        source_revision="rev-2", repository_id=REPO,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def test_contract_loads_and_passes_the_fact_contract_gate():
    contract = load_contract("verify_code_change", contracts_dir=CONTRACTS_DIR)
    assert contract.decision_type == "verify_code_change"
    assert contract.contract_version == "verify_code_change/v1"
    assert set(contract.allowed_actions) == {"verify", "rework", "continue"}

    # The R1-R11 gate with the REAL registries (composed at the control tier exactly as the
    # production gate does) — every required fact must resolve to a declared predicate with a
    # producing reducer, at a reachable scope, with legal on_missing/on_conflict.
    from agentic_dynamics.core.contracts import validate_fact_contracts

    class _Spec:
        rules = ()

    errors = validate_fact_contracts(
        _Spec(), predicates=FACT_PREDICATES, reducers=REDUCERS,
        contracts={contract.decision_type: contract},
    )
    assert errors == [], "\n".join(errors)


def test_contract_compiles_admissible_through_real_compile_context():
    contract = load_contract("verify_code_change", contracts_dir=CONTRACTS_DIR)
    facts = (
        _fact("sonar_analysis_status", "available"),
        _fact("lsp_analysis_status", "available"),
        _fact("changed_symbol_count", "2"),
        _fact("ast_parse_coverage", "1.0"),
        _fact("code_change_risk", "0.245"),
    )
    request = ContextRequest(
        decision_type="verify_code_change", scope_type="job", scope_id=CELL, scope_path=JOB_SCOPE,
        repository_id=REPO,
    )
    ctx = compile_context(request, store=InMemoryFactStore(facts=facts), now=NOW, contract=contract)
    assert ctx.admissible is True
    resolved = {ref.predicate for ref in ctx.job}
    assert {"changed_symbol_count", "ast_parse_coverage", "code_change_risk"} <= resolved
