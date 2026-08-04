"""WAI-ARIA grid keyboard navigation. Mirrors hooks/useKeyboardNav.ts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CellPosition:
    row: int
    col: int


NAV_KEYS = frozenset(
    {"ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"}
)


def navigate(
    pos: CellPosition,
    key: str,
    row_count: int,
    col_count: int,
    page_size: int,
    ctrl: bool = False,
) -> CellPosition:
    """Compute the next focused cell for a navigation key press."""
    if row_count == 0 or col_count == 0:
        return pos

    def clamp(r: int, c: int) -> CellPosition:
        return CellPosition(
            max(0, min(row_count - 1, r)),
            max(0, min(col_count - 1, c)),
        )

    if key == "ArrowUp":
        return clamp(pos.row - 1, pos.col)
    if key == "ArrowDown":
        return clamp(pos.row + 1, pos.col)
    if key == "ArrowLeft":
        return clamp(pos.row, pos.col - 1)
    if key == "ArrowRight":
        return clamp(pos.row, pos.col + 1)
    if key == "Home":
        return clamp(0, 0) if ctrl else clamp(pos.row, 0)
    if key == "End":
        return clamp(row_count - 1, col_count - 1) if ctrl else clamp(pos.row, col_count - 1)
    if key == "PageUp":
        return clamp(pos.row - page_size, pos.col)
    if key == "PageDown":
        return clamp(pos.row + page_size, pos.col)
    return pos
