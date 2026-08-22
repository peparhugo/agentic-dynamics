"""Measurement-coverage guard (measurement-contribution closure, m2).

``docs/review/measurement_contribution_review.md`` P1/P2 found the same defect in every
canonical producer under different names: an unavailable measurement was coerced to
numeric zero, so "not measured" became "measured as 0" and diluted published averages
(``or 0`` cost defaults, ``sum(costs)/len(all_cells)``, ``if cost > 0`` with no coverage).

The m2 invariant is: **an unavailable measurement is ``null`` with zero coverage — never
numeric zero — and a published average never treats missing cost as $0.** This module
guards that invariant three ways:

1. the shared :class:`MeasurementCoverage` primitive behaves as specified (``value`` is
   ``None`` exactly when ``n_available == 0``);
2. the cost helpers reject a missing/zero cost as "captured";
3. a *source-level* grep over every canonical producer fails on any remaining
   zero-coercion of a cost / optional-score field — the class is unrepresentable, not just
   fixed in one place.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agentic_dynamics.reporting.lab_manifest import load_lab_manifest
from agentic_dynamics.reporting.measurement_coverage import (
    MeasurementCoverage,
    cost_captured,
    cost_coverage,
)

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "experiments" / "results"

#: The fields the m2 invariant governs — a cost or an optional score whose *absence* is
#: "not measured", never "measured as zero". (Counts — tokens, reads, lines, tests — are
#: deliberately absent: 0 is a real value there.)
_OPTIONAL_FIELDS = (
    "total_cost",
    "cost_usd",
    "correctness_score",
    "constraint_score",
    "code_quality_score",
    "novelty_score",
    "composite_score",
    "escape_score",
    "cyclomatic_complexity",
    "cache_hit_rate",
    "total_context_tokens",
    "total_tokens",
)

#: `get("field", 0) or 0` / `get("field", 0.0) or 0.0` for an optional field — the exact
#: missing→zero coercion the review named, in one regex tolerant of whitespace.
_ZERO_COERCION_RE = re.compile(
    r'get\(\s*"(?:' + "|".join(_OPTIONAL_FIELDS) + r')"\s*,\s*0(?:\.0)?\s*\)\s*or\s*0(?:\.0)?'
)


def _canonical_producers() -> list[str]:
    """The eight canonical lab scripts + ``build_data.py`` + ``sync_data.py``.

    ``sync_data`` writes the story parquet (a published cost/correctness surface), so it is
    a canonical producer too — the m5 adversarial hunt found it still carried the
    ``get("total_cost", 0) or 0`` / ``cost > 0`` class, so it is guarded here now.
    """
    labs = [e.script for e in load_lab_manifest() if e.publication_eligible]
    return [f"scripts/{s}" for s in sorted(labs)] + [
        "scripts/build_data.py",
        "scripts/sync_data.py",
    ]


# ---------------------------------------------------------------------------
# 1. The primitive behaves as the m2 SHAPE specifies
# ---------------------------------------------------------------------------


def test_measurement_coverage_value_is_null_when_none_available():
    """``value`` is ``None`` — never 0 — when no record measured the value."""
    mc = MeasurementCoverage.over([], n_total=3)
    assert mc.value is None
    assert mc.n_available == 0
    assert mc.n_total == 3
    assert mc.coverage == 0.0
    assert not mc.measured


def test_measurement_coverage_over_computes_mean_and_coverage():
    """The mean is over available values only, and coverage is available/total."""
    mc = MeasurementCoverage.over([2.0, 4.0], n_total=5, round_value=3)
    assert mc.value == 3.0
    assert mc.n_available == 2
    assert mc.n_total == 5
    assert mc.coverage == 0.4


def test_measurement_coverage_to_dict_shape():
    """The JSON shape is exactly ``{value, n_available, n_total, coverage}``."""
    mc = MeasurementCoverage.over([1.0, 3.0], n_total=4)
    assert mc.to_dict() == {"value": 2.0, "n_available": 2, "n_total": 4, "coverage": 0.5}


def test_cost_captured_rejects_missing_and_zero():
    """A cost is captured only when it is a finite, positive real number."""
    assert cost_captured(1.0)
    assert cost_captured(0.0001)
    assert not cost_captured(0.0)
    assert not cost_captured(0)
    assert not cost_captured(None)
    assert not cost_captured("2.0")
    assert not cost_captured(True)


def test_cost_coverage_shape_and_captured_only_mean():
    """``cost_coverage`` publishes the five fields and averages captured costs only."""
    stats = cost_coverage([2.0, 4.0, 0.0, None], n_total=4)
    assert stats["avg_captured_cost"] == round(3.0, 6)
    assert stats["total_captured_cost"] == round(6.0, 6)
    assert stats["cost_captured_records"] == 2
    assert stats["total_records"] == 4
    assert stats["cost_coverage"] == 0.5


def test_cost_coverage_is_null_when_nothing_captured():
    """A population with no captured cost publishes ``avg_captured_cost: null``."""
    stats = cost_coverage([0.0, None], n_total=2)
    assert stats["avg_captured_cost"] is None
    assert stats["cost_captured_records"] == 0
    assert stats["cost_coverage"] == 0.0


# ---------------------------------------------------------------------------
# 2. The zero-coercion class is unrepresentable (source-level grep)
# ---------------------------------------------------------------------------


def test_canonical_producers_have_no_zero_coercion():
    """No canonical producer coerces a missing cost/optional score to numeric zero.

    This is a mutation-style guard: reintroducing ``get("total_cost", 0) or 0`` (or any
    sibling field) in any published producer fails here, so the class cannot silently
    return after this phase.
    """
    violations: list[str] = []
    for script in _canonical_producers():
        path = ROOT / script
        if not path.exists():  # pragma: no cover - files are committed
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _ZERO_COERCION_RE.search(line):
                violations.append(f"{script}:{lineno}: {line.strip()}")
    assert not violations, (
        "zero-coercion of a cost/optional field found in a canonical producer:\n"
        + "\n".join(violations)
    )


def test_canonical_producers_use_the_shared_primitive():
    """Every cost-computing canonical lab imports the shared coverage primitive."""
    cost_labs = (
        "scripts/lab_condition_effects.py",
        "scripts/lab_cache_economics.py",
        "scripts/lab_story_arc.py",
        "scripts/lab_story_review.py",
        "scripts/lab_quality_frontier.py",
        "scripts/lab_verification_frontier.py",
        "scripts/build_data.py",
    )
    for script in cost_labs:
        src = (ROOT / script).read_text(encoding="utf-8")
        assert "measurement_coverage" in src, (
            f"{script} does not import the shared measurement-coverage primitive"
        )


# ---------------------------------------------------------------------------
# 3. Producer-level: a lab with n_available == 0 publishes value null
# ---------------------------------------------------------------------------


def test_quality_frontier_optional_metric_null_when_unavailable():
    """A quality-frontier model with no measured score publishes ``value: null``.

    The ``*_coverage`` dicts follow :class:`MeasurementCoverage`: when a model had no cell
    with the metric, ``value`` is ``None`` and ``n_available`` is 0 (never an averaged 0).
    """
    path = RESULTS_DIR / "lab_quality_frontier.json"
    if not path.exists():  # pragma: no cover
        pytest.skip("lab_quality_frontier not run")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for model in payload["models"]:
        cov = model["code_quality_score_coverage"]
        assert cov["n_available"] <= cov["n_total"]
        if model["code_quality_score"] is None:
            assert cov["value"] is None
            assert cov["n_available"] == 0
            assert cov["coverage"] == 0.0
        else:
            assert cov["value"] is not None
            assert cov["n_available"] > 0
        # cost coverage is published on every model, and its value agrees with avg_cost.
        assert model["avg_cost"] == model["avg_captured_cost"]
        assert model["cost_captured_records"] <= model["total_records"]
