"""Row selection model (single / multi / range). Mirrors hooks/useSelection.ts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class SelectionState:
    selected: frozenset[str] = frozenset()
    anchor_index: Optional[int] = None


def reduce_selection(
    state: SelectionState,
    mode: str,
    clicked_index: int,
    visible_keys: Sequence[str],
    ctrl: bool = False,
    shift: bool = False,
) -> SelectionState:
    """Apply a row click.

    - ``single``: click always replaces the selection.
    - ``multi``/``range``: ctrl toggles; shift extends from the anchor
      over the visible order; ctrl+shift extends additively.
    """
    if clicked_index < 0 or clicked_index >= len(visible_keys):
        return state
    key = visible_keys[clicked_index]

    if mode == "single":
        return SelectionState(frozenset({key}), clicked_index)

    if shift and state.anchor_index is not None:
        lo = min(state.anchor_index, clicked_index)
        hi = max(state.anchor_index, clicked_index)
        rng = set(visible_keys[lo : hi + 1])
        base = set(state.selected) if ctrl else set()
        return SelectionState(frozenset(base | rng), state.anchor_index)

    if ctrl:
        current = set(state.selected)
        if key in current:
            current.discard(key)
        else:
            current.add(key)
        return SelectionState(frozenset(current), clicked_index)

    return SelectionState(frozenset({key}), clicked_index)


def select_all(visible_keys: Sequence[str]) -> SelectionState:
    return SelectionState(
        frozenset(visible_keys), 0 if visible_keys else None
    )


def clear_selection() -> SelectionState:
    return SelectionState()
