"""Tests for the deterministic retrieval + evidence-card layer.

Covers the query planner (pure regexes), fusion math, graph-decay boost, token
budgeting, dedupe, conflict retention, fallback-mode resolution, and evidence-card
derivation — all without requiring Chroma/Neo4j/Ollama (the store-dependent
orchestration is exercised only through its pure helpers).
"""

import ast
import json
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentic_dynamics.knowledge.context_layers import (
    CONTEXT_ROUTE_LAYER_KEYS,
    CONTEXT_ROUTE_RECORD_KEYS,
    CONTEXT_ROUTE_SCHEMA,
    LAYER_SELF,
    LAYER_STATUS_EMPTY,
    LAYER_STATUS_EXCLUDED,
    LAYER_STATUS_NAMED_ABSENT,
    LAYER_STATUS_SET,
    LAYER_STATUS_UNKNOWN,
    PROJECT_KNOWLEDGE_SCOPE,
    ROLE_IMPLEMENTATION,
    ROLE_REVIEW,
    SERVING_SCOPE_POLICY,
    UNRESOLVED_UNCLASSIFIED_MIXED_REASON,
    UNRESOLVED_UNCLASSIFIED_WITHHELD_ONLY_REASON,
    UNRESOLVED_WITHHELD_REASON,
    LayerRoute,
    build_context_route_record,
    classify_phase_role,
    layer_source_types,
    resolve_phase_layers,
    serving_scope_grants,
    shared_history_scopes,
)
from agentic_dynamics.knowledge.knowledge import SOURCE_TYPES, Authority
from agentic_dynamics.knowledge.retrieval import (
    ADVISORY_FRESH_30D,
    ADVISORY_FRESH_90D,
    AUTHORITY_MULTIPLIER,
    CODE_QUERY_TYPE_PRIORS,
    CONFLICT_MULTIPLIER,
    DENSE_SEARCH_INCOMPLETE_KEY,
    EMBEDDER_MODULE_ABSENT_TOKEN,
    EMBEDDER_UNREACHABLE_TOKEN,
    EXACT_COMMIT_MULTIPLIER,
    FINDINGS_QUERY_TYPE_PRIORS,
    RELATIONSHIP_WEIGHTS,
    SOURCE_TYPE_EXCLUDED_REASON,
    SOURCE_TYPE_METADATA_ERROR_KEY,
    SOURCE_TYPE_RESOLVER_ERROR_KEY,
    UNTYPED_EXCLUDED_REASON,
    WEIGHTS_VERSION,
    Candidate,
    EvidenceCard,
    FallbackMode,
    QueryShape,
    _dense_filter,
    acl_excluded,
    build_evidence_cards,
    build_query_plan,
    classify_query_shape,
    collapse_redundant,
    compute_fused_score,
    compute_token_budget,
    deduplicate,
    exact_identifier_hit,
    freshness_multiplier,
    fuse_candidates,
    graph_boost,
    is_conflict_relationship,
    ordering_tiebreak_tier,
    pattern_uncertainty_multiplier,
    resolve_fallback_mode,
    retrieve,
    rrf_base,
    select_evidence,
    source_ordering_bucket,
    source_type_prior,
)

NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)


def _cand(
    cid: str,
    *,
    text: str = "some text",
    authority: Authority = Authority.SOURCE,
    locator: str = "",
    content_hash: str = "",
    lexical_rank: int | None = None,
    dense_rank: int | None = None,
    token_count: int = 1,
    conflict: bool = False,
    observed_at: str | None = None,
    commit_sha: str = "",
    **kwargs,
) -> Candidate:
    return Candidate(
        id=cid,
        text=text,
        content_hash=content_hash or f"hash:{cid}",
        authority=authority,
        locator=locator or cid,
        lexical_rank=lexical_rank,
        dense_rank=dense_rank,
        token_count=token_count,
        conflict=conflict,
        observed_at=observed_at,
        commit_sha=commit_sha,
        **kwargs,
    )


# ── Planner extraction ──────────────────────────────────────────

RAW = (
    'Fix "infinite loop" in src/instrument/graph.py at graph.py:524 (build_step_graph). '
    "Add test_build_step_graph_doc_id and tests/test_retrieval.py. "
    "Run pytest -k test_retrieval with --verbose. "
    'The bug is File "foo.py", line 10, in bar. Use module.submodule.Symbol and Neo4jClient.'
)


def test_planner_extracts_quoted_strings():
    plan = build_query_plan(RAW)
    assert "infinite loop" in plan.quoted_strings


def test_planner_extracts_file_paths():
    plan = build_query_plan(RAW)
    assert "src/instrument/graph.py" in plan.file_paths
    assert "tests/test_retrieval.py" in plan.file_paths


def test_planner_extracts_stack_frames():
    plan = build_query_plan(RAW)
    assert "graph.py:524" in plan.stack_frames
    assert 'File "foo.py", line 10' in plan.stack_frames


def test_planner_extracts_test_names():
    plan = build_query_plan(RAW)
    assert "test_build_step_graph_doc_id" in plan.test_names
    assert "test_retrieval" in plan.test_names


def test_planner_extracts_cli_flags():
    plan = build_query_plan(RAW)
    assert "--verbose" in plan.cli_flags
    assert "-k" in plan.cli_flags


def test_planner_extracts_dotted_identifiers():
    plan = build_query_plan(RAW)
    assert "module.submodule.Symbol" in plan.dotted_identifiers


def test_planner_extracts_symbols():
    plan = build_query_plan(RAW)
    assert "Neo4jClient" in plan.symbols
    assert "build_step_graph" in plan.symbols


def test_planner_dense_query_includes_objective_truncated():
    plan = build_query_plan("short task", phase_objective="build a thing")
    assert plan.dense_query.startswith("short task")
    assert "build a thing" in plan.dense_query


def test_planner_is_deterministic():
    a = build_query_plan(RAW)
    b = build_query_plan(RAW)
    assert a == b


def test_planner_does_not_rewrite_raw():
    plan = build_query_plan(RAW)
    assert plan.raw == RAW


# ── Fusion math ─────────────────────────────────────────────────


def test_rrf_base_both_legs():
    expected = 1.2 / 60.0 + 1.0 / 60.0
    assert rrf_base(0, 0) == pytest.approx(expected)


def test_rrf_base_missing_leg_contributes_zero():
    assert rrf_base(None, 0) == pytest.approx(1.0 / 60.0)
    assert rrf_base(0, None) == pytest.approx(1.2 / 60.0)
    assert rrf_base(None, None) == 0.0


def test_authority_multipliers_are_versioned_and_ordered():
    assert AUTHORITY_MULTIPLIER[Authority.SOURCE] > AUTHORITY_MULTIPLIER[Authority.ADVISORY]
    assert AUTHORITY_MULTIPLIER[Authority.SOURCE] == 1.15
    assert AUTHORITY_MULTIPLIER[Authority.ADVISORY] == 0.80
    assert Authority.POLICY not in AUTHORITY_MULTIPLIER  # pinned, never retrieved
    assert WEIGHTS_VERSION.startswith("retrieval-weights/")


def test_fused_score_applies_all_multipliers():
    base = rrf_base(0, 5)
    expected = base * 1.15 * 1.10 * 1.15 * 0.70
    assert compute_fused_score(
        lexical_rank=0,
        dense_rank=5,
        authority=Authority.SOURCE,
        freshness=1.10,
        exact_identifier_match=True,
        conflict=True,
    ) == pytest.approx(expected)


def test_fused_score_conflict_penalty():
    no_conflict = compute_fused_score(
        lexical_rank=0,
        dense_rank=0,
        authority=Authority.SOURCE,
        freshness=1.0,
        exact_identifier_match=False,
        conflict=False,
    )
    with_conflict = compute_fused_score(
        lexical_rank=0,
        dense_rank=0,
        authority=Authority.SOURCE,
        freshness=1.0,
        exact_identifier_match=False,
        conflict=True,
    )
    assert with_conflict == pytest.approx(no_conflict * CONFLICT_MULTIPLIER)


def test_pattern_uncertainty_multiplier_prefers_low_uncertainty():
    assert pattern_uncertainty_multiplier(0.10) > pattern_uncertainty_multiplier(0.80)
    assert pattern_uncertainty_multiplier(None) == pytest.approx(1.0)


def test_pattern_fusion_uses_uncertainty_at_equal_relevance():
    low = _cand(
        "pattern-low",
        authority=Authority.DERIVED,
        dense_rank=0,
        source_type="pattern",
        pattern_payload={"uncertainty": 0.10},
    )
    high = _cand(
        "pattern-high",
        authority=Authority.DERIVED,
        dense_rank=0,
        source_type="pattern",
        pattern_payload={"uncertainty": 0.80},
    )
    fused = fuse_candidates([high, low], exact_terms=[])
    assert [c.id for c in fused] == ["pattern-low", "pattern-high"]


def test_freshness_exact_commit_and_source():
    # Exact commit match keeps its soft boost.
    assert freshness_multiplier(
        authority=Authority.SOURCE, commit_sha="abc", observed_at=None, current_commit="abc"
    ) == pytest.approx(EXACT_COMMIT_MULTIPLIER)
    # A different, non-empty commit is a HARD exclusion (the safety rationale).
    assert (
        freshness_multiplier(
            authority=Authority.SOURCE, commit_sha="xyz", observed_at=None, current_commit="abc"
        )
        is None
    )
    # The exact-commit boost is preserved for the knowledge authorities too.
    assert freshness_multiplier(
        authority=Authority.MEASURED, commit_sha="abc", observed_at=None, current_commit="abc"
    ) == pytest.approx(EXACT_COMMIT_MULTIPLIER)


def test_freshness_commit_gate_only_hard_excludes_source():
    # Design B1: the commit gate keeps another branch's SOURCE *code* out; the
    # knowledge authorities stay reachable across revisions.
    # SOURCE + mismatched non-empty commit → hard exclusion.
    assert (
        freshness_multiplier(
            authority=Authority.SOURCE, commit_sha="xyz", observed_at=None, current_commit="abc"
        )
        is None
    )
    # MEASURED / DERIVED + mismatched commit → neutral (admitted at 1.00).
    for authority in (Authority.MEASURED, Authority.DERIVED):
        assert freshness_multiplier(
            authority=authority, commit_sha="xyz", observed_at=None, current_commit="abc"
        ) == pytest.approx(1.0)


def test_freshness_empty_commit_is_eligible():
    # An empty commit_sha is treated as current/unknown → eligible at 1.00.
    for authority in (Authority.SOURCE, Authority.MEASURED, Authority.DERIVED):
        assert freshness_multiplier(
            authority=authority, commit_sha="", observed_at=None, current_commit="abc"
        ) == pytest.approx(1.0)


def test_freshness_no_current_commit_keeps_soft_behavior():
    # Without a known current commit the hard filter is not enforced (back-compat).
    assert freshness_multiplier(
        authority=Authority.SOURCE, commit_sha="xyz", observed_at=None, current_commit=""
    ) == pytest.approx(1.0)


def test_freshness_advisory_ignores_commit_scope():
    # Advisory evidence is time-bucketed, not commit-scoped: a non-matching commit
    # does not hard-exclude it — its freshness window still applies (unchanged).
    observed = (NOW - timedelta(days=10)).isoformat()
    assert freshness_multiplier(
        authority=Authority.ADVISORY,
        commit_sha="xyz",
        observed_at=observed,
        current_commit="abc",
        now=NOW,
    ) == pytest.approx(ADVISORY_FRESH_30D)


def test_dense_filter_commit_scope_prefilter():
    # The commit scope $or admits empty (unknown/current), the exact commit, AND the
    # commit-exempt knowledge authorities (design B1) — SOURCE stays gated.
    exempt = [
        {"authority": "MEASURED"},
        {"authority": "DERIVED"},
        {"authority": "ADVISORY"},
    ]
    assert _dense_filter({"commit_sha": "abc"}) == {
        "$or": [{"commit_sha": ""}, {"commit_sha": "abc"}, *exempt]
    }
    # No commit scope → no filter at all.
    assert _dense_filter({"commit_sha": ""}) == {}
    assert _dense_filter({}) == {}
    # A single non-commit condition stays unwrapped.
    assert _dense_filter({"repository_id": "repo"}) == {"repository_id": "repo"}
    # Multiple conditions combine under $and (Chroma allows exactly one top-level key).
    assert _dense_filter({"repository_id": "repo", "commit_sha": "abc"}) == {
        "$and": [
            {"repository_id": "repo"},
            {"$or": [{"commit_sha": ""}, {"commit_sha": "abc"}, *exempt]},
        ]
    }
    # The exemptions are equality clauses, not `$in` (Chroma matches them directly).
    assert all("$in" not in clause for clause in _dense_filter({"commit_sha": "abc"})["$or"])


def test_freshness_advisory_age_buckets():
    def obs(days_ago: int) -> str:
        return (NOW - timedelta(days=days_ago)).isoformat()

    assert freshness_multiplier(
        authority=Authority.ADVISORY, commit_sha="", observed_at=obs(10), current_commit="", now=NOW
    ) == pytest.approx(ADVISORY_FRESH_30D)
    assert freshness_multiplier(
        authority=Authority.ADVISORY, commit_sha="", observed_at=obs(60), current_commit="", now=NOW
    ) == pytest.approx(ADVISORY_FRESH_90D)
    # >90 days old advisory evidence is excluded.
    assert (
        freshness_multiplier(
            authority=Authority.ADVISORY,
            commit_sha="",
            observed_at=obs(100),
            current_commit="",
            now=NOW,
        )
        is None
    )


def test_freshness_policy_is_never_retrieved():
    assert (
        freshness_multiplier(
            authority=Authority.POLICY, commit_sha="abc", observed_at=None, current_commit="abc"
        )
        is None
    )


def test_exact_identifier_hit():
    c = _cand("k1", locator="src/instrument/graph.py", text="def build_step_graph(): ...")
    assert exact_identifier_hit(c, ["graph.py", "build_step_graph"]) is True
    assert exact_identifier_hit(c, ["unrelated_symbol"]) is False


# ── Graph decay ─────────────────────────────────────────────────


def test_graph_boost_decays_with_depth():
    assert graph_boost(1.0, 0, "DEFINES") == pytest.approx(1.0)
    assert graph_boost(1.0, 1, "DEFINES") == pytest.approx(0.7)
    assert graph_boost(1.0, 2, "DEFINES") == pytest.approx(0.49)
    assert graph_boost(1.0, 2, "DEFINES") < graph_boost(1.0, 1, "DEFINES")


def test_graph_boost_applies_relationship_weight():
    assert graph_boost(1.0, 1, "IMPORTS") == pytest.approx(0.8 * 0.7)
    assert graph_boost(1.0, 1, "CONTRADICTS") == pytest.approx(0.6 * 0.7)


def test_graph_boost_is_a_boost_not_a_peer():
    # An expanded node is strictly below a direct seed (depth 0) regardless of weight.
    assert graph_boost(1.0, 1, "DEFINES") < 1.0
    assert RELATIONSHIP_WEIGHTS["CONTRADICTS"] < RELATIONSHIP_WEIGHTS["DEFINES"]


def test_conflict_relationship_flag():
    assert is_conflict_relationship("CONTRADICTS") is True
    assert is_conflict_relationship("DEFINES") is False


# ── Budget cap + whole-chunk selection ──────────────────────────


def test_token_budget_is_min_of_all_limits():
    assert (
        compute_token_budget(
            executor_context_tokens=200_000, remaining_input_tokens=200_000, rag_token_limit=8000
        )
        == 8000
    )
    # 20% of a 10k context = 2000, and remaining input 5000 → 2000.
    assert (
        compute_token_budget(
            executor_context_tokens=10_000, remaining_input_tokens=5_000, rag_token_limit=8000
        )
        == 2000
    )
    # Tight remaining input dominates.
    assert (
        compute_token_budget(
            executor_context_tokens=200_000, remaining_input_tokens=100, rag_token_limit=8000
        )
        == 100
    )


def test_select_evidence_never_splits_a_chunk():
    a = _cand("a", text="x", token_count=4, dense_rank=0)  # highest score
    b = _cand("b", text="y", token_count=7, dense_rank=1)
    c = _cand("c", text="z", token_count=3, dense_rank=2)
    # score order: a, b, c. budget 10 → a (4), skip b (7 > 6), c (3).
    selected = select_evidence([a, b, c], token_budget=10)
    assert [s.id for s in selected] == ["a", "c"]
    assert sum(s.token_count for s in selected) == 7


def test_select_evidence_skips_oversized_chunk():
    a = _cand("a", token_count=15, dense_rank=0)
    b = _cand("b", token_count=2, dense_rank=1)
    selected = select_evidence([a, b], token_budget=10)
    assert [s.id for s in selected] == ["b"]  # 15-token chunk does not fit → skipped whole


def test_select_evidence_source_diversity_cap():
    src = "session_1"
    cands = [
        _cand("a", locator=src, token_count=1, dense_rank=0),
        _cand("b", locator=src, token_count=1, dense_rank=1),
        _cand("c", locator=src, token_count=1, dense_rank=2),
    ]
    selected = select_evidence(cands, token_budget=10, max_chunks_per_source=2)
    assert len(selected) == 2


# ── Dedupe + conflict retention ─────────────────────────────────


def test_deduplicate_collapses_identical_content():
    c1 = _cand("k1", content_hash="h", authority=Authority.ADVISORY, locator="locA")
    c2 = _cand("k2", content_hash="h", authority=Authority.SOURCE, locator="locB")
    out = deduplicate([c1, c2])
    assert len(out) == 1
    assert out[0].id == "k2"  # higher authority survives
    assert out[0].authority is Authority.SOURCE
    assert set(out[0].provenance) == {"locA", "locB"}  # provenance merged


def test_deduplicate_keeps_distinct_content():
    c1 = _cand("k1", content_hash="h1")
    c2 = _cand("k2", content_hash="h2")
    assert len(deduplicate([c1, c2])) == 2


def test_collapse_redundant_retains_conflicts():
    a = _cand("a", content_hash="h1", authority=Authority.SOURCE)
    b = _cand("b", content_hash="h2", authority=Authority.ADVISORY)
    similarities = {("a", "b"): 0.95}
    # No conflict → the redundant ADVISORY side is dropped.
    assert [c.id for c in collapse_redundant([a, b], similarities)] == ["a"]
    # With a conflict flag on either side → both retained (don't hide uncertainty).
    a_conflict = _cand("a", content_hash="h1", authority=Authority.SOURCE, conflict=True)
    assert [c.id for c in collapse_redundant([a_conflict, b], similarities)] == ["a", "b"]


def test_collapse_redundant_below_threshold_keeps_both():
    a = _cand("a", authority=Authority.SOURCE)
    b = _cand("b", authority=Authority.ADVISORY)
    assert [c.id for c in collapse_redundant([a, b], {("a", "b"): 0.5})] == ["a", "b"]


# ── Fallback modes (monotonic degradation) ──────────────────────


def test_fallback_modes_monotonic():
    assert resolve_fallback_mode(dense_ok=True, lexical_ok=True, graph_ok=True) is FallbackMode.FULL
    assert (
        resolve_fallback_mode(dense_ok=False, lexical_ok=True, graph_ok=True)
        is FallbackMode.LEXICAL_GRAPH_ONLY
    )
    assert (
        resolve_fallback_mode(dense_ok=True, lexical_ok=False, graph_ok=True)
        is FallbackMode.DENSE_LOCAL_EXACT
    )
    assert (
        resolve_fallback_mode(dense_ok=False, lexical_ok=False, graph_ok=False)
        is FallbackMode.NO_RAG
    )


def test_fallback_modes_are_named_distinct_values():
    assert {m.value for m in FallbackMode} == {
        "full",
        "lexical_graph_only",
        "dense_local_exact",
        "no_rag",
    }


# ── Evidence card derivation ────────────────────────────────────


def _run(**kw) -> dict:
    base = {
        "worktree_name": "wt-1",
        "model": "deepseek/deepseek-v4-pro",
        "operator": "remove_critical_constraint",
        "perturbation_class": "specification_corruption",
        "strategy": "exploratory",
        "correctness": 0.8,
        "cost": 0.018,
        "flail": 0.62,
        "narration_failure": False,
    }
    base.update(kw)
    return base


def test_build_evidence_cards_derives_offline():
    cards = build_evidence_cards([_run()])
    assert len(cards) == 1
    card = cards[0]
    assert isinstance(card, EvidenceCard)
    assert card.model == "deepseek/deepseek-v4-pro"
    assert card.operator == "remove_critical_constraint"
    assert card.correctness == pytest.approx(0.8)
    assert card.cost == pytest.approx(0.018)
    assert card.flail == pytest.approx(0.62)
    # One-line finding, never synthesized at query time.
    assert "deepseek/deepseek-v4-pro" in card.text
    assert "remove_critical_constraint" in card.text


def test_build_evidence_cards_skips_narration_failure():
    cards = build_evidence_cards(
        [_run(worktree_name="a"), _run(worktree_name="b", narration_failure=True)]
    )
    assert [c.run_id for c in cards] == ["a"]


def test_build_evidence_cards_skips_negative_correctness():
    cards = build_evidence_cards(
        [_run(worktree_name="ok"), _run(worktree_name="bad", correctness=-1)]
    )
    assert [c.run_id for c in cards] == ["ok"]


def test_build_evidence_cards_flail_falls_back_to_escape():
    run = _run(flail=None, escape=0.51)
    del run["flail"]
    card = build_evidence_cards([run])[0]
    assert card.flail == pytest.approx(0.51)


def test_build_evidence_cards_is_deterministic():
    runs = [_run(), _run(worktree_name="wt-2", model="anthropic/claude-sonnet-5", flail=0.1)]
    assert build_evidence_cards(runs) == build_evidence_cards(runs)


def test_build_evidence_cards_absent_new_signals_render_dash_and_omit():
    # The legacy run shape (no confidence/strength/test fields) must not crash and
    # must not fabricate numbers: confidence renders an em-dash placeholder, and the
    # test/strength segments are omitted entirely.
    card = build_evidence_cards([_run()])[0]
    assert card.confidence is None
    assert card.perturbation_strength is None
    assert card.test_executed_success is None
    assert "confidence —" in card.text
    assert "perturb_strength" not in card.text
    assert "tests " not in card.text


def test_build_evidence_cards_renders_present_signals():
    card = build_evidence_cards(
        [_run(confidence=0.72, perturbation_strength=0.5, test_executed_success=True)]
    )[0]
    assert card.confidence == pytest.approx(0.72)
    assert card.perturbation_strength == pytest.approx(0.5)
    assert card.test_executed_success is True
    assert "confidence 0.72" in card.text
    assert "perturb_strength 0.50" in card.text
    assert "tests pass" in card.text


def test_build_evidence_cards_preserves_pattern_surface_when_present():
    payload = {
        "claim": "recovers_under_objective_mutation",
        "population": "finding:task_manager",
        "conditions": ["test_executed_success=true"],
        "support": 3,
        "uncertainty": 0.25,
        "validity_window": "abc123",
        "source_experiment": "finding:entity:k1",
    }
    card = build_evidence_cards(
        [_run(source_type="pattern", pattern_payload=json.dumps(payload, sort_keys=True))]
    )[0]
    assert card.source_type == "pattern"
    assert card.pattern_payload == payload


def test_build_evidence_cards_nan_treated_as_unmeasured():
    # NaN must behave exactly like an absent value: not crash, not render a number.
    card = build_evidence_cards(
        [
            _run(
                confidence=float("nan"),
                perturbation_strength=float("nan"),
                test_executed_success=float("nan"),
            )
        ]
    )[0]
    assert card.confidence is None
    assert card.perturbation_strength is None
    assert card.test_executed_success is None
    assert "confidence —" in card.text
    assert "perturb_strength" not in card.text


