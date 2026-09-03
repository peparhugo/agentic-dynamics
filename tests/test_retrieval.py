"""Tests for the deterministic retrieval + evidence-card layer.

Covers the query planner (pure regexes), fusion math, graph-decay boost, token
budgeting, dedupe, conflict retention, fallback-mode resolution, and evidence-card
derivation — all without requiring Chroma/Neo4j/Ollama (the store-dependent
orchestration is exercised only through its pure helpers).
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from agentic_dynamics.knowledge.knowledge import Authority
from agentic_dynamics.knowledge.retrieval import (
    ADVISORY_FRESH_30D,
    ADVISORY_FRESH_90D,
    AUTHORITY_MULTIPLIER,
    CODE_QUERY_TYPE_PRIORS,
    CONFLICT_MULTIPLIER,
    EXACT_COMMIT_MULTIPLIER,
    FINDINGS_QUERY_TYPE_PRIORS,
    RELATIONSHIP_WEIGHTS,
    UNTYPED_EXCLUDED_REASON,
    WEIGHTS_VERSION,
    Candidate,
    EvidenceCard,
    FallbackMode,
    QueryShape,
    _dense_filter,
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


def test_freshness_non_matching_commit_excluded_for_all_non_advisory():
    # SOURCE / MEASURED / DERIVED are all hard-excluded on a different commit.
    for authority in (Authority.SOURCE, Authority.MEASURED, Authority.DERIVED):
        assert (
            freshness_multiplier(
                authority=authority, commit_sha="xyz", observed_at=None, current_commit="abc"
            )
            is None
        )


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
    # Commit scope alone → $or (empty is unknown/current, or exact match).
    assert _dense_filter({"commit_sha": "abc"}) == {
        "$or": [{"commit_sha": ""}, {"commit_sha": "abc"}]
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
            {"$or": [{"commit_sha": ""}, {"commit_sha": "abc"}]},
        ]
    }


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


# ── Query-shape classification + source-type ordering (k3 — the finding-layer wave) ──

FINDINGS_QUERY = (
    "what did the control database evidence wave conclude about per-phase finding records"
)
FINDINGS_OBJECTIVE = "determine what the control_db_evidence wave concluded"
CODE_QUERY = "implement the function build_step_graph and return its graph structure"
CODE_OBJECTIVE = ""


def test_query_shape_classifier_is_deterministic_and_named():
    shape = classify_query_shape(build_query_plan(FINDINGS_QUERY), phase_objective=FINDINGS_OBJECTIVE)
    assert shape is QueryShape.FINDINGS
    again = classify_query_shape(build_query_plan(FINDINGS_QUERY), phase_objective=FINDINGS_OBJECTIVE)
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
    assert (
        source_ordering_bucket(source_type="finding", evidence_class="[M]") == "evidence"
    )
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
    assert source_type_prior("evidence", QueryShape.FINDINGS) == FINDINGS_QUERY_TYPE_PRIORS["evidence"]
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
        "k_finding", "the control_db_evidence phase concluded records are reliable",
        source_type="finding", authority="measured", evidence_class="[M]",
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

