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


def test_checkpoint_decisions_and_reasons_distribution():
    """The checkpoint behavior: decision + reason distribution + approval-evidence presence."""
    corpus = _corpus(
        checkpoints=[
            agg.Checkpoint(
                "p1",
                "awaiting",
                "2026-08-30T00:00:00+00:00",
                "2026-08-30T00:01:00+00:00",
                reason="checkpoint_reached",
            ),
            agg.Checkpoint(
                "p1",
                "approved",
                "2026-08-30T00:00:00+00:00",
                "2026-08-30T00:01:00+00:00",
                reason="approval_required",
                approval_evidence={"valid": True},
            ),
            agg.Checkpoint(
                "p2",
                "rejected",
                "2026-08-30T00:00:00+00:00",
                "2026-08-30T00:02:00+00:00",
                reason="approval_required",
            ),
        ]
    )
    result = agg.compute_checkpoint_latency(corpus)
    assert result.measurable is True
    assert result.value["decisions"] == {"approved": 1, "awaiting": 1, "rejected": 1}
    assert result.value["reasons"] == {"approval_required": 2, "checkpoint_reached": 1}
    assert result.value["with_approval_evidence"] == 1


def test_sla_behavior_measured_from_gate_fields():
    """SLA/limit behavior is measured from the runner's timeout + gate-breach phase fields."""
    corpus = _corpus(
        phases=[
            agg.Phase("a", "agent", "ok", 1.0, 10.0, breach_fields_recorded=True),
            agg.Phase(
                "b",
                "agent",
                "failed",
                1.0,
                10.0,
                breach_fields_recorded=True,
                stall_evidence={"reason": "STALLED"},
            ),
            agg.Phase(
                "c",
                "agent",
                "failed",
                1.0,
                10.0,
                breach_fields_recorded=True,
                deploy_gate={"reason": "DEPLOY_GATE"},
            ),
        ]
    )
    result = agg.compute_sla_behavior(corpus)
    assert result.measurable is True
    assert result.basis == "measured"
    assert result.value["total_phases_with_breach_fields"] == 3
    assert result.value["timeout_breaches"] == 1
    assert result.value["gate_breaches"] == 1
    assert result.value["breakdown"]["stall"] == 1
    assert result.value["breakdown"]["deploy_gate"] == 1
    assert result.value["timeout_breach_rate"] == pytest.approx(1 / 3)


def test_sla_behavior_not_measurable_when_breach_fields_absent():
    """A pre-hardening ledger omits the breach keys entirely -> not-measurable, NOT zero breaches."""
    corpus = _corpus(phases=[agg.Phase("a", "agent", "ok", 1.0, 10.0)])  # no breach_fields_recorded
    result = agg.compute_sla_behavior(corpus)
    assert result.measurable is False
    assert result.value is None
    assert "stall_evidence" in result.reason


def test_workload_volume_and_phase_cost_structure_reported():
    """W (workload volume) and the agent-vs-test phase cost structure are reported per campaign."""
    corpus = _corpus(
        jobs=[_job("a", 1, cost=1.0), _job("b", 1, cost=2.0)],
        phases=[
            agg.Phase("p", "agent", "ok", 1.5, 10.0),
            agg.Phase("t", "test", "ok", 0.0, 1.0),
        ],
    )
    row = agg.compute_campaign_metrics(corpus)
    assert row["workload_volume"]["W"] == 2
    assert row["phase_cost_structure"]["n_agent_phases"] == 1
    assert row["phase_cost_structure"]["n_test_phases"] == 1
    assert row["phase_cost_structure"]["agent_cost_usd"] == pytest.approx(1.5)
    assert row["phase_cost_structure"]["test_cost_usd"] == pytest.approx(0.0)


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
    assert "stall_evidence" in result.reason


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


# ── Framework comparison (p2) ─────────────────────────────────────────────────


def test_measured_ex_values_reads_score_file(tmp_path):
    """The measured E_x is cited from the escalation-measurement score file, not re-derived."""
    score_dir = tmp_path / "experiments" / "results" / "cap_escalation_measurement"
    score_dir.mkdir(parents=True)
    (score_dir / "cap_escalation_measurement_score.json").write_text(
        '{"per_model":[{"escalation_model":"openai/gpt-5.6-sol","E_x":11.4671},'
        '{"escalation_model":"anthropic/claude-sonnet-5","E_x":12.5134}],'
        '"conclusion":{"measured_ex_range":[11.4671,12.5134]}}'
    )
    ex = agg._measured_ex_values(tmp_path)
    assert ex["values"][0]["E_x"] == pytest.approx(11.4671)
    assert ex["values"][1]["escalation_model"] == "anthropic/claude-sonnet-5"
    assert ex["measured_ex_range"] == [11.4671, 12.5134]


def test_framework_comparison_places_measured_beside_constants(tmp_path):
    """The comparison stage places the measured r beside the 11.5% scenario and the E_x values
    beside the 28.2×/68.7× price ratios — labelled as different quantities."""
    pooled = {
        "retry_rate": {"values": [{"value": 0.125}]},
        "escalation_rate": {"values": []},
    }
    comp = agg.framework_comparison(tmp_path, pooled)
    assert comp["retry_rate"]["measured_r"] == pytest.approx(0.125)
    assert comp["retry_rate"]["framework_scenario"] == pytest.approx(0.115)
    assert comp["escalation"]["measured_escalation_rate"] is None  # no escalation marker -> None
    assert comp["escalation"]["framework_ex_price_ratios"]["deepseek_to_gpt56"] == pytest.approx(
        28.2
    )
    assert comp["escalation"]["framework_ex_price_ratios"]["deepseek_to_claude"] == pytest.approx(
        68.7
    )
    # The E_x values are price ratios [X], not the measured multiplier — the two are kept apart.
    assert comp["escalation"]["measured_ex"]["values"] == []  # no score file in this tree