def test_build_evidence_cards_flags_failed_suite_unverified():
    # A run whose independent suite failed must be flagged so it never reads as a
    # verified finding — the card is kept (the data point is still measured) but the
    # text carries an explicit UNVERIFIED marker.
    card = build_evidence_cards([_run(confidence=0.91, test_executed_success=False)])[0]
    assert card.test_executed_success is False
    assert "tests FAIL (unverified)" in card.text
    assert "tests pass" not in card.text


def test_build_evidence_cards_skips_unmeasured_correctness():
    # A run with absent or NaN correctness is unmeasured, not a "0.00" finding.
    absent = _run()
    del absent["correctness"]
    nan = _run(correctness=float("nan"))
    cards = build_evidence_cards([absent, nan])
    assert cards == []


# ── RetrievalAttempt sanity (recorded before any LLM call) ──────


def test_candidate_citation_format():
    c = _cand("k1", locator="symbol:foo", commit_sha="abc")
    assert c.citation() == "[K:k1@abc:symbol:foo]"


# ── Overlap instrument (retrieval_fusion_quality p1 — the cross-leg content join) ──


def _lexical_hit_without_hash(cid="doc_lex", text="lexical websocket reload hit"):
    """A lexical hit whose Neo4j properties carry NO content_hash (the real gap)."""
    return {
        "id": "elem:lex",
        "properties": {
            "text": text,
            "authority": "source",
            "knowledge_id": cid,
        },
        "score": 0.9,
    }


def test_candidate_legs_attribution():
    both = _cand("b", dense_rank=0, lexical_rank=0)
    dense = _cand("d", dense_rank=0)
    lexical = _cand("l", lexical_rank=0)
    expanded = _cand("e", graph_depth=1)
    assert both.legs == "both"
    assert dense.legs == "dense"
    assert lexical.legs == "lexical"
    assert expanded.legs == "expansion"


def test_dense_leg_carries_persisted_and_join_content_hash():
    from agentic_dynamics.knowledge.knowledge import compute_content_hash

    text = "the retrieval fusion is a union under disjoint top-k"
    hit = _dense_hit("k_dense", text, authority="source", content_hash="artifact-hash")
    attempt = retrieve("retrieval fusion", dense_store=_FakeDenseStore([hit]))
    cand = next(c for c in attempt.candidates if c.id == "k_dense")
    # The persisted artifact hash stays on content_hash (unchanged semantics).
    assert cand.content_hash == "artifact-hash"
    # The join-consistent text hash is derived identically on the dense leg.
    assert cand.join_content_hash == compute_content_hash(text)


def test_lexical_leg_derives_join_content_hash_when_store_lacks_it():
    from agentic_dynamics.knowledge.knowledge import compute_content_hash

    text = "a lexical hit whose node carries no content_hash property"
    graph = _FakeGraph(lexical_hits=[_lexical_hit_without_hash(cid="k_lex", text=text)])
    attempt = retrieve("lexical websocket reload", dense_store=None, graph_client=graph)
    cand = next(c for c in attempt.candidates if c.id == "k_lex")
    # The gap is honest: no persisted artifact hash on the lexical leg.
    assert cand.content_hash == ""
    # The join-consistent text hash closes the gap with the same hashing rule.
    assert cand.join_content_hash == compute_content_hash(text)


def _no_embedder(monkeypatch):
    """Force the cosine-collapse to degrade to a no-op (deterministic pair tests)."""
    import agentic_dynamics.knowledge.embeddings as embeddings

    class _Unavailable:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("ollama unavailable in this test")

    monkeypatch.setattr(embeddings, "EmbeddingClient", _Unavailable)


def test_seeded_same_content_pair_is_detected_by_the_join(monkeypatch):
    # H1 shape: the SAME text indexed under DIFFERENT ids on the two legs — the
    # id-based fusion check can never fire (ids differ), but the content join must.
    from agentic_dynamics.knowledge.knowledge import compute_content_hash

    _no_embedder(monkeypatch)
    text = "the same websocket reload protocol documented under two ids"
    dense = _FakeDenseStore([_dense_hit("dense-id", text, authority="source")])
    graph = _FakeGraph(lexical_hits=[_lexical_hit_without_hash(cid="lexical-id", text=text)])
    attempt = retrieve("websocket reload protocol", dense_store=dense, graph_client=graph)

    ids = {c.id for c in attempt.candidates}
    assert {"dense-id", "lexical-id"} <= ids  # two genuinely distinct records kept
    assert all(c.legs == "dense" or c.legs == "lexical" for c in attempt.candidates)

    overlap = attempt.leg_overlap()
    assert overlap["fused"] == 0  # id-based fusion still cannot fire (different ids)
    assert overlap["content_pairs"] == 1  # ... but the content join sees the pair
    assert overlap["distinct_content_hashes"] == 1
    assert ("dense-id", "lexical-id") in overlap["sample_pairs"]
    # The pair's shared text hash is the exact compute_content_hash rule.
    shared = {c.join_content_hash for c in attempt.candidates}
    assert shared == {compute_content_hash(text)}


def test_distinct_content_pair_never_joins(monkeypatch):
    # H2 shape: genuinely distinct texts on the two legs must never form a pair.
    _no_embedder(monkeypatch)
    dense = _FakeDenseStore(
        [_dense_hit("d1", "quantum entanglement of distant particles", authority="source")]
    )
    graph = _FakeGraph(
        lexical_hits=[_lexical_hit_without_hash(cid="l1", text="websocket reload protocol")]
    )
    attempt = retrieve("websocket reload", dense_store=dense, graph_client=graph)
    assert {c.id for c in attempt.candidates} == {"d1", "l1"}
    overlap = attempt.leg_overlap()
    assert overlap["content_pairs"] == 0
    assert overlap["distinct_content_hashes"] == 0
    assert overlap["sample_pairs"] == []


def test_leg_overlap_matches_rank_attribution_on_a_both_leg_candidate():
    # The join must agree with the census's id-level attribution: a candidate the
    # lexical leg merges onto (same id) counts as fused, with zero content pairs.
    from agentic_dynamics.knowledge.knowledge import compute_content_hash

    text = "same record surfaced by both legs under the same id"
    dense = _FakeDenseStore([_dense_hit("k_both", text, authority="source")])
    graph = _FakeGraph(lexical_hits=[_lexical_hit_without_hash(cid="k_both", text=text)])
    attempt = retrieve("websocket reload", dense_store=dense, graph_client=graph)

    both = [c for c in attempt.candidates if c.id == "k_both"]
    assert len(both) == 1  # merged under the shared id
    assert both[0].legs == "both"
    assert both[0].join_content_hash == compute_content_hash(text)

    overlap = attempt.leg_overlap()
    assert overlap["fused"] == 1
    assert overlap["dense_only"] == 0 and overlap["lexical_only"] == 0
    assert overlap["content_pairs"] == 0  # one candidate, not a cross-id pair


def test_join_instrument_does_not_change_fusion_off_path():
    # The join fields are observational only: deduplicate must still key on the
    # persisted content_hash (or id when absent) — never on the join hash — so a
    # candidate carrying a join_content_hash but no persisted hash is NOT collapsed.
    c1 = _cand("k1", content_hash="")
    c2 = _cand("k2", content_hash="")
    c1.join_content_hash = "shared-text-hash"
    c2.join_content_hash = "shared-text-hash"
    out = deduplicate([c1, c2])
    assert len(out) == 2  # distinct ids, no persisted hash → never merged


# ── Graph-expansion leg wiring (real seed score × weight × decay) ──


class _FakeDenseStore:
    """Minimal dense store: returns scripted hits, or raises (simulates a down leg)."""

    def __init__(self, hits, error=None):
        self._hits = hits
        self._error = error

    def search(self, query, *, top_k=40, where=None):
        if self._error is not None:
            raise self._error
        return list(self._hits)


class _FakeGraph:
    """Minimal graph client: scripted lexical hits, expansion nodes, or down legs."""

    def __init__(self, expanded=None, lexical_hits=None, lexical_error=None, expand_error=None):
        self._expanded = expanded or []
        self._lexical_hits = lexical_hits or []
        self._lexical_error = lexical_error
        self._expand_error = expand_error
        self.expand_seeds = None
        self.lexical_queries = []

    def search_knowledge_fulltext(self, query, *, limit=10, commit=None):
        # The lexical leg targets the KB full-text index (Knowledge.text), so the
        # fake mirrors that method — the Step path (search_fulltext) is never used.
        self.lexical_queries.append(query)
        if self._lexical_error is not None:
            raise self._lexical_error
        return list(self._lexical_hits)

    def expand_candidates(self, seeds, **kwargs):
        self.expand_seeds = list(seeds)
        if self._expand_error is not None:
            raise self._expand_error
        return list(self._expanded)


def _seed_hit():
    return {
        "id": "k_seed",
        "document": "seed document about websocket reload protocol",
        "metadata": {"authority": "source", "content_hash": "hash_seed"},
        "distance": 0.1,
    }


def _dense_hit(cid, text, *, authority="source", content_hash="", distance=0.1):
    return {
        "id": cid,
        "document": text,
        "metadata": {"authority": authority, "content_hash": content_hash or f"hash:{cid}"},
        "distance": distance,
    }


def _pattern_dense_hit(cid="pattern-1", *, uncertainty=0.25, repository_id=""):
    payload = {
        "claim": "recovers_under_objective_mutation",
        "population": "finding:task=task_manager,perturbation_class=objective_mutation",
        "conditions": ["test_executed_success=true"],
        "support": 3,
        "uncertainty": uncertainty,
        "validity_window": "abc123",
        "source_experiment": "finding:entity:k1",
    }
    return {
        "id": cid,
        "document": json.dumps(payload, sort_keys=True),
        "metadata": {
            "authority": "derived",
            "source_type": "pattern",
            "pattern_payload": json.dumps(payload, sort_keys=True),
            "content_hash": f"hash:{cid}",
            "repository_id": repository_id,
        },
        "distance": 0.1,
    }


def _lexical_hit(cid="doc_lex", text="lexical websocket reload hit"):
    return {
        "id": "elem:lex",
        "properties": {
            "text": text,
            "authority": "source",
            "content_hash": "hash_lex",
            "doc_id": cid,
        },
        "score": 0.9,
    }


def _knowledge_lexical_hit(
    cid="k_kb", text="task manager api building finding", authority="measured"
):
    return {
        "id": "elem:knowledge",
        "properties": {
            "knowledge_id": cid,
            "entity_id": "ent_kb",
            "text": text,
            "authority": authority,
            "source_type": "finding",
            "commit_sha": "abc",
        },
        "score": 0.9,
    }


def _expanded_node(origin, *, rel_type="DEFINES", depth=1, cid="k_expanded"):
    return {
        "id": "elem:expanded",
        "canonical_id": cid,
        "labels": ["Knowledge"],
        "properties": {
            "text": "expanded neighbor text",
            "authority": "source",
            "content_hash": "hash_expanded",
        },
        "rel_type": rel_type,
        "depth": depth,
        "path": [origin, cid],
        "origin_seed": origin,
    }


def test_retrieve_expansion_scores_with_real_seed_and_rel_type():
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([_seed_hit()]),
        graph_client=_FakeGraph([_expanded_node("k_seed")]),
    )

    seed = next(c for c in attempt.candidates if c.id == "k_seed")
    expanded = next(c for c in attempt.candidates if c.id == "k_expanded")

    # The expansion hop is scored with the seed's REAL fused score (not a hardcoded
    # 1.0), the traversed relationship weight, and the decay at the returned depth.
    expected = seed.fused_score * RELATIONSHIP_WEIGHTS["DEFINES"] * (0.7**1)
    assert expanded.fused_score == pytest.approx(expected)
    assert expanded.graph_depth == 1
    assert expanded.graph_path == ["k_seed", "k_expanded"]
    assert expanded.relationship_weight == RELATIONSHIP_WEIGHTS["DEFINES"]


def test_retrieve_expansion_uses_canonical_id_not_element_id():
    # The expanded node's canonical_id (not its elementId) keys the candidate.
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([_seed_hit()]),
        graph_client=_FakeGraph([_expanded_node("k_seed")]),
    )
    ids = {c.id for c in attempt.candidates}
    assert "k_expanded" in ids
    assert "elem:expanded" not in ids


def test_retrieve_expansion_skips_orphan_origin():
    # An expanded node whose origin seed is not in the fused set is skipped cleanly,
    # never emitted as a zero-score candidate.
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([_seed_hit()]),
        graph_client=_FakeGraph([_expanded_node("unknown_seed")]),
    )
    assert all(c.id != "k_expanded" for c in attempt.candidates)


# ── End-to-end pipeline wiring (fuse → dedupe → collapse → expand → select) ──


def test_retrieve_end_to_end_pipeline():
    # Two dense hits sharing a content_hash (deduplicate collapses the advisory one)
    # plus a distinct third hit; the graph leg contributes one expanded neighbor.
    dense = _FakeDenseStore(
        [
            _dense_hit(
                "k1", "websocket live reload protocol", authority="source", content_hash="dup"
            ),
            _dense_hit(
                "k2", "websocket live reload protocol", authority="advisory", content_hash="dup"
            ),
            _dense_hit(
                "k3",
                "quantum entanglement of distant particles",
                authority="source",
                content_hash="distinct",
            ),
        ]
    )
    graph = _FakeGraph([_expanded_node("k1", cid="k_expanded")])

    attempt = retrieve("websocket reload", dense_store=dense, graph_client=graph)

    ids = {c.id for c in attempt.candidates}
    # fused: every candidate carries a real fused score.
    assert all(c.fused_score > 0 for c in attempt.candidates)
    # deduped: content-hash duplicate collapsed (k2 dropped, k1 survives as SOURCE).
    assert "k1" in ids and "k2" not in ids
    # expanded: graph neighbor appended (k1 survives collapse → is a seed).
    assert "k_expanded" in ids
    assert next(c for c in attempt.candidates if c.id == "k_expanded").graph_depth == 1
    # budgeted + selected: evidence is a non-empty, budget-respecting subset.
    assert attempt.selected_evidence
    assert set(c.id for c in attempt.selected_evidence) <= ids
    assert attempt.token_count == sum(c.token_count for c in attempt.selected_evidence)
    assert attempt.token_count <= compute_token_budget()
    # both legs + graph survived → full.
    assert attempt.fallback_mode == "full"


def test_retrieve_collapse_redundant_wired(monkeypatch):
    import agentic_dynamics.knowledge.embeddings as embeddings

    class _FakeEmbedder:
        """Deterministic embedder double: text → fixed vector, real cosine distance."""

        VECTORS = {
            "near duplicate text one": [1.0, 0.0],
            "near duplicate text two": [1.0, 0.0],
            "completely different topic": [0.0, 1.0],
        }

        def embed(self, text):
            if text not in self.VECTORS:
                raise KeyError(text)
            return self.VECTORS[text]

        def cosine_distance(self, a, b):
            import math

            dot = sum(x * y for x, y in zip(a, b, strict=False))
            ma = math.sqrt(sum(x * x for x in a))
            mb = math.sqrt(sum(y * y for y in b))
            if ma == 0 or mb == 0:
                return 1.0
            return (1.0 - dot / (ma * mb)) / 2.0

    monkeypatch.setattr(embeddings, "EmbeddingClient", _FakeEmbedder)

    # Distinct content hashes → deduplicate keeps all three; only the embedding-based
    # collapse (similarity 1.0 > 0.92) drops the lower-authority near-duplicate.
    dense = _FakeDenseStore(
        [
            _dense_hit("k1", "near duplicate text one", authority="source"),
            _dense_hit("k2", "near duplicate text two", authority="advisory"),
            _dense_hit("k3", "completely different topic", authority="source"),
        ]
    )

    attempt = retrieve("near duplicate text one", dense_store=dense)

    assert attempt.dedup_path == "embedding"
    ids = {c.id for c in attempt.candidates}
    assert "k1" in ids and "k3" in ids
    assert "k2" not in ids  # near-duplicate collapsed by cosine similarity


@pytest.mark.parametrize(
    "dense_store, graph_client, expected_mode",
    [
        (_FakeDenseStore([_seed_hit()]), None, "dense_local_exact"),
        (None, _FakeGraph(lexical_hits=[_lexical_hit()]), "lexical_graph_only"),
        (_FakeDenseStore([_seed_hit()]), _FakeGraph(), "full"),
        (None, None, "no_rag"),
    ],
)
def test_retrieve_fallback_reflects_surviving_legs(dense_store, graph_client, expected_mode):
    attempt = retrieve("websocket reload", dense_store=dense_store, graph_client=graph_client)
    assert attempt.fallback_mode == expected_mode


def test_retrieve_empty_dense_leg_is_not_marked_as_failure():
    """A healthy dense leg returning no rows stays distinct from an unavailable leg.

    The empty result is honest evidence that this leg found nothing. It must not be
    converted into a synthetic error, while the named fallback still records that only
    the dense leg was available for this pass.
    """
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([]),
        graph_client=None,
    )

    assert attempt.fallback_mode == "dense_local_exact"
    assert "dense" not in attempt.leg_errors
    assert attempt.candidates == []
    assert attempt.selected_evidence == []


def test_retrieve_failed_dense_and_lexical_legs_are_named():
    """Backend failures remain observable instead of masquerading as empty success.

    Check each store independently: a failed dense leg leaves the lexical fallback
    available, and a failed lexical leg leaves the dense fallback available. The two
    outcomes have the same possible empty evidence shape but different audit state.
    """
    dense_failed = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([], error=RuntimeError("chroma down")),
        graph_client=_FakeGraph(lexical_hits=[_lexical_hit()]),
    )
    assert dense_failed.fallback_mode == "lexical_graph_only"
    assert "dense" in dense_failed.leg_errors
    assert "chroma down" in dense_failed.leg_errors["dense"]

    lexical_failed = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([_seed_hit()]),
        graph_client=_FakeGraph(lexical_error=RuntimeError("neo4j down")),
    )
    assert lexical_failed.fallback_mode == "dense_local_exact"
    assert "lexical" in lexical_failed.leg_errors
    assert "neo4j down" in lexical_failed.leg_errors["lexical"]


def test_retrieve_fully_down_yields_no_rag_empty_evidence():
    # Both stores raise (infra down): each leg is marked down, evidence is empty,
    # and the attempt degrades to no_rag without raising.
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([], error=RuntimeError("chroma down")),
        graph_client=_FakeGraph(lexical_error=RuntimeError("neo4j down")),
    )
    assert attempt.fallback_mode == "no_rag"
    assert attempt.candidates == []
    assert attempt.selected_evidence == []
    assert attempt.token_count == 0
    assert attempt.dedup_path == "none"  # no survivors → embeddings never attempted
    assert set(attempt.leg_errors) >= {"dense", "lexical"}


def test_retrieve_scope_filter_runs_before_fusion_for_both_legs():
    """Foreign cell candidates never enter the fused candidate set.

    The fake dense store intentionally ignores its backend ``where`` clause and the
    fake graph client returns both cells. This proves the retrieval seam's local hard
    filter, not just the optional service-side filters.
    """
    local_dense = _dense_hit("local-dense", "local websocket finding", authority="source")
    local_dense["metadata"]["repository_id"] = "cell-a"
    foreign_dense = _dense_hit("foreign-dense", "foreign websocket finding", authority="source")
    foreign_dense["metadata"]["repository_id"] = "cell-b"

    local_lexical = _knowledge_lexical_hit(cid="local-lexical", text="local lexical finding")
    local_lexical["properties"]["repository_id"] = "cell-a"
    foreign_lexical = _knowledge_lexical_hit(cid="foreign-lexical", text="foreign lexical finding")
    foreign_lexical["properties"]["repository_id"] = "cell-b"

    attempt = retrieve(
        "websocket finding",
        dense_store=_FakeDenseStore([foreign_dense, local_dense]),
        graph_client=_FakeGraph(lexical_hits=[foreign_lexical, local_lexical]),
        repository_id="cell-a",
    )

    candidate_ids = {candidate.id for candidate in attempt.candidates}
    assert candidate_ids == {"local-dense", "local-lexical"}
    assert {candidate.id for candidate in attempt.selected_evidence} <= candidate_ids
    assert not {"foreign-dense", "foreign-lexical"} & candidate_ids


def test_retrieve_lexical_leg_returns_knowledge_records():
    # The lexical leg surfaces Knowledge records (authority MEASURED/SOURCE/POLICY),
    # keyed by knowledge_id — never Step reasoning (ADVISORY).
    graph = _FakeGraph(lexical_hits=[_knowledge_lexical_hit()])
    attempt = retrieve("build a task manager api", dense_store=None, graph_client=graph)

    assert attempt.fallback_mode == "lexical_graph_only"
    kb = next(c for c in attempt.candidates if c.id == "k_kb")
    assert kb.authority is Authority.MEASURED
    assert kb.text == "task manager api building finding"
    assert kb.commit_sha == "abc"
    # The KB leg is keyed by knowledge_id, not the opaque elementId.
    assert all(c.id != "elem:knowledge" for c in attempt.candidates)


def test_retrieve_lexical_leg_never_calls_step_search():
    # The lexical leg must target search_knowledge_fulltext, never search_fulltext
    # (the Step index). A graph client whose Step path raises proves the KB path is
    # the one taken: if retrieve still hit search_fulltext, the leg would go down
    # and the Knowledge candidate would never appear.
    class _KBOnlyGraph:
        def search_fulltext(self, *args, **kwargs):
            raise AssertionError("lexical leg must not use search_fulltext")

        def search_knowledge_fulltext(self, query, *, limit=10, commit=None):
            return [_knowledge_lexical_hit()]

        def expand_candidates(self, seeds, **kwargs):
            return []

    attempt = retrieve("build a task manager api", dense_store=None, graph_client=_KBOnlyGraph())
    ids = {c.id for c in attempt.candidates}
    assert "k_kb" in ids
    assert next(c for c in attempt.candidates if c.id == "k_kb").authority is Authority.MEASURED


def test_pattern_projection_is_opt_in_and_facts_stay_out_of_candidates():
    ordinary = _dense_hit("ordinary", "ordinary knowledge", authority="source")
    fact = _dense_hit("raw-fact", '{"predicate":"pattern"}', authority="derived")
    fact["metadata"]["source_type"] = "fact"
    pattern = _pattern_dense_hit()

    off = retrieve(
        "ordinary knowledge",
        dense_store=_FakeDenseStore([pattern, ordinary, fact]),
        pattern_projection=False,
    )
    baseline = retrieve(
        "ordinary knowledge",
        dense_store=_FakeDenseStore([ordinary]),
        pattern_projection=False,
    )
    enabled = retrieve(
        "ordinary knowledge",
        dense_store=_FakeDenseStore([pattern, ordinary, fact]),
        pattern_projection=True,
    )

    assert [c.id for c in off.candidates] == [c.id for c in baseline.candidates]
    assert off.ranks == baseline.ranks
    assert off.raw_scores == baseline.raw_scores
    assert all(c.source_type != "fact" for c in off.candidates + enabled.candidates)
    projected = next(c for c in enabled.candidates if c.id == "pattern-1")
    assert projected.is_pattern is True
    assert projected.pattern_payload is not None
    assert projected.pattern_payload["support"] == 3
    assert enabled.query_plan.pattern_projection is True


def test_pattern_projection_preserves_scope_filter():
    pattern = _pattern_dense_hit(repository_id="other-cell")
    attempt = retrieve(
        "ordinary knowledge",
        dense_store=_FakeDenseStore([pattern]),
        repository_id="this-cell",
        pattern_projection=True,
    )
    assert attempt.candidates == []


def test_advisory_pattern_proposal_is_not_a_derived_candidate():
    hit = _pattern_dense_hit()
    hit["metadata"]["authority"] = "advisory"
    hit["metadata"]["evidence_class"] = "[H]"
    attempt = retrieve(
        "ordinary knowledge",
        dense_store=_FakeDenseStore([hit]),
        pattern_projection=True,
    )
    assert attempt.candidates == []


# ── Lucene escaping (p4_activation_gate — the retrieval census measured the lexical leg ────
# silently dying on real, punctuation-heavy work-item text) ─────────────────────────────────


