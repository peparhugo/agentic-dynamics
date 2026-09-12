"""Tests for the P10 ``batch`` projection (step 7, d3 §5 P10).

Pins: without a ``batch_mode`` marker the endpoint is NOT measurable, names the missing record,
and serves the rule-6 scenario labeled ``X/P`` — never a fabricated fraction. If a marker ever
appears, the fraction becomes a measured computation over the marked jobs.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.control.projections.batch import (  # noqa: E402
    SCHEMA,
    build_batch,
)

_NOW = "2026-09-12T12:00:00+00:00"


def test_without_marker_it_is_not_measurable_and_never_fabricates():
    jobs = [{"job_id": "j1"}, {"job_id": "j2", "state": "queued"}]
    payload = build_batch(jobs, now=_NOW)
    assert payload["schema"] == SCHEMA
    assert payload["measurable"] is False
    assert payload["reason"] == "no batch_mode marker"
    assert payload["scanned_jobs"] == 2
    assert "batch_fraction" not in payload
    assert payload["modeled"] == {
        "discount": 0.5,
        "horizon_h": 72,
        "class": "X/P",
        "source": "rule 6 (Batch Discount) — proposed [C]; no batch executor exists",
    }


def test_marker_flips_it_to_a_measured_fraction():
    jobs = [
        {"job_id": "j1", "batch_mode": True},
        {"job_id": "j2", "batch_mode": False},
        {"job_id": "j3"},  # unmarked: not part of the denominator
    ]
    payload = build_batch(jobs, now=_NOW)
    assert payload["measurable"] is True
    assert payload["batch_jobs"] == 1
    assert payload["marked_jobs"] == 2
    assert payload["batch_fraction"] == 0.5
    # the scenario block stays labeled even when the fraction is measured
    assert payload["modeled"]["class"] == "X/P"


def test_a_non_boolean_marker_is_not_a_measurement():
    jobs = [{"job_id": "j1", "batch_mode": "yes"}]  # a string is not the boolean marker
    payload = build_batch(jobs, now=_NOW)
    assert payload["measurable"] is False
    assert payload["reason"] == "no batch_mode marker"


def test_an_empty_queue_classifies_nothing():
    """No jobs is not 'no marker' — the reason names the empty queue, never a fake zero."""
    payload = build_batch([], now=_NOW)
    assert payload["measurable"] is False
    assert payload["reason"] == "queue empty — nothing to classify"
    assert payload["scanned_jobs"] == 0


def test_lane_tagged_jobs_measure_the_split_and_label_the_discount():
    """The room tags each job by its lane (the lane IS the mode) — the split is measured."""
    jobs = [
        {"cell_id": "a", "batch_mode": False},
        {"cell_id": "b", "batch_mode": True},
        {"cell_id": "c", "batch_mode": True},
        {"cell_id": "d", "batch_mode": True},
    ]
    payload = build_batch(jobs, now=_NOW)
    assert payload["measurable"] is True
    assert payload["batch_fraction"] == 0.75
    assert payload["batch_jobs"] == 3
    assert payload["on_demand_jobs"] == 1
    # the 50% economics stay a labeled scenario — no provider batch transport exists
    assert payload["modeled"]["class"] == "X/P"
