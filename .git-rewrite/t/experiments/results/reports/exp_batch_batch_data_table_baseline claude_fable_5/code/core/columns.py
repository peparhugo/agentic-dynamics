"""Column reorder / resize / visibility. Mirrors hooks/useColumns.ts."""

from __future__ import annotations

from typing import Sequence


def reorder(order: Sequence[str], from_index: int, to_index: int) -> list[str]:
    """Move a column id from one position to another (clamped)."""
    result = list(order)
    if from_index < 0 or from_index >= len(result):
        return result
    clamped_to = max(0, min(to_index, len(result) - 1))
    moved = result.pop(from_index)
    result.insert(clamped_to, moved)
    return result


def resize_width(current: float, delta: float, min_width: float = 40, max_width: float = 1000) -> float:
    """Apply a resize delta clamped to [min_width, max_width]."""
    return max(min_width, min(max_width, current + delta))


def visible_columns(order: Sequence[str], hidden: set[str] | frozenset[str]) -> list[str]:
    return [c for c in order if c not in hidden]


def toggle_visibility(hidden: frozenset[str], column_id: str) -> frozenset[str]:
    if column_id in hidden:
        return hidden - {column_id}
    return hidden | {column_id}