class TestLuceneEscape:
    """``_lucene_escape`` (``agentic_dynamics.knowledge.graph``) neutralizes Lucene classic
    QueryParser syntax so ``search_fulltext``/``search_knowledge_fulltext`` matches free text
    literally instead of raising a parser error on a file path, a call, or a CLI flag — the
    exact shape of a real ``QueryPlan.lexical_query`` (see ``build_query_plan``).
    """

    def test_plain_words_are_unchanged(self):
        from agentic_dynamics.knowledge.graph import _lucene_escape

        assert _lucene_escape("task manager api story") == "task manager api story"

    def test_file_path_slashes_are_escaped(self):
        from agentic_dynamics.knowledge.graph import _lucene_escape

        escaped = _lucene_escape("src/agentic_dynamics/knowledge/retrieval.py")
        assert escaped == r"src\/agentic_dynamics\/knowledge\/retrieval.py"

    def test_parens_and_colon_are_escaped(self):
        from agentic_dynamics.knowledge.graph import _lucene_escape

        escaped = _lucene_escape("retrieve() fallback_mode: full")
        assert escaped == r"retrieve\(\) fallback_mode\: full"

    def test_a_literal_backslash_is_escaped_exactly_once(self):
        from agentic_dynamics.knowledge.graph import _lucene_escape

        assert _lucene_escape(r"a\b") == r"a\\b"

    def test_search_fulltext_escapes_before_sending_the_query(self, monkeypatch):
        """``search_fulltext`` must send the ESCAPED query as the Cypher ``$query`` param."""
        from agentic_dynamics.knowledge import graph as graph_module

        client = graph_module.Neo4jClient.__new__(graph_module.Neo4jClient)
        captured: dict = {}

        def _fake_run(query_str, params):
            captured["params"] = params
            return []

        monkeypatch.setattr(client, "_run", _fake_run)
        client.search_fulltext("knowledge_text_ft", "retrieve() RRF")
        assert captured["params"]["query"] == r"retrieve\(\) RRF"


class TestKnowledgeFulltextCommitExemption:
    """Design B1's lexical layer: ``search_knowledge_fulltext`` exempts the knowledge
    authorities from the commit pre-filter, while ``search_fulltext`` (the Step path and
    any caller that passes no exemptions) stays back-compatible. Hermetic — a stubbed
    ``_run`` captures the built Cypher + params without a live Neo4j.
    """

    def _client(self, monkeypatch, captured):
        from agentic_dynamics.knowledge import graph as graph_module

        client = graph_module.Neo4jClient.__new__(graph_module.Neo4jClient)

        def _fake_run(query_str, params):
            captured["query"] = query_str
            captured["params"] = params
            return []

        monkeypatch.setattr(client, "_run", _fake_run)
        return client

    def test_kb_fulltext_passes_the_three_knowledge_authorities(self, monkeypatch):
        captured: dict = {}
        client = self._client(monkeypatch, captured)
        client.search_knowledge_fulltext("task manager api", commit="abc")
        assert set(captured["params"]["exempt"]) == {"MEASURED", "DERIVED", "ADVISORY"}
        assert "OR node.authority IN $exempt" in captured["query"]

    def test_step_fulltext_without_exemptions_stays_back_compatible(self, monkeypatch):
        # The default (no exemptions) must NOT emit the authority clause — Step nodes
        # carry no authority property and the historical filter shape is unchanged.
        captured: dict = {}
        client = self._client(monkeypatch, captured)
        client.search_fulltext("step_text_ft", "websocket", commit="abc")
        assert "exempt" not in captured["params"]
        assert "authority" not in captured["query"]

    def test_no_commit_never_emits_the_exemption_clause(self, monkeypatch):
        # With no commit filter there is no WHERE at all (back-compatible), even on the
        # knowledge path.
        captured: dict = {}
        client = self._client(monkeypatch, captured)
        client.search_knowledge_fulltext("task manager api")
        assert "exempt" not in captured["params"]
        assert "WHERE" not in captured["query"]


# ── Query-shape classification + source-type ordering (k3 — the finding-layer wave) ──

FINDINGS_QUERY = (
    "what did the control database evidence wave conclude about per-phase finding records"
)
FINDINGS_OBJECTIVE = "determine what the control_db_evidence wave concluded"
CODE_QUERY = "implement the function build_step_graph and return its graph structure"
CODE_OBJECTIVE = ""


def test_query_shape_classifier_is_deterministic_and_named():
    shape = classify_query_shape(
        build_query_plan(FINDINGS_QUERY), phase_objective=FINDINGS_OBJECTIVE
    )
    assert shape is QueryShape.FINDINGS
    again = classify_query_shape(
        build_query_plan(FINDINGS_QUERY), phase_objective=FINDINGS_OBJECTIVE
    )
    assert shape is again
    assert {s.value for s in QueryShape} == {"findings", "code", "neutral"}
    assert QueryShape.NEUTRAL.value == "neutral"


def test_query_shape_classifier_distinguishes_code_and_neutral():
    assert (
        classify_query_shape(build_query_plan(CODE_QUERY), phase_objective=CODE_OBJECTIVE)
        is QueryShape.CODE
    )
    # A plain task phrasing with neither findings vocabulary nor code structure stays neutral
    # (the shape that preserves the pre-existing fusion behaviour).
    assert classify_query_shape(build_query_plan("build a task manager api")) is QueryShape.NEUTRAL
    assert classify_query_shape(build_query_plan("websocket reload")) is QueryShape.NEUTRAL


def test_source_ordering_bucket_maps_source_type_and_evidence_class():
    # A finding with measured evidence is distilled ``evidence`` content.
    assert source_ordering_bucket(source_type="finding", evidence_class="[M]") == "evidence"
    # A code record is always the bare ``code`` surface, regardless of its [C] class.
    assert source_ordering_bucket(source_type="code", evidence_class="[C]") == "code"
    # A review (heuristic [H]) is distilled ``advisory`` content — it still outranks code
    # on a findings query (the SHAPE names reviews explicitly).
    assert source_ordering_bucket(source_type="review", evidence_class="[H]") == "advisory"
    # An empty source_type is ``untyped`` — and only an empty source_type is.
    assert source_ordering_bucket(source_type="", evidence_class="[C]") == "untyped"
    # A typed record of an unknown type is never demoted to the untyped bucket.
    assert source_ordering_bucket(source_type="still_typed", evidence_class="") == "advisory"


def test_source_type_priors_are_intent_conditional_and_finite():
    # Findings shape: distilled content outranks code; code is never suppressed (1.0).
    assert FINDINGS_QUERY_TYPE_PRIORS["evidence"] > 1.0
    assert FINDINGS_QUERY_TYPE_PRIORS["advisory"] > FINDINGS_QUERY_TYPE_PRIORS["code"]
    assert FINDINGS_QUERY_TYPE_PRIORS["code"] == 1.0
    assert (
        source_type_prior("evidence", QueryShape.FINDINGS) == FINDINGS_QUERY_TYPE_PRIORS["evidence"]
    )
    # Code shape: code stays first at comparable relevance.
    assert CODE_QUERY_TYPE_PRIORS["code"] == 1.0
    assert CODE_QUERY_TYPE_PRIORS["evidence"] < 1.0
    # NEUTRAL / None resolve to the identity prior (pre-existing scores unchanged).
    assert source_type_prior("evidence", QueryShape.NEUTRAL) == 1.0
    assert source_type_prior("code", None) == 1.0
    # The untyped bucket ties the lowest typed prior under each active shape (hard rule 4):
    # it can never out-rank a typed record it ties with on score.
    assert source_type_prior("untyped", QueryShape.CODE) == CODE_QUERY_TYPE_PRIORS["advisory"]
    assert source_type_prior("untyped", QueryShape.FINDINGS) == FINDINGS_QUERY_TYPE_PRIORS["code"]
    assert source_type_prior("untyped", QueryShape.NEUTRAL) == 1.0


def test_untyped_tiebreak_tier_is_last_under_every_shape():
    # Hard rule 4: at an equal fused score an untyped record sorts after every typed bucket,
    # under every query shape (NEUTRAL included).
    for shape in (None, QueryShape.NEUTRAL, QueryShape.FINDINGS, QueryShape.CODE):
        untyped = ordering_tiebreak_tier("untyped", shape)
        assert untyped > ordering_tiebreak_tier("evidence", shape)
        assert untyped > ordering_tiebreak_tier("advisory", shape)
        assert untyped > ordering_tiebreak_tier("code", shape)


def _typed_dense_hit(
    cid: str,
    text: str,
    *,
    source_type: str,
    authority: str,
    evidence_class: str,
    distance: float = 0.1,
) -> dict:
    hit = _dense_hit(cid, text, authority=authority, distance=distance)
    hit["metadata"]["source_type"] = source_type
    hit["metadata"]["evidence_class"] = evidence_class
    return hit


# A distilled finding (MEASURED [M]) and a bare code signature (SOURCE [C]) that both match
# the same question. The code hit is returned by the store FIRST (dense_rank 0, the better raw
# leg position) so the ordering test must overcome a relevance *disadvantage*, not coast on it.
def _finding_and_code_hits():
    finding = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable evidence: "
        "status, tests verdict, cost, and commit recorded on every phase",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )
    code = _typed_dense_hit(
        "k_code",
        "def _record_phase_evidence(phase, attempt): return ledger.write(phase, attempt)",
        source_type="code",
        authority="source",
        evidence_class="[C]",
    )
    return [code, finding]  # code first in raw leg order (rank 0), finding second (rank 1)


def test_findings_query_returns_the_finding_above_code(monkeypatch):
    # (a) A phase-objective/findings-shaped query over a synthetic corpus (a finding record +
    # a code record both matching) returns the finding FIRST — the source-type prior overcomes
    # the code record's better raw dense rank.
    _no_embedder(monkeypatch)
    attempt = retrieve(
        FINDINGS_QUERY,
        dense_store=_FakeDenseStore(_finding_and_code_hits()),
        phase_objective=FINDINGS_OBJECTIVE,
    )
    assert attempt.query_plan.pattern_projection is False
    ids = [c.id for c in attempt.candidates]
    assert ids.index("k_finding") < ids.index("k_code")
    assert attempt.candidates[0].id == "k_finding"
    finding = next(c for c in attempt.candidates if c.id == "k_finding")
    code = next(c for c in attempt.candidates if c.id == "k_code")
    assert finding.fused_score > code.fused_score
    # The code record is NOT suppressed — it still surfaces and remains selectable.
    assert code in attempt.candidates
    assert any(c.id == "k_code" for c in attempt.selected_evidence)
    # The attempt records the weights version that introduced the ordering signal.
    assert attempt.weights_version == WEIGHTS_VERSION


def test_neutral_query_keeps_code_first_and_identity_scores(monkeypatch):
    # The same corpus under a NEUTRAL-shaped query must NOT be re-ranked by source type: code
    # keeps its better raw position and every fused score equals the pre-existing computation
    # (no blanket code suppression, no source-type prior in neutral shape).
    _no_embedder(monkeypatch)
    attempt = retrieve(
        "store the completed phase rows in the ledger store",
        dense_store=_FakeDenseStore(_finding_and_code_hits()),
    )
    assert classify_query_shape(attempt.query_plan) is QueryShape.NEUTRAL
    ids = [c.id for c in attempt.candidates]
    assert ids.index("k_code") < ids.index("k_finding")
    code = next(c for c in attempt.candidates if c.id == "k_code")
    finding = next(c for c in attempt.candidates if c.id == "k_finding")
    expected_code = compute_fused_score(
        lexical_rank=None,
        dense_rank=0,
        authority=Authority.SOURCE,
        freshness=1.0,
        exact_identifier_match=False,
        conflict=False,
    )
    expected_finding = compute_fused_score(
        lexical_rank=None,
        dense_rank=1,
        authority=Authority.MEASURED,
        freshness=1.0,
        exact_identifier_match=False,
        conflict=False,
    )
    assert code.fused_score == pytest.approx(expected_code)
    assert finding.fused_score == pytest.approx(expected_finding)


def test_code_query_keeps_code_first_even_when_finding_is_raw_better(monkeypatch):
    # (b) A code-shaped query (a function name + structure words) returns the code record
    # FIRST — even when the finding record occupies the better raw dense position.
    _no_embedder(monkeypatch)
    hits = list(reversed(_finding_and_code_hits()))  # finding@0 (raw better), code@1
    attempt = retrieve(CODE_QUERY, dense_store=_FakeDenseStore(hits))
    assert classify_query_shape(attempt.query_plan) is QueryShape.CODE
    ids = [c.id for c in attempt.candidates]
    assert ids.index("k_code") < ids.index("k_finding")
    assert attempt.candidates[0].id == "k_code"
    code = next(c for c in attempt.candidates if c.id == "k_code")
    finding = next(c for c in attempt.candidates if c.id == "k_finding")
    assert code.fused_score > finding.fused_score


@pytest.mark.parametrize(
    "shape, typed_source_type, typed_evidence_class",
    [
        (None, "code", "[C]"),
        (QueryShape.NEUTRAL, "code", "[C]"),
        (QueryShape.FINDINGS, "code", "[C]"),  # code ties untyped (both prior 1.0) in findings
        (QueryShape.CODE, "finding", "[M]"),  # content ties untyped (both prior 0.85) in code
    ],
)
def test_untyped_never_outranks_typed_at_equal_scores(
    shape, typed_source_type, typed_evidence_class
):
    # (c) At EQUAL fused scores an untyped record (empty source_type) never outranks a typed
    # one, under every query shape. The typed candidate's bucket is chosen so its prior ties
    # the untyped prior under the shape → identical compute_fused_score; only the tie-break
    # tier can separate them.
    typed = _cand(
        "k_typed",
        text="a record that matches the query",
        authority=Authority.SOURCE,
        dense_rank=0,
        source_type=typed_source_type,
        evidence_class=typed_evidence_class,
    )
    untyped = _cand(
        "k_untyped",
        text="a record that matches the query",
        authority=Authority.SOURCE,
        dense_rank=0,
        source_type="",
        evidence_class="",
    )
    fused = fuse_candidates([untyped, typed], exact_terms=[], query_shape=shape)
    assert [c.id for c in fused] == ["k_typed", "k_untyped"]
    # The equal-score precondition holds: without the tie-break the two would be adjacent.
    assert fused[0].fused_score == fused[1].fused_score


def test_untyped_typed_mixed_batch_keeps_untyped_last_at_equal_scores():
    # Three candidates at an equal fused score — a distilled finding, a code record, and an
    # untyped one — sort by score then by the shape's tiers; untyped is always last.
    base = dict(
        text="equal relevance everywhere",
        authority=Authority.MEASURED,
        dense_rank=0,
    )
    finding = Candidate(
        id="f",
        text=base["text"],
        authority=base["authority"],
        dense_rank=base["dense_rank"],
        source_type="finding",
        evidence_class="[M]",
        content_hash="h:eq1",
        locator="f",
    )
    code = Candidate(
        id="c",
        text=base["text"],
        authority=base["authority"],
        dense_rank=base["dense_rank"],
        source_type="code",
        evidence_class="[C]",
        content_hash="h:eq2",
        locator="c",
    )
    untyped = Candidate(
        id="u",
        text=base["text"],
        authority=base["authority"],
        dense_rank=base["dense_rank"],
        content_hash="h:eq3",
        locator="u",
    )
    for shape in (QueryShape.NEUTRAL, QueryShape.FINDINGS, QueryShape.CODE):
        fused = fuse_candidates([finding, code, untyped], exact_terms=[], query_shape=shape)
        assert fused[-1].id == "u"
        assert set(c.id for c in fused) == {"f", "c", "u"}


# ── k4 no-silent-empties: source-type resolution + untyped exclusion (the finding-layer wave) ──
#
# The retrieval probe (2026-09-02) returned 40 empty-source_type candidates of 61 selected for a
# findings query. Investigation: nothing CURRENT writes an untyped record (record_factory.build_record
# requires source_type); the empties are STALE STORE METADATA — the dense leg's Chroma population was
# written by an older projection (pre-637fd8455) that omitted the source_type property, while the same
# records' durable artifacts (kb/<id>.json) carry the real type. k4 fixes retrieval two ways:
#   1. TYPE them: a source_type_resolver side channel (durable-artifact-backed in default_retrieve_fn)
#      types a candidate whose store metadata is silent, so it never enters selection untyped.
#   2. EXCLUDE-with-reason: a candidate still untyped after resolution is excluded from the top-K when
#      a typed candidate exists, with the exclusion recorded on the attempt (UNTYPED_EXCLUDED_REASON).
# These tests are hermetic: they inject a resolver mapping a stale knowledge_id -> its real type.


def _untyped_dense_hit(cid, text, *, authority="source"):
    """A dense-leg hit whose metadata carries NO source_type (the pre-637fd8455 store shape)."""
    return {
        "id": cid,
        "document": text,
        "metadata": {"authority": authority, "content_hash": f"hash:{cid}"},
        "distance": 0.1,
    }


def test_k4_resolver_types_stale_metadata_candidate():
    # (a) A candidate whose store metadata is silent (an older projection) is TYPED from the
    # authoritative resolver before it can participate: it carries the resolved type, never "".
    resolver = {"stale-review-1": "review"}
    attempt = retrieve(
        "task manager api coherence review",
        dense_store=_FakeDenseStore(
            [_untyped_dense_hit("stale-review-1", "task_manager_api coherence review text")]
        ),
        source_type_resolver=lambda cid: resolver.get(cid),
    )
    cand = next(c for c in attempt.candidates if c.id == "stale-review-1")
    assert cand.source_type == "review"
    assert cand.id in [c.id for c in attempt.selected_evidence]
    assert attempt.untyped_excluded == []  # typed, so never excluded


def test_k4_still_untyped_candidate_is_excluded_with_recorded_reason_when_typed_exists():
    # (b) A candidate that remains untyped AFTER the resolver was consulted never participates in
    # selection ahead of a typed one: it is excluded from the top-K and the exclusion is recorded.
    resolver = {}  # resolves nothing — the stale record stays untyped
    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )
    stale = _untyped_dense_hit("stale-1", "a matching but untyped stale record")
    attempt = retrieve(
        "control db evidence finding",
        dense_store=_FakeDenseStore([stale, typed]),
        source_type_resolver=lambda cid: resolver.get(cid),
    )
    selected_ids = {c.id for c in attempt.selected_evidence}
    assert "k_finding" in selected_ids
    assert "stale-1" not in selected_ids  # excluded from the top-K — never ahead of a typed one
    assert {"id": "stale-1", "reason": UNTYPED_EXCLUDED_REASON} in attempt.untyped_excluded
    # The exclusion is recorded, never silent: the attempt surfaces it in its audit dict.
    assert any(e["id"] == "stale-1" for e in attempt.to_dict()["untyped_excluded"])


def test_k4_untyped_exclusion_reason_is_deterministic_and_names_hard_rule():
    assert UNTYPED_EXCLUDED_REASON.startswith("empty source_type:")
    assert "hard rule 4" in UNTYPED_EXCLUDED_REASON


def test_k4_all_untyped_legacy_pool_remains_selectable():
    # Back-compat: a pool that is ENTIRELY untyped (a pure legacy store with no typed alternative)
    # still selects — there is no typed record for an untyped one to displace.
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([_seed_hit()]),
    )
    assert attempt.untyped_excluded == []
    assert {c.id for c in attempt.selected_evidence} == {"k_seed"}


def test_k4_lexical_leg_types_a_record_the_dense_leg_could_not():
    # Cross-leg typing: the SAME record surfaced by the dense leg (silent metadata) and by the typed
    # lexical leg (Neo4j carries source_type) must adopt the typed value on the shared candidate.
    dense = _FakeDenseStore([_untyped_dense_hit("shared-kb", "control db evidence finding text")])
    graph = _FakeGraph(
        lexical_hits=[
            {
                "id": "elem:shared",
                "properties": {
                    "knowledge_id": "shared-kb",
                    "entity_id": "ent_kb",
                    "text": "control db evidence finding text",
                    "authority": "measured",
                    "source_type": "finding",
                },
                "score": 0.9,
            }
        ]
    )
    attempt = retrieve("control db evidence", dense_store=dense, graph_client=graph)
    shared = next(c for c in attempt.candidates if c.id == "shared-kb")
    assert shared.source_type == "finding"  # typed by the lexical leg, never left untyped
    assert shared.id in [c.id for c in attempt.selected_evidence]


# ── u3/F3: a throwing resolver is a NAMED diagnostic, not a clean absence ──
#
# Before the repair ``_resolve_source_type`` caught every Exception and returned "", so a
# resolver that FAILED (artifact store offline, resolver bug) was indistinguishable from one
# that authoritatively returned None. F3 separates them: a raise records a named diagnostic on
# the attempt's leg_errors, a clean None records nothing, and the phase never fails either way.


def test_f3_throwing_resolver_records_named_diagnostic_and_retrieval_returns():
    """F3 (u3): a resolver that RAISES is recorded, never swallowed into a silent empty.

    The phase stays safe — retrieval still returns and the candidate stays untyped (then
    excluded from the top-K when a typed alternative exists) — but the failure is a NAMED
    diagnostic on the attempt record, so an auditor can tell it from an authoritative empty.
    """

    def _boom(cid):
        raise RuntimeError("durable artifact store offline")

    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable evidence",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )
    stale = _untyped_dense_hit("stale-throw", "a matching but untyped stale record")
    attempt = retrieve(
        "control db evidence finding",
        dense_store=_FakeDenseStore([stale, typed]),
        source_type_resolver=_boom,
    )

    # The pass returned (this line executes) and the failure is named with its cause.
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in attempt.leg_errors
    assert "RuntimeError" in attempt.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]
    assert "durable artifact store offline" in attempt.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]
    # The failing candidate is NAMED, so the recorded cause is attributable (not an anonymous
    # "something failed"): the auditor can see which record the resolver could not type.
    assert "'stale-throw'" in attempt.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]
    # The candidate remained untyped and the existing untyped-exclusion gate still applied.
    stale_cand = next(c for c in attempt.candidates if c.id == "stale-throw")
    assert stale_cand.source_type == ""
    assert {"id": "stale-throw", "reason": UNTYPED_EXCLUDED_REASON} in attempt.untyped_excluded
    # The diagnostic survives into the audit dict the ledger reads (never a host-only value).
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in attempt.to_dict()["leg_errors"]


def test_f3_clean_absence_resolver_leaves_diagnostic_unset():
    """F3 (u3): an authoritative None is CLEAN absence — it must not set the diagnostic.

    Same evidence shape as the throwing case, but the resolver returns None. The candidate
    stays untyped and is excluded, yet NO ``source_type_resolver`` diagnostic is recorded,
    which is what makes a resolver failure distinguishable from an authoritative empty.
    """
    attempt = retrieve(
        "control db evidence finding",
        dense_store=_FakeDenseStore(
            [
                _untyped_dense_hit("stale-none", "a matching but untyped stale record"),
                _typed_dense_hit(
                    "k_finding",
                    "the control_db_evidence phase concluded per-phase records are reliable",
                    source_type="finding",
                    authority="measured",
                    evidence_class="[M]",
                ),
            ]
        ),
        source_type_resolver=lambda cid: None,
    )

    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in attempt.leg_errors
    stale_cand = next(c for c in attempt.candidates if c.id == "stale-none")
    assert stale_cand.source_type == ""  # still untyped — clean absence, not a typed miss
    assert {"id": "stale-none", "reason": UNTYPED_EXCLUDED_REASON} in attempt.untyped_excluded


