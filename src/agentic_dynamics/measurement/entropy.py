"""Architectural entropy — information-theoretic measure of codebase order.

Quantifies how much "surprise" or disorder exists in the codebase structure.
Lower entropy = more ordered, consistent, predictable.
Higher entropy = more disorder, inconsistency, unpredictability.

Five dimensions:
  1. Function length distribution
  2. Module (file) size distribution
  3. Import graph edge distribution
  4. Naming convention consistency
  5. File-to-responsibility mapping

ΔH = H(after) - H(before): Positive = more disorder introduced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agentic_dynamics.core.language import (
    LanguageProfile,
    _should_skip,
    collect_functions,
    detect_language,
    parse_codebase,
)

# ── Data Structures ────────────────────────────────────────────

@dataclass
class EntropyProfile:
    """Architectural entropy across five dimensions."""

    # Dimension 1: Function length distribution
    function_length_entropy: float = 0.0
    function_length_histogram: dict[str, int] = field(default_factory=dict)

    # Dimension 2: Module size distribution
    module_size_entropy: float = 0.0
    module_size_histogram: dict[str, int] = field(default_factory=dict)

    # Dimension 3: Import graph edge distribution
    import_edge_entropy: float = 0.0
    imports_per_file: dict[str, int] = field(default_factory=dict)

    # Dimension 4: Naming convention consistency
    naming_entropy: float = 0.0
    naming_patterns: dict[str, int] = field(default_factory=dict)

    # Dimension 5: File-to-responsibility mapping
    file_responsibility_entropy: float = 0.0
    file_class_counts: dict[str, int] = field(default_factory=dict)

    # Composite
    composite_entropy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_length_entropy": round(self.function_length_entropy, 4),
            "module_size_entropy": round(self.module_size_entropy, 4),
            "import_edge_entropy": round(self.import_edge_entropy, 4),
            "naming_entropy": round(self.naming_entropy, 4),
            "file_responsibility_entropy": round(self.file_responsibility_entropy, 4),
            "composite_entropy": round(self.composite_entropy, 4),
            "histograms": {
                "function_length": self.function_length_histogram,
                "module_size": self.module_size_histogram,
                "imports_per_file": self.imports_per_file,
                "naming_patterns": self.naming_patterns,
            },
        }


# ── Entropy Calculation ────────────────────────────────────────

def compute_entropy(
    codebase_path: Path,
    profile: LanguageProfile | None = None,
    *,
    file_filter: Callable[[Path], bool] | None = None,
) -> EntropyProfile:
    """Compute architectural entropy for a codebase.

    Args:
        codebase_path: Root directory of the codebase.
        profile: Language profile. Auto-detected if None.
        file_filter: Optional predicate over each source file. When supplied, only files
            for which it returns True contribute to every dimension (a file it rejects is
            treated as if it were skipped). This is the Δ-entropy instrument's
            solution/test split seam (design ``neo4j_graph_analysis_design.md`` §3): the
            caller passes ``lambda p: not is_test_file(p, profile)`` to measure the
            production-only tree, or ``lambda p: is_test_file(p, profile)`` for the test
            tree. ``None`` keeps the original whole-tree behavior (backward-compatible).

    Returns:
        EntropyProfile with all five dimensions populated.
    """
    if profile is None:
        profile = detect_language(codebase_path)
    if profile is None:
        return EntropyProfile()

    ast = parse_codebase(codebase_path, profile)
    if ast is None:
        return EntropyProfile()

    def _include(file_path: Path) -> bool:
        """The shared walk gate: skip dirs + optional caller filter."""
        if _should_skip(file_path):
            return False
        if file_filter is not None and not file_filter(file_path):
            return False
        return True

    ep = EntropyProfile()

    # ── Dimension 1: Function length distribution ──
    func_lengths: list[int] = []
    for file_path in codebase_path.rglob("*"):
        if not _include(file_path):
            continue
        if file_path.suffix in profile.extensions and file_path.is_file():
            try:
                source = file_path.read_bytes()
                parser = __import__("tree_sitter_languages", fromlist=["get_parser"]).get_parser(
                    profile.tree_sitter_id
                )
                tree = parser.parse(source)
                for func in collect_functions(tree, source):
                    loc = func.get("loc", 0)
                    if loc > 0:
                        func_lengths.append(loc)
            except Exception:
                pass

    ep.function_length_entropy = _shannon_entropy(func_lengths, bins=10)
    ep.function_length_histogram = _histogram(func_lengths, bins=5)

    # ── Dimension 2: Module size distribution ──
    file_sizes: list[int] = []
    for file_path in codebase_path.rglob("*"):
        if not _include(file_path):
            continue
        if file_path.suffix in profile.extensions and file_path.is_file():
            try:
                lines = len(file_path.read_bytes().split(b"\n"))
                file_sizes.append(lines)
            except Exception:
                pass

    ep.module_size_entropy = _shannon_entropy(file_sizes, bins=10)
    ep.module_size_histogram = _histogram(file_sizes, bins=5)

    # ── Dimension 3: Import graph edge distribution ──
    import_counts: list[int] = []
    file_imports: dict[str, int] = {}
    for file_path in codebase_path.rglob("*"):
        if not _include(file_path):
            continue
        if file_path.suffix in profile.extensions and file_path.is_file():
            try:
                source = file_path.read_bytes()
                parser = __import__("tree_sitter_languages", fromlist=["get_parser"]).get_parser(
                    profile.tree_sitter_id
                )
                tree = parser.parse(source)
                from agentic_dynamics.core.language import collect_imports
                imports = collect_imports(tree, source)
                count = len(imports)
                import_counts.append(count)
                rel = str(file_path.relative_to(codebase_path))
                file_imports[rel] = count
            except Exception:
                pass

    ep.import_edge_entropy = _shannon_entropy(import_counts, bins=8)
    ep.imports_per_file = file_imports

    # ── Dimension 4: Naming convention consistency ──
    naming_counts: dict[str, int] = {}
    for file_path in codebase_path.rglob("*"):
        if not _include(file_path):
            continue
        if file_path.suffix in profile.extensions and file_path.is_file():
            try:
                source = file_path.read_bytes()
                parser = __import__("tree_sitter_languages", fromlist=["get_parser"]).get_parser(
                    profile.tree_sitter_id
                )
                tree = parser.parse(source)
                for func in collect_functions(tree, source):
                    name = func.get("name", "unknown")
                    # Classify naming pattern
                    pattern = _classify_name(name)
                    naming_counts[pattern] = naming_counts.get(pattern, 0) + 1
            except Exception:
                pass

    ep.naming_entropy = _dict_entropy(naming_counts)
    ep.naming_patterns = naming_counts

    # ── Dimension 5: File-to-responsibility mapping ──
    file_classes: dict[str, int] = {}
    for file_path in codebase_path.rglob("*"):
        if not _include(file_path):
            continue
        if file_path.suffix in profile.extensions and file_path.is_file():
            try:
                source = file_path.read_bytes()
                parser = __import__("tree_sitter_languages", fromlist=["get_parser"]).get_parser(
                    profile.tree_sitter_id
                )
                tree = parser.parse(source)
                class_count = _count_classes(tree, profile)
                if class_count > 0:
                    rel = str(file_path.relative_to(codebase_path))
                    file_classes[rel] = class_count
            except Exception:
                pass

    ep.file_responsibility_entropy = _shannon_entropy(
        list(file_classes.values()), bins=5
    )
    ep.file_class_counts = file_classes

    # ── Composite ──
    ep.composite_entropy = (
        0.25 * ep.function_length_entropy
        + 0.20 * ep.module_size_entropy
        + 0.20 * ep.import_edge_entropy
        + 0.20 * ep.naming_entropy
        + 0.15 * ep.file_responsibility_entropy
    )

    return ep


def entropy_delta(before: EntropyProfile, after: EntropyProfile) -> float:
    """Compute entropy difference between two states.

    ΔH = H(after) - H(before)
    Positive → more disorder introduced.
    Negative → agent reduced entropy (organized the codebase).
    Zero → agent preserved existing order.
    """
    return after.composite_entropy - before.composite_entropy


def entropy_delta_detailed(
    before: EntropyProfile, after: EntropyProfile
) -> dict[str, float]:
    """Compute per-dimension entropy deltas."""
    return {
        "composite_delta": round(entropy_delta(before, after), 4),
        "function_length_delta": round(
            after.function_length_entropy - before.function_length_entropy, 4
        ),
        "module_size_delta": round(
            after.module_size_entropy - before.module_size_entropy, 4
        ),
        "import_edge_delta": round(
            after.import_edge_entropy - before.import_edge_entropy, 4
        ),
        "naming_delta": round(
            after.naming_entropy - before.naming_entropy, 4
        ),
        "file_responsibility_delta": round(
            after.file_responsibility_entropy - before.file_responsibility_entropy, 4
        ),
    }


# ── Helpers ─────────────────────────────────────────────────────

def _shannon_entropy(values: list[int], bins: int = 10) -> float:
    """Compute Shannon entropy of a binned value distribution."""
    if not values:
        return 0.0
    if len(values) == 1:
        return 0.0

    min_v = min(values)
    max_v = max(values)
    if min_v == max_v:
        return 0.0

    bin_width = (max_v - min_v) / bins
    if bin_width == 0:
        return 0.0

    histogram = [0] * bins
    for v in values:
        idx = min(int((v - min_v) / bin_width), bins - 1)
        histogram[idx] += 1

    total = sum(histogram)
    entropy = 0.0
    for count in histogram:
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)

    # Normalize by max possible entropy for this bin count
    max_entropy = math.log2(bins)
    if max_entropy == 0:
        return 0.0
    return entropy / max_entropy


def _dict_entropy(counts: dict[str, int]) -> float:
    """Compute Shannon entropy of a categorical distribution."""
    total = sum(counts.values())
    if total <= 1:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    # Normalize by max possible entropy
    n = len(counts)
    if n <= 1:
        return 0.0
    max_entropy = math.log2(n)
    if max_entropy == 0:
        return 0.0
    return entropy / max_entropy


def _histogram(values: list[int], bins: int = 5) -> dict[str, int]:
    """Create a labeled histogram."""
    if not values:
        return {}
    min_v = min(values)
    max_v = max(values)
    if min_v == max_v:
        return {f"{min_v}": len(values)}

    bin_width = (max_v - min_v) / bins
    result: dict[str, int] = {}
    for v in values:
        idx = min(int((v - min_v) / bin_width), bins - 1)
        label = f"{int(min_v + idx * bin_width)}-{int(min_v + (idx + 1) * bin_width)}"
        result[label] = result.get(label, 0) + 1
    return result


def _classify_name(name: str) -> str:
    """Classify a function/class name into a naming pattern."""
    if not name:
        return "empty"
    if name.startswith("_"):
        return "private"
    if "_" in name and name.islower():
        return "snake_case"
    if name[0].isupper() and "_" not in name:
        return "PascalCase"
    if name[0].islower() and any(c.isupper() for c in name):
        return "camelCase"
    if name.islower():
        return "lowercase"
    if name.isupper():
        return "UPPERCASE"
    return "other"


def _count_classes(tree, profile: LanguageProfile) -> int:
    """Count class/struct definitions in a tree."""
    count = 0

    def walk(node):
        nonlocal count
        if node.type in profile.class_node_types:
            count += 1
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return count
