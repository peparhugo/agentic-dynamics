"""Tests for the portfolio-diversity instrument (design B3).

Contract under test (frozen after four adversarial-review rounds):
  * parseable Python is scored, with comments/whitespace/formatting canonicalized via AST;
  * the ``run.py`` multi-file ``solution_code`` blob is split and parsed per file;
  * any non-parseable source is UNSCORED — null axes, ``scored: False`` — never a guessed
    number (no false zeros, no cosmetic inflation);
  * null-not-zero: aggregates are ``None`` when there is no scored pair, unsupported pairs are
    reported via ``unsupported_pairs``/``unsupported_fraction``.
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


def _unsupported_reason(result: dict) -> str:
    assert result["scored"] is False
    assert result["composite"] is None
    return result["reason"]


def test_pairwise_identical_is_zero_and_reuses_basin_axes():
    """Identical samples are zero divergence on every axis — including empty strings."""
    for sample in (SAMPLE_A, "", "   \n  "):
        result = pairwise_divergence(sample, sample)
        assert result["scored"] is True
        assert result["composite"] == 0.0
        assert result["novelty"] == 0.0
        assert result["architecture_divergence"] == 0.0
        assert result["structure_divergence"] == 0.0


def test_pairwise_fields_are_the_basin_primitives_on_canonical_python():
    """The pairwise axes must be the basin primitives on the CANONICAL sources, not a second
    copy of the math."""
    canonical_a = diversity._normalize_source(SAMPLE_A)
    canonical_b = diversity._normalize_source(SAMPLE_B)
    assert canonical_a is not None and canonical_b is not None
    result = pairwise_divergence(SAMPLE_A, SAMPLE_B)
    assert result["scored"] is True
    assert result["architecture_divergence"] == basin._architecture_divergence(canonical_a, canonical_b)
    assert result["structure_divergence"] == basin._structure_divergence(
        diversity._count_loc(canonical_a),
        diversity._count_loc(canonical_b),
        canonical_a,
        canonical_b,
    )
    assert result["novelty"] == basin._compute_novelty(canonical_a, canonical_b)
    assert result["composite"] == pytest.approx(
        0.4 * result["architecture_divergence"]
        + 0.3 * result["structure_divergence"]
        + 0.3 * result["novelty"]
    )


def test_python_cosmetic_edits_score_exactly_zero():
    """Comments, blank lines, and reformatting are canonicalized away (scored, zero)."""
    base = "def f():\n    return 1\n"
    for variant in (
        base + "\n\n   \n",
        base + "# a comment\n",
        "def f():\n    return 1  # inline\n",
        "def f():\n\n    return 1\n",
    ):
        result = pairwise_divergence(base, variant)
        assert result["scored"] is True, result
        assert result["composite"] == 0.0, (variant, result)
    assert pairwise_divergence("", " \n\t\n")["composite"] == 0.0


def test_python_semantic_change_is_positive():
    result = pairwise_divergence("def f():\n    return 1\n", "def f():\n    return 2\n")
    assert result["scored"] is True
    assert result["composite"] > 0.0


def test_multi_file_solution_blob_is_scored_and_normalized():
    """The run.py ``solution_code`` blob (per-file headers) is supported: header-free bodies
    are parsed per file, so a cosmetic edit reads zero and a semantic edit reads positive."""
    blob_v1 = "# === a.py ===\nprint('a')\n# === sub/b.py ===\nx = 1\n"
    blob_v2_cosmetic = "# === a.py ===\nprint('a')\n# === sub/b.py ===\nx = 1  # note\n\n"
    blob_v2_semantic = "# === a.py ===\nprint('a')\n# === sub/b.py ===\nx = 2\n"
    assert pairwise_divergence(blob_v1, blob_v2_cosmetic)["composite"] == 0.0
    assert pairwise_divergence(blob_v1, blob_v2_semantic)["composite"] > 0.0


def test_non_python_is_unscored_never_a_guessed_number():
    """Unsupported sources are null, not a false zero and not cosmetic inflation."""
    js = "function f(){ return 1; }"
    c = "int f(void){ return 1; }"
    assert _unsupported_reason(pairwise_divergence(js, js + " // cosmetic")) == "unsupported_source"
    assert _unsupported_reason(pairwise_divergence(c, "int f(void) { return 1; }")) == "unsupported_source"
    assert _unsupported_reason(
        pairwise_divergence("#define V 1\nint f(){ return V; }", "#define V 2\nint f(){ return V; }")
    ) == "unsupported_source"


def test_identical_portfolio_zero_composite_and_distinct_fraction():
    report = portfolio_diversity([SAMPLE_A, SAMPLE_A])
    assert isinstance(report, PortfolioDiversity)
    assert report.n == 2
    assert report.n_pairs == 1
    assert report.n_scored_pairs == 1
    assert report.unsupported_pairs == 0
    assert report.coverage == "full"
    assert report.unsupported_fraction == 0.0
    assert report.mean_composite == 0.0
    assert report.max_composite == 0.0
    assert report.distinct_fraction == 0.0


def test_divergent_portfolio_positive_divergence():
    report = portfolio_diversity([SAMPLE_A, SAMPLE_B])
    assert report.n_pairs == 1
    assert report.coverage == "full"
    assert report.mean_novelty > 0.0
    assert report.mean_composite > 0.0
    assert report.max_composite > 0.0
    assert report.distinct_fraction == 1.0


def test_unsupported_pair_is_reported_not_averaged():
    """A non-Python sample's pair is counted as unsupported; scored aggregates stay honest."""
    report = portfolio_diversity([SAMPLE_A, SAMPLE_B, "function f(){ return 1; }"])
    assert report.n == 3
    assert report.n_pairs == 3
    assert report.n_scored_pairs == 1
    assert report.unsupported_pairs == 2
    assert report.unsupported_fraction == pytest.approx(2 / 3)
    scored_only = portfolio_diversity([SAMPLE_A, SAMPLE_B])
    assert report.mean_composite == pytest.approx(scored_only.mean_composite)


