"""Comments anchored to text ranges.

Anchors are character ids, so comments stay attached to the right text as the
document is edited concurrently. If the entire commented range is deleted the
comment becomes orphaned (shown in the sidebar as "original text deleted").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .crdt import Document, OpId


@dataclass
class Comment:
    id: str
    author: str
    text: str
    start: OpId  # first commented character
    end: OpId    # last commented character (inclusive)
    resolved: bool = False
    replies: List[Tuple[str, str]] = field(default_factory=list)  # (author, text)


class CommentManager:
    def __init__(self, doc: Document):
        self.doc = doc
        self.comments: Dict[str, Comment] = {}
        self._counter = 0

    def add(self, author: str, text: str, start_index: int, end_index: int) -> Comment:
        if end_index <= start_index:
            raise ValueError("empty comment range")
        start = self.doc.id_at(start_index)
        end = self.doc.id_at(end_index - 1)
        self._counter += 1
        c = Comment(f"c{self._counter}", author, text, start, end)
        self.comments[c.id] = c
        return c

    def reply(self, cid: str, author: str, text: str) -> None:
        self.comments[cid].replies.append((author, text))

    def resolve(self, cid: str) -> None:
        self.comments[cid].resolved = True

    def is_orphaned(self, cid: str) -> bool:
        c = self.comments[cid]
        si, ei = self.doc._pos(c.start), self.doc._pos(c.end)
        if si is None or ei is None:
            return True
        return all(self.doc.nodes[i].deleted for i in range(si, ei + 1))

    def range(self, cid: str) -> Optional[Tuple[int, int]]:
        """Current visible (start, end) of the comment, or None if orphaned."""
        if self.is_orphaned(cid):
            return None
        c = self.comments[cid]
        start = self._visible_before(c.start)
        end_before = self._visible_before(c.end)
        end_node = self.doc._node(c.end)
        end = end_before + (0 if end_node.deleted else 1)
        return (start, end)

    def anchored_text(self, cid: str) -> str:
        r = self.range(cid)
        if r is None:
            return ""
        return self.doc.text[r[0]:r[1]]

    def open_comments(self) -> List[Comment]:
        return [c for c in self.comments.values() if not c.resolved]

    def _visible_before(self, op_id: OpId) -> int:
        count = 0
        for n in self.doc.nodes:
            if n.id == op_id:
                return count
            if not n.deleted:
                count += 1
        raise KeyError(op_id)
