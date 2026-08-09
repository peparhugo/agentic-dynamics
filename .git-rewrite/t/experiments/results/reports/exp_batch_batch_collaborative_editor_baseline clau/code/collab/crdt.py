"""Core sequence CRDT (RGA - Replicated Growable Array) for collaborative text.

This is the conflict-resolution heart of the editor. Each character is a node
with a globally unique id (lamport counter, site id). Concurrent inserts at the
same position are ordered deterministically by id, so all replicas converge
without a central authority (unlike OT, no server-side transformation needed).

Rich-text formatting is stored as per-character marks with last-writer-wins
(LWW) resolution keyed by op id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union


@dataclass(frozen=True, order=True)
class OpId:
    """Globally unique, totally ordered operation id (lamport counter + site)."""

    counter: int
    site: str


@dataclass(frozen=True)
class InsertOp:
    id: OpId
    origin: Optional[OpId]  # id of the character to the left; None = doc start
    char: str


@dataclass(frozen=True)
class DeleteOp:
    id: OpId
    target: OpId


@dataclass(frozen=True)
class UndeleteOp:
    """Resurrects a tombstone (used by undo of a delete / redo of an insert)."""

    id: OpId
    target: OpId


@dataclass(frozen=True)
class FormatOp:
    id: OpId
    targets: Tuple[OpId, ...]
    mark: str  # e.g. "bold", "italic", "link"
    value: object


Op = Union[InsertOp, DeleteOp, UndeleteOp, FormatOp]


@dataclass
class Node:
    id: OpId
    origin: Optional[OpId]
    char: str
    deleted: bool = False
    # mark -> (value, op id that set it) for LWW resolution
    attrs: Dict[str, Tuple[object, OpId]] = field(default_factory=dict)


class Document:
    """One replica of the shared document."""

    def __init__(self, site: str):
        self.site = site
        self.clock = 0  # lamport clock
        self.nodes: List[Node] = []  # includes tombstones
        self._ids: Set[OpId] = set()  # ids of integrated character nodes
        self._applied: Set[OpId] = set()  # every op id ever applied (idempotency)
        self.pending: List[Op] = []  # causally-buffered ops awaiting deps

    # ------------------------------------------------------------------ ids
    def _next_id(self) -> OpId:
        self.clock += 1
        return OpId(self.clock, self.site)

    def _tick(self, op_id: OpId) -> None:
        self.clock = max(self.clock, op_id.counter)

    def _pos(self, op_id: OpId) -> Optional[int]:
        for i, n in enumerate(self.nodes):
            if n.id == op_id:
                return i
        return None

    def _node(self, op_id: OpId) -> Node:
        pos = self._pos(op_id)
        if pos is None:
            raise KeyError(op_id)
        return self.nodes[pos]

    # ------------------------------------------------------------- visibility
    @property
    def text(self) -> str:
        return "".join(n.char for n in self.nodes if not n.deleted)

    def __len__(self) -> int:
        return sum(1 for n in self.nodes if not n.deleted)

    def _visible_node_at(self, index: int) -> Node:
        count = 0
        for n in self.nodes:
            if not n.deleted:
                if count == index:
                    return n
                count += 1
        raise IndexError(index)

    def id_at(self, index: int) -> OpId:
        """Id of the visible character at a visible index."""
        return self._visible_node_at(index).id

    def anchor_index(self, anchor: Optional[OpId]) -> int:
        """Visible index just after `anchor` (None = doc start).

        Used for cursors and comments: anchors survive remote edits because
        they reference immutable ids, not offsets. If the anchor char was
        deleted, this resolves to where the char used to be.
        """
        if anchor is None:
            return 0
        count = 0
        for n in self.nodes:
            if not n.deleted:
                count += 1
                if n.id == anchor:
                    return count
            elif n.id == anchor:
                return count
        raise KeyError(anchor)

    # ---------------------------------------------------------- local edits
    def local_insert(self, index: int, char: str) -> InsertOp:
        origin = None if index == 0 else self.id_at(index - 1)
        op = InsertOp(self._next_id(), origin, char)
        self.apply(op)
        return op

    def local_insert_text(self, index: int, text: str) -> List[InsertOp]:
        return [self.local_insert(index + i, ch) for i, ch in enumerate(text)]

    def local_delete(self, index: int, length: int = 1) -> List[DeleteOp]:
        ops = []
        for _ in range(length):
            op = DeleteOp(self._next_id(), self.id_at(index))
            self.apply(op)
            ops.append(op)
        return ops

    def local_format(self, start: int, end: int, mark: str, value: object) -> FormatOp:
        targets = tuple(self.id_at(i) for i in range(start, end))
        op = FormatOp(self._next_id(), targets, mark, value)
        self.apply(op)
        return op

    # -------------------------------------------------------------- applying
    def apply(self, op: Op) -> bool:
        """Apply a local or remote op. Idempotent, commutative, causal-safe."""
        ok = self._apply_one(op)
        if ok:
            self._drain_pending()
        return ok

    def _apply_one(self, op: Op) -> bool:
        if op.id in self._applied:
            return True  # duplicate delivery: no-op

        if isinstance(op, InsertOp):
            if op.origin is not None and op.origin not in self._ids:
                self._defer(op)
                return False
            self._tick(op.id)
            self._integrate(Node(op.id, op.origin, op.char))
            self._ids.add(op.id)
            self._applied.add(op.id)
            return True

        targets = op.targets if isinstance(op, FormatOp) else (op.target,)
        if any(t not in self._ids for t in targets):
            self._defer(op)
            return False

        self._tick(op.id)
        if isinstance(op, DeleteOp):
            self._node(op.target).deleted = True
        elif isinstance(op, UndeleteOp):
            self._node(op.target).deleted = False
        else:  # FormatOp - LWW per (char, mark)
            for t in op.targets:
                node = self._node(t)
                cur = node.attrs.get(op.mark)
                if cur is None or cur[1] < op.id:
                    node.attrs[op.mark] = (op.value, op.id)
        self._applied.add(op.id)
        return True

    def _defer(self, op: Op) -> None:
        if all(p.id != op.id for p in self.pending):
            self.pending.append(op)

    def _drain_pending(self) -> None:
        progress = True
        while progress and self.pending:
            progress = False
            still = []
            for op in self.pending:
                if self._apply_one(op):
                    progress = True
                else:
                    still.append(op)
            self.pending = still

    def _integrate(self, node: Node) -> None:
        """RGA integration: place after origin, skipping concurrent nodes with
        larger ids. With lamport counters this yields convergence and avoids
        interleaving of concurrent runs of text."""
        if node.origin is None:
            idx = 0
        else:
            idx = self._pos(node.origin) + 1
        while idx < len(self.nodes) and self.nodes[idx].id > node.id:
            idx += 1
        self.nodes.insert(idx, node)

    # ------------------------------------------------------------ formatting
    def spans(self) -> List[Tuple[str, Dict[str, object]]]:
        """Visible characters with resolved marks (what the renderer consumes)."""
        out = []
        for n in self.nodes:
            if n.deleted:
                continue
            attrs = {k: v for k, (v, _id) in n.attrs.items() if v not in (None, False)}
            out.append((n.char, attrs))
        return out

    def marks_in_range(self, start: int, end: int) -> Dict[str, object]:
        """Marks active across the whole selection (drives toolbar button state)."""
        spans = self.spans()[start:end]
        if not spans:
            return {}
        common: Dict[str, object] = dict(spans[0][1])
        for _ch, attrs in spans[1:]:
            common = {k: v for k, v in common.items() if attrs.get(k) == v}
        return common