def test_f3_empty_and_valid_resolver_returns_leave_diagnostic_unset():
    """F3 (u3): only a RAISE is a failure — an empty or valid return is never diagnosed.

    The prior test covers an authoritative ``None``. This closes the literal
    ``None``/**empty** clause by running (a) a whitespace-only return, which is still a
    clean absence, and (b) a valid typed return, a successful resolution. Neither may set
    :data:`SOURCE_TYPE_RESOLVER_ERROR_KEY`, so a successful or empty typing can never be
    confused with a resolver that failed.
    """
    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )

    # (a) An authoritative whitespace-only return is clean absence, not a failure.
    empty_attempt = retrieve(
        "control db evidence finding",
        dense_store=_FakeDenseStore(
            [
                _untyped_dense_hit("stale-empty", "a matching but untyped stale record"),
                typed,
            ]
        ),
        source_type_resolver=lambda cid: "   ",
    )
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in empty_attempt.leg_errors
    empty_cand = next(c for c in empty_attempt.candidates if c.id == "stale-empty")
    assert empty_cand.source_type == ""  # clean absence, never a fabricated type
    assert {
        "id": "stale-empty",
        "reason": UNTYPED_EXCLUDED_REASON,
    } in empty_attempt.untyped_excluded

    # (b) A valid typed return is a successful resolution, not a diagnosed failure.
    valid_attempt = retrieve(
        "control db evidence finding",
        dense_store=_FakeDenseStore(
            [
                _untyped_dense_hit("stale-valid", "a matching but untyped stale record"),
                typed,
            ]
        ),
        source_type_resolver=lambda cid: "decision",
    )
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in valid_attempt.leg_errors
    valid_cand = next(c for c in valid_attempt.candidates if c.id == "stale-valid")
    assert valid_cand.source_type == "decision"  # resolvable typing is not a failure
    assert valid_attempt.untyped_excluded == []


# ── R2: the PRODUCTION resolver's read/parse failure is a named diagnostic, not absence ──
#
# The F3 tests above inject a THROWING callable, so they exercise retrieval's diagnostic but
# never the production resolver that retrieval binds in ``default_retrieve_fn``. That
# resolver caught every artifact-read/JSON failure, returned ``None``, and CACHED it — so a
# store outage read exactly like an authoritative empty (the astra R2 finding). This test
# binds the REAL ``_durable_source_type_resolver()`` to the real ``retrieve`` and drives it
# with an unreadable artifact, a malformed artifact, and a genuinely absent artifact.


def test_production_resolver_unreadable_and_malformed_artifacts_are_named_not_absence(
    tmp_path, monkeypatch
):
    """R2: the production resolver raises on unreadable/malformed artifacts; absence is clean.

    Falsifier for the exact production defect: with the REAL resolver bound to a tmp artifact
    dir, (a) a directory occupying the artifact path (unreadable) and (b) invalid JSON
    (malformed) each set :data:`SOURCE_TYPE_RESOLVER_ERROR_KEY` on the attempt while
    ``retrieve`` still returns; (c) a genuinely absent artifact sets nothing. The failure is
    also NOT memoised: once an artifact becomes readable the same resolver types it, which a
    cached ``None`` would have prevented.
    """
    from agentic_dynamics.knowledge.augment import _durable_source_type_resolver

    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", tmp_path)

    # (a) UNREADABLE: a directory occupies the artifact path, so Path.open() raises.
    (tmp_path / "unreadable.json").mkdir()
    # (b) MALFORMED: the artifact exists but is not valid JSON.
    (tmp_path / "malformed.json").write_text("{not valid json", encoding="utf-8")
    # (c) ABSENT: no file at all for ``absent``.

    resolver = _durable_source_type_resolver()
    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )

    def _attempt(cid):
        return retrieve(
            "control db evidence finding",
            dense_store=_FakeDenseStore(
                [_untyped_dense_hit(cid, "a matching but untyped stale record"), typed]
            ),
            source_type_resolver=resolver,
        )

    # (a) An unreadable artifact is a NAMED operational failure, and the pass returns.
    unreadable = _attempt("unreadable")
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in unreadable.leg_errors
    assert "unreadable" in unreadable.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]
    # The diagnostic survives into the audit dict the phase record reads (never host-only).
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in unreadable.to_dict()["leg_errors"]

    # (b) A malformed artifact is the same named failure, attributed to its candidate.
    malformed = _attempt("malformed")
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in malformed.leg_errors
    assert "malformed" in malformed.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]

    # (c) A genuinely absent artifact is clean absence: no diagnostic (distinguishable).
    absent = _attempt("absent")
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in absent.leg_errors
    absent_cand = next(c for c in absent.candidates if c.id == "absent")
    assert absent_cand.source_type == ""

    # Not memoised as absence: repair the artifact and the SAME resolver now types it. A
    # cached ``None`` (the pre-repair defect) would keep returning a clean empty forever.
    (tmp_path / "unreadable.json").rmdir()
    (tmp_path / "unreadable.json").write_text('{"source_type": "decision"}', encoding="utf-8")
    fixed = _attempt("unreadable")
    fixed_cand = next(c for c in fixed.candidates if c.id == "unreadable")
    assert fixed_cand.source_type == "decision"
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in fixed.leg_errors

    # The same failure reaches the PHASE RECORD, not only the attempt: ``augment_prompt``
    # copies ``attempt.leg_errors`` onto the outcome, and the context-route record it builds
    # carries them. This closes the review's literal "attempt AND phase record" clause.
    import types

    from agentic_dynamics.knowledge.augment import augment_prompt

    phase_outcome = augment_prompt(
        base_prompt="control db evidence finding",
        goal="goal",
        phase_def={"name": "execute", "kind": "agent"},
        model="m",
        commit_sha="rev",
        inherited_tools=["read"],
        pinned_policy="",
        rag_params={},
        retrieve_fn=lambda **_kwargs: _attempt("malformed"),
        construct_fn=lambda _request: types.SimpleNamespace(
            prompt="AUG",
            fallback=False,
            fallback_reason="",
            evidence_ids=[],
            constructor_attempt_id="c",
            versions={},
            token_counts={},
            cost_usd=0.0,
        ),
    )
    assert phase_outcome.context_route is not None
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in phase_outcome.context_route["leg_errors"]


# ── R2a: an OBSTRUCTED artifact store must not read as clean absence (the astra repair) ──
#
# ``Path.exists()`` is not an authoritative absence test: when a parent path component is a
# regular file (``<file>/<id>.json`` is ENOTDIR) ``exists()`` swallows the ``OSError`` and
# returns ``False``, so the production resolver cached ``None`` and an outage read exactly
# like a genuinely missing record. The repair stats the store directory explicitly, so an
# obstruction is a named ``source_type_resolver`` diagnostic while a missing store directory
# and a missing record in a valid directory stay clean absence.


def test_production_resolver_obstructed_store_is_named_not_absence(tmp_path, monkeypatch):
    """R2a: an obstructed artifact store is a NAMED diagnostic, never a cached absence.

    Falsifier for the exact production defect: with ``KB_ARTIFACT_DIR`` pointing at a
    REGULAR FILE, ``<file>/<id>.json`` is ENOTDIR. The repaired resolver stats the store
    directory and raises the typed :class:`SourceTypeResolutionError`, so an untyped
    candidate yields :data:`SOURCE_TYPE_RESOLVER_ERROR_KEY` on the attempt, in its audit
    dict, and on the phase record built by ``augment_prompt`` — while the pass still returns
    the base prompt safely. The failure is NOT memoised: once the store is a valid directory
    holding the artifact, the SAME resolver types the id. A genuinely absent artifact in a
    valid directory sets NO diagnostic. Reverting to ``Path.exists()`` makes the obstructed
    case return clean absence and the first assertion fail.
    """
    from agentic_dynamics.knowledge.augment import (
        _durable_source_type_resolver,
        augment_prompt,
    )

    # OBSTRUCTED: the store path itself is a regular file, so every child is ENOTDIR.
    obstructed = tmp_path / "artifact-store-is-a-file"
    obstructed.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", obstructed)

    resolver = _durable_source_type_resolver()
    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )

    def _attempt(cid):
        return retrieve(
            "control db evidence finding",
            dense_store=_FakeDenseStore(
                [_untyped_dense_hit(cid, "a matching but untyped stale record"), typed]
            ),
            source_type_resolver=resolver,
        )

    # The pass returned (this line executes) and the obstruction is a NAMED diagnostic.
    obstructed_attempt = _attempt("obstructed")
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in obstructed_attempt.leg_errors
    assert "obstructed" in obstructed_attempt.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]
    assert "not a directory" in obstructed_attempt.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]
    # The diagnostic survives into the audit dict the phase record reads (never host-only).
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in obstructed_attempt.to_dict()["leg_errors"]
    # The candidate stayed untyped; an obstructed store never fabricates a type.
    obstructed_cand = next(c for c in obstructed_attempt.candidates if c.id == "obstructed")
    assert obstructed_cand.source_type == ""

    # The failure also reaches the PHASE RECORD, and a failing pass safely returns the base
    # prompt instead of blocking (the seam's invariant).
    def _raise_construct(_request):
        raise RuntimeError("constructor offline")

    phase_outcome = augment_prompt(
        base_prompt="BASE PROMPT PRESERVED",
        goal="goal",
        phase_def={"name": "execute", "kind": "agent"},
        model="m",
        commit_sha="rev",
        inherited_tools=["read"],
        pinned_policy="",
        rag_params={},
        retrieve_fn=lambda **_kwargs: _attempt("obstructed"),
        construct_fn=_raise_construct,
    )
    assert phase_outcome.context_route is not None
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in phase_outcome.context_route["leg_errors"]
    assert phase_outcome.prompt == "BASE PROMPT PRESERVED"
    assert phase_outcome.fallback is True

    # NOT MEMOISED: repoint the store at a valid directory holding the artifact and the SAME
    # resolver now types it — a cached ``None`` (the pre-repair defect) could never recover.
    valid = tmp_path / "valid-store"
    valid.mkdir()
    (valid / "obstructed.json").write_text('{"source_type": "decision"}', encoding="utf-8")
    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", valid)

    repaired_attempt = _attempt("obstructed")
    repaired_cand = next(c for c in repaired_attempt.candidates if c.id == "obstructed")
    assert repaired_cand.source_type == "decision"
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in repaired_attempt.leg_errors

    # CLEAN ABSENCE: a genuinely absent artifact in a valid directory sets NO diagnostic.
    absent_attempt = _attempt("absent")
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in absent_attempt.leg_errors
    absent_cand = next(c for c in absent_attempt.candidates if c.id == "absent")
    assert absent_cand.source_type == ""


# ── A9-R2a: an OBSTRUCTED individual ARTIFACT lookup must be classified, not absence ──
#
# The A8-R2a repair classified an obstructed STORE directory but still tested the individual
# artifact with ``Path.exists()``. That method follows a symlink and swallows the ``OSError``
# when the link's TARGET is obstructed — a parent component of the target is a regular file,
# so resolving the link is ENOTDIR (errno 20) — returning ``False`` for an outage exactly as
# for a genuinely missing record. This unit stats the individual artifact and CLASSIFIES the
# result: ENOENT is clean, memoised absence; any other ``OSError`` raises the typed failure
# and never touches the cache, so a repaired store is visible to the same resolver instance.


def test_production_resolver_obstructed_artifact_symlink_is_named_not_absence(
    tmp_path, monkeypatch
):
    """A9-R2a: an ENOTDIR artifact symlink is a NAMED diagnostic, never a cached absence.

    Falsifier for the exact production defect: with a VALID store directory holding a flat
    64-hex knowledge id whose ``<id>.json`` symlink targets a child of a regular file,
    ``os.stat(<artifact>)`` raises ``NotADirectoryError``. The repaired resolver raises the
    typed :class:`SourceTypeResolutionError`, so an untyped candidate yields
    :data:`SOURCE_TYPE_RESOLVER_ERROR_KEY` on the attempt, in its audit dict, and on the
    phase record built by ``augment_prompt`` — while the base prompt is returned. The failure
    is NOT memoised: once the symlink is replaced by a valid artifact the SAME resolver types
    the id. A genuinely missing artifact in the valid store sets NO diagnostic. Reverting to
    ``Path.exists()`` makes the obstructed case return clean absence and the first assertion
    fail.
    """
    from agentic_dynamics.knowledge.augment import (
        _durable_source_type_resolver,
        augment_prompt,
    )

    store = tmp_path / "store"
    store.mkdir()
    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", store)

    # A flat 64-hex knowledge id (the resolver's own id shape), whose artifact symlink's
    # target is a child of a REGULAR FILE — following it is ENOTDIR, which ``Path.exists()``
    # reports as ``False``.
    blocked_id = "a" * 64
    missing_id = "b" * 64
    target_parent = tmp_path / "regular-file"
    target_parent.write_text("not a directory", encoding="utf-8")
    (store / f"{blocked_id}.json").symlink_to(target_parent / "child.json")

    resolver = _durable_source_type_resolver()
    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )

    def _attempt(cid):
        return retrieve(
            "control db evidence finding",
            dense_store=_FakeDenseStore(
                [_untyped_dense_hit(cid, "a matching but untyped stale record"), typed]
            ),
            source_type_resolver=resolver,
        )

    # The pass returned (this line executes) and the obstruction is a NAMED diagnostic that
    # names the artifact and the stat error.
    obstructed = _attempt(blocked_id)
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in obstructed.leg_errors
    diagnostic = obstructed.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]
    assert blocked_id in diagnostic
    assert "NotADirectoryError" in diagnostic
    # The diagnostic survives into the audit dict the phase record reads (never host-only).
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in obstructed.to_dict()["leg_errors"]
    obstructed_cand = next(c for c in obstructed.candidates if c.id == blocked_id)
    assert obstructed_cand.source_type == ""

    # The failure also reaches the PHASE RECORD while the base prompt is safely returned (the
    # seam's never-blocks invariant).
    def _raise_construct(_request):
        raise RuntimeError("constructor offline")

    phase_outcome = augment_prompt(
        base_prompt="BASE PROMPT PRESERVED",
        goal="goal",
        phase_def={"name": "execute", "kind": "agent"},
        model="m",
        commit_sha="rev",
        inherited_tools=["read"],
        pinned_policy="",
        rag_params={},
        retrieve_fn=lambda **_kwargs: _attempt(blocked_id),
        construct_fn=_raise_construct,
    )
    assert phase_outcome.context_route is not None
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in phase_outcome.context_route["leg_errors"]
    assert phase_outcome.prompt == "BASE PROMPT PRESERVED"
    assert phase_outcome.fallback is True

    # NOT MEMOISED: replace the obstructed symlink with a valid artifact and the SAME resolver
    # types the id — a cached ``None`` (the pre-repair defect) could never recover.
    (store / f"{blocked_id}.json").unlink()
    (store / f"{blocked_id}.json").write_text('{"source_type": "decision"}', encoding="utf-8")
    repaired = _attempt(blocked_id)
    repaired_cand = next(c for c in repaired.candidates if c.id == blocked_id)
    assert repaired_cand.source_type == "decision"
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in repaired.leg_errors

    # CLEAN ABSENCE: a genuinely missing artifact in the valid store sets NO diagnostic.
    absent = _attempt(missing_id)
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in absent.leg_errors
    absent_cand = next(c for c in absent.candidates if c.id == missing_id)
    assert absent_cand.source_type == ""


def test_production_resolver_missing_store_directory_is_clean_absence(tmp_path, monkeypatch):
    """R2a: a MISSING artifact-store directory stays clean absence, not a diagnosed failure.

    The obstruction repair distinguishes a store path that does not exist at all (no durable
    layer created yet) from one that exists but is not a directory. Only the latter is an
    operational failure; a missing store is the ordinary "no durable artifact to type from"
    case and must remain a clean, memoised ``None`` with no diagnostic.
    """
    from agentic_dynamics.knowledge.augment import _durable_source_type_resolver

    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", tmp_path / "does-not-exist")
    resolver = _durable_source_type_resolver()
    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )
    attempt = retrieve(
        "control db evidence finding",
        dense_store=_FakeDenseStore(
            [_untyped_dense_hit("missing-store", "a matching but untyped stale record"), typed]
        ),
        source_type_resolver=resolver,
    )
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in attempt.leg_errors
    cand = next(c for c in attempt.candidates if c.id == "missing-store")
    assert cand.source_type == ""


# ── R2b: a MALFORMED source_type FIELD is a named diagnostic, not absence or a fake type ──
#
# The production resolver coerced the artifact field with ``str(rec.get("source_type") or "")``.
# That collapses every falsy JSON value to clean absence (``[]`` and ``false`` became ``""``)
# and FABRICATES a type string from any truthy non-string (``{"bad": 1}`` became
# ``"{'bad': 1}"``). The repair validates the field's TYPE: missing/``null``/empty-string stay
# clean absence; a string is normalized; any other JSON type raises the typed
# ``SourceTypeResolutionError``, which retrieval records as a named diagnostic while the pass
# continues, and which is never memoised.


def test_production_resolver_malformed_source_type_field_is_named_not_absent(tmp_path, monkeypatch):
    """R2b: list/bool/dict ``source_type`` values are named diagnostics with safe continuation.

    Falsifier for the exact production defect: with the REAL resolver bound to a tmp artifact
    dir, ``{"source_type": []}``, ``{"source_type": false}`` and ``{"source_type": {"bad": 1}}``
    each set :data:`SOURCE_TYPE_RESOLVER_ERROR_KEY` while ``retrieve`` still returns, and each
    candidate stays untyped (never ``"[]"`` / ``"false"`` / ``"{'bad': 1}"``). The failure is NOT
    memoised: rewriting the artifact with a real string type makes the SAME resolver type it. A
    missing field, an explicit ``null`` and a whitespace-only string remain clean absence with
    no diagnostic. Reverting to ``str(rec.get("source_type") or "")`` makes the malformed
    assertions fail: the list/bool collapse to clean absence and the dict fabricates a string.
    """
    from agentic_dynamics.knowledge.augment import (
        _durable_source_type_resolver,
        augment_prompt,
    )

    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", tmp_path)

    # MALFORMED fields: each is a real JSON type the artifact never meant as a type string.
    malformed = {
        "listy": ("list", '{"source_type": []}'),
        "booly": ("bool", '{"source_type": false}'),
        "dicty": ("dict", '{"source_type": {"bad": 1}}'),
    }
    for cid, (_type_name, payload) in malformed.items():
        (tmp_path / f"{cid}.json").write_text(payload, encoding="utf-8")
    # CLEAN ABSENCE: a missing field, an explicit null, and a whitespace-only string.
    (tmp_path / "missing-field.json").write_text("{}", encoding="utf-8")
    (tmp_path / "null-field.json").write_text('{"source_type": null}', encoding="utf-8")
    (tmp_path / "blank-field.json").write_text('{"source_type": "   "}', encoding="utf-8")

    resolver = _durable_source_type_resolver()
    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )

    def _attempt(cid):
        return retrieve(
            "control db evidence finding",
            dense_store=_FakeDenseStore(
                [_untyped_dense_hit(cid, "a matching but untyped stale record"), typed]
            ),
            source_type_resolver=resolver,
        )

    # Each malformed field is a NAMED diagnostic naming the offending type, and the candidate
    # stays untyped — never a fabricated string.
    fabricated = {"[]", "false", "{'bad': 1}"}
    for cid, (type_name, _payload) in malformed.items():
        attempt = _attempt(cid)
        assert SOURCE_TYPE_RESOLVER_ERROR_KEY in attempt.leg_errors, cid
        diagnostic = attempt.leg_errors[SOURCE_TYPE_RESOLVER_ERROR_KEY]
        assert "non-string source_type" in diagnostic
        assert f"of type {type_name}" in diagnostic
        # The diagnostic survives into the audit dict the phase record reads.
        assert SOURCE_TYPE_RESOLVER_ERROR_KEY in attempt.to_dict()["leg_errors"]
        cand = next(c for c in attempt.candidates if c.id == cid)
        assert cand.source_type == ""
        assert cand.source_type not in fabricated

    # Clean absence stays silent in all three shapes (missing, null, blank string).
    for cid in ("missing-field", "null-field", "blank-field"):
        attempt = _attempt(cid)
        assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in attempt.leg_errors, cid
        cand = next(c for c in attempt.candidates if c.id == cid)
        assert cand.source_type == ""

    # The diagnostic also reaches the PHASE RECORD while a failing pass safely returns the
    # base prompt (the seam's never-blocks invariant).
    def _raise_construct(_request):
        raise RuntimeError("constructor offline")

    phase_outcome = augment_prompt(
        base_prompt="BASE PROMPT PRESERVED",
        goal="goal",
        phase_def={"name": "execute", "kind": "agent"},
        model="m",
        commit_sha="rev",
        inherited_tools=["read"],
        pinned_policy="",
        rag_params={},
        retrieve_fn=lambda **_kwargs: _attempt("listy"),
        construct_fn=_raise_construct,
    )
    assert phase_outcome.context_route is not None
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY in phase_outcome.context_route["leg_errors"]
    assert phase_outcome.prompt == "BASE PROMPT PRESERVED"
    assert phase_outcome.fallback is True

    # NOT MEMOISED: rewrite the malformed artifact as a real type and the SAME resolver types
    # it — a cached clean absence (the pre-repair ``[]``/``false`` collapse) could never recover.
    (tmp_path / "listy.json").write_text('{"source_type": "decision"}', encoding="utf-8")
    repaired = _attempt("listy")
    repaired_cand = next(c for c in repaired.candidates if c.id == "listy")
    assert repaired_cand.source_type == "decision"
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in repaired.leg_errors


# ── A9-R2b: a malformed PROJECTED source_type METADATA field is named, never fabricated ──
#
# The A8-R2b repair validated the DURABLE artifact's ``source_type`` field, but the store's
# PROJECTED metadata — the Chroma/Neo4j property that reaches ``retrieve`` directly — was still
# coerced by ``_source_type`` with ``str(metadata.get("source_type", "") or "")``. That
# FABRICATED a type string from a truthy non-string (``{"bad": 1}`` → ``"{'bad': 1}"``) and
# silently collapsed ``[]``/``false`` to clean absence, which was then laundered through the
# authoritative resolver as if the field were legitimately missing. This unit validates the
# projected field's JSON TYPE in ``_resolve_source_type``: an absent key, an explicit ``None``
# and a string keep today's behaviour; any present non-string records
# :data:`SOURCE_TYPE_METADATA_ERROR_KEY`, leaves the candidate UNTYPED, and does NOT consult the
# resolver (a malformed projection is not an authoritative absence).


def test_projected_source_type_non_string_is_named_not_fabricated():
    """A9-R2b: dict/list/bool/number projected ``source_type`` values are named diagnostics.

    Falsifier for the exact projected-metadata defect: with the REAL ``retrieve`` and a fake
    dense store, a hit whose metadata carries ``{"source_type": {"bad": 1}}``, a nonempty list,
    ``[]``, ``False`` or a number must leave ``candidate.source_type == ""`` with
    :data:`SOURCE_TYPE_METADATA_ERROR_KEY` on the attempt, in its audit dict, and on the
    ``augment_prompt`` phase record — and the authoritative resolver must NOT be consulted
    (it would otherwise type the candidate, laundering the malformation as absence). Reverting
    the type validation fabricates ``"{'bad': 1}"`` / ``"['code']"`` or silently erases
    ``[]``/``false`` and fails these assertions.
    """
    from agentic_dynamics.knowledge.augment import augment_prompt

    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )
    malformed = {
        "dicty": {"bad": 1},
        "listy": ["code"],
        "emptylisty": [],
        "booly": False,
        "inty": 7,
    }
    # A resolver that WOULD type any candidate it is handed. Recording its calls proves a
    # malformed projection is never laundered as authoritative absence.
    resolver_calls: list[str] = []

    def _resolver(cid: str) -> str:
        resolver_calls.append(cid)
        return "decision"

    def _attempt(cid: str, value):
        hit = _dense_hit(cid, "a matching projected stale record", authority="source")
        hit["metadata"]["source_type"] = value
        return retrieve(
            "control db evidence finding",
            dense_store=_FakeDenseStore([hit, typed]),
            source_type_resolver=_resolver,
        )

    for cid, value in malformed.items():
        attempt = _attempt(cid, value)
        # The malformation is a NAMED diagnostic that attributes the candidate, and it survives
        # into the audit dict the phase record reads (never a host-only value).
        assert SOURCE_TYPE_METADATA_ERROR_KEY in attempt.leg_errors, cid
        diagnostic = attempt.leg_errors[SOURCE_TYPE_METADATA_ERROR_KEY]
        assert cid in diagnostic, cid
        assert SOURCE_TYPE_METADATA_ERROR_KEY in attempt.to_dict()["leg_errors"], cid
        # The candidate stayed untyped — never a fabricated string.
        cand = next(c for c in attempt.candidates if c.id == cid)
        assert cand.source_type == "", cid
        assert cand.source_type != str(value).strip().lower(), cid
        # The malformed field is NOT handed to the resolver as if absent.
        assert cid not in resolver_calls, cid

    # The diagnostic also reaches the PHASE RECORD while a failing pass safely returns the
    # base prompt (the seam's never-blocks invariant).
    def _raise_construct(_request):
        raise RuntimeError("constructor offline")

    phase_outcome = augment_prompt(
        base_prompt="BASE PROMPT PRESERVED",
        goal="goal",
        phase_def={"name": "execute", "kind": "agent"},
        model="m",
        commit_sha="rev",
        inherited_tools=["read"],
        pinned_policy="",
        rag_params={},
        retrieve_fn=lambda **_kwargs: _attempt("dicty", {"bad": 1}),
        construct_fn=_raise_construct,
    )
    assert phase_outcome.context_route is not None
    assert SOURCE_TYPE_METADATA_ERROR_KEY in phase_outcome.context_route["leg_errors"]
    assert phase_outcome.prompt == "BASE PROMPT PRESERVED"
    assert phase_outcome.fallback is True


