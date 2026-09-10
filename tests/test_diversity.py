"""Tests for the portfolio-diversity instrument (design B3).

The ladder measures how varied a *portfolio* of independent attempts is, so the instrument's
contract must be pinned from both ends: identical samples score zero, genuinely divergent
samples score positive, and a portfolio too small to have a pair reports ``None`` rather than
a fabricated zero (null-not-zero). These are pure-unit tests over source strings.
"""

import pytest

from agentic_dynamics.measurement import basin
from agentic_dynamics.measurement.diversity import (
    PortfolioDiversity,
    pairwise_divergence,
    portfolio_diversity,
)

pytestmark = pytest.mark.fast

# Two small, materially different task-manager designs: A is a Flask/dict implementation,
# B is a Django/SQLite object model. They share almost no structure or vocabulary.
SAMPLE_A = '''\
"""Task manager using Flask and an in-memory dict."""
import json

TASKS = {}


def add_task(task_id, title):
    TASKS[task_id] = {"title": title, "done": False}
    return TASKS[task_id]


def complete(task_id):
    TASKS[task_id]["done"] = True
'''

SAMPLE_B = '''\
"""Task manager built around a Django-style record model and a SQLite backend."""


class TaskRecord:
    def __init__(self, pk, title, status="todo"):
        self.pk = pk
        self.title = title
        self.status = status

    def to_dict(self):
        return {"id": self.pk, "title": self.title, "status": self.status}


class TaskStore:
    def __init__(self):
        self._rows = []

    def insert(self, title):
        row = TaskRecord(len(self._rows) + 1, title)
        self._rows.append(row)
        return row
'''


def test_pairwise_identical_is_zero_and_reuses_basin_axes():
    """Identical samples are zero divergence on every axis — including empty strings."""
    for sample in (SAMPLE_A, "", "   \n  "):
        result = pairwise_divergence(sample, sample)
        assert result == {
            "novelty": 0.0,
            "architecture_divergence": 0.0,
            "structure_divergence": 0.0,
            "composite": 0.0,
        }


def test_pairwise_fields_are_the_basin_primitives():
    """The pairwise axes must be the basin primitives, not a second copy of the math."""
    result = pairwise_divergence(SAMPLE_A, SAMPLE_B)
    a_loc = len(
        [line for line in SAMPLE_A.split("\n") if line.strip() and not line.strip().startswith("#")]
    )
    b_loc = len(
        [line for line in SAMPLE_B.split("\n") if line.strip() and not line.strip().startswith("#")]
    )
    assert result["architecture_divergence"] == basin._architecture_divergence(SAMPLE_A, SAMPLE_B)
    assert result["structure_divergence"] == basin._structure_divergence(
        a_loc, b_loc, SAMPLE_A, SAMPLE_B
    )
    assert result["novelty"] == basin._compute_novelty(SAMPLE_A, SAMPLE_B)
    assert result["composite"] == pytest.approx(
        0.4 * result["architecture_divergence"]
        + 0.3 * result["structure_divergence"]
        + 0.3 * result["novelty"]
    )


def test_identical_portfolio_zero_composite_and_distinct_fraction():
    """Two identical samples: composite 0 and no distinct pair."""
    report = portfolio_diversity([SAMPLE_A, SAMPLE_A])
    assert isinstance(report, PortfolioDiversity)
    assert report.n == 2
    assert report.n_pairs == 1
    assert report.coverage == "full"
    assert report.mean_composite == 0.0
    assert report.max_composite == 0.0
    assert report.distinct_fraction == 0.0


def test_divergent_portfolio_positive_divergence():
    """Two divergent samples produce positive novelty and composite."""
    report = portfolio_diversity([SAMPLE_A, SAMPLE_B])
    assert report.n == 2
    assert report.n_pairs == 1
    assert report.coverage == "full"
    assert report.mean_novelty > 0.0
    assert report.mean_composite > 0.0
    assert report.max_composite > 0.0
    assert report.distinct_fraction == 1.0  # the single pair clears the 0.5 threshold


def test_single_sample_means_are_none():
    """One sample has no pair: every aggregate is unmeasured, and coverage says 'single'."""
    report = portfolio_diversity([SAMPLE_A])
    assert report.n == 1
    assert report.n_pairs == 0
    assert report.coverage == "single"
    assert report.mean_novelty is None
    assert report.mean_architecture_divergence is None
    assert report.mean_structure_divergence is None
    assert report.mean_composite is None
    assert report.max_composite is None
    assert report.distinct_fraction is None


def test_empty_portfolio():
    """No samples: coverage 'empty', no pairs, no fabricated means."""
    report = portfolio_diversity([])
    assert report.n == 0
    assert report.n_pairs == 0
    assert report.coverage == "empty"
    assert report.mean_composite is None
    assert report.max_composite is None
    assert report.distinct_fraction is None


def test_threshold_controls_distinct_fraction():
    """A pair below the distinct threshold is not counted, but composite is still measured."""
    # A near-zero divergence pair (one cosmetic line) is below the default 0.5 threshold.
    nearly = SAMPLE_A.replace('"done": False', '"done": false')
    report = portfolio_diversity([SAMPLE_A, nearly], threshold=0.99)
    assert report.n_pairs == 1
    assert report.mean_composite is not None
    assert report.distinct_fraction == 0.0


def test_to_dict_rounds_but_keeps_none():
    """Serialization rounds measured floats and passes unmeasured ones through as None."""
    full = portfolio_diversity([SAMPLE_A, SAMPLE_B]).to_dict()
    assert set(full) == {
        "n",
        "n_pairs",
        "mean_novelty",
        "mean_architecture_divergence",
        "mean_structure_divergence",
        "mean_composite",
        "max_composite",
        "distinct_fraction",
        "coverage",
    }
    assert full["coverage"] == "full"
    empty = portfolio_diversity([]).to_dict()
    assert empty["mean_composite"] is None
    assert empty["coverage"] == "empty"