def test_all_unsupported_portfolio_is_null_not_zero():
    report = portfolio_diversity(["int f(){ return 1; }", "int f(){ return 2; }"])
    assert report.n_pairs == 1
    assert report.n_scored_pairs == 0
    assert report.unsupported_pairs == 1
    assert report.unsupported_fraction == 1.0
    assert report.mean_composite is None
    assert report.max_composite is None
    assert report.distinct_fraction is None


def test_single_sample_means_are_none():
    report = portfolio_diversity([SAMPLE_A])
    assert report.n == 1
    assert report.n_pairs == 0
    assert report.n_scored_pairs == 0
    assert report.coverage == "single"
    assert report.unsupported_fraction is None
    assert report.mean_novelty is None
    assert report.mean_architecture_divergence is None
    assert report.mean_structure_divergence is None
    assert report.mean_composite is None
    assert report.max_composite is None
    assert report.distinct_fraction is None


def test_empty_portfolio():
    report = portfolio_diversity([])
    assert report.n == 0
    assert report.n_pairs == 0
    assert report.coverage == "empty"
    assert report.unsupported_fraction is None
    assert report.mean_composite is None
    assert report.max_composite is None
    assert report.distinct_fraction is None


def test_threshold_controls_distinct_fraction():
    """A scored pair below the distinct threshold is not counted, but composite is measured."""
    nearly = SAMPLE_A.replace('"done": False', '"done": false')
    report = portfolio_diversity([SAMPLE_A, nearly], threshold=0.99)
    assert report.n_pairs == 1
    assert report.mean_composite is not None
    assert report.distinct_fraction == 0.0


def test_to_dict_shape_and_none_passthrough():
    full = portfolio_diversity([SAMPLE_A, SAMPLE_B]).to_dict()
    assert set(full) == {
        "n",
        "n_pairs",
        "n_scored_pairs",
        "unsupported_pairs",
        "coverage",
        "unsupported_fraction",
        "mean_novelty",
        "mean_architecture_divergence",
        "mean_structure_divergence",
        "mean_composite",
        "max_composite",
        "distinct_fraction",
    }
    assert full["coverage"] == "full"
    assert full["unsupported_fraction"] == 0.0
    empty = portfolio_diversity([]).to_dict()
    assert empty["mean_composite"] is None
    assert empty["coverage"] == "empty"