def test_projected_source_type_valid_and_absent_controls_are_distinct():
    """A9-R2b controls: a valid projected type resolves; a genuinely absent field stays clean.

    The malformed diagnostic must not swallow the two legitimate shapes. (a) A valid projected
    string (``Code``) is normalized to ``code`` with NO diagnostic and the resolver is never
    consulted. (b) A genuinely absent projected field (and an explicit ``None``, and a
    whitespace-only string) stays clean absence with NO diagnostic while the authoritative
    resolver IS still consulted. These are the distinct controls that make the malformed case
    meaningful: storage metadata, not only durable JSON.
    """
    typed = _typed_dense_hit(
        "k_finding",
        "the control_db_evidence phase concluded per-phase records are reliable",
        source_type="finding",
        authority="measured",
        evidence_class="[M]",
    )

    def _must_not_run(_cid: str) -> str:
        raise AssertionError("the resolver must not be consulted for a valid projected type")

    # (a) A VALID projected string type resolves (normalized) with no diagnostic, and no resolver.
    valid_hit = _dense_hit("projected-code", "a projected code signature", authority="source")
    valid_hit["metadata"]["source_type"] = "Code"
    valid = retrieve(
        "control db evidence finding",
        dense_store=_FakeDenseStore([valid_hit]),
        source_type_resolver=_must_not_run,
    )
    assert SOURCE_TYPE_METADATA_ERROR_KEY not in valid.leg_errors
    assert SOURCE_TYPE_RESOLVER_ERROR_KEY not in valid.leg_errors
    valid_cand = next(c for c in valid.candidates if c.id == "projected-code")
    assert valid_cand.source_type == "code"

    # (b) A genuinely ABSENT projected field, an explicit None and a blank string are clean
    # absence: no diagnostic, and the authoritative resolver is STILL consulted.
    for cid, build in (
        ("projected-absent", lambda m: None),
        ("projected-none", lambda m: m.__setitem__("source_type", None)),
        ("projected-blank", lambda m: m.__setitem__("source_type", "   ")),
    ):
        hit = _dense_hit(cid, "a matching untyped projected record", authority="source")
        build(hit["metadata"])
        calls: list[str] = []

        def _resolver(resolved_cid: str, _calls=calls) -> None:
            _calls.append(resolved_cid)
            return None

        attempt = retrieve(
            "control db evidence finding",
            dense_store=_FakeDenseStore([hit, typed]),
            source_type_resolver=_resolver,
        )
        assert SOURCE_TYPE_METADATA_ERROR_KEY not in attempt.leg_errors, cid
        assert calls == [cid], cid  # the authoritative resolver was still consulted
        cand = next(c for c in attempt.candidates if c.id == cid)
        assert cand.source_type == "", cid


def test_freshness_multiplier_advisory_naive_timestamp_is_utc():
    """A naive ISO timestamp must not crash ADVISORY freshness (live dense probe, 2026-09-10).

    ``datetime.fromisoformat("2026-09-01T00:00:00")`` is naive while the reference clock is
    aware; subtracting them raised TypeError on the first host-side Chroma probe, which
    excluded every ADVISORY record (reviews, decisions) from retrieval.
    """
    from agentic_dynamics.knowledge.retrieval import freshness_multiplier

    fresh = freshness_multiplier(
        authority=Authority.ADVISORY,
        commit_sha="rev-a",
        observed_at="2026-09-01T00:00:00",
        current_commit="rev-b",
        now=datetime(2026, 9, 10, tzinfo=timezone.utc),
    )
    assert fresh is not None and fresh > 0
    stale = freshness_multiplier(
        authority=Authority.ADVISORY,
        commit_sha="rev-a",
        observed_at="2026-01-01T00:00:00",
        current_commit="rev-b",
        now=datetime(2026, 9, 10, tzinfo=timezone.utc),
    )
    assert stale is None


def test_retrieve_expansion_applies_commit_gate_to_source_neighbors():
    """Review-4 A2: an expanded stale SOURCE neighbor never bypasses the commit gate."""
    stale = _expanded_node("k_seed", cid="k_stale_source")
    stale["properties"]["commit_sha"] = "other"
    expanded_knowledge = _expanded_node("k_seed", cid="k_measured_neighbor")
    expanded_knowledge["properties"]["authority"] = "measured"
    expanded_knowledge["properties"]["commit_sha"] = "other"

    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([_seed_hit()]),
        graph_client=_FakeGraph([stale, expanded_knowledge]),
        commit_sha="current",
    )
    candidate_ids = {c.id for c in attempt.candidates}
    assert "k_stale_source" not in candidate_ids
    assert "k_measured_neighbor" in candidate_ids
    assert "k_stale_source" not in {c.id for c in attempt.selected_evidence}


def test_direct_lexical_leg_enforces_acl_scope():
    """Review-5 F3: a foreign-ACL record never surfaces via the direct lexical leg.

    The pre-existing leak: the lexical leg filtered only ``repository_id``, so a record with a
    matching repository but a different ACL scope was selectable.
    """

    def hit():
        h = _knowledge_lexical_hit(cid="foreign-acl", text="task manager api building finding")
        h["properties"]["repository_id"] = "self-a"
        h["properties"]["acl_scope"] = "private-b"
        return h

    leaked = retrieve(
        "build a task manager api",
        dense_store=None,
        graph_client=_FakeGraph(lexical_hits=[hit()]),
        repository_id="self-a",
        acl_scope="private-a",
    )
    assert leaked.candidates == []
    assert leaked.selected_evidence == []

    admitted = retrieve(
        "build a task manager api",
        dense_store=None,
        graph_client=_FakeGraph(lexical_hits=[hit()]),
        repository_id="self-a",
        acl_scope="private-b",
    )
    assert {c.id for c in admitted.candidates} == {"foreign-acl"}


# ── Context layers (register L60, unit u1) ─────────────────────
#
# The gate for ``knowledge/context_layers.py``: the deterministic phase-kind -> layer
# mapping, the explicit-only shared-scope parser, the registered source-type material,
# and the single record builder's stable schema + closed status set with a NAMED absence
# for a failed layer. These tests are pure vocabulary + arithmetic — no store, no network.


def test_context_layers_phase_kind_mapping_is_exact():
    """The routing rule: planning/implementation -> L1; L2 always; verification/review differ."""
    planning = resolve_phase_layers("prior", "agent")
    implementation = resolve_phase_layers("execute", "agent")
    verification = resolve_phase_layers("g_test_gate", "test")
    review = resolve_phase_layers("g_adversarial", "agent")

    # L1 structure is the planning/implementation need.
    assert "L1" in planning.layers
    assert planning.role == "planning"
    assert "L1" in implementation.layers
    assert implementation.role == "implementation"

    # Verification/review resolve differently: history but no structure.
    assert verification.role == "verification"
    assert review.role == "review"
    assert "L2" in verification.layers and "L1" not in verification.layers
    assert "L2" in review.layers and "L1" not in review.layers

    # L3 outcomes land at planning moments, and only there unless a risk hint forces it.
    assert "L3" in planning.layers
    assert "L3" not in implementation.layers
    assert "L3" in resolve_phase_layers("execute", "agent", {"risk": True}).layers

    # Every phase resolves L2 history at open — even an unrecognised one.
    for name, kind in (
        ("prior", "agent"),
        ("execute", "agent"),
        ("g_test_gate", "test"),
        ("g_adversarial", "agent"),
        ("mystery_phase", "agent"),
    ):
        assert "L2" in resolve_phase_layers(name, kind).layers

    # L4 self is NEVER resolved for a cell phase: recorded prohibited, absent from layers.
    for route in (planning, implementation, verification, review):
        assert LAYER_SELF in route.prohibited
        assert LAYER_SELF not in route.layers


def test_context_layers_resolver_is_deterministic():
    """Identical inputs yield an equal route (no clock, no RNG, no store)."""
    first = resolve_phase_layers(
        "execute", "agent", {"risk": True, "shared_history_scopes": ["s1"]}
    )
    second = resolve_phase_layers(
        "execute", "agent", {"risk": True, "shared_history_scopes": ["s1"]}
    )
    assert first == second
    assert first is not second  # distinct objects, identical value (frozen dataclass)
    assert classify_phase_role("prior", "agent") == classify_phase_role("prior", "agent")


def test_shared_history_scopes_is_explicit_only():
    """Explicit repository ids only; absent means empty; empty never means global."""
    assert shared_history_scopes({}) == []
    assert shared_history_scopes(None) == []
    assert shared_history_scopes({"shared_history_scopes": []}) == []
    # Strips, de-dupes (first-seen), and drops empties.
    assert shared_history_scopes(
        {"shared_history_scopes": [" repo-a ", "repo-b", "repo-a", ""]}
    ) == ["repo-a", "repo-b"]
    # Aliases are honoured; a bare string is one scope.
    assert shared_history_scopes({"shared_scopes": ["repo-c"]}) == ["repo-c"]
    assert shared_history_scopes({"shared_repository_ids": "repo-d"}) == ["repo-d"]
    # The explicit global wildcards are refused — a cell can never widen to the whole KB.
    assert shared_history_scopes({"shared_history_scopes": ["*", "global", "all"]}) == []


def test_layer_source_types_names_only_registered_types():
    """Every mapped source type is a member of the one KB vocabulary (knowledge.SOURCE_TYPES)."""
    assert layer_source_types(["L1"]) == ("code",)
    assert layer_source_types([]) == ()
    mapped = layer_source_types(["L2", "L3", "L4", "L1"])
    assert mapped  # the union is nonempty
    assert set(mapped).issubset(set(SOURCE_TYPES))
    # A single string is one layer id, not an iterable of characters.
    assert layer_source_types("L1") == ("code",)


def test_build_context_route_record_stable_schema_and_named_absent():
    """The single builder owns the stable keys and names a failed layer's absence."""
    route = resolve_phase_layers("execute", "agent")
    record = build_context_route_record(
        "execute",
        route,
        None,  # no attempt -> a failed retrieval must be a NAMED absence, never a zero
        {"fallback": True, "fallback_reason": "retrieve_failed", "fallback_mode": "no_rag"},
        shared_scopes=[],
    )
    assert set(record) == set(CONTEXT_ROUTE_RECORD_KEYS)
    assert record["schema"] == CONTEXT_ROUTE_SCHEMA
    assert record["route_status"] == "resolved"
    assert record["shared_scopes"] == []
    by_layer = {entry["layer"]: entry for entry in record["layers"]}
    assert set(by_layer) >= {"L0", "L1", "L2", LAYER_SELF}
    assert by_layer["L0"]["status"] == "served"
    assert by_layer["L1"]["status"] == LAYER_STATUS_NAMED_ABSENT
    assert by_layer["L2"]["status"] == LAYER_STATUS_NAMED_ABSENT
    assert by_layer[LAYER_SELF]["status"] == LAYER_STATUS_EXCLUDED
    # The closed status set holds for every disposition the builder emits.
    assert all(entry["status"] in LAYER_STATUS_SET for entry in record["layers"])
    # The per-layer entry schema is stable too.
    assert all(set(entry) == set(CONTEXT_ROUTE_LAYER_KEYS) for entry in record["layers"])


def test_build_context_route_record_serves_attributes_and_excludes_l4():
    """Served items map to their layer; L4 content is excluded, never served."""
    route = resolve_phase_layers("execute", "agent")
    record = build_context_route_record(
        "execute",
        route,
        {"selected_evidence": [], "leg_errors": {}},
        {
            "selected_evidence": [
                {"id": "k-code", "source_type": "code"},
                {"id": "k-belief", "source_type": "belief"},
            ],
            "fallback": False,
            "fallback_mode": "full",
            "retrieval_leg_errors": {},
        },
        shared_scopes=["shared-repo"],
    )
    by_layer = {entry["layer"]: entry for entry in record["layers"]}
    assert by_layer["L1"]["status"] == "served"
    assert by_layer["L1"]["evidence_ids"] == ["k-code"]
    assert by_layer["L2"]["status"] == "empty"  # clean pass, nothing matched
    assert by_layer[LAYER_SELF]["status"] == LAYER_STATUS_EXCLUDED
    assert by_layer[LAYER_SELF]["evidence_ids"] == ["k-belief"]
    assert record["served_count"] == 1  # the L4 item is excluded, never counted served
    assert record["shared_scopes"] == ["shared-repo"]


def test_build_context_route_record_unknown_route_records_unclassified():
    """An unroutable request records its served items as UNKNOWN, with a layer disposition."""
    record = build_context_route_record(
        "mystery_phase",
        None,
        {"selected_evidence": [], "leg_errors": {}},
        {"selected_evidence": [{"id": "k-untyped", "source_type": ""}]},
        shared_scopes=[],
    )
    assert record["route_status"] == "unknown"
    assert record["role"] == "unknown"
    assert record["served_count"] == 0
    assert record["unclassified"] == [
        {
            "id": "k-untyped",
            "source_type": "untyped",
            "status": LAYER_STATUS_UNKNOWN,
            "reason": "unroutable request: no layer resolved",
        }
    ]
    by_layer = {entry["layer"]: entry for entry in record["layers"]}
    assert by_layer["unclassified"]["status"] == LAYER_STATUS_UNKNOWN
    assert by_layer["unclassified"]["evidence_ids"] == ["k-untyped"]


def test_build_context_route_record_explicit_unknown_sentinel_is_unknown_and_named():
    """R4: the explicit ``LayerRoute.unknown()`` sentinel records ``unknown`` + a reason.

    The public UNKNOWN sentinel resolves NO layers, exactly like ``None``, so both must
    record ``route_status == "unknown"`` with a NAMED routing reason (never a silent
    "resolved"). A route that DID resolve the L2 floor keeps its real material and stays
    ``resolved`` even when its role is unknown — the two cases must not conflate. A served
    non-self item under the sentinel is recorded ``unclassified``/``unknown`` with
    ``served_count == 0``, so no item is ever served without a resolved layer.
    """
    sentinel = build_context_route_record(
        "execute",
        LayerRoute.unknown("execute", "agent"),
        {"selected_evidence": [], "leg_errors": {}},
        {"selected_evidence": [{"id": "k-code", "source_type": "code"}]},
        shared_scopes=[],
    )
    assert sentinel["route_status"] == "unknown"
    assert sentinel["routing_reason"]  # a NAMED reason, never an empty success
    assert sentinel["served_count"] == 0
    assert [item["id"] for item in sentinel["unclassified"]] == ["k-code"]
    by_layer = {entry["layer"]: entry for entry in sentinel["layers"]}
    assert by_layer["unclassified"]["evidence_ids"] == ["k-code"]
    assert by_layer["unclassified"]["status"] == LAYER_STATUS_UNKNOWN
    assert set(sentinel) == set(CONTEXT_ROUTE_RECORD_KEYS)

    none_route = build_context_route_record(
        "execute",
        None,
        {"selected_evidence": [], "leg_errors": {}},
        {"selected_evidence": []},
        shared_scopes=[],
    )
    assert none_route["route_status"] == "unknown"
    assert none_route["routing_reason"]  # the same named default as the sentinel

    # An unknown ROLE that still resolved the L2 floor is resolved, not the sentinel.
    floor = resolve_phase_layers("mystery_phase", "agent")
    assert set(floor.layers) == {"L2"}
    floor_record = build_context_route_record(
        "mystery_phase", floor, None, {"fallback": False}, shared_scopes=[]
    )
    assert floor_record["route_status"] == "resolved"


def test_build_context_route_record_routing_reason_survives_fallback():
    """A8-R4: a competing fallback never erases the routing diagnosis.

    Both unresolved forms — the explicit ``LayerRoute.unknown()`` sentinel and ``None`` —
    must serialize BOTH the named routing reason (``routing_reason``) AND the outcome's
    retrieval/constructor failure (``fallback_reason``). The old
    ``route_unresolved and not fallback_reason`` gating dropped the routing reason whenever
    a fallback existed; this gate refuses that regression. A route that resolved the L2
    floor has no routing failure, so ``routing_reason`` stays empty while ``fallback_reason``
    keeps the retrieval failure.
    """
    sentinel = LayerRoute.unknown("execute", "agent")
    unresolved_forms = ((None, "routing unresolved"), (sentinel, sentinel.reason))
    for route, expected_reason in unresolved_forms:
        for failure in ("retrieve_failed", "construct_failed"):
            record = build_context_route_record(
                "execute",
                route,
                {"selected_evidence": [], "leg_errors": {}},
                {
                    "selected_evidence": [],
                    "fallback": True,
                    "fallback_mode": "no_rag",
                    "fallback_reason": failure,
                },
                shared_scopes=[],
            )
            # BOTH diagnoses coexist; the fallback does not erase the routing reason.
            assert record["fallback_reason"] == failure
            assert record["routing_reason"] == expected_reason
            assert record["route_status"] == "unknown"
            assert set(record) == set(CONTEXT_ROUTE_RECORD_KEYS)

    # A resolved L2-floor route has no routing failure: ``routing_reason`` is empty even
    # when retrieval failed, while ``fallback_reason`` keeps the retrieval failure.
    floor = resolve_phase_layers("mystery_phase", "agent")
    assert set(floor.layers) == {"L2"}
    floor_record = build_context_route_record(
        "mystery_phase",
        floor,
        {"selected_evidence": [], "leg_errors": {}},
        {
            "selected_evidence": [],
            "fallback": True,
            "fallback_mode": "no_rag",
            "fallback_reason": "retrieve_failed",
        },
        shared_scopes=[],
    )
    assert floor_record["routing_reason"] == ""
    assert floor_record["fallback_reason"] == "retrieve_failed"
    assert set(floor_record) == set(CONTEXT_ROUTE_RECORD_KEYS)


def test_build_context_route_record_withheld_only_summary_is_truthful():
    """A9-R1-note: the synthetic ``unclassified`` layer's reason matches what was listed.

    An unresolved route records a synthetic ``unclassified``/``unknown`` layer. Its
    reason must be truthful about the ITEMS it lists: a withheld-only record
    (``served_count == 0``, no served-but-unattributable item) must never claim served
    evidence; a MIXED record names both dispositions. The item-level reasons,
    ``evidence_ids`` and ``served_count`` are the unchanged controls — this gate changes
    only the layer-level summary.

    Falsifier: with the single hardcoded ``served evidence carries no layer disposition``
    string, the withheld-only assertion fails.
    """
    # Withheld-only: one untyped item withheld before construction; nothing served.
    withheld_only = build_context_route_record(
        "mystery_phase",
        None,
        {"selected_evidence": [], "leg_errors": {}},
        {"selected_evidence": []},
        shared_scopes=[],
        withheld_evidence=[{"id": "k-untyped", "source_type": ""}],
    )
    assert withheld_only["route_status"] == "unknown"
    assert withheld_only["served_count"] == 0
    withholding_layer = {e["layer"]: e for e in withheld_only["layers"]}["unclassified"]
    assert withholding_layer["status"] == LAYER_STATUS_UNKNOWN
    assert withholding_layer["reason"] == UNRESOLVED_UNCLASSIFIED_WITHHELD_ONLY_REASON
    # Truthful: it names the withhold and never claims served evidence.
    assert "served evidence carries no layer disposition" not in withholding_layer["reason"]
    assert "no evidence was served" in withholding_layer["reason"]
    assert "withheld before construction" in withholding_layer["reason"]
    assert withholding_layer["evidence_ids"] == ["k-untyped"]
    # The item-level disposition is the unchanged control.
    assert withheld_only["unclassified"] == [
        {
            "id": "k-untyped",
            "source_type": "untyped",
            "status": LAYER_STATUS_UNKNOWN,
            "reason": UNRESOLVED_WITHHELD_REASON,
        }
    ]

    # MIXED: one served-but-unattributable item plus one withheld item names BOTH.
    mixed = build_context_route_record(
        "mystery_phase",
        None,
        {"selected_evidence": [], "leg_errors": {}},
        {"selected_evidence": [{"id": "k-code", "source_type": "code"}]},
        shared_scopes=[],
        withheld_evidence=[{"id": "k-untyped", "source_type": ""}],
    )
    assert mixed["served_count"] == 0
    mixed_unclassified = {e["layer"]: e for e in mixed["layers"]}["unclassified"]
    assert mixed_unclassified["reason"] == UNRESOLVED_UNCLASSIFIED_MIXED_REASON
    assert "served evidence carries no layer disposition" in mixed_unclassified["reason"]
    assert "withheld before construction" in mixed_unclassified["reason"]
    assert set(mixed_unclassified["evidence_ids"]) == {"k-code", "k-untyped"}
    # The item-level reasons stay distinct and unchanged.
    item_reasons = {item["id"]: item["reason"] for item in mixed["unclassified"]}
    assert item_reasons["k-code"] == "unroutable request: no layer resolved"
    assert item_reasons["k-untyped"] == UNRESOLVED_WITHHELD_REASON


# ── u2: source-type prefilter + requested ∪ shared scope union ──
#
# The gate for the u2 slice of `retrieval.py` (the F2 repair):
#   * the dense where-expression's repository clause is the requested scope UNION the
#     explicit shared scope ids (never a single equality when a shared scope exists), so a
#     declared shared decision stays retrievable through the dense leg;
#   * the local hard scope pre-filter keeps shared-scope candidates and STILL drops a
#     foreign private (non-requested, non-shared) scope;
#   * a non-empty `source_types` prefilter restricts fusion to the resolved layers' material
#     and records every dropped candidate; an empty set is the identity (unrouted pass).
# These tests are store-free/network-free: the fakes are scripted in-memory stores.


def _where_matches(metadata: dict, where: dict | None) -> bool:
    """Evaluate the subset of Chroma's where grammar that :func:`_dense_filter` emits.

    Supports a bare equality clause, ``$or``, and ``$and`` — exactly the shapes the filter
    produces. This lets a test prove a candidate in a requested-or-shared repository stays
    retrievable through the dense leg's OWN where-expression, not merely through retrieve's
    local hard filter.
    """
    if not where:
        return True
    if "$and" in where:
        return all(_where_matches(metadata, clause) for clause in where["$and"])
    if "$or" in where:
        return any(_where_matches(metadata, clause) for clause in where["$or"])
    return all(metadata.get(key) == value for key, value in where.items())


class _WhereAwareDenseStore:
    """Dense store that APPLIES the where-expression it is handed (Chroma-shaped).

    ``_FakeDenseStore`` deliberately ignores ``where`` to prove retrieve's local filter; this
    store honours it, so the positive shared-retrievability assertion also exercises the
    store-side union clause — and would fail if the clause regressed to a single equality.
    """

    def __init__(self, hits):
        self._hits = hits
        self.where = None

    def search(self, query, *, top_k=40, where=None):
        self.where = where
        return [h for h in self._hits if _where_matches(h.get("metadata") or {}, where)]


