"""Tests for the deterministic retrieval + evidence-card layer.

Covers the query planner (pure regexes), fusion math, graph-decay boost, token
budgeting, dedupe, conflict retention, fallback-mode resolution, and evidence-card
derivation — all without requiring Chroma/Neo4j/Ollama (the store-dependent
orchestration is exercised only through its pure helpers).
"""

from datetime import datetime, timedelta, timezone

import pytest

from agentic_dynamics.knowledge.knowledge import Authority
from agentic_dynamics.knowledge.retrieval import (
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
    _dense_filter,
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
    retrieve,
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
    # Exact commit match keeps its soft boost.
    assert freshness_multiplier(
        authority=Authority.SOURCE, commit_sha="abc", observed_at=None, current_commit="abc"
    ) == pytest.approx(EXACT_COMMIT_MULTIPLIER)
    # A different, non-empty commit is a HARD exclusion (the safety rationale).
    assert freshness_multiplier(
        authority=Authority.SOURCE, commit_sha="xyz", observed_at=None, current_commit="abc"
    ) is None


def test_freshness_non_matching_commit_excluded_for_all_non_advisory():
    # SOURCE / MEASURED / DERIVED are all hard-excluded on a different commit.
    for authority in (Authority.SOURCE, Authority.MEASURED, Authority.DERIVED):
        assert freshness_multiplier(
            authority=authority, commit_sha="xyz", observed_at=None, current_commit="abc"
        ) is None


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
        authority=Authority.ADVISORY, commit_sha="xyz", observed_at=observed,
        current_commit="abc", now=NOW,
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


def test_build_evidence_cards_nan_treated_as_unmeasured():
    # NaN must behave exactly like an absent value: not crash, not render a number.
    card = build_evidence_cards(
        [_run(confidence=float("nan"), perturbation_strength=float("nan"),
              test_executed_success=float("nan"))]
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
    card = build_evidence_cards(
        [_run(confidence=0.91, test_executed_success=False)]
    )[0]
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


def _lexical_hit(cid="doc_lex", text="lexical websocket reload hit"):
    return {
        "id": "elem:lex",
        "properties": {"text": text, "authority": "source", "content_hash": "hash_lex", "doc_id": cid},
        "score": 0.9,
    }


def _knowledge_lexical_hit(cid="k_kb", text="task manager api building finding", authority="measured"):
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
    expected = seed.fused_score * RELATIONSHIP_WEIGHTS["DEFINES"] * (0.7 ** 1)
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
    dense = _FakeDenseStore([
        _dense_hit("k1", "websocket live reload protocol", authority="source", content_hash="dup"),
        _dense_hit("k2", "websocket live reload protocol", authority="advisory", content_hash="dup"),
        _dense_hit("k3", "quantum entanglement of distant particles", authority="source", content_hash="distinct"),
    ])
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
    dense = _FakeDenseStore([
        _dense_hit("k1", "near duplicate text one", authority="source"),
        _dense_hit("k2", "near duplicate text two", authority="advisory"),
        _dense_hit("k3", "completely different topic", authority="source"),
    ])

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

    attempt = retrieve(
        "build a task manager api", dense_store=None, graph_client=_KBOnlyGraph()
    )
    ids = {c.id for c in attempt.candidates}
    assert "k_kb" in ids
    assert next(c for c in attempt.candidates if c.id == "k_kb").authority is Authority.MEASURED
