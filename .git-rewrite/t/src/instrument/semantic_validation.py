"""Semantic validation — output-based perturbation classification.

Replaces embedding analysis with three measurable signals:
1. Pragmatic marker analysis (linguistic fingerprinting)
2. AST edit distance (structural code comparison)
3. Tool-call latency pattern (behavioral escape measurement)

All three work on any model's text output and tool-call trace.
No embeddings. No model internals. No API-specific features.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any


# ── Method 1: Pragmatic Marker Analysis ──

EXPLANATORY_MARKERS = [
    "because", "in order to", "this ensures", "since", "otherwise",
    "therefore", "thus", "consequently", "as a result", "the reason",
    "so that", "to prevent", "to ensure", "to avoid", "so we",
]

SURFACE_MARKERS = [
    "rename", "replace", "type", "convert", "string", "syntax",
    "import", "refactor", "restructure", "reorganize", "variable",
    "function name", "class name", "module", "package",
]

CONSTRAINT_MARKERS = [
    "must", "required", "never", "always", "constraint",
    "specification", "requirement", "mandatory", "critical",
    "essential", "necessary", "shall", "should not",
]


@dataclass
class MarkerProfile:
    """Counts of pragmatic markers in model reasoning text."""

    operator: str = ""
    perturbation_class: str = ""
    explanatory_count: int = 0
    surface_count: int = 0
    constraint_count: int = 0
    total_words: int = 0

    @property
    def explanatory_ratio(self) -> float:
        return self.explanatory_count / max(self.total_words, 1) * 1000

    @property
    def surface_ratio(self) -> float:
        return self.surface_count / max(self.total_words, 1) * 1000

    @property
    def constraint_ratio(self) -> float:
        return self.constraint_count / max(self.total_words, 1) * 1000

    @property
    def predicted_class(self) -> str:
        """Predict perturbation class from marker ratios."""
        semantic_score = self.explanatory_ratio + self.constraint_ratio
        manifold_score = self.surface_ratio
        return "semantic" if semantic_score > manifold_score else "manifold"

    @property
    def prediction_matches(self) -> bool:
        return self.predicted_class == self.perturbation_class

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "perturbation_class": self.perturbation_class,
            "explanatory_ratio": round(self.explanatory_ratio, 2),
            "surface_ratio": round(self.surface_ratio, 2),
            "constraint_ratio": round(self.constraint_ratio, 2),
            "predicted_class": self.predicted_class,
            "prediction_matches": self.prediction_matches,
        }


def analyze_markers(
    reasoning_text: str,
    operator: str = "",
    perturbation_class: str = "",
) -> MarkerProfile:
    """Count pragmatic markers in model reasoning text."""
    text_lower = reasoning_text.lower()
    words = text_lower.split()
    profile = MarkerProfile(
        operator=operator,
        perturbation_class=perturbation_class,
        total_words=len(words),
    )
    profile.explanatory_count = sum(1 for m in EXPLANATORY_MARKERS if m in text_lower)
    profile.surface_count = sum(1 for m in SURFACE_MARKERS if m in text_lower)
    profile.constraint_count = sum(1 for m in CONSTRAINT_MARKERS if m in text_lower)
    return profile


def marker_validation_summary(profiles: list[MarkerProfile]) -> str:
    """Generate a markdown table validating perturbation classification."""
    lines = [
        "| Operator | Class | Explanatory | Surface | Constraint | Predicted | Match? |",
        "|----------|-------|-------------|---------|------------|-----------|--------|",
    ]
    semantic_hits = 0
    manifold_hits = 0
    for p in profiles:
        match_str = "✓" if p.prediction_matches else "✗"
        lines.append(
            f"| {p.operator} | {p.perturbation_class} | "
            f"{p.explanatory_ratio:.1f} | {p.surface_ratio:.1f} | "
            f"{p.constraint_ratio:.1f} | {p.predicted_class} | {match_str} |"
        )
        if p.prediction_matches:
            if p.perturbation_class == "semantic":
                semantic_hits += 1
            else:
                manifold_hits += 1

    total = len(profiles)
    if total > 0:
        lines.append(
            f"\n**Accuracy:** {semantic_hits + manifold_hits}/{total} "
            f"({(semantic_hits + manifold_hits) / total:.0%}) "
            f"— validated by output text patterns, not embeddings."
        )
    return "\n".join(lines)


# ── Method 2: AST Edit Distance ──

@dataclass
class ASTProfile:
    """Structural differences between baseline and perturbed code."""

    operator: str = ""
    perturbation_class: str = ""
    node_count_delta: int = 0
    function_count_delta: int = 0
    class_count_delta: int = 0
    if_count_delta: int = 0
    rename_rate: float = 0.0
    structural_divergence: float = 0.0

    @property
    def predicted_class(self) -> str:
        """High structural change + logic additions = semantic."""
        if self.if_count_delta > 0 or self.function_count_delta > 0:
            return "semantic"
        if self.rename_rate > 0.2:
            return "manifold"
        return "semantic" if self.structural_divergence > 0.3 else "manifold"

    @property
    def prediction_matches(self) -> bool:
        return self.predicted_class == self.perturbation_class

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "perturbation_class": self.perturbation_class,
            "node_count_delta": self.node_count_delta,
            "function_count_delta": self.function_count_delta,
            "if_count_delta": self.if_count_delta,
            "rename_rate": round(self.rename_rate, 4),
            "structural_divergence": round(self.structural_divergence, 4),
            "predicted_class": self.predicted_class,
            "prediction_matches": self.prediction_matches,
        }


def analyze_ast(
    baseline_code: str,
    perturbed_code: str,
    operator: str = "",
    perturbation_class: str = "",
) -> ASTProfile | None:
    """Compare AST structures between baseline and perturbed code."""
    try:
        bt = ast.parse(baseline_code)
        pt = ast.parse(perturbed_code)
    except SyntaxError:
        return None

    profile = ASTProfile(operator=operator, perturbation_class=perturbation_class)

    def count_nodes(tree):
        funcs = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        classes = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        ifs = sum(1 for n in ast.walk(tree) if isinstance(n, ast.If))
        total = len(list(ast.walk(tree)))
        return total, funcs, classes, ifs

    bt_total, bt_funcs, bt_classes, bt_ifs = count_nodes(bt)
    pt_total, pt_funcs, pt_classes, pt_ifs = count_nodes(pt)

    profile.node_count_delta = pt_total - bt_total
    profile.function_count_delta = pt_funcs - bt_funcs
    profile.class_count_delta = pt_classes - bt_classes
    profile.if_count_delta = pt_ifs - bt_ifs

    # Rename rate: compare function/variable names
    bt_names = {n.name if isinstance(n, ast.FunctionDef) else n.id
                for n in ast.walk(bt)
                if isinstance(n, (ast.FunctionDef, ast.Name))
                and (isinstance(n, ast.FunctionDef) or isinstance(n, ast.Name))}
    pt_names = {n.name if isinstance(n, ast.FunctionDef) else n.id
                for n in ast.walk(pt)
                if isinstance(n, (ast.FunctionDef, ast.Name))
                and (isinstance(n, ast.FunctionDef) or isinstance(n, ast.Name))}
    all_names = bt_names | pt_names
    if all_names:
        renamed = len(pt_names - bt_names)
        profile.rename_rate = renamed / len(all_names)

    # Structural divergence
    if bt_total > 0:
        profile.structural_divergence = abs(pt_total - bt_total) / bt_total

    return profile


# ── Method 3: Tool-Call Latency Pattern ──

@dataclass
class EscapeProfile:
    """Behavioral escape measurement from tool-call patterns."""

    operator: str = ""
    perturbation_class: str = ""
    tool_calls_before_write: int = 0
    read_tool_calls: int = 0
    total_tool_calls: int = 0
    entrapment: bool = False
    escape_successful: bool = False

    @property
    def exploration_ratio(self) -> float:
        """Read-heavy tool calls before writing = semantic confusion."""
        return self.read_tool_calls / max(self.total_tool_calls, 1)

    @property
    def predicted_class(self) -> str:
        if self.entrapment:
            return "entrapped"
        if self.exploration_ratio > 0.3:
            return "semantic"  # exploring/reading = trying to find missing logic
        return "manifold"  # direct write = surface-level adaptation

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "perturbation_class": self.perturbation_class,
            "tool_calls_before_write": self.tool_calls_before_write,
            "read_tool_calls": self.read_tool_calls,
            "total_tool_calls": self.total_tool_calls,
            "exploration_ratio": round(self.exploration_ratio, 4),
            "entrapment": self.entrapment,
            "escape_successful": self.escape_successful,
            "predicted_class": self.predicted_class,
        }


def analyze_escape(
    tool_calls: list[dict[str, Any]],
    operator: str = "",
    perturbation_class: str = "",
    has_output: bool = True,
) -> EscapeProfile:
    """Analyze tool-call patterns for basin escape behavior."""
    profile = EscapeProfile(
        operator=operator,
        perturbation_class=perturbation_class,
        total_tool_calls=len(tool_calls),
    )

    # Count reads before writes
    write_seen = False
    for tc in tool_calls:
        tool = tc.get("tool", "")
        if not write_seen:
            if tool in ("write", "edit", "bash"):
                write_seen = True
            else:
                profile.tool_calls_before_write += 1
        if tool in ("read", "grep", "ls", "glob"):
            profile.read_tool_calls += 1

    # Entrapment: 0 tool calls = stuck in text-explanation basin
    profile.entrapment = profile.total_tool_calls == 0
    profile.escape_successful = has_output and not profile.entrapment

    return profile
