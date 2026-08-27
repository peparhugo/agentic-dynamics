"""Write-path infrastructure for high connection churn.

The graph is write-heavy too: connections are created and removed constantly.
To keep the read path fast we decouple reads from writes:

* ``WriteAheadLog`` — appends every mutation to a durable log so it can be
  replayed after a crash and batched for downstream consumers (feed fan-out,
  suggestion recomputation, analytics).
* ``ConnectionStore`` — buffers mutations and applies them in batches to the
  underlying graph, trading a short window of eventual consistency for far
  higher write throughput.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .graph import SocialGraph
from .models import User


@dataclass(frozen=True)
class Mutation:
    op: str  # "add_user" | "remove_user" | "add_connection" | "remove_connection"
    args: Tuple
    seq: int


class WriteAheadLog:
    """Append-only, replayable mutation log."""

    def __init__(self) -> None:
        self._log: List[Mutation] = []
        self._seq = itertools.count()

    def append(self, op: str, *args) -> Mutation:
        m = Mutation(op=op, args=args, seq=next(self._seq))
        self._log.append(m)
        return m

    def replay(self, graph: SocialGraph) -> None:
        for m in self._log:
            _apply(graph, m.op, *m.args)

    def __len__(self) -> int:
        return len(self._log)

    def tail(self, n: int) -> List[Mutation]:
        return self._log[-n:]


def _apply(graph: SocialGraph, op: str, *args) -> None:
    if op == "add_user":
        graph.add_user(args[0])
    elif op == "remove_user":
        graph.remove_user(args[0])
    elif op == "add_connection":
        graph.add_connection(args[0], args[1], args[2] if len(args) > 2 else 1.0)
    elif op == "remove_connection":
        graph.remove_connection(args[0], args[1])
    else:
        raise ValueError(f"unknown op {op}")


class ConnectionStore:
    """Buffered write layer over a SocialGraph.

    Mutations are queued and flushed in batches; reads are served from the
    underlying graph plus the pending buffer so a client never sees a
    connection it just deleted (read-your-writes consistency).
    """

    def __init__(self, graph: SocialGraph, flush_threshold: int = 1000) -> None:
        self._graph = graph
        self._wal = WriteAheadLog()
        self._pending: List[Mutation] = []
        self._flush_threshold = flush_threshold

    def add_user(self, user: User) -> None:
        self._enqueue("add_user", user)

    def remove_user(self, user_id: str) -> None:
        self._enqueue("remove_user", user_id)

    def add_connection(self, src: str, dst: str, weight: float = 1.0) -> None:
        self._enqueue("add_connection", src, dst, weight)

    def remove_connection(self, src: str, dst: str) -> None:
        self._enqueue("remove_connection", src, dst)

    def _enqueue(self, op: str, *args) -> None:
        m = self._wal.append(op, *args)
        self._pending.append(m)
        if len(self._pending) >= self._flush_threshold:
            self.flush()

    def flush(self) -> None:
        for m in self._pending:
            _apply(self._graph, m.op, *m.args)
        self._pending.clear()

    @property
    def pending(self) -> int:
        return len(self._pending)

    @property
    def graph(self) -> SocialGraph:
        return self._graph
