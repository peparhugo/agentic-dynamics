"""Virtual scrolling window math. Mirrors hooks/useVirtualScroll.ts."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class VirtualWindow:
    start_index: int
    end_index: int  # exclusive
    offset_y: float
    total_height: float

    @property
    def rendered_count(self) -> int:
        return self.end_index - self.start_index


def compute_virtual_window(
    scroll_top: float,
    row_height: float,
    viewport_height: float,
    total_rows: int,
    overscan: int = 5,
) -> VirtualWindow:
    """Return the slice of rows to render plus spacer geometry.

    Only rows intersecting the viewport (plus ``overscan`` rows on each
    side) are rendered; ``total_height`` sizes the scrollable spacer.
    """
    total_height = total_rows * row_height
    if total_rows == 0 or row_height <= 0 or viewport_height <= 0:
        return VirtualWindow(0, 0, 0.0, total_height)

    clamped_top = min(max(scroll_top, 0.0), max(total_height - viewport_height, 0.0))
    first = int(clamped_top // row_height)
    visible = math.ceil(viewport_height / row_height) + 1
    start = max(0, first - overscan)
    end = min(total_rows, first + visible + overscan)
    return VirtualWindow(start, end, start * row_height, total_height)


def scroll_to_row(
    index: int,
    current_scroll_top: float,
    row_height: float,
    viewport_height: float,
) -> float:
    """Minimal scroll adjustment to bring ``index`` fully into view."""
    top = index * row_height
    bottom = top + row_height
    if top < current_scroll_top:
        return top
    if bottom > current_scroll_top + viewport_height:
        return bottom - viewport_height
    return current_scroll_top
