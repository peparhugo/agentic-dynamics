"""Multi-column stable sorting. Mirrors hooks/useSorting.ts."""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class SortSpec:
    column_id: str
    direction: str = "asc"  # "asc" | "desc"


def default_compare(a: Any, b: Any) -> int:
    """Nulls/empties last; numbers numerically; otherwise string compare."""
    a_null = a is None or a == ""
    b_null = b is None or b == ""
    if a_null and b_null:
        return 0
    if a_null:
        return 1
    if b_null:
        return -1
    if isinstance(a, bool) and isinstance(b, bool):
        return int(a) - int(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return (a > b) - (a < b)
    sa, sb = str(a), str(b)
    return (sa > sb) - (sa < sb)


def multi_sort(
    rows: Sequence[Mapping[str, Any]],
    sorts: Sequence[SortSpec],
    comparators: Mapping[str, Callable[[Any, Any], int]] | None = None,
) -> list[int]:
    """Return original row indices in sorted order (stable)."""
    indices = list(range(len(rows)))
    if not sorts:
        return indices
    comparators = comparators or {}

    def cmp(ia: int, ib: int) -> int:
        for spec in sorts:
            comparator = comparators.get(spec.column_id, default_compare)
            result = comparator(rows[ia].get(spec.column_id), rows[ib].get(spec.column_id))
            if result != 0:
                return result if spec.direction == "asc" else -result
        return ia - ib  # stability

    indices.sort(key=functools.cmp_to_key(cmp))
    return indices


def toggle_sort(sorts: Sequence[SortSpec], column_id: str, additive: bool) -> list[SortSpec]:
    """Cycle none -> asc -> desc -> none; shift(additive) preserves others."""
    existing = next((s for s in sorts if s.column_id == column_id), None)
    others = [s for s in sorts if s.column_id != column_id] if additive else []
    if existing is None:
        return [*others, SortSpec(column_id, "asc")]
    if existing.direction == "asc":
        return [*others, SortSpec(column_id, "desc")]
    return list(others)
