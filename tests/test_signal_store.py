"""Tests for the signal store (docs/routing_next_steps.md item 1).

Covers the two per-entry derivations (``cache_hit_rate``, ``constraint_score``) including
their zero-denominator guards, the model-id alias layer (legacy ``openai/gpt-5.6`` → pool
``openai/gpt-5.6-sol``), that a model measured only under a legacy id resolves into the store,
and that ``correctness``/``cost`` now skip NaN/None rows instead of defaulting to 0.
"""

import json

import pytest

from agentic_dynamics.control.signal_store import (
    MODEL_ALIASES,
    build_signal_store,
    derive_cache_hit_rate,
    derive_constraint_score,
    load_results,
    normalize_model_id,
)

DS = "deepseek/deepseek-v4-pro"
CL = "anthropic/claude-fable-5"
SOL = "openai/gpt-5.6-sol"
LEGACY = "openai/gpt-5.6"


# ── Derivation: cache hit rate ──────────────────────────────────


def test_derive_cache_hit_rate_basic():
    e = {"tokens_cache_read": 300, "tokens_input": 100}
    assert derive_cache_hit_rate(e) == pytest.approx(300 / 400)


def test_derive_cache_hit_rate_zero_denominator():
    # No input and no cache reads → the ratio is undefined, not 0.0.
    assert derive_cache_hit_rate({"tokens_cache_read": 0, "tokens_input": 0}) is None


def test_derive_cache_hit_rate_missing_fields():
    assert derive_cache_hit_rate({"tokens_cache_read": 300}) is None
    assert derive_cache_hit_rate({"tokens_input": 100}) is None
    assert derive_cache_hit_rate({}) is None


# ── Derivation: constraint score ────────────────────────────────


def test_derive_constraint_score_basic():
    assert derive_constraint_score({"constraints_met": 7, "constraints_total": 10}) == pytest.approx(0.7)


def test_derive_constraint_score_zero_total():
    assert derive_constraint_score({"constraints_met": 0, "constraints_total": 0}) is None


def test_derive_constraint_score_missing_fields():
    assert derive_constraint_score({"constraints_met": 7}) is None
    assert derive_constraint_score({"constraints_total": 10}) is None
    assert derive_constraint_score({}) is None


# ── Model-id aliasing ───────────────────────────────────────────


def test_normalize_model_id_maps_legacy_to_pool():
    assert normalize_model_id(LEGACY) == SOL
    assert SOL in MODEL_ALIASES
    assert LEGACY in MODEL_ALIASES[SOL]


def test_normalize_model_id_keeps_pool_and_matching_ids_unchanged():
    # A pool id passes through; an id that already matches on both sides is untouched.
    assert normalize_model_id(SOL) == SOL
    assert normalize_model_id(DS) == DS
    assert normalize_model_id(CL) == CL


def test_normalize_model_id_unknown_id_unchanged():
    assert normalize_model_id("some/unknown-model") == "some/unknown-model"


# ── Aggregation with derivations + aliases ──────────────────────


def test_build_signal_store_resolves_model_measured_only_under_legacy_id():
    # The measured corpus records ``openai/gpt-5.6``; the pool id is ``openai/gpt-5.6-sol``.
    # The store must key the aggregation under the *pool* id so route_step can look it up.
    entries = [
        {"model": LEGACY, "correctness": 0.9, "cost": 0.01},
        {"model": LEGACY, "correctness": 0.7, "cost": 0.02},
    ]
    store = build_signal_store(entries)
    assert SOL in store
    assert LEGACY not in store
    assert store[SOL].correctness == pytest.approx(0.8)
    assert store[SOL].cost == pytest.approx(0.015)


def test_build_signal_store_derives_constraint_score_and_cache_hit_rate():
    entries = [
        {"model": DS, "constraints_met": 5, "constraints_total": 10,
         "tokens_cache_read": 100, "tokens_input": 100},
        {"model": DS, "constraints_met": 2, "constraints_total": 5,
         "tokens_cache_read": 0, "tokens_input": 0},
    ]
    store = build_signal_store(entries)
    assert store[DS].constraint_score == pytest.approx((0.5 + 0.4) / 2)
    # Second entry has a zero denominator → its cache_hit_rate is dropped, not 0.0-averaged.
    assert store[DS].cache_hit_rate == pytest.approx(0.5)


def test_build_signal_store_skips_nan_and_none_rows_for_correctness_and_cost():
    # The old store averaged missing correctness/cost in as 0.0 (``or 0``); the new store
    # must skip NaN/None rows so a sparse entry cannot bias the aggregate (item 5.3).
    entries = [
        {"model": DS, "correctness": 0.8, "cost": 0.001},
        {"model": DS, "correctness": None, "cost": 0.003},
        {"model": DS, "correctness": float("nan"), "cost": float("nan")},
    ]
    store = build_signal_store(entries)
    assert store[DS].correctness == pytest.approx(0.8)  # only the first finite row contributes
    assert store[DS].cost == pytest.approx((0.001 + 0.003) / 2)  # NaN cost dropped


def test_build_signal_store_efficiency_requires_positive_cost():
    entries = [
        {"model": DS, "correctness": 0.8},
        {"model": CL, "correctness": 0.9, "cost": 0.0},
    ]
    store = build_signal_store(entries)
    assert store[DS].efficiency is None  # no measured cost
    assert store[CL].efficiency is None  # zero cost → undefined


def test_build_signal_store_never_populates_unmeasured_signals():
    # confidence / edge_case_coverage stay None — the store does not consume unmeasured signals.
    entries = [{"model": DS, "correctness": 0.8, "cost": 0.001}]
    store = build_signal_store(entries)
    assert store[DS].edge_case_coverage is None


# ── load_results ────────────────────────────────────────────────


def test_load_results_reads_entries_not_by_model(tmp_path):
    p = tmp_path / "_results_summary.json"
    p.write_text(json.dumps({
        "entries": [{"model": DS, "correctness": 0.8}],
        "by_model": {"openai/gpt-5.6": [{"correctness": 0.9}]},
    }))
    entries = load_results(p)
    assert entries == [{"model": DS, "correctness": 0.8}]
