"""Finding-economics closure guards (docs/reviews/finding_economics_review.md P0).

The review found the last unconverted data path — the single-task FINDING corpus — still
treated uncaptured economics as measured zeroes: ``build_data._finding_entry_from_run``
coerced ``cost_usd``/``energy_j``/``escape_score``/… to ``0.0`` via ``float(x or 0.0)``, and
``correctness_per_dollar = correctness / max(cost, 1e-9)`` turned an uncaptured cost into an
enormous positive economic score (a free perfect run).

This module guards the closure three ways, mirroring the m2 lesson (guard STRUCTURE, not a
string pattern):

1. **structural** — the finding adapter routes the economic/optional fields through the shared
   ``MeasurementCoverage``/``cost_coverage`` primitives (import + usage), never an inline
   ``or 0.0``;
2. **mutation** — reintroducing ``float(run.get("cost_usd") or 0.0)`` (or any sibling field,
   or a ``max(cost, 1e-9)`` ratio denominator) fails;
3. **data** — the published ``data.js`` has no finding-model row with ``avg_cost == 0.0``
   alongside ``avg_correctness == 1.0``, and no ``correctness_per_dollar > 1e7``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
BUILD_DATA = ROOT / "scripts" / "build_data.py"
ROUTING = ROOT / "src" / "agentic_dynamics" / "control" / "routing.py"
DATA_JS = ROOT / "apps" / "website" / "data.js"

#: The finding-corpus economic/optional fields whose *absence* is "not measured" (null), never
#: "measured as zero" (docs/reviews/finding_economics_review.md P0).
_FINDING_OPTIONAL_FIELDS = (
    "cost_usd",
    "energy_j",
    "correctness",
    "escape_score",
    "architecture_divergence",
    "composite_score",
    "quality_per_joule",
    "thinking_ratio",
)

#: ``float(run.get("<field>") or 0.0)`` — the exact expression variant the review cited as the
#: gap the narrow zero-coercion guard missed.
_FLOAT_OR_ZERO_RE = re.compile(
    r'float\(\s*run\.get\(\s*"(?:'
    + "|".join(_FINDING_OPTIONAL_FIELDS)
    + r')"\s*\)\s*or\s*0\.0\s*\)'
)

#: Any ``max(<cost>, 1e-9)`` / ``max(<cost>, 1e-6)`` ratio-denominator fudge (the superspike
#: source), and any ``get("field", 0)`` default on an optional field.
_RATIO_FUDGE_RE = re.compile(r"max\([^)]*1e-9|max\([^)]*1e-6")


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. structural — the finding adapter routes optional fields through the primitive
# ---------------------------------------------------------------------------


def test_finding_adapter_imports_the_coverage_primitives():
    """build_data imports MeasurementCoverage and cost_coverage/cost_captured (m2)."""
    src = _read_source(BUILD_DATA)
    assert "from agentic_dynamics.reporting.measurement_coverage import" in src
    assert "MeasurementCoverage" in src
    assert "cost_coverage" in src
    assert "cost_captured" in src


def test_finding_adapter_uses_cost_coverage_for_finding_fields():
    """The finding aggregators delegate to ``cost_coverage`` (the shared cost tuple).

    The model, operator and class aggregations must call the shared primitive — not a local
    ``sum(costs) / n`` over zero-filled lists — so the captured-cost denominator policy is one
    place.
    """
    src = _read_source(BUILD_DATA)
    # At least the three finding aggregation sites route cost through cost_coverage.
    assert src.count("cost_coverage(") >= 3, (
        "the finding model/operator/class aggregators must delegate cost to cost_coverage"
    )


def test_finding_adapter_uses_measurement_coverage_for_optional_fields():
    """The finding aggregators emit ``{value, n_available, n_total, coverage}`` via the shared
    ``_coverage_dict`` → ``MeasurementCoverage`` path for the optional scores."""
    src = _read_source(BUILD_DATA)
    assert "_coverage_dict" in src
    # _coverage_dict is the thin list-based wrapper over MeasurementCoverage (the shared primitive).
    assert "MeasurementCoverage.over(" in src or "MeasurementCoverage(" in src


# ---------------------------------------------------------------------------
# 2. mutation — the zero-coercion class is unrepresentable
# ---------------------------------------------------------------------------


def test_finding_adapter_rejects_float_or_zero_reintroduction():
    """Reintroducing ``float(run.get("cost_usd") or 0.0)`` (or any sibling) fails.

    This is the mutation guard: the exact expression variant the review named is asserted
    absent from build_data, so the class cannot silently return.
    """
    src = _read_source(BUILD_DATA)
    for lineno, line in enumerate(src.splitlines(), 1):
        assert not _FLOAT_OR_ZERO_RE.search(line), (
            f"build_data.py:{lineno}: zero-coercion reintroduced: {line.strip()}"
        )


def test_finding_adapter_rejects_ratio_denominator_fudge():
    """Reintroducing a ``max(cost, 1e-9)``/``1e-6`` denominator (the superspike source) fails."""
    src = _read_source(BUILD_DATA)
    for lineno, line in enumerate(src.splitlines(), 1):
        assert not _RATIO_FUDGE_RE.search(line), (
            f"build_data.py:{lineno}: ratio-denominator fudge reintroduced: {line.strip()}"
        )


def test_routing_rejects_zero_cost_default():
    """routing.py must not default a missing cost/correctness to zero (free-execution model)."""
    src = _read_source(ROUTING)
    assert "cost_captured" in src, "routing must use the shared cost_captured primitive"
    for lineno, line in enumerate(src.splitlines(), 1):
        assert not _RATIO_FUDGE_RE.search(line), (
            f"routing.py:{lineno}: ratio-denominator fudge reintroduced: {line.strip()}"
        )
        # No `e.get("cost", 0)` / `e.get("correctness", 0)` zero-default on the optional fields.
        if re.search(r'get\("(?:cost|correctness)",\s*0\)', line):
            pytest.fail(f"routing.py:{lineno}: zero-default reintroduced: {line.strip()}")


# ---------------------------------------------------------------------------
# 3. data — the published data.js honors the invariant
# ---------------------------------------------------------------------------


def _load_data_js() -> dict:
    if not DATA_JS.exists():  # pragma: no cover - generated file, present in CI
        pytest.skip("apps/website/data.js not generated")
    text = _read_source(DATA_JS)
    return json.loads(text[text.index("{") : text.rindex("}") + 1])


def test_data_js_has_no_free_perfect_finding_model():
    """No finding-model row publishes ``avg_cost == 0.0`` alongside ``avg_correctness == 1.0``.

    The review's concrete case (a free perfect run: correctness 1.0 / cost 0.0) must be
    unrepresentable: a zero/uncaptured cost is never ``avg_cost 0.0`` with full correctness.
    """
    data = _load_data_js()
    models = data.get("perturbation_models") or []
    violations = []
    for m in models:
        correctness = None
        if isinstance(m.get("correctness_coverage"), dict):
            correctness = m["correctness_coverage"].get("value")
        elif m.get("avg_correctness") is not None:
            correctness = m.get("avg_correctness")
        if m.get("avg_cost") == 0.0 and correctness == 1.0:
            violations.append(m.get("id") or m.get("label"))
    assert not violations, (
        "free-perfect finding model (avg_cost 0.0 + correctness 1.0): " + ", ".join(violations)
    )


def test_data_js_finding_models_have_no_superspiked_correctness_per_dollar():
    """No finding-model row publishes ``correctness_per_dollar > 1e7`` (the 1e-9 fudge)."""
    data = _load_data_js()
    models = data.get("perturbation_models") or []
    violations = []
    for m in models:
        cpd = m.get("correctness_per_dollar")
        if isinstance(cpd, (int, float)) and cpd > 1e7:
            violations.append(f"{m.get('id') or m.get('label')}={cpd}")
    assert not violations, "superspiked correctness_per_dollar: " + ", ".join(violations)


def test_data_js_finding_operator_and_class_aggregations_have_no_free_perfect_row():
    """The operator/class aggregations (the review's Claude arms) also carry no free-perfect row."""
    data = _load_data_js()

    def _scan(container: dict):
        bad = []
        for name, group in container.items():
            if not isinstance(group, dict):
                continue
            for model, row in group.items():
                if not isinstance(row, dict):
                    continue
                if row.get("avg_cost") == 0.0 and row.get("avg_correctness") == 1.0:
                    bad.append(f"{name}/{model}")
        return bad

    problems = []
    for section in ("operator_comparison", "perturbation_class_breakdown"):
        problems.extend(_scan(data.get(section) or {}))
    # operator_comparison nests under models: {op: {perturbation_class, models: {label: row}}}
    for op, group in (data.get("operator_comparison") or {}).items():
        for model, row in (group.get("models") or {}).items():
            if row.get("avg_cost") == 0.0 and row.get("avg_correctness") == 1.0:
                problems.append(f"operator_comparison/{op}/{model}")
    assert not problems, "free-perfect aggregation rows: " + ", ".join(problems)
