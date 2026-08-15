"""Tests for the deterministic retrieval + evidence-card layer.

Covers the query planner (pure regexes), fusion math, graph-decay boost, token
budgeting, dedupe, conflict retention, fallback-mode resolution, and evidence-card
derivation — all without requiring Chroma/Neo4j/Ollama (the store-dependent
orchestration is exercised only through its pure helpers).
"""

from datetime import datetime, timedelta, timezone

import pytest

from instrument.knowledge import Authority
from instrument.retrieval import (
    ADVISORY_FRESH_30D,
    ADVISORY_FRESH_90D,
    AUTHORITY_MULTIPLIER,
    CONFLICT_MULTIPLIER,
    EXACT_COMMIT_MULTIPLIER,
    RELATIONSHIP_WEIGHTS,
    WEIGHTS_VERSION,
    Candidate,
    EvidenceCard,
    FallbackMode,
    build_evidence_cards,
    build_query_plan,
    collapse_redundant,
    compute_fused_score,
    compute_token_budget,
    deduplicate,
    exact_identifier_hit,
    freshness_multiplier,
    graph_boost,
    is_conflict_relationship,
    resolve_fallback_mode,
    rrf_base,
    select_evidence,
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
        lexical_rank=0, dense_rank=0, authority=Authority.SOURCE,
        freshness=1.0, exact_identifier_match=False, conflict=False,
    )
    with_conflict = compute_fused_score(
        lexical_rank=0, dense_rank=0, authority=Authority.SOURCE,
        freshness=1.0, exact_identifier_match=False, conflict=True,
    )
    assert with_conflict == pytest.approx(no_conflict * CONFLICT_MULTIPLIER)


def test_freshness_exact_commit_and_source():
    assert freshness_multiplier(
        authority=Authority.SOURCE, commit_sha="abc", observed_at=None, current_commit="abc"
    ) == pytest.approx(EXACT_COMMIT_MULTIPLIER)
    assert freshness_multiplier(
        authority=Authority.SOURCE, commit_sha="xyz", observed_at=None, current_commit="abc"
    ) == pytest.approx(1.0)


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
    assert freshness_multiplier(
        authority=Authority.ADVISORY, commit_sha="", observed_at=obs(100), current_commit="", now=NOW
    ) is None


def test_freshness_policy_is_never_retrieved():
    assert freshness_multiplier(
        authority=Authority.POLICY, commit_sha="abc", observed_at=None, current_commit="abc"
    ) is None


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
    assert compute_token_budget(
        executor_context_tokens=200_000, remaining_input_tokens=200_000, rag_token_limit=8000
    ) == 8000
    # 20% of a 10k context = 2000, and remaining input 5000 → 2000.
    assert compute_token_budget(
        executor_context_tokens=10_000, remaining_input_tokens=5_000, rag_token_limit=8000
    ) == 2000
    # Tight remaining input dominates.
    assert compute_token_budget(
        executor_context_tokens=200_000, remaining_input_tokens=100, rag_token_limit=8000
    ) == 100


def test_select_evidence_never_splits_a_chunk():
    a = _cand("a", text="x", token_count=4, dense_rank=0)   # highest score
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
    assert out[0].id == "k2"            # higher authority survives
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
        "full", "lexical_graph_only", "dense_local_exact", "no_rag",
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
    cards = build_evidence_cards([_run(worktree_name="a"), _run(worktree_name="b", narration_failure=True)])
    assert [c.run_id for c in cards] == ["a"]


def test_build_evidence_cards_skips_negative_correctness():
    cards = build_evidence_cards([_run(worktree_name="ok"), _run(worktree_name="bad", correctness=-1)])
    assert [c.run_id for c in cards] == ["ok"]


def test_build_evidence_cards_flail_falls_back_to_escape():
    run = _run(flail=None, escape=0.51)
    del run["flail"]
    card = build_evidence_cards([run])[0]
    assert card.flail == pytest.approx(0.51)


def test_build_evidence_cards_is_deterministic():
    runs = [_run(), _run(worktree_name="wt-2", model="anthropic/claude-sonnet-5", flail=0.1)]
    assert build_evidence_cards(runs) == build_evidence_cards(runs)


# ── RetrievalAttempt sanity (recorded before any LLM call) ──────

def test_candidate_citation_format():
    c = _cand("k1", locator="symbol:foo", commit_sha="abc")
    assert c.citation() == "[K:k1@abc:symbol:foo]"
