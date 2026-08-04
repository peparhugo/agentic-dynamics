"""Sync engine: op relay server + client with offline queue and reconnect.

Because the document is a CRDT, the "server" is a dumb ordered op log (in the
real app: WebSocket fan-out + persistence). Clients that go offline keep
editing locally, queue ops in an outbox, and on reconnect (a) flush the
outbox and (b) pull every op they missed. Convergence is guaranteed by the
CRDT regardless of delivery order or duplication.
"""

from __future__ import annotations

from typing import List, Tuple

from .crdt import Document, Op
from .cursor import CursorManager
from .undo import UndoManager


class Server:
    """Ordered, append-only op log (stand-in for the realtime backend)."""

    def __init__(self):
        self.log: List[Op] = []

    def submit(self, ops) -> int:
        self.log.extend(ops)
        return len(self.log)

    def ops_since(self, seq: int) -> Tuple[List[Op], int]:
        return list(self.log[seq:]), len(self.log)


class Client:
    """One user's editor session (document replica + presence + undo + queue)."""

    def __init__(self, site: str, server: Server):
        self.site = site
        self.server = server
        self.doc = Document(site)
        self.cursors = CursorManager(self.doc)
        self.undo_manager = UndoManager(self)
        self.connected = True
        self.outbox: List[Op] = []
        self.last_seq = 0
        self.sync()

    # --------------------------------------------------------------- editing
    def insert(self, index: int, text: str) -> None:
        ops = self.doc.local_insert_text(index, text)
        self.undo_manager.record_insert([op.id for op in ops])
        self.broadcast(ops)

    def delete(self, index: int, length: int = 1) -> None:
        ops = self.doc.local_delete(index, length)
        self.undo_manager.record_delete([op.target for op in ops])
        self.broadcast(ops)

    def format(self, start: int, end: int, mark: str, value: object = True) -> None:
        targets = [self.doc.id_at(i) for i in range(start, end)]
        entries = []
        for t in targets:
            cur = self.doc._node(t).attrs.get(mark)
            entries.append((t, mark, cur[0] if cur else None))
        op = self.doc.local_format(start, end, mark, value)
        self.undo_manager.record_format(entries)
        self.broadcast([op])

    def undo(self) -> bool:
        return self.undo_manager.undo()

    def redo(self) -> bool:
        return self.undo_manager.redo()

    # ------------------------------------------------------------- transport
    def broadcast(self, ops) -> None:
        if not ops:
            return
        if self.connected:
            self.server.submit(list(ops))
            self.sync()
        else:
            self.outbox.extend(ops)

    def sync(self) -> None:
        """Pull and apply everything we haven't seen (idempotent)."""
        if not self.connected:
            return
        ops, seq = self.server.ops_since(self.last_seq)
        for op in ops:
            self.doc.apply(op)
        self.last_seq = seq

    def disconnect(self) -> None:
        self.connected = False

    def connect(self) -> None:
        """Reconnect: flush offline edits, then catch up on missed remote ops."""
        self.connected = True
        if self.outbox:
            self.server.submit(self.outbox)
            self.outbox = []
        self.sync()

    # -------------------------------------------------------------- niceties
    @property
    def text(self) -> str:
        return self.doc.text
