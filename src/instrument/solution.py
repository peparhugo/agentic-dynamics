"""Solution quality measurement — what the model actually built.

Measures the product of reasoning, not just the reasoning process.
Evaluates code quality, constraint satisfaction, correctness, and
structural novelty compared to baseline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SolutionMetrics:
    """Quality metrics for a generated solution.

    Captures four dimensions:
    1. Correctness — does it work?
    2. Constraint satisfaction — does it meet requirements?
    3. Code quality — how elegant/efficient is the implementation?
    4. Novelty — how structurally different from baseline?
    """

    # Correctness
    tests_passed: int = 0
    tests_total: int = 0
    correctness_score: float = 0.0

    # Constraint satisfaction
    constraints_met: int = 0
    constraints_total: int = 0
    constraint_score: float = 0.0

    # Code quality
    lines_of_code: int = 0
    cyclomatic_complexity: float = 0.0
    comment_ratio: float = 0.0
    code_quality_score: float = 0.0

    # Novelty vs baseline
    novelty_score: float = 0.0

    # Composite
    composite_score: float = 0.0

    # SonarQube static analysis (optional — only when sonar-scanner available)
    sonar_analyzed: bool = False
    sonar_bugs: int = 0
    sonar_vulnerabilities: int = 0
    sonar_code_smells: int = 0
    sonar_cognitive_complexity: int = 0
    sonar_duplicated_lines_density: float = 0.0
    sonar_ncloc: int = 0
    sonar_maintainability_rating: str = ""
    sonar_reliability_rating: str = ""
    sonar_security_rating: str = ""
    sonar_quality_gate: str = ""
    sonar_quality_score: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "correctness_score": round(self.correctness_score, 4),
            "constraints_met": self.constraints_met,
            "constraints_total": self.constraints_total,
            "constraint_score": round(self.constraint_score, 4),
            "lines_of_code": self.lines_of_code,
            "cyclomatic_complexity": round(self.cyclomatic_complexity, 4),
            "code_quality_score": round(self.code_quality_score, 4),
            "novelty_score": round(self.novelty_score, 4),
            "composite_score": round(self.composite_score, 4),
            "sonar_analyzed": self.sonar_analyzed,
            "sonar_bugs": self.sonar_bugs,
            "sonar_vulnerabilities": self.sonar_vulnerabilities,
            "sonar_code_smells": self.sonar_code_smells,
            "sonar_cognitive_complexity": self.sonar_cognitive_complexity,
            "sonar_duplicated_lines_density": round(self.sonar_duplicated_lines_density, 1),
            "sonar_ncloc": self.sonar_ncloc,
            "sonar_maintainability_rating": self.sonar_maintainability_rating,
            "sonar_reliability_rating": self.sonar_reliability_rating,
            "sonar_security_rating": self.sonar_security_rating,
            "sonar_quality_gate": self.sonar_quality_gate,
            "sonar_quality_score": round(self.sonar_quality_score, 4),
        }


def evaluate_solution(
    code: str,
    constraints: list[str],
    test_results: dict[str, bool] | None = None,
    baseline_code: str = "",
    code_files: dict[str, str] | None = None,
) -> SolutionMetrics:
    """Evaluate a generated solution across all quality dimensions.

    Args:
        code: The generated implementation code or model response.
        constraints: List of constraint descriptions to check.
        test_results: Dict of test_name -> passed for correctness.
        baseline_code: Baseline implementation for novelty comparison.
        code_files: Dict of filename -> content for generated source files.

    Returns:
        SolutionMetrics with quality scores.
    """
    m = SolutionMetrics()

    # Combine response + all generated files for richer analysis
    full_text = code
    if code_files:
        full_text += "\n" + "\n".join(code_files.values())

    # ── Correctness ──
    if test_results:
        m.tests_total = len(test_results)
        m.tests_passed = sum(1 for v in test_results.values() if v)
        m.correctness_score = m.tests_passed / max(m.tests_total, 1)
    else:
        m.correctness_score = _estimate_correctness(full_text)

    # ── Constraint satisfaction ──
    m.constraints_total = len(constraints)
    m.constraints_met = sum(1 for c in constraints if _check_constraint(full_text, c, code_files))
    m.constraint_score = m.constraints_met / max(m.constraints_total, 1)

    # ── Code quality ──
    lines = [l for l in full_text.split("\n") if l.strip() and not l.strip().startswith("#")]
    m.lines_of_code = len(lines)
    m.cyclomatic_complexity = _estimate_complexity(full_text)
    m.comment_ratio = _comment_ratio(full_text)
    # Quality: lower complexity and fewer lines = higher quality (with minimum bounds)
    complexity_bonus = max(0, 1.0 - m.cyclomatic_complexity / 30.0)
    density_bonus = min(1.0, 200.0 / max(m.lines_of_code, 1))
    m.code_quality_score = (complexity_bonus + density_bonus) / 2.0

    # ── Novelty vs baseline ──
    if baseline_code:
        m.novelty_score = _compute_novelty(baseline_code, full_text)
    else:
        m.novelty_score = 0.5

    # ── Composite ──
    if m.sonar_analyzed:
        m.composite_score = (
            0.30 * m.correctness_score
            + 0.25 * m.constraint_score
            + 0.20 * m.sonar_quality_score
            + 0.15 * m.code_quality_score
            + 0.10 * m.novelty_score
        )
    else:
        m.composite_score = (
            0.35 * m.correctness_score
            + 0.30 * m.constraint_score
            + 0.20 * m.code_quality_score
            + 0.15 * m.novelty_score
        )

    return m


def _estimate_correctness(code: str) -> float:
    """Estimate correctness from code structure when tests unavailable."""
    signals = 0
    # Has function/class definitions
    if "def " in code or "class " in code or "func " in code or "fn " in code:
        signals += 1
    # Has imports
    if "import " in code or "from " in code or "require(" in code:
        signals += 1
    # Has error handling
    if "try" in code or "except" in code or "catch" in code or "error" in code.lower():
        signals += 1
    # Has return/output
    if "return " in code or "print(" in code or "console." in code or "fmt." in code:
        signals += 1
    # Non-trivial length
    if len(code) > 200:
        signals += 1
    return min(signals / 5.0, 1.0)


def _check_constraint(code: str, constraint: str, code_files: dict[str, str] | None = None) -> bool:
    """Check if a constraint is approximately satisfied in the code.

    Uses domain-specific keyword expansions (shared with constraint_detection.py)
    and checks both response text and generated source files.
    """
    from .constraint_detection import _constraint_keywords, _is_code_context
    keywords = _constraint_keywords(constraint)
    if not keywords:
        keywords = [w for w in constraint.lower().split() if len(w) > 3]

    # Search in combined text: response + all code files
    search_text = code.lower()
    if code_files:
        search_text += "\n" + "\n".join(v.lower() for v in code_files.values())

    matches = sum(1 for kw in keywords if kw in search_text)
    threshold = max(1, int(len(keywords) * 0.35))
    return matches >= threshold


def _estimate_complexity(code: str) -> float:
    """Estimate cyclomatic complexity from control flow keywords."""
    indicators = [
        "if ", "elif ", "else:", "for ", "while ", "case ", "switch",
        "&&", "||", "and ", "or ", "except", "catch", "match ",
    ]
    count = sum(code.count(i) for i in indicators)
    return float(count + 1)


def _comment_ratio(code: str) -> float:
    """Ratio of comment lines to total lines."""
    lines = code.split("\n")
    if not lines:
        return 0.0
    comment_lines = sum(
        1 for l in lines
        if l.strip().startswith("#")
        or l.strip().startswith("//")
        or l.strip().startswith("--")
        or l.strip().startswith("/*")
        or l.strip().startswith("*")
    )
    return comment_lines / len(lines)


def _compute_novelty(baseline: str, perturbed: str) -> float:
    """Compute structural novelty between two code samples."""
    # Trigram-based Jaccard distance
    def trigrams(text: str) -> set[str]:
        t = text.lower()
        return {t[i:i + 5] for i in range(len(t) - 4)}

    bt = trigrams(baseline)
    pt = trigrams(perturbed)
    union = len(bt | pt)
    intersection = len(bt & pt)
    if union == 0:
        return 0.5
    return 1.0 - (intersection / union)