def test_dense_filter_repository_union_over_requested_and_shared():
    """The repository clause is a $or over requested ∪ shared; a lone scope stays historical."""
    # Requested only → the pre-existing single equality (back-compat).
    assert _dense_filter({"repository_id": "cell-a"}) == {"repository_id": "cell-a"}
    # Requested ∪ explicit shared → a $or over BOTH ids, never a single equality.
    assert _dense_filter({"repository_id": "cell-a", "shared_repository_ids": ["cell-b"]}) == {
        "$or": [{"repository_id": "cell-a"}, {"repository_id": "cell-b"}]
    }
    # The union de-dupes and drops the requested id from the shared list.
    assert _dense_filter(
        {"repository_id": "cell-a", "shared_repository_ids": ["cell-a", "cell-b", ""]}
    ) == {"$or": [{"repository_id": "cell-a"}, {"repository_id": "cell-b"}]}
    # No repository scope (requested empty, no shared) → no repository condition at all.
    assert _dense_filter({"shared_repository_ids": []}) == {}


def test_retrieve_shared_scope_union_keeps_shared_and_excludes_foreign():
    """F2: shared scope stays retrievable (where + local filter); a foreign private scope does not."""
    requested = _dense_hit("requested", "websocket finding from the requested cell")
    requested["metadata"]["repository_id"] = "cell-a"
    shared = _dense_hit("shared", "websocket finding from a declared shared cell")
    shared["metadata"]["repository_id"] = "cell-b"
    foreign = _dense_hit("foreign", "websocket finding from a foreign private cell")
    foreign["metadata"]["repository_id"] = "cell-c"

    # Part 1 — the store HONOURS the where-expression retrieve hands it. The dense leg's
    # clause must be the union, or the shared hit never reaches retrieve at all.
    aware = _WhereAwareDenseStore([foreign, requested, shared])
    attempt = retrieve(
        "websocket finding",
        dense_store=aware,
        repository_id="cell-a",
        shared_repository_ids=["cell-b"],
    )
    assert aware.where == {"$or": [{"repository_id": "cell-a"}, {"repository_id": "cell-b"}]}
    assert attempt.filters["shared_repository_ids"] == ["cell-b"]
    aware_ids = {c.id for c in attempt.candidates}
    assert "requested" in aware_ids
    assert "shared" in aware_ids  # positive: the declared shared scope stays retrievable
    assert "foreign" not in aware_ids  # negative: a foreign private scope stays excluded

    # Part 2 — a store that IGNORES its where clause still cannot leak the foreign scope: the
    # local hard pre-filter keeps shared and drops foreign on its own. This is the assertion
    # that fails if `scope_excluded` regresses to a single requested-scope equality.
    local = retrieve(
        "websocket finding",
        dense_store=_FakeDenseStore([foreign, requested, shared]),
        repository_id="cell-a",
        shared_repository_ids=["cell-b"],
    )
    local_ids = {c.id for c in local.candidates}
    assert {"requested", "shared"} <= local_ids
    assert "foreign" not in local_ids

    # A pass with no shared scope is unchanged: the foreign scope is still excluded.
    plain = retrieve(
        "websocket finding",
        dense_store=_FakeDenseStore([foreign, requested, shared]),
        repository_id="cell-a",
    )
    assert {c.id for c in plain.candidates} == {"requested"}


def test_retrieve_source_types_prefilter_restricts_selected_evidence():
    """A non-empty source_types set restricts fusion and records every dropped candidate."""
    code = _dense_hit("k-code", "build_step_graph function reference")
    code["metadata"]["source_type"] = "code"
    finding = _dense_hit("k-finding", "build_step_graph measured finding", authority="measured")
    finding["metadata"]["source_type"] = "finding"

    filtered = retrieve(
        "build_step_graph implementation",
        dense_store=_FakeDenseStore([code, finding]),
        source_types=["code"],
    )
    assert {c.id for c in filtered.candidates} == {"k-code"}
    # The prefilter restricts SELECTED evidence, not merely the fused pool: the excluded
    # finding can never be served even when the token budget would admit it.
    assert {c.id for c in filtered.selected_evidence} == {"k-code"}
    assert filtered.query_plan.source_types == ("code",)
    assert filtered.filters["source_types"] == ["code"]
    # The excluded candidate is RECORDED with its type and the named reason (never silent).
    assert filtered.source_type_excluded == [
        {
            "id": "k-finding",
            "source_type": "finding",
            "reason": SOURCE_TYPE_EXCLUDED_REASON,
        }
    ]
    assert filtered.to_dict()["source_type_excluded"] == filtered.source_type_excluded

    # An empty set is the identity — the pre-existing, unrouted path keeps every type.
    unfiltered = retrieve(
        "build_step_graph implementation",
        dense_store=_FakeDenseStore([code, finding]),
    )
    assert {c.id for c in unfiltered.candidates} == {"k-code", "k-finding"}
    assert {c.id for c in unfiltered.selected_evidence} == {"k-code", "k-finding"}
    assert unfiltered.source_type_excluded == []


def test_build_query_plan_records_source_types_prefilter():
    """The plan normalises the type set (lower-cased, de-duped, empties dropped)."""
    plan = build_query_plan("x", source_types=["Code", " code ", "", None])
    assert plan.source_types == ("code",)
    # Absent / None / empty all mean the identity prefilter (no narrowing).
    assert build_query_plan("x").source_types == ()
    assert build_query_plan("x", source_types=None).source_types == ()
    assert build_query_plan("x", source_types=[]).source_types == ()
    # A bare string is one type, and retrieve threads it onto the plan it builds.
    assert retrieve("x", source_types="Code").query_plan.source_types == ("code",)


def test_shared_repository_ids_refuses_the_global_wildcards():
    """Explicit shared scopes only: the global wildcards never widen a cell into the whole KB."""
    attempt = retrieve(
        "websocket finding",
        dense_store=_FakeDenseStore([_dense_hit("k", "websocket finding")]),
        repository_id="cell-a",
        shared_repository_ids=["*", "global", "all", "cell-b", "cell-b"],
    )
    assert attempt.filters["shared_repository_ids"] == ["cell-b"]


# ── u2/F2/R3: the AUTHORIZED shared ACL contract ──
#
# The repository union alone is not enough: the normal runner config defaults ``acl_scope``
# to the private cell scope (``workflow_runner._resolve_rag_params``), so the dense clause
# becomes ``(repository=cell-a OR repository=cell-b) AND acl_scope=cell-a`` and the shared
# decision — which carries its OWN ACL — is still hidden at the store boundary. An EXPLICIT
# shared repository scope authorizes that scope's own ACL namespace (the cell convention sets
# ``repository_id == acl_scope``), so the authorized ACL set is requested ∪ shared. The
# assertions below fail if the ACL clause regresses to a single requested equality; a foreign
# private ACL stays excluded and no wildcard can enter the authorized set.


def test_dense_filter_acl_union_over_requested_and_authorized_shared():
    """The ACL clause is requested ∪ authorized shared; a lone ACL stays the historical equality."""
    # Lone requested ACL → the pre-existing single equality (back-compat).
    assert _dense_filter({"acl_scope": "cell-a"}) == {"acl_scope": "cell-a"}
    # Requested ACL ∪ explicit shared scope → a $or over BOTH ACLs, never an equality.
    assert _dense_filter({"repository_id": "cell-a", "acl_scope": "cell-a"}) == {
        "$and": [{"repository_id": "cell-a"}, {"acl_scope": "cell-a"}]
    }
    assert _dense_filter(
        {"repository_id": "cell-a", "acl_scope": "cell-a", "shared_repository_ids": ["cell-b"]}
    ) == {
        "$and": [
            {"$or": [{"repository_id": "cell-a"}, {"repository_id": "cell-b"}]},
            {"$or": [{"acl_scope": "cell-a"}, {"acl_scope": "cell-b"}]},
        ]
    }
    # No requested ACL → the ACL clause stays omitted entirely (ACL-free pass unchanged).
    assert _dense_filter({"repository_id": "cell-a", "shared_repository_ids": ["cell-b"]}) == {
        "$or": [{"repository_id": "cell-a"}, {"repository_id": "cell-b"}]
    }


def test_acl_excluded_authorized_shared_acl_contract():
    """Authorized shared ACLs are eligible; a foreign private ACL is excluded; empty is legacy."""
    # Historical single requested ACL.
    assert acl_excluded("cell-a", "cell-a") is False
    assert acl_excluded("cell-c", "cell-a") is True
    # The explicit shared repository scope authorizes its OWN ACL namespace.
    assert acl_excluded("cell-b", "cell-a", shared_acl_scopes=["cell-b"]) is False
    assert acl_excluded("cell-c", "cell-a", shared_acl_scopes=["cell-b"]) is True
    # An empty candidate ACL is unknown/legacy and stays eligible.
    assert acl_excluded("", "cell-a", shared_acl_scopes=["cell-b"]) is False
    # Wildcards never enter the authorized shared set.
    assert acl_excluded("all", "cell-a", shared_acl_scopes=["*", "global", "all"]) is True
    # No requested ACL disables the filter (historical behavior preserved).
    assert acl_excluded("cell-c", "") is False


def test_retrieve_authorized_shared_acl_decision_reaches_evidence():
    """Under the NORMAL private-ACL config + an explicit shared-history hint, a shared decision
    carrying its OWN ACL reaches selection, while a foreign private ACL is excluded.

    This is the R3 gate: a regression of the dense ACL clause to a single requested equality
    would exclude ``k-shared-decision`` at the store boundary and fail the positive assertion.
    """
    code = _dense_hit("k-code", "websocket code signature", authority="source")
    code["metadata"].update(
        {"repository_id": "cell-a", "acl_scope": "cell-a", "source_type": "code"}
    )
    requested = _dense_hit("k-req-decision", "websocket decision from the private cell")
    requested["metadata"].update(
        {"repository_id": "cell-a", "acl_scope": "cell-a", "source_type": "decision"}
    )
    shared = _dense_hit("k-shared-decision", "websocket decision from a declared shared cell")
    shared["metadata"].update(
        {"repository_id": "cell-b", "acl_scope": "cell-b", "source_type": "decision"}
    )
    foreign = _dense_hit("k-foreign-decision", "websocket decision from a foreign cell")
    foreign["metadata"].update(
        {"repository_id": "cell-c", "acl_scope": "cell-c", "source_type": "decision"}
    )

    aware = _WhereAwareDenseStore([code, requested, shared, foreign])
    attempt = retrieve(
        "websocket decision",
        dense_store=aware,
        repository_id="cell-a",
        acl_scope="cell-a",
        shared_repository_ids=["cell-b"],
        source_types=["decision"],
    )
    # The dense clause is the repository union AND the AUTHORIZED-ACL union: an ACL equality
    # to the private cell scope would hide the shared decision at the store boundary.
    assert aware.where == {
        "$and": [
            {"$or": [{"repository_id": "cell-a"}, {"repository_id": "cell-b"}]},
            {"$or": [{"acl_scope": "cell-a"}, {"acl_scope": "cell-b"}]},
        ]
    }
    assert attempt.filters["acl_scope"] == "cell-a"
    assert attempt.filters["shared_repository_ids"] == ["cell-b"]
    ids = {c.id for c in attempt.candidates}
    assert {"k-req-decision", "k-shared-decision"} <= ids  # positive shared serving
    assert "k-foreign-decision" not in ids  # negative foreign private ACL
    assert "k-code" not in ids  # the source_types prefilter narrowed fusion
    assert {c.id for c in attempt.selected_evidence} == {"k-req-decision", "k-shared-decision"}


# ── u7: the serving-scope grants do NOT leak private scope (the two-channel rule) ─────
#
# Granting a phase the read-only project-level scope (``agentic-dynamics``) authorizes that
# scope's OWN ACL namespace — the cell convention sets ``repository_id == acl_scope`` — but it
# must never become a wildcard. Three records are repository-eligible; only ONE may be served:
#
#   * the granted project finding (repository=agentic-dynamics, acl=agentic-dynamics)  -> served
#   * a foreign cell              (repository=self-other-cell, acl=self-other-cell)    -> excluded
#   * an AIO org-root record      (repository=agentic-dynamics, acl=org:agentic-dynamics) -> excluded
#
# The org-root row is the subtle case: its ``repository_id`` MATCHES the grant, so a
# repository-only filter would leak it — but its ACL namespace is the org root, which the
# grant does not name. The store-side authorized-ACL union (and the lexical leg's
# ``acl_excluded``) must keep it out; retrieve's local hard filter is the complementary
# REPOSITORY-dimension arm. The served set must count only the granted finding. This is the
# falsifier for the "grant the project scope, accidentally serve the AIO's org-root records"
# failure mode the plan names, and it refuses a wildcard/global scope in the grant path itself.


def test_serving_scope_grant_serves_granted_and_excludes_foreign_and_org_root():
    """u7: the granted project scope serves its OWN finding while a foreign ``self-*`` cell
    AND an org-root (``acl_scope=org:agentic-dynamics``) record stay excluded — the
    two-channel bound made falsifiable."""
    granted = _dense_hit("k-granted", "websocket reload finding from the granted project scope")
    granted["metadata"].update(
        {
            "repository_id": "agentic-dynamics",
            "acl_scope": "agentic-dynamics",
            "source_type": "finding",
            "authority": "measured",
        }
    )
    # A foreign cell's private record: neither the requested scope nor the granted scope.
    foreign = _dense_hit("k-foreign", "websocket reload finding from another cell")
    foreign["metadata"].update(
        {
            "repository_id": "self-other-cell",
            "acl_scope": "self-other-cell",
            "source_type": "finding",
            "authority": "measured",
        }
    )
    # The AIO org-root record: the SAME repository_id as the grant, but the org ACL namespace.
    org_root = _dense_hit("k-org-root", "websocket reload decision from the org root")
    org_root["metadata"].update(
        {
            "repository_id": "agentic-dynamics",
            "acl_scope": "org:agentic-dynamics",
            "source_type": "decision",
            "authority": "measured",
        }
    )

    requested = "self-my-cell"  # the cell's private scope (the requested arm)
    grant = "agentic-dynamics"  # the explicit serving-scope grant (the shared arm)

    # (1) The store is handed the repository union (requested ∪ grant) AND the AUTHORIZED-ACL
    # union (requested ∪ grant). The org-root ACL is outside both, so the where-clause alone
    # already hides it: a regression to a repository-only clause would leak the org row.
    aware = _WhereAwareDenseStore([org_root, foreign, granted])
    attempt = retrieve(
        "websocket reload",
        dense_store=aware,
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=[grant],
        source_types=["finding", "decision"],
    )
    assert aware.where == {
        "$and": [
            {"$or": [{"repository_id": requested}, {"repository_id": grant}]},
            {"$or": [{"acl_scope": requested}, {"acl_scope": grant}]},
        ]
    }
    aware_ids = {c.id for c in attempt.candidates}
    assert "k-granted" in aware_ids  # positive: the granted finding is served
    assert "k-foreign" not in aware_ids  # negative: another cell's private record
    assert "k-org-root" not in aware_ids  # negative: the org root, despite the grant repository
    assert {c.id for c in attempt.selected_evidence} == {"k-granted"}

    # (2) The explicit authorized-ACL controls: the org-root namespace is NOT the grant, so it
    # is excluded; the granted scope's own ACL namespace IS authorized. This is the exact rule
    # the store-side ACL union and the lexical leg both apply.
    assert acl_excluded("org:agentic-dynamics", requested, shared_acl_scopes=[grant]) is True
    assert acl_excluded(grant, requested, shared_acl_scopes=[grant]) is False

    # (3) The local repository pre-filter is the SECOND, independent arm — but only for the
    # REPOSITORY dimension. A store that IGNORES its where clause cannot leak the foreign cell
    # (a different repository) past the local filter; the org-root row deliberately does NOT
    # survive that filter, because its repository_id IS the grant — which is precisely why the
    # store-side authorized-ACL clause in (1) is load-bearing, not redundant. Neither arm
    # alone suffices and together they close the leak.
    local = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([org_root, foreign, granted]),
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=[grant],
        source_types=["finding", "decision"],
    )
    local_ids = {c.id for c in local.candidates}
    assert "k-granted" in local_ids
    assert "k-foreign" not in local_ids  # the local repository filter drops the foreign cell
    # Honest: repository-only filtering cannot drop the org-root (same repository as the grant).
    # The lexical leg applies ``acl_excluded`` (line 2096) and the dense leg's store clause does;
    # a hypothetical store that ignores BOTH would be the only leak, and that is not a store
    # shape retrieve can compensate for locally without a repository duplicate.
    assert "k-org-root" in local_ids

    # (4) The production-shaped pass (the store honours the clause it is handed) records and
    # counts ONLY the granted evidence id: the L2 history disposition names it, ``served_count``
    # equals the one served id — never the foreign or org-root rows. The record still NAMES the
    # granted scope it honoured (never a silent global widening).
    record = build_context_route_record(
        "implement",
        resolve_phase_layers("implement", "agent"),
        attempt,
        None,
        shared_scopes=[grant],
    )
    assert record["shared_scopes"] == [grant]
    assert record["served_count"] == 1
    l2 = next(entry for entry in record["layers"] if entry["layer"] == "L2")
    assert l2["status"] == "served"
    assert l2["evidence_ids"] == ["k-granted"]
    served_ids = {entry_id for entry in record["layers"] for entry_id in entry["evidence_ids"]}
    assert served_ids == {"k-granted"}

    # (5) The grant itself refuses wildcards: the project scope authorizes only its OWN
    # namespace, never ``*``/``global``/``all``.
    assert serving_scope_grants(
        "implementation",
        policy={"implementation": ["*", "global", "all", grant, grant]},
    ) == (grant,)


# ── u1/R2: the run-findings grant is PROOF-CARRYING (a run-derived lineage scope) ─────────
#
# ``<run-findings>`` promised "the run's OWN findings". The repair makes the substitution
# PROOF-CARRYING: :func:`serving_scope_grants` substitutes the token ONLY from the caller's
# run-derived ``lineage_scope`` and withholds it otherwise — the retired ``is_isolated_run_scope``
# name denylist is no longer the ownership predicate, so a custom/reused emission destination
# cannot smuggle a whole shared namespace in under "own findings". A broader project-history
# grant stays the implementation role's EXPLICIT entry, exercised through the REAL ``retrieve``
# path below (no injected route).


def test_run_findings_grant_requires_a_lineage_scope_not_a_name():
    """R2 (u1): the placeholder resolves ONLY from a caller-supplied run-derived lineage scope."""
    # Every bare NAME offered via the retired ``run_scope`` argument is IGNORED...
    for name in (PROJECT_KNOWLEDGE_SCOPE, "org:agentic-dynamics", "team-findings", "self-run", ""):
        assert serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope=name) == ()
    # ...the trusted run-derived lineage scope is the ONE substitution...
    assert serving_scope_grants(
        ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, lineage_scope="self-this-run"
    ) == ("self-this-run",)
    # ...and the EXPLICIT project-knowledge grant on the implementation role stays untouched.
    assert serving_scope_grants(
        ROLE_IMPLEMENTATION, policy=SERVING_SCOPE_POLICY, run_scope=PROJECT_KNOWLEDGE_SCOPE
    ) == (PROJECT_KNOWLEDGE_SCOPE,)


def test_run_findings_grant_run_scope_boundary_real_retrieve_path():
    """R2 (u1): a same-repository/different-run project finding is NOT served to a review role
    (its retired ``run_scope`` name is not an ownership proof, so the token is withheld) but IS
    served to an implementation role via its explicit project grant — through the real
    ``retrieve`` path."""
    project = _dense_hit("k-project", "websocket finding emitted by another run")
    project["metadata"].update(
        {
            "repository_id": "agentic-dynamics",
            "acl_scope": "agentic-dynamics",
            "source_type": "finding",
            "authority": "measured",
        }
    )
    requested = "self-my-run"
    store = _WhereAwareDenseStore([project])

    # Review: the retired ``run_scope`` name does not substitute the token, so the review role
    # gets NO shared scope and the same-repository/different-run finding is invisible.
    review = retrieve(
        "websocket finding",
        dense_store=store,
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=list(
            serving_scope_grants(
                ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope="agentic-dynamics"
            )
        ),
        source_types=["finding"],
    )
    assert review.filters["shared_repository_ids"] == []
    assert {c.id for c in review.candidates} == set()
    assert review.selected_evidence == []

    # Implementation: the EXPLICIT project grant stays, so the same finding IS served.
    impl = retrieve(
        "websocket finding",
        dense_store=store,
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=list(
            serving_scope_grants(
                ROLE_IMPLEMENTATION, policy=SERVING_SCOPE_POLICY, run_scope="agentic-dynamics"
            )
        ),
        source_types=["finding"],
    )
    assert impl.filters["shared_repository_ids"] == ["agentic-dynamics"]
    assert {c.id for c in impl.candidates} == {"k-project"}
    assert {c.id for c in impl.selected_evidence} == {"k-project"}


def test_same_candidate_namespace_serves_neither_runs_findings_through_run_findings():
    """R2 acceptance falsifier (u3): TWO unrelated runs in the SAME candidate namespace.

    The adversarial review's measured falsifier placed a run-A finding and a run-B finding in
    the SAME repository/ACL namespace (``team-findings``) and showed that a name-denylist repair
    served BOTH to run-B's review under the ``<run-findings>`` label. The repaired contract makes
    the token PROOF-CARRYING: a declared emission destination is not a run/lineage identity, so
    the review grant is WITHHELD and neither run's finding is served.

    This drives the REAL ``retrieve`` path with the existing where-aware store. The non-vacuous
    control below substitutes the destination name the OLD denylist accepted (``team-findings``)
    and shows BOTH unrelated runs' findings reach review — so the withheld assertion discriminates
    the repair from a regression, rather than passing because the store happened to be empty.
    """

    def _run_finding(cid, run_label):
        """A measured finding with a ``run_id`` marker that is DELIBERATELY non-authoritative.

        Nothing in this code consults ``run_id``; the run label exists only to name the two
        unrelated producing runs. Their repository/ACL is the one shared candidate namespace.
        """
        hit = _dense_hit(cid, f"websocket reload finding produced by {run_label}")
        hit["metadata"].update(
            {
                "repository_id": "team-findings",
                "acl_scope": "team-findings",
                "source_type": "finding",
                "authority": "measured",
                "run_id": run_label,
            }
        )
        return hit

    run_a = _run_finding("k-finding-A", "run-A")
    run_b = _run_finding("k-finding-B", "run-B")
    requested = "self-run-B"  # run-B's own private cell scope
    store = _WhereAwareDenseStore([run_a, run_b])

    # The declared emission destination ``team-findings`` offered via the retired ``run_scope``
    # argument is NOT an ownership proof: the review grant is WITHHELD.
    assert (
        serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope="team-findings")
        == ()
    )

    review = retrieve(
        "websocket reload finding",
        dense_store=store,
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=[],
        source_types=["finding"],
    )
    assert review.filters["shared_repository_ids"] == []
    assert {c.id for c in review.candidates} == set()
    assert review.selected_evidence == []

    # NON-VACUOUS: a regression to the name denylist substitutes ``team-findings`` and serves
    # BOTH unrelated runs' findings to run-B's review — the exact leak the repair removes.
    regressed = retrieve(
        "websocket reload finding",
        dense_store=store,
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=["team-findings"],
        source_types=["finding"],
    )
    assert {c.id for c in regressed.selected_evidence} == {"k-finding-A", "k-finding-B"}

    # The trusted, run-DERIVED lineage scope is the ONE substitution: run-B's review retrieves
    # run-B's own earlier-phase finding while another run's private scope stays excluded.
    own = _run_finding("k-finding-B", "run-B")
    own["metadata"].update({"repository_id": requested, "acl_scope": requested})
    foreign_private = _run_finding("k-finding-A", "run-A")
    foreign_private["metadata"].update({"repository_id": "self-run-A", "acl_scope": "self-run-A"})
    lineage = serving_scope_grants(
        ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, lineage_scope=requested
    )
    assert lineage == (requested,)
    positive = retrieve(
        "websocket reload finding",
        dense_store=_WhereAwareDenseStore([own, foreign_private]),
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=list(lineage),
        source_types=["finding"],
    )
    assert {c.id for c in positive.selected_evidence} == {"k-finding-B"}
    assert "k-finding-A" not in {c.id for c in positive.selected_evidence}


