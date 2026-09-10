"""Tests for the portfolio-diversity instrument (design B3).

The ladder measures how varied a *portfolio* of independent attempts is, so the instrument's
contract must be pinned from both ends: identical samples score zero, genuinely divergent
samples score positive, and a portfolio too small to have a pair reports ``None`` rather than
a fabricated zero (null-not-zero). These are pure-unit tests over source strings.
"""

import pytest

from agentic_dynamics.measurement import basin, diversity
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
    """The pairwise axes must be the basin primitives on the NORMALIZED sources, not a second
    copy of the math (normalization strips cosmetic-only edits — the g5 F3 finding)."""
    normalized_a = diversity._normalize_source(SAMPLE_A)
    normalized_b = diversity._normalize_source(SAMPLE_B)
    result = pairwise_divergence(SAMPLE_A, SAMPLE_B)
    a_loc = len(
        [
            line
            for line in normalized_a.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
    )
    b_loc = len(
        [
            line
            for line in normalized_b.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
    )
    assert result["architecture_divergence"] == basin._architecture_divergence(
        normalized_a, normalized_b
    )
    assert result["structure_divergence"] == basin._structure_divergence(
        a_loc, b_loc, normalized_a, normalized_b
    )
    assert result["novelty"] == basin._compute_novelty(normalized_a, normalized_b)
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


def test_cosmetic_edits_normalize_to_zero():
    """The g5 F3 finding: whitespace/comment-only pairs must not read as divergence."""
    base = "def f():\n    return 1\n"
    assert pairwise_divergence(base, base + "\n\n   \n")["composite"] == 0.0
    assert pairwise_divergence(base, "def f():\n    return 1\n# a comment\n")["composite"] == 0.0
    assert pairwise_divergence("def f():\n    return 1  # inline\n", base)["composite"] == 0.0
    assert pairwise_divergence("", " \n\t\n")["composite"] == 0.0


def test_cosmetic_portfolio_has_zero_diversity():
    variants = [
        "def f():\n    return 1\n",
        "def f():\n    return 1\n# c1\n",
        "def f():\n\n    return 1  # c2\n",
    ]
    d = portfolio_diversity(variants)
    assert d.coverage == "full"
    assert d.mean_composite == 0.0
    assert d.distinct_fraction == 0.0


def test_genuine_change_remains_positive():
    assert pairwise_divergence(
        "def f():\n    return 1\n", "def g():\n    return 2\n"
    )["composite"] > 0.0


def test_inline_and_block_comments_in_non_python_normalize_to_zero():
    """The g5 round-2 F1 finding: inline ``//`` and C block comments must not read as churn."""
    js = "function f(){ return 1; }"
    assert pairwise_divergence(js, js + " // cosmetic")["composite"] == 0.0
    c = "int f() { return 1; }"
    assert pairwise_divergence(c, "/* cosmetic */\n" + c)["composite"] == 0.0
    assert pairwise_divergence(c, c + " /* trailing */")["composite"] == 0.0
    # String contents are preserved, so a URL is not mistaken for a comment (JS sample —
    # in Python a trailing "//" would be floor-division, not a comment; the AST path owns it).
    from agentic_dynamics.measurement.diversity import _strip_comments

    assert _strip_comments('var u = "http://x"; // note') == 'var u = "http://x"; '
    assert pairwise_divergence(
        'var u = "http://x";', 'var u = "http://x"; // note'
    )["composite"] == 0.0
