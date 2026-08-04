"""Presence layer: multi-user cursors and selections.

Cursors are stored as anchors (character ids), not integer offsets, so they
survive concurrent remote edits without transformation. The renderer converts
anchors back to visible indices on every frame.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .crdt import Document, OpId


class CursorManager:
    def __init__(self, doc: Document):
        self.doc = doc
        # user -> (anchor, head) anchors; anchor==head means a caret
        self._cursors: Dict[str, Tuple[Optional[OpId], Optional[OpId]]] = {}

    # -------- local user -> broadcastable state
    def set_cursor(self, user: str, index: int) -> Tuple[Optional[OpId], Optional[OpId]]:
        a = self._anchor_for(index)
        self._cursors[user] = (a, a)
        return self._cursors[user]

    def set_selection(self, user: str, start: int, end: int):
        self._cursors[user] = (self._anchor_for(start), self._anchor_for(end))
        return self._cursors[user]

    def _anchor_for(self, index: int) -> Optional[OpId]:
        return None if index == 0 else self.doc.id_at(index - 1)

    # -------- remote presence messages
    def receive(self, user: str, anchors) -> None:
        self._cursors[user] = tuple(anchors)

    def remove(self, user: str) -> None:
        self._cursors.pop(user, None)

    # -------- resolution for rendering
    def get_index(self, user: str) -> int:
        return self.doc.anchor_index(self._cursors[user][0])

    def get_selection(self, user: str) -> Tuple[int, int]:
        a, h = self._cursors[user]
        return self.doc.anchor_index(a), self.doc.anchor_index(h)

    def anchors(self, user: str):
        return self._cursors[user]

    def all_positions(self) -> Dict[str, Tuple[int, int]]:
        return {u: self.get_selection(u) for u in self._cursors}
