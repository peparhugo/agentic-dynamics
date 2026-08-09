"""Per-collaborator undo/redo.

Google-Docs semantics: undo only reverts *your own* operations, and it must
work even after other users' concurrent edits. We achieve this by inverting
ops against the CRDT (delete <-> undelete tombstones) rather than replaying
index-based edits, so positions never go stale.
"""

from __future__ import annotations

from typing import List, Tuple

from .crdt import DeleteOp, FormatOp, UndeleteOp


class UndoManager:
    def __init__(self, client):
        self.client = client
        self._undo: List[Tuple[str, list]] = []
        self._redo: List[Tuple[str, list]] = []

    # ------------------------------------------------------------- recording
    def record_insert(self, ids) -> None:
        self._push(("hide", list(ids)))

    def record_delete(self, ids) -> None:
        self._push(("show", list(ids)))

    def record_format(self, entries) -> None:
        # entries: [(target_id, mark, previous_value)]
        self._push(("format", list(entries)))

    def _push(self, spec) -> None:
        self._undo.append(spec)
        self._redo.clear()  # new local edit invalidates the redo branch

    # -------------------------------------------------------------- queries
    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    # ------------------------------------------------------------- execution
    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._apply(self._undo.pop()))
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._apply(self._redo.pop()))
        return True

    def _apply(self, spec) -> Tuple[str, list]:
        """Apply an inverse spec, emit resulting ops, return spec's inverse."""
        doc = self.client.doc
        kind, data = spec
        ops = []
        if kind == "hide":
            for tid in data:
                ops.append(DeleteOp(doc._next_id(), tid))
            inverse = ("show", data)
        elif kind == "show":
            for tid in data:
                ops.append(UndeleteOp(doc._next_id(), tid))
            inverse = ("hide", data)
        else:  # format
            inv_entries = []
            for tid, mark, value in data:
                cur = doc._node(tid).attrs.get(mark)
                inv_entries.append((tid, mark, cur[0] if cur else None))
                ops.append(FormatOp(doc._next_id(), (tid,), mark, value))
            inverse = ("format", inv_entries)

        for op in ops:
            doc.apply(op)
        self.client.broadcast(ops)
        return inverse