def test_same_derived_telemetry_namespace_serves_neither_runs_findings():
    """u3(b) (retrieval_serving REPAIR ROUND 3): the SAME-DERIVED-NAMESPACE falsifier at the
    ``retrieve`` seam.

    Unlike ``test_same_candidate_namespace_serves_neither_runs_findings_through_run_findings``
    (a DECLARED destination ``team-findings``), this exercises the runner-derived telemetry
    namespace ``self-wf_<spec>_<model>`` — the exact SHARED name the pre-repair derived-cell-scope
    grant substituted, and the namespace two unrelated same-spec/model runs both derive. The
    repaired contract substitutes the token ONLY from a caller-supplied ``lineage_scope``; the
    same telemetry name offered through the retired ``run_scope`` channel is IGNORED, so review
    serves neither run's finding.

    The non-vacuous control substitutes the telemetry namespace through the TRUSTED
    ``lineage_scope`` channel (the retired grant's own effect) and shows BOTH unrelated findings
    are reachable — so the withheld assertion discriminates the repair rather than passing
    because the store happened to be empty. This is the REAL ``retrieve`` path with the existing
    where-aware store; no network/Redis/Neo4j.
    """
    # The shape the runner derives for a spec/model — SHARED across runs, so not an ownership
    # proof. ``run_id`` is deliberately non-authoritative; nothing consults it.
    telemetry_ns = "self-wf_retrieval_serving_m"

    def _run_finding(cid, run_label):
        hit = _dense_hit(cid, f"websocket reload finding produced by {run_label}")
        hit["metadata"].update(
            {
                "repository_id": telemetry_ns,
                "acl_scope": telemetry_ns,
                "source_type": "finding",
                "authority": "measured",
                "run_id": run_label,
            }
        )
        return hit

    store = _WhereAwareDenseStore(
        [_run_finding("k-finding-A", "run-A"), _run_finding("k-finding-B", "run-B")]
    )
    requested = "self-run-B"  # run-B's own private cell scope

    # The bare telemetry NAME through the retired ``run_scope`` channel is not an ownership
    # proof: the review grant is WITHHELD and neither run's finding is served.
    assert (
        serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope=telemetry_ns) == ()
    )
    review = retrieve(
        "websocket reload finding",
        dense_store=store,
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=list(
            serving_scope_grants(ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, run_scope=telemetry_ns)
        ),
        source_types=["finding"],
    )
    assert review.filters["shared_repository_ids"] == []
    assert review.selected_evidence == []

    # NON-VACUOUS: the SAME namespace through the TRUSTED ``lineage_scope`` channel resolves the
    # token and serves BOTH unrelated findings — the exact leak the repair removes.
    trusted = serving_scope_grants(
        ROLE_REVIEW, policy=SERVING_SCOPE_POLICY, lineage_scope=telemetry_ns
    )
    assert trusted == (telemetry_ns,)
    granted = retrieve(
        "websocket reload finding",
        dense_store=store,
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=list(trusted),
        source_types=["finding"],
    )
    assert {c.id for c in granted.selected_evidence} == {"k-finding-A", "k-finding-B"}


# ── u3/R1: per-role grants serve DISJOINT evidence, never the run-wide union ─────────────


def test_per_phase_role_grants_serve_disjoint_evidence_not_the_run_wide_union():
    """u3 (retrieval_serving R1): the per-role grants serve DISJOINT evidence, and the
    run-wide UNION (the R1 defect) is strictly wider — so this is the falsifier for a
    regression back to unioning every role's grant.

    One where-aware store holds an implementation-scoped hit, a review-scoped hit, and a
    foreign hit. Each role's OWN resolved grant is passed through the real ``retrieve`` path:
    only that role's hit is served. The union of both grants serves BOTH role hits — the exact
    over-serving the per-phase repair removed — so the disjointness assertion discriminates the
    repaired resolution from the defect rather than passing vacuously. The unknown role grants
    nothing and serves nothing.
    """

    def _scoped_hit(cid, scope):
        hit = _dense_hit(cid, f"websocket finding in {scope}")
        hit["metadata"].update(
            {
                "repository_id": scope,
                "acl_scope": scope,
                "source_type": "finding",
                "authority": "measured",
            }
        )
        return hit

    store = _WhereAwareDenseStore(
        [
            _scoped_hit("k-impl", "impl-shared"),
            _scoped_hit("k-review", "review-shared"),
            _scoped_hit("k-foreign", "foreign-shared"),
        ]
    )
    policy = {ROLE_IMPLEMENTATION: ("impl-shared",), ROLE_REVIEW: ("review-shared",)}
    requested = "self-my-run"

    def _run(role):
        return retrieve(
            "websocket finding",
            dense_store=store,
            repository_id=requested,
            acl_scope=requested,
            shared_repository_ids=list(serving_scope_grants(role, policy=policy)),
            source_types=["finding"],
        )

    impl = _run(ROLE_IMPLEMENTATION)
    assert impl.filters["shared_repository_ids"] == ["impl-shared"]
    assert {c.id for c in impl.selected_evidence} == {"k-impl"}

    review = _run(ROLE_REVIEW)
    assert review.filters["shared_repository_ids"] == ["review-shared"]
    assert {c.id for c in review.selected_evidence} == {"k-review"}

    # Disjoint: the two roles' served evidence shares nothing. A role that inherited the
    # other's grant (or a run-wide union) would serve the sibling hit here.
    assert {c.id for c in impl.selected_evidence}.isdisjoint(
        {c.id for c in review.selected_evidence}
    )

    # The run-wide UNION (the defect) is strictly wider: it serves BOTH role-scoped hits,
    # which is why the per-phase separation is observable rather than cosmetic.
    union = retrieve(
        "websocket finding",
        dense_store=store,
        repository_id=requested,
        acl_scope=requested,
        shared_repository_ids=["impl-shared", "review-shared"],
        source_types=["finding"],
    )
    assert {c.id for c in union.selected_evidence} == {"k-impl", "k-review"}


# ── A10-R2: the dense store's KNOWN incomplete-search signal is a NAMED diagnostic ──────
#
# The production dense store expands candidates in bounded rounds and sets an explicit
# ``incomplete`` state when the scan hits its cap before exhausting the scoped corpus
# (neo4j_vectors.Neo4jVectorStore.search_with_stats). If the retrieval seam ignored that
# signal, a capped scan returning no scoped hits would look exactly like a genuinely empty
# scoped corpus: the affected layer would record a clean ``empty`` instead of a named
# absence, and an auditor could not tell that scoped candidates went unexamined. The repair
# consumes the store's PER-CALL ``search_with_stats`` result (falling back to the legacy
# shared ``last_search_incomplete`` for a pre-refactor store) and records the named
# ``dense_search_incomplete`` diagnostic on the attempt, its audit dict, and the phase record
# built by ``augment_prompt``. The two bounded follow-ups (top-K crowding; shared
# graph-neighbor expansion) are deliberately NOT addressed here.


class _CappedDenseStore:
    """A deterministic dense double exposing the A10-R2 per-call contract.

    ``stats`` is returned verbatim from ``search_with_stats`` so the test can script a capped
    scan (``incomplete`` true, ``scanned`` at the cap) or an exhausted scan
    (``incomplete`` false) with no store, network, or external service. Setting
    ``shared_incomplete`` also plants a (possibly stale) shared attribute, so a test can show
    the per-call result is preferred when both signals exist.
    """

    def __init__(self, hits, stats, *, shared_incomplete=None):
        self._hits = hits
        self._stats = stats
        if shared_incomplete is not None:
            self.last_search_incomplete = shared_incomplete

    def search_with_stats(self, query, *, top_k=40, where=None):
        return list(self._hits), dict(self._stats)


class _LegacyIncompleteDenseStore:
    """A pre-refactor store: no per-call method, only the shared ``last_search_incomplete``."""

    last_search_incomplete = True

    def search(self, query, *, top_k=40, where=None):
        return []


class _NoOpEmbedder:
    """Constructible embedder stand-in so the optional embedding leg records no failure.

    A host without the optional ``ollama`` package would otherwise add an unrelated
    ``embedding`` leg error on every ``retrieve`` call, which would mask the clean-empty
    control's layer disposition.
    """

    def embed(self, text):
        return [0.0]


class _ZeroCorpusResult:
    """Iterable result for the A11-R2 fake driver (mirrors the Neo4j Result protocol)."""

    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _ZeroCorpusTx:
    def __init__(self, session, timeout=None):
        self._session = session

    def run(self, cypher, **params):
        return _ZeroCorpusResult(self._session.respond(cypher, params))

    def close(self):
        pass


class _ZeroCorpusSession:
    """A fake Neo4j session: successful ``count()==0`` and no vector rows (A11-R2 fixture).

    Only the two production queries the real store issues are answered: the count seam
    returns the KNOWN ZERO and every vector query returns no rows. Recording the calls lets
    the gate prove the REAL store's ``count()`` path ran rather than a scripted double.
    """

    def __init__(self):
        self.calls = []

    def respond(self, cypher, params):
        self.calls.append((cypher, params))
        if "count(k) AS n" in cypher:
            return [{"n": 0}]  # the production count() of a genuinely empty scoped corpus
        return []  # no embedded rows exist at this scope

    def begin_transaction(self, timeout=None):
        return _ZeroCorpusTx(self, timeout)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _ZeroCorpusClient:
    """The store client shim exposing ``_driver.session()`` and ``close()``."""

    def __init__(self, session):
        self._driver = self
        self._session = session

    def session(self):
        return self._session

    def close(self):
        pass


def _known_zero_store():
    """Build the REAL ``Neo4jVectorStore`` over a fake driver: ``count()==0``, no rows.

    ``_corpus_count = -1`` forces the first filtered search to run the production ``count()``
    against the fake session, so the gate exercises the real exhaustion arithmetic — not a
    hand-scripted stats dict.
    """
    from agentic_dynamics.knowledge.neo4j_vectors import Neo4jVectorStore

    store = Neo4jVectorStore.__new__(Neo4jVectorStore)
    session = _ZeroCorpusSession()
    store._client = _ZeroCorpusClient(session)
    store._embedder = _NoOpEmbedder()
    store.dimensions = 1
    store.timeout_s = 5.0
    store.last_search_stats = {}
    store.last_search_incomplete = False
    store._corpus_count = -1
    return store, session


def _phase_record_for(retrieve_fn, route):
    """Run the real ``augment_prompt`` seam over ``retrieve_fn`` and return the outcome.

    The constructor echoes the base prompt, so ``outcome.prompt`` proves the base prompt was
    preserved while the retrieval diagnostic rides the record. The construction SUCCEEDS (not
    a fallback), so the layer disposition is driven by ``leg_errors`` rather than erased by a
    competing fallback reason.
    """
    import types

    from agentic_dynamics.knowledge.augment import augment_prompt

    def _echo_construct(request):
        return types.SimpleNamespace(
            prompt=request.raw_work_item,
            fallback=False,
            fallback_reason="",
            evidence_ids=[],
            constructor_attempt_id="c",
            versions={},
            token_counts={},
            cost_usd=0.0,
        )

    return augment_prompt(
        base_prompt="BASE PROMPT PRESERVED",
        goal="goal",
        phase_def={"name": "execute", "kind": "agent"},
        model="m",
        commit_sha="rev",
        inherited_tools=["read"],
        pinned_policy="",
        rag_params={},
        retrieve_fn=retrieve_fn,
        construct_fn=_echo_construct,
        route=route,
    )


def test_dense_capped_scan_is_named_incomplete_not_clean_empty(monkeypatch):
    """A10-R2: a capped dense scan names ``dense_search_incomplete`` on attempt AND record.

    Falsifier: if the dense leg ignored the store's signal, ``leg_errors`` would not carry
    the key and the routed layer's reason could not name it (the old production defect).
    """
    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.EmbeddingClient", _NoOpEmbedder)
    route = resolve_phase_layers("execute", "agent")
    store = _CappedDenseStore(
        [], {"incomplete": True, "scanned": 256, "corpus": 4096, "returned": 0}
    )

    def _retrieve_fn(**_kwargs):
        return retrieve(
            "implement the projection resolver",
            dense_store=store,
            graph_client=_FakeGraph(lexical_hits=[]),
        )

    attempt = _retrieve_fn()
    assert DENSE_SEARCH_INCOMPLETE_KEY in attempt.leg_errors
    assert DENSE_SEARCH_INCOMPLETE_KEY in attempt.to_dict()["leg_errors"]
    assert "scanned=256" in attempt.leg_errors[DENSE_SEARCH_INCOMPLETE_KEY]
    assert "corpus=4096" in attempt.leg_errors[DENSE_SEARCH_INCOMPLETE_KEY]

    outcome = _phase_record_for(_retrieve_fn, route)
    assert outcome.context_route is not None
    assert DENSE_SEARCH_INCOMPLETE_KEY in outcome.context_route["leg_errors"]
    by_layer = {entry["layer"]: entry for entry in outcome.context_route["layers"]}
    assert by_layer["L1"]["status"] == LAYER_STATUS_NAMED_ABSENT
    assert by_layer["L1"]["status"] != LAYER_STATUS_EMPTY
    assert DENSE_SEARCH_INCOMPLETE_KEY in by_layer["L1"]["reason"]
    # A real construction ran (not a fallback) and the base prompt is preserved.
    assert outcome.fallback is False
    assert outcome.prompt == "BASE PROMPT PRESERVED"


def test_dense_exhausted_empty_scan_is_clean_empty_control(monkeypatch):
    """Control: an exhausted genuinely-empty scan records NO diagnostic and stays ``empty``.

    This distinguishes the KNOWN-incomplete signal from a clean absence: the dense leg
    returned, the corpus really was exhausted, and no diagnostic is fabricated.
    """
    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.EmbeddingClient", _NoOpEmbedder)
    route = resolve_phase_layers("execute", "agent")
    store = _CappedDenseStore([], {"incomplete": False, "scanned": 40, "corpus": 40, "returned": 0})

    def _retrieve_fn(**_kwargs):
        return retrieve(
            "implement the projection resolver",
            dense_store=store,
            graph_client=_FakeGraph(lexical_hits=[]),
        )

    attempt = _retrieve_fn()
    assert DENSE_SEARCH_INCOMPLETE_KEY not in attempt.leg_errors

    outcome = _phase_record_for(_retrieve_fn, route)
    assert outcome.context_route is not None
    assert DENSE_SEARCH_INCOMPLETE_KEY not in outcome.context_route["leg_errors"]
    by_layer = {entry["layer"]: entry for entry in outcome.context_route["layers"]}
    assert by_layer["L1"]["status"] == LAYER_STATUS_EMPTY


def test_dense_legacy_shared_incomplete_is_named_fallback(monkeypatch):
    """A pre-refactor store (no per-call method) still names it via ``last_search_incomplete``.

    The production shape before A10-R2 carried the signal on the store instance; that signal
    must not be silently re-lost by the refactor.
    """
    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.EmbeddingClient", _NoOpEmbedder)

    def _retrieve_fn(**_kwargs):
        return retrieve(
            "implement the projection resolver",
            dense_store=_LegacyIncompleteDenseStore(),
            graph_client=_FakeGraph(lexical_hits=[]),
        )

    attempt = _retrieve_fn()
    assert DENSE_SEARCH_INCOMPLETE_KEY in attempt.leg_errors


def test_dense_per_call_signal_preferred_over_stale_shared_state(monkeypatch):
    """The per-call ``search_with_stats`` result outranks a stale shared instance flag."""
    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.EmbeddingClient", _NoOpEmbedder)
    # The store carries a STALE shared ``last_search_incomplete`` true, while THIS call's
    # per-call stats say the scan exhausted. The per-call result must win: no diagnostic.
    store = _CappedDenseStore(
        [],
        {"incomplete": False, "scanned": 40, "corpus": 40, "returned": 0},
        shared_incomplete=True,
    )

    def _retrieve_fn(**_kwargs):
        return retrieve(
            "implement the projection resolver",
            dense_store=store,
            graph_client=_FakeGraph(lexical_hits=[]),
        )

    attempt = _retrieve_fn()
    assert DENSE_SEARCH_INCOMPLETE_KEY not in attempt.leg_errors


def test_dense_known_zero_corpus_is_clean_empty_not_incomplete(monkeypatch):
    """A11-R2: the REAL production store's known-zero scoped corpus is a clean empty scan.

    The production store (fake driver/embedder, a successful ``count()==0``) must report
    ``corpus == 0`` and ``incomplete is False``; carried through the real ``retrieve()``
    (nonempty repository filter, healthy empty lexical leg) and the real ``augment_prompt()``,
    there is NO ``dense_search_incomplete`` diagnostic and the routed L1 layer is a clean
    ``empty`` (never ``named_absent``), with the base prompt preserved.

    Falsifier: reverting the ``neo4j_vectors`` exhaustion hunk reports ``corpus`` ``None`` and
    ``incomplete`` ``True`` at the measured zero, so this test's no-diagnostic and clean
    ``empty`` assertions fail (pre-fix: L1 ``named_absent``).
    """
    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.EmbeddingClient", _NoOpEmbedder)
    store, session = _known_zero_store()
    route = resolve_phase_layers("execute", "agent")

    def _retrieve_fn(**_kwargs):
        return retrieve(
            "implement the projection resolver",
            dense_store=store,
            graph_client=_FakeGraph(lexical_hits=[]),
            repository_id="agentic-dynamics",
        )

    attempt = _retrieve_fn()
    # The REAL store's count() ran and measured a known zero (not a scripted double).
    assert store._corpus_count == 0
    assert any("count(k) AS n" in cypher for cypher, _params in session.calls)
    assert DENSE_SEARCH_INCOMPLETE_KEY not in attempt.leg_errors
    assert DENSE_SEARCH_INCOMPLETE_KEY not in attempt.to_dict()["leg_errors"]

    outcome = _phase_record_for(_retrieve_fn, route)
    assert outcome.context_route is not None
    assert DENSE_SEARCH_INCOMPLETE_KEY not in outcome.context_route["leg_errors"]
    by_layer = {entry["layer"]: entry for entry in outcome.context_route["layers"]}
    assert by_layer["L1"]["status"] == LAYER_STATUS_EMPTY
    assert by_layer["L1"]["status"] != LAYER_STATUS_NAMED_ABSENT
    assert outcome.fallback is False
    assert outcome.prompt == "BASE PROMPT PRESERVED"


# ── Embedder transport (u3): CELL-VIABLE by default, stdlib HTTP, typed failures ──


class _FakeHTTPResponse:
    """Minimal context-managed stand-in for the object ``urlopen`` yields.

    ``urlopen`` is used as a context manager and only ``read()`` is called on the result,
    so this double mirrors exactly that surface — no live socket, fully deterministic.
    """

    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def test_embedding_client_constructs_without_the_optional_ollama_package(monkeypatch):
    """Cell-viability: the DEFAULT transport imports ONLY the standard library.

    ``sys.modules['ollama'] = None`` makes any ``import ollama`` raise ImportError, so a
    construction that touched the optional package would fail loudly. The client must use
    the stdlib HTTP transport and the documented localhost default when nothing overrides it.
    """
    from agentic_dynamics.knowledge import embeddings

    monkeypatch.setitem(sys.modules, "ollama", None)
    client = embeddings.EmbeddingClient()
    assert client.transport == embeddings.TRANSPORT_HTTP
    assert client.host == embeddings.DEFAULT_OLLAMA_HOST
    # Construction performs NO I/O and never touches the optional client: it is built lazily
    # only when the explicitly selected ollama transport is actually used.
    assert client._ollama_client is None


def test_embedding_client_stdlib_http_transport_end_to_end(monkeypatch):
    """A monkeypatched stdlib HTTP transport embeds a text end-to-end.

    Proves the default path POSTs to ``{OLLAMA_HOST}/api/embeddings`` with the Ollama REST
    body ``{model, prompt}`` and parses ``{embedding: [...]}`` into a float vector — with no
    optional package involved.
    """
    from agentic_dynamics.knowledge import embeddings

    captured: dict = {}

    def _fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeHTTPResponse({"embedding": [0.5, -1.0, 2.0]})

    monkeypatch.setattr(embeddings.urllib.request, "urlopen", _fake_urlopen)
    client = embeddings.EmbeddingClient(
        model="bge-m3:latest", host="http://embed.test:11434", timeout_s=3.5
    )
    vector = client.embed("hello world")

    assert vector == [0.5, -1.0, 2.0]
    assert captured["url"] == "http://embed.test:11434/api/embeddings"
    assert captured["body"] == {"model": "bge-m3:latest", "prompt": "hello world"}
    assert captured["timeout"] == 3.5


