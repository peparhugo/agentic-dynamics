"""Tests for scripts/aggregate_workflow_metrics.py — the autonomous-workflow metrics aggregator.

These tests lock the two halves of the instrument's contract:

1. **The arithmetic** — the pinned §3 metric definitions applied to synthetic ledgers with
   known answers (retry rate, cost-per-accepted, throughput, checkpoint latency).
2. **The missing-field handling** — a ledger without the I10 checkpoint records (or without the
   declared-not-written attempt fields) is *covered*, not imputed: the metric reports
   ``measurable=False`` with the named missing field, never a fabricated zero.
"""

from __future__ import annotations

import importlib

import pytest

# The script lives in scripts/ (not on the package import path); import it as a module by name,
# matching the sibling script tests (e.g. tests/test_evidence_prereq_gate.py).
agg = importlib.import_module("scripts.aggregate_workflow_metrics")


def _job(job_id, n_attempts, status="accepted", cost=1.0):
    return agg.Job(
        job_id=job_id,
        n_attempts=n_attempts,
        status=status,
        cost_usd=cost,
        accepted=(status == "accepted"),
        started_at="",
        ended_at="",
    )


def _corpus(jobs=None, attempts=None, phases=None, checkpoints=None, started_at="", ended_at=""):
    return agg.LedgerCorpus(
        name="synthetic",
        paths=["experiments/results/synthetic/ledger.json"],
        jobs=jobs or [],
        attempts=attempts or [],
        phases=phases or [],
        checkpoints=checkpoints or [],
        started_at=started_at,
        ended_at=ended_at,
    )


# ── Arithmetic ────────────────────────────────────────────────────────────────


def test_retry_rate_arithmetic():
    """r = jobs with attempt_count > 1 / total jobs — derived from the attempts array."""
    corpus = _corpus(jobs=[_job("a", 1), _job("b", 1), _job("c", 2), _job("d", 1)])
    result = agg.compute_retry_rate(corpus)
    assert result.measurable is True
    assert result.basis == "derived"
    assert result.value == pytest.approx(0.25)  # 1 multi-attempt job / 4 jobs


def test_retry_rate_zero_when_no_retries():
    corpus = _corpus(jobs=[_job("a", 1), _job("b", 1)])
    result = agg.compute_retry_rate(corpus)
    assert result.value == 0.0


def test_retry_rate_not_measurable_without_attempts():
    corpus = _corpus(jobs=[])  # no jobs -> no attempts -> not measurable, NOT 0.0
    result = agg.compute_retry_rate(corpus)
    assert result.measurable is False
    assert result.value is None
    assert "attempt_count" in result.reason


def test_cost_per_accepted_arithmetic():
    """cost-per-accepted sums realized_cost over the accepted jobs only."""
    corpus = _corpus(
        jobs=[
            _job("a", 1, status="accepted", cost=1.5),
            _job("b", 1, status="failed", cost=2.0),
            _job("c", 1, status="accepted", cost=0.5),
        ]
    )
    result = agg.compute_cost_per_accepted(corpus)
    assert result.measurable is True
    assert result.basis == "measured"
    assert result.value["accepted_count"] == 2
    assert result.value["total_accepted_cost_usd"] == pytest.approx(2.0)


def test_throughput_phases_per_hour():
    """throughput = phases / span-hours, from started_at/ended_at."""
    corpus = _corpus(
        phases=[agg.Phase("p", "agent", "ok", 1.0, 60.0) for _ in range(10)],
        started_at="2026-08-30T00:00:00+00:00",
        ended_at="2026-08-30T02:00:00+00:00",
    )
    result = agg.compute_throughput(corpus)
    assert result.measurable is True
    assert result.value["phases_per_hour"] == pytest.approx(5.0)
    assert result.value["span_hours"] == pytest.approx(2.0)


def test_throughput_not_measurable_without_timestamps():
    corpus = _corpus(phases=[agg.Phase("p", "agent", "ok", 1.0, 60.0)])
    result = agg.compute_throughput(corpus)
    assert result.measurable is False
    assert result.value == {"phases": 1}


def test_checkpoint_latency_arithmetic():
    """checkpoint latency = decided_at - reached_at per approval."""
    corpus = _corpus(
        checkpoints=[
            agg.Checkpoint(
                "p1", "approved", "2026-08-30T00:00:00+00:00", "2026-08-30T00:01:00+00:00"
            ),
            agg.Checkpoint(
                "p2", "approved", "2026-08-30T00:00:00+00:00", "2026-08-30T00:02:00+00:00"
            ),
        ]
    )
    result = agg.compute_checkpoint_latency(corpus)
    assert result.measurable is True
    assert result.value["checkpoint_count"] == 2
    assert result.value["mean_seconds"] == pytest.approx(90.0)
    assert result.value["median_seconds"] == pytest.approx(90.0)
    assert result.value["max_seconds"] == pytest.approx(120.0)


# ── Missing-field handling (covered, not imputed) ─────────────────────────────