def test_embedding_client_connection_refused_raises_typed_unreachable(monkeypatch):
    """A refused endpoint is the TYPED ``EmbedderUnreachable`` — never a bare OSError.

    This is the named ``embedder-unreachable`` state the retrieval seam must be able to record
    (DISTINCT from module absence and from a clean empty pass).
    """
    from agentic_dynamics.knowledge import embeddings

    def _refused(request, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    monkeypatch.setattr(embeddings.urllib.request, "urlopen", _refused)
    client = embeddings.EmbeddingClient(host="http://127.0.0.1:9")
    with pytest.raises(embeddings.EmbedderUnreachable) as excinfo:
        client.embed("anything")
    assert excinfo.value.token == "embedder-unreachable"


def test_embedding_client_honors_ollama_host_env(monkeypatch):
    """``OLLAMA_HOST`` is honored; an explicit ``host`` wins over the env (trailing slash stripped)."""
    from agentic_dynamics.knowledge import embeddings

    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.internal:11434/")
    client = embeddings.EmbeddingClient()
    assert client.host == "http://ollama.internal:11434"
    explicit = embeddings.EmbeddingClient(host="http://explicit:1234")
    assert explicit.host == "http://explicit:1234"


def test_optional_ollama_transport_absent_is_named_module_absent(monkeypatch):
    """The optional transport's absence is a NAMED state, DISTINCT from unreachable.

    Selecting ``transport='ollama'`` with the package made unimportable must raise the typed
    ``EmbedderModuleAbsent`` (token ``embedder-module-absent``), never a raw ImportError and
    never the unreachable token.
    """
    from agentic_dynamics.knowledge import embeddings

    monkeypatch.setitem(sys.modules, "ollama", None)
    client = embeddings.EmbeddingClient(transport="ollama")
    with pytest.raises(embeddings.EmbedderModuleAbsent) as excinfo:
        client.embed("anything")
    assert excinfo.value.token == "embedder-module-absent"
    # The two failure states must never collapse into one diagnostic.
    assert excinfo.value.token != embeddings.EmbedderUnreachable.token


def test_resolve_ollama_host_normalizes_scheme_less_forms(monkeypatch):
    """The conventional scheme-less ``OLLAMA_HOST`` forms gain the ``http://`` scheme (R3).

    ``host:port`` / bare host / bracketed IPv6 are how an operator actually sets the env
    (Ollama's own CLI accepts ``127.0.0.1:11434``); each must normalize to a usable base URL
    rather than being handed to ``urlopen`` as an opaque string that fails as unreachable.
    """
    from agentic_dynamics.knowledge import embeddings

    assert embeddings.resolve_ollama_host("ollama:11434") == "http://ollama:11434"
    assert embeddings.resolve_ollama_host("127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert embeddings.resolve_ollama_host("localhost") == "http://localhost"
    assert embeddings.resolve_ollama_host("[::1]:11434") == "http://[::1]:11434"
    assert embeddings.resolve_ollama_host("[::1]") == "http://[::1]"
    # The env is the same path (read at call time), and a trailing slash never doubles.
    monkeypatch.setenv("OLLAMA_HOST", "ollama:11434/")
    assert embeddings.resolve_ollama_host() == "http://ollama:11434"


def test_resolve_ollama_host_preserves_declared_scheme_and_strips_trailing_slash():
    """A declared ``http://`` / ``https://`` scheme is PRESERVED; a trailing slash stripped."""
    from agentic_dynamics.knowledge import embeddings

    assert embeddings.resolve_ollama_host("http://host:11434/") == "http://host:11434"
    assert embeddings.resolve_ollama_host("http://host:11434") == "http://host:11434"
    assert embeddings.resolve_ollama_host("https://host:11434/") == "https://host:11434"


def test_resolve_ollama_host_unsupported_scheme_is_named_configuration_error(monkeypatch):
    """An unsupported declared scheme is a TYPED config error, NEVER ``embedder-unreachable``.

    R3's core requirement: a bad URL form must not be misreported as a network outage. The
    error is an :class:`EmbedderError` carrying a distinct token, and it is raised at
    construction time (before any I/O) so the seam can name the configuration fault.
    """
    from agentic_dynamics.knowledge import embeddings

    with pytest.raises(embeddings.EmbedderConfigurationError) as excinfo:
        embeddings.resolve_ollama_host("ftp://host:11434")
    assert isinstance(excinfo.value, embeddings.EmbedderError)
    assert excinfo.value.token == "embedder-config-error"
    assert excinfo.value.token != embeddings.EmbedderUnreachable.token

    # The client's construction runs the same resolver, so a misconfiguration refuses loudly
    # rather than constructing a client that would later masquerade as unreachable.
    monkeypatch.setenv("OLLAMA_HOST", "unix:///var/run/ollama.sock")
    with pytest.raises(embeddings.EmbedderConfigurationError):
        embeddings.EmbeddingClient()


def test_embedding_client_scheme_less_ollama_host_posts_to_normalized_url(monkeypatch):
    """``OLLAMA_HOST=ollama:11434`` POSTs to ``http://ollama:11434/api/embeddings``.

    End-to-end through the stdlib transport with a stub ``urlopen``: the normalized scheme
    is what the request URL actually carries, proving the normalization is on the request
    path and not merely a resolver convenience.
    """
    from agentic_dynamics.knowledge import embeddings

    captured: dict = {}

    def _fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        return _FakeHTTPResponse({"embedding": [1.0, 2.0]})

    monkeypatch.setenv("OLLAMA_HOST", "ollama:11434")
    monkeypatch.setattr(embeddings.urllib.request, "urlopen", _fake_urlopen)
    client = embeddings.EmbeddingClient()
    assert client.host == "http://ollama:11434"
    assert client.embed("hello") == [1.0, 2.0]
    assert captured["url"] == "http://ollama:11434/api/embeddings"


def test_embedding_client_default_transport_end_to_end_without_optional_package(monkeypatch):
    """The DEFAULT stdlib transport embeds end-to-end while the optional package is UNIMPORTABLE.

    The acceptance asks for one pass in which a stub ``urlopen`` observes the normalized
    ``http://<host>:11434/api/embeddings`` URL AND the parsed vector — with NO optional package
    present (base deps only). The construction test proves only construction, and the other
    end-to-end tests run against whatever the host happens to have installed; here
    ``sys.modules['ollama'] = None`` forces an ImportError for ANY import attempt, so on a host
    that DOES have the package, a hidden default-path dependency on it is still caught. This is
    the cell-viability discriminator the earlier split tests could not give.

    Falsifier: routing the default transport through the optional package, eagerly importing it
    in ``__init__``/``_http_embed``, or selecting it by default raises ImportError or
    :class:`EmbedderModuleAbsent` here instead of returning the vector — on every host.
    """
    from agentic_dynamics.knowledge import embeddings

    captured: dict = {}

    def _fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeHTTPResponse({"embedding": [0.25, -0.5, 0.75]})

    # No optional package can be imported for the whole test.
    monkeypatch.setitem(sys.modules, "ollama", None)
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:11434")
    monkeypatch.setattr(embeddings.urllib.request, "urlopen", _fake_urlopen)

    client = embeddings.EmbeddingClient()
    assert client.transport == embeddings.TRANSPORT_HTTP
    vector = client.embed("cell-viable embedding path")

    assert captured["url"] == "http://127.0.0.1:11434/api/embeddings"
    assert captured["body"] == {
        "model": "bge-m3:latest",
        "prompt": "cell-viable embedding path",
    }
    assert vector == [0.25, -0.5, 0.75]


@pytest.mark.parametrize(
    ("host_env", "expected_host"),
    [
        ("ollama:11434", "http://ollama:11434"),
        ("127.0.0.1:11434", "http://127.0.0.1:11434"),
    ],
)
def test_default_stdlib_transport_ignores_an_importable_optional_package(
    monkeypatch, host_env, expected_host
):
    """The CONVERSE of cell-viability: an INSTALLED optional package must not become the default.

    The credited construction/end-to-end guards make ``ollama`` UNIMPORTABLE, proving the
    stdlib path works on a base-deps host. This guard proves the other half of the contract on
    a host where the package IS importable: a monkeypatched ``ollama`` whose ``Client`` counts
    every use is placed in ``sys.modules``, and the DEFAULT ``EmbeddingClient()`` must still
    select the stdlib HTTP transport, never build the optional client, and never call it. Both
    conventional scheme-less ``OLLAMA_HOST`` forms are driven through the SAME stub, so the
    outgoing URL proves normalization reaches the request path (R3's falsifier) rather than
    only the resolver.

    Falsifier: defaulting to the optional transport when the package is present, eagerly
    building the optional client in ``__init__``/``embed``, or appending ``/api/embeddings`` to
    an un-normalized host either trips ``calls['client_calls']``/``_ollama_client`` or fails the
    exact-URL assertion — on a host that actually has ``ollama`` installed.
    """
    import types

    from agentic_dynamics.knowledge import embeddings

    calls = {"client_calls": 0}

    class _SentinelOllamaClient:
        """Sentinel optional client: any construction or call is counted (and fails the test)."""

        def __init__(self, *args, **kwargs):
            calls["client_calls"] += 1

        def embeddings(self, *args, **kwargs):
            calls["client_calls"] += 1
            return {"embedding": [9.0, 9.0]}

    # The optional package IS importable here — the default must still ignore it.
    monkeypatch.setitem(sys.modules, "ollama", types.SimpleNamespace(Client=_SentinelOllamaClient))
    monkeypatch.setenv("OLLAMA_HOST", host_env)
    monkeypatch.delenv("FINOPS_EMBED_TRANSPORT", raising=False)

    captured: dict = {}

    def _fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeHTTPResponse({"embedding": [0.125, 0.25]})

    monkeypatch.setattr(embeddings.urllib.request, "urlopen", _fake_urlopen)

    client = embeddings.EmbeddingClient()
    assert client.transport == embeddings.TRANSPORT_HTTP
    assert client.host == expected_host
    # Construction never touched the importable optional package.
    assert client._ollama_client is None

    assert client.embed("default stays stdlib") == [0.125, 0.25]
    assert captured["url"] == f"{expected_host}/api/embeddings"
    assert captured["body"] == {"model": "bge-m3:latest", "prompt": "default stays stdlib"}
    # The optional client was neither built nor called on the default path.
    assert calls["client_calls"] == 0


# ── Embedding-leg named diagnostics (u4): THREE distinct states, never a collapsed traceback ──


def test_retrieval_embedder_tokens_match_the_embedder_vocabulary():
    """The seam's literals are pinned to the embedder's own class attributes.

    If the embedder ever renames a token, this guard fails rather than letting the seam's
    two literals drift away from the vocabulary the typed errors actually carry. Every typed
    embedder failure is also proven PAIRWISE DISTINCT — unreachable, module-absent,
    config-error and response-error never share a token and never fall back to the untyped
    base. Collapsing two of them would let the seam record the wrong provisioning cause for a
    real fault, which is exactly the distinction the spec requires (a dead network must not be
    blamed on a missing package, and a bad URL must not be blamed on the network).
    """
    from agentic_dynamics.knowledge import embeddings

    assert embeddings.EmbedderUnreachable.token == EMBEDDER_UNREACHABLE_TOKEN
    assert embeddings.EmbedderModuleAbsent.token == EMBEDDER_MODULE_ABSENT_TOKEN
    # And the failure states stay distinct: unreachable is NOT module absence.
    assert EMBEDDER_UNREACHABLE_TOKEN != EMBEDDER_MODULE_ABSENT_TOKEN
    # The full typed vocabulary is pairwise distinct and namespaced (never the untyped base
    # ``embedder-error``), so no two failure classes can be confused at the seam.
    failure_tokens = [
        embeddings.EmbedderUnreachable.token,
        embeddings.EmbedderModuleAbsent.token,
        embeddings.EmbedderConfigurationError.token,
        embeddings.EmbedderResponseError.token,
    ]
    assert len(set(failure_tokens)) == len(failure_tokens), (
        f"embedder failure tokens collapsed into one: {failure_tokens}"
    )
    assert all(token.startswith("embedder-") for token in failure_tokens)
    assert embeddings.EmbedderError.token == "embedder-error"
    assert embeddings.EmbedderError.token not in failure_tokens


def test_retrieve_records_named_embedder_unreachable_when_no_endpoint(monkeypatch):
    """No live endpoint is the NAMED ``embedder-unreachable`` state at the seam.

    The REAL stdlib transport is driven against a refused socket (monkeypatched ``urlopen``),
    so the pass exercised the embedder path end-to-end and recorded the stable token under
    ``leg_errors["embedding"]`` — never a raw class name and never a module-missing collapse.
    """
    from agentic_dynamics.knowledge import embeddings

    def _refused(request, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    monkeypatch.setattr(embeddings.urllib.request, "urlopen", _refused)
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore(
            [_dense_hit("d1", "alpha text"), _dense_hit("d2", "beta text")]
        ),
    )
    assert "embedding" in attempt.leg_errors
    assert EMBEDDER_UNREACHABLE_TOKEN in attempt.leg_errors["embedding"]
    assert EMBEDDER_MODULE_ABSENT_TOKEN not in attempt.leg_errors["embedding"]
    assert "No module named" not in attempt.leg_errors["embedding"]
    # The named state survives into the audit dict the ledger reads.
    assert EMBEDDER_UNREACHABLE_TOKEN in attempt.to_dict()["leg_errors"]["embedding"]


def test_retrieve_records_named_embedder_module_absent_distinct_from_unreachable(monkeypatch):
    """An explicitly-selected-but-missing optional transport is the module-ABSENT state.

    With the ollama transport selected (env) and the package made unimportable, the SAME seam
    must record ``embedder-module-absent`` — DISTINCT from ``embedder-unreachable`` — proving
    the two provisioning failures never collapse into one diagnostic.
    """
    monkeypatch.setenv("FINOPS_EMBED_TRANSPORT", "ollama")
    monkeypatch.setitem(sys.modules, "ollama", None)
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore(
            [_dense_hit("d1", "alpha text"), _dense_hit("d2", "beta text")]
        ),
    )
    assert "embedding" in attempt.leg_errors
    assert EMBEDDER_MODULE_ABSENT_TOKEN in attempt.leg_errors["embedding"]
    assert EMBEDDER_UNREACHABLE_TOKEN not in attempt.leg_errors["embedding"]


def test_retrieve_records_named_embedder_config_error_distinct_from_unreachable(monkeypatch):
    """A misconfigured endpoint is the NAMED config-error state, proven at the seam.

    The THIRD provisioning fault — an unsupported ``OLLAMA_HOST`` scheme — must never collapse
    into ``embedder-unreachable`` (the network is fine; the value is wrong) or module absence.
    Driving the REAL ``retrieve`` path with such a host makes ``EmbeddingClient()`` refuse at
    CONSTRUCTION with the typed ``EmbedderConfigurationError``; the seam records its stable
    token under ``leg_errors["embedding"]``. This is the end-to-end counterpart to
    ``test_resolve_ollama_host_unsupported_scheme_is_named_configuration_error`` (the resolver
    level), without which the config state was the only one never observed through the seam.

    Falsifier: folding a bad scheme into ``EmbedderUnreachable`` records the wrong token here;
    dropping the ``except`` around construction surfaces the traceback instead.
    """
    from agentic_dynamics.knowledge import embeddings

    monkeypatch.setenv("OLLAMA_HOST", "ftp://embed.test:11434")
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore(
            [_dense_hit("d1", "alpha text"), _dense_hit("d2", "beta text")]
        ),
    )
    assert "embedding" in attempt.leg_errors
    assert embeddings.EmbedderConfigurationError.token in attempt.leg_errors["embedding"]
    # The other two states must not be the recorded diagnosis.
    assert EMBEDDER_UNREACHABLE_TOKEN not in attempt.leg_errors["embedding"]
    assert EMBEDDER_MODULE_ABSENT_TOKEN not in attempt.leg_errors["embedding"]
    # The named state survives into the audit dict the ledger reads.
    assert (
        embeddings.EmbedderConfigurationError.token in attempt.to_dict()["leg_errors"]["embedding"]
    )


def test_retrieve_clean_empty_records_no_embedding_diagnostic(monkeypatch):
    """A clean empty pass records NO ``embedding`` key — a failure must never be fabricated.

    The embedder is healthy (a no-op double) and the pass returns no candidates, so the
    collapse leg never runs. Silence here means "clean empty", never a collapsed error.
    """
    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.EmbeddingClient", _NoOpEmbedder)
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore([]),
        graph_client=_FakeGraph(lexical_hits=[]),
    )
    assert "embedding" not in attempt.leg_errors
    assert attempt.fallback_mode == FallbackMode.FULL.value


def test_embedder_four_states_are_pairwise_distinct_at_the_seam(monkeypatch):
    """The four embedder states never collapse into one another at the retrieval seam (u4).

    The acceptance names FOUR distinct outcomes — ``embedder-unreachable`` (the endpoint is
    configured but nothing answers), ``embedder-module-absent`` (the explicitly-selected
    optional transport is not installed), ``embedder-config-error`` (a bad ``OLLAMA_HOST``
    scheme refused before any I/O), and a CLEAN EMPTY pass that records NO embedding
    diagnostic at all. Each state is proven in isolation elsewhere; this guard drives the
    REAL ``retrieve`` path under all four in one place and asserts the recorded footprints
    are PAIRWISE DISTINCT — the property no single-state test can establish, because a
    collapse is only visible when two states are compared against each other.

    Falsifier: folding ``EmbedderConfigurationError`` into ``EmbedderUnreachable``, letting a
    selected absent optional transport surface as a raw ``ModuleNotFoundError`` string, or
    fabricating an ``embedding`` key on the clean-empty pass each collapses two footprints
    (or manufactures a fourth) and trips the exactness/parity checks below — the distinct
    diagnosis is the unit's whole point (a dead network must never be blamed on a missing
    package, and a bad URL must never be blamed on the network).
    """
    from agentic_dynamics.knowledge import embeddings

    def _footprint(*, dense_hits, graph_client=None) -> str | None:
        # Capture ONLY the embedding leg's diagnostic — the other legs are irrelevant here.
        attempt = retrieve(
            "websocket reload",
            dense_store=_FakeDenseStore(dense_hits),
            graph_client=graph_client,
        )
        return attempt.leg_errors.get("embedding")

    hits = [_dense_hit("d1", "alpha text"), _dense_hit("d2", "beta text")]

    # (1) unreachable — a refused socket on the REAL stdlib transport (base deps only).
    monkeypatch.delenv("FINOPS_EMBED_TRANSPORT", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    def _refused(request, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    monkeypatch.setattr(embeddings.urllib.request, "urlopen", _refused)
    unreachable = _footprint(dense_hits=hits)

    # (2) module-absent — the explicitly-selected optional transport cannot import.
    monkeypatch.setenv("FINOPS_EMBED_TRANSPORT", "ollama")
    monkeypatch.setitem(sys.modules, "ollama", None)
    module_absent = _footprint(dense_hits=hits)

    # (3) config-error — an unsupported scheme refuses at CONSTRUCTION, before any I/O.
    monkeypatch.delenv("FINOPS_EMBED_TRANSPORT", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "ftp://embed.test:11434")
    config_error = _footprint(dense_hits=hits)

    # (4) clean-empty — a healthy embedder and no candidates records NO diagnostic.
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.EmbeddingClient", _NoOpEmbedder)
    clean_empty = _footprint(dense_hits=[], graph_client=_FakeGraph(lexical_hits=[]))

    config_token = embeddings.EmbedderConfigurationError.token
    # The clean-empty pass is silent — a failure must never be fabricated.
    assert clean_empty is None
    # Each state records its OWN named token...
    assert unreachable is not None and EMBEDDER_UNREACHABLE_TOKEN in unreachable
    assert module_absent is not None and EMBEDDER_MODULE_ABSENT_TOKEN in module_absent
    assert config_error is not None and config_token in config_error
    # ...and NEVER a neighbour's: no two provisioning causes get confused.
    assert EMBEDDER_MODULE_ABSENT_TOKEN not in unreachable
    assert config_token not in unreachable
    assert EMBEDDER_UNREACHABLE_TOKEN not in module_absent
    assert config_token not in module_absent
    assert EMBEDDER_UNREACHABLE_TOKEN not in config_error
    assert EMBEDDER_MODULE_ABSENT_TOKEN not in config_error
    # The four footprints are pairwise distinct (``None`` is the clean-empty footprint).
    footprints = {unreachable, module_absent, config_error, clean_empty}
    assert len(footprints) == 4, f"embedder states collapsed into one: {footprints}"


def test_dense_vector_store_constructs_without_the_optional_ollama_package(monkeypatch):
    """Dense store construction no longer imports the optional ``ollama`` package.

    With the package made unimportable, the REAL ``Neo4jVectorStore`` must still construct
    (no DB I/O: a shim client + ``ensure_index=False``) and its embedder must be the default
    stdlib HTTP transport. This is the exact construction failure the live evidence recorded.
    """
    import types

    from agentic_dynamics.knowledge import embeddings
    from agentic_dynamics.knowledge.neo4j_vectors import Neo4jVectorStore

    monkeypatch.setitem(sys.modules, "ollama", None)
    store = Neo4jVectorStore(client=types.SimpleNamespace(close=lambda: None), ensure_index=False)
    assert store._embedder.transport == embeddings.TRANSPORT_HTTP


def test_dense_store_search_propagates_typed_embedder_token(monkeypatch):
    """The dense store's query-embed call site does not collapse the typed failure.

    ``search_with_stats`` embeds its query before any DB call; a typed ``EmbedderUnreachable``
    must propagate UNCHANGED (not wrapped into ``Neo4jVectorStoreError``), so the retrieval
    seam can read ``.token`` and name the state.
    """
    from agentic_dynamics.knowledge import embeddings
    from agentic_dynamics.knowledge.neo4j_vectors import Neo4jVectorStore

    class _RefusingEmbedder:
        def embed(self, text):
            raise embeddings.EmbedderUnreachable("no endpoint")

    store = Neo4jVectorStore.__new__(Neo4jVectorStore)
    store._embedder = _RefusingEmbedder()
    store._corpus_count = -1
    with pytest.raises(embeddings.EmbedderUnreachable) as excinfo:
        store.search_with_stats("query", top_k=5, where={"repository_id": "agentic-dynamics"})
    assert excinfo.value.token == EMBEDDER_UNREACHABLE_TOKEN


def test_both_dense_and_embedding_diagnoses_are_preserved(monkeypatch):
    """A failing dense leg must not suppress the separate embedding-leg diagnosis.

    Both failures are the same NAMED state (unreachable) but they are DIFFERENT legs: the
    attempt must carry BOTH keys, each with the token, never a single collapsed string.
    """
    from agentic_dynamics.knowledge import embeddings

    class _RaisingEmbedder:
        def __init__(self, *args, **kwargs):
            pass

        def embed(self, text):
            raise embeddings.EmbedderUnreachable("endpoint down")

        def cosine_distance(self, a, b):
            return 0.5

    monkeypatch.setattr("agentic_dynamics.knowledge.embeddings.EmbeddingClient", _RaisingEmbedder)
    attempt = retrieve(
        "websocket reload",
        dense_store=_FakeDenseStore(
            [], error=embeddings.EmbedderUnreachable("dense query embed failed")
        ),
        graph_client=_FakeGraph(
            lexical_hits=[
                _knowledge_lexical_hit("a", "alpha unique text"),
                _knowledge_lexical_hit("b", "beta unique text"),
            ]
        ),
    )
    assert "dense" in attempt.leg_errors
    assert "embedding" in attempt.leg_errors
    assert EMBEDDER_UNREACHABLE_TOKEN in attempt.leg_errors["dense"]
    assert EMBEDDER_UNREACHABLE_TOKEN in attempt.leg_errors["embedding"]
    assert {"dense", "embedding"} <= set(attempt.to_dict()["leg_errors"])


def test_unavailable_dense_store_chains_typed_embedder_token(monkeypatch):
    """A construction-time typed embedder failure still names its token through the wrap.

    ``augment._UnavailableDenseStore`` raises a ``RuntimeError`` for the recorded cause but
    chains the original typed exception, and the retrieval seam's one-level ``__cause__``
    lookup recovers ``embedder-unreachable`` — the pre-u4 evidence had a collapsed
    ``ModuleNotFoundError`` string here instead.
    """
    from agentic_dynamics.knowledge import augment as aug
    from agentic_dynamics.knowledge import embeddings

    store = aug._UnavailableDenseStore(
        "dense store construction failed: boom",
        cause_exc=embeddings.EmbedderUnreachable("no endpoint"),
    )
    attempt = retrieve(
        "websocket reload", dense_store=store, graph_client=_FakeGraph(lexical_hits=[])
    )
    assert "dense" in attempt.leg_errors
    assert EMBEDDER_UNREACHABLE_TOKEN in attempt.leg_errors["dense"]
    assert "No module named" not in attempt.leg_errors["dense"]


# ── u6: the embedder module is cell-viable by CONSTRUCTION (AST guard, not a live import) ──


def test_embeddings_module_has_no_module_level_optional_import():
    """AST guard: no optional package is imported at ``embeddings.py`` module scope (u6).

    Cell viability is a STRUCTURAL contract: a base-deps cell must be able to IMPORT this
    module, so the optional ``ollama`` package may be imported only inside a function (the
    explicitly selected transport), never at module scope. Parsing the module's AST — rather
    than inspecting an imported object — makes the guard hold even on a host where ``ollama``
    happens to be installed, so the mutation it catches is the import MOVING to module scope.
    The same scan asserts every module-level import is stdlib, proving the refactor REMOVED a
    runtime dependency rather than swapping in another. Finally it proves the optional
    transport's import still EXISTS, but only function-locally (a genuinely lazy optional).

    Falsifier: adding a top-level ``import ollama`` (or any third-party module) to
    ``embeddings.py`` fails this gate; removing the lazy import entirely also fails it.
    """
    from agentic_dynamics.knowledge import embeddings

    source = Path(embeddings.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(embeddings.__file__))

    module_level: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            module_level.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_level.add(node.module.split(".")[0])

    assert "ollama" not in module_level, (
        f"embeddings.py imports the optional 'ollama' package at module scope: {module_level}"
    )
    non_stdlib = module_level - set(sys.stdlib_module_names)
    assert not non_stdlib, (
        f"embeddings.py gained a non-stdlib module-level dependency: {sorted(non_stdlib)}"
    )

    # The optional package stays reachable — but ONLY as a function-local, lazy import.
    nested_ollama_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        and any(alias.name.split(".")[0] == "ollama" for alias in node.names)
    ]
    assert nested_ollama_imports, "the lazily imported optional ollama transport disappeared"
    direct_children = {id(node) for node in tree.body}
    assert all(id(node) not in direct_children for node in nested_ollama_imports), (
        "an 'import ollama' statement is a module-level statement"
    )