def test_checkpoint_absent_is_covered_not_imputed():
    """A ledger without I10 records -> checkpoint_latency is not-measurable, not a 0."""
    result = agg.compute_checkpoint_latency(_corpus())
    assert result.measurable is False
    assert result.value is None
    assert "checkpoints" in result.reason


def test_first_call_resolution_is_not_measurable():
    """WOC needs the declared-not-written first_pass field — never fabricated."""
    result = agg.compute_first_call_resolution(_corpus())
    assert result.measurable is False
    assert "first_pass" in result.reason


def test_escalation_rate_is_not_measurable():
    result = agg.compute_escalation_rate(_corpus())
    assert result.measurable is False
    assert "escalation" in result.reason


def test_batch_fraction_is_not_measurable():
    result = agg.compute_batch_fraction(_corpus())
    assert result.measurable is False
    assert "batch_mode" in result.reason


def test_sla_behavior_is_not_measurable():
    result = agg.compute_sla_behavior(_corpus())
    assert result.measurable is False
    assert "timeout" in result.reason


# ── Pinned definitions are complete (hard rule 3) ─────────────────────────────


def test_pinned_definitions_cover_all_eight_metrics():
    """The §3 vocabulary is exactly the eight operating metrics — none missing, none extra."""
    assert set(agg.PINNED_METRIC_DEFINITIONS) == {
        "retry_rate",
        "first_call_resolution",
        "escalation_rate",
        "batch_fraction",
        "throughput",
        "cost_per_accepted",
        "checkpoint_latency",
        "sla_behavior",
    }
    # Every metric has a registered computer.
    assert {name for name, _ in agg.METRIC_COMPUTERS} == set(agg.PINNED_METRIC_DEFINITIONS)


# ── Classification ─────────────────────────────────────────────────────────────


def test_classify_attempt_ledger():
    assert agg.classify({"cells": [{"attempts": []}]}) == agg.KIND_ATTEMPT


def test_classify_workflow_run_ledger():
    assert agg.classify({"spec_name": "x", "phases": []}) == agg.KIND_WORKFLOW_RUN


def test_classify_campaign_phase_ledger_with_run_ledger():
    assert agg.classify({"campaign": "x", "run_ledger": {"phases": []}}) == agg.KIND_CAMPAIGN_PHASE


def test_classify_other():
    assert agg.classify({"campaign": "x", "per_cell": []}) == agg.KIND_OTHER


# ── End-to-end over a synthetic tree ──────────────────────────────────────────


def test_end_to_end_emits_and_aggregates(tmp_path):
    """A synthetic tree with one attempt ledger and one workflow ledger round-trips to JSON."""
    results = tmp_path / "experiments" / "results"
    (results / "workflows" / "demo").mkdir(parents=True)
    (results / "cap_demo").mkdir(parents=True)

    (results / "cap_demo" / "ledger.json").write_text(
        '{"cells":['
        '{"cell_id":"c1","status":"accepted","realized_cost":1.5,"attempts":[{"attempt_number":1,"retry_reason":"","status":"ok","actual_cost":1.5}]},'
        '{"cell_id":"c2","status":"accepted","realized_cost":2.5,"attempts":[{"attempt_number":1,"retry_reason":"","status":"fail","actual_cost":1.0},{"attempt_number":2,"retry_reason":"retry","status":"ok","actual_cost":1.5}]}'
        "]}"
    )
    (results / "workflows" / "demo" / "20260830T000000Z.json").write_text(
        '{"spec_name":"demo","model":"m","goal":"g","started_at":"2026-08-30T00:00:00+00:00",'
        '"ended_at":"2026-08-30T02:00:00+00:00","ok":true,"phases":['
        '{"phase":"p1","kind":"agent","status":"ok","cost_usd":1.0,"duration_s":10.0},'
        '{"phase":"p2","kind":"agent","status":"ok","cost_usd":1.0,"duration_s":10.0}'
        '],"checkpoints":[]}'
    )

    doc = agg.emit(tmp_path, dry_run=True)
    campaigns = {r["campaign"]: r for r in doc["campaigns"]}

    # The attempt ledger: retry rate = 1/2, cost-per-accepted = $4.0 over 2 accepted jobs.
    demo = campaigns["cap_demo"]
    assert demo["metrics"]["retry_rate"]["measurable"] is True
    assert demo["metrics"]["retry_rate"]["value"] == pytest.approx(0.5)
    assert demo["metrics"]["cost_per_accepted"]["value"][
        "total_accepted_cost_usd"
    ] == pytest.approx(4.0)

    # The workflow ledger: throughput = 2 phases / 2h, no checkpoints -> covered, not imputed.
    demo_run = campaigns["demo"]
    assert demo_run["metrics"]["throughput"]["value"]["phases_per_hour"] == pytest.approx(1.0)
    assert demo_run["metrics"]["checkpoint_latency"]["measurable"] is False

    # Coverage table is exact and per-campaign.
    assert {r["campaign"] for r in doc["coverage"]} == {"cap_demo", "demo"}
