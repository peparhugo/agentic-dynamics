"""Path finding between users.

Social graphs are dominated by short paths (the "six degrees" effect), so a
bidirectional breadth-first search is the workhorse: it meets in the middle
and explores roughly O(b^(d/2)) nodes instead of O(b^d) for unidirectional
BFS, which matters when fan-out ``b`` is in the hundreds.
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Dict, List, Optional

from .graph import SocialGraph
from .models import PathResult


def neighbors(graph: SocialGraph, user_id: str) -> List[str]:
    return list(graph.connections(user_id))


def bfs_path(graph: SocialGraph, src: str, dst: str) -> PathResult:
    """Unidirectional BFS returning a shortest path (by edge count)."""
    if src == dst:
        return PathResult(path=[src], distance=0)
    if not graph.has_user(src) or not graph.has_user(dst):
        return PathResult(path=None, distance=-1)

    prev: Dict[str, Optional[str]] = {src: None}
    queue = deque([src])
    while queue:
        cur = queue.popleft()
        for nxt in graph.connections(cur):
            if nxt in prev:
                continue
            prev[nxt] = cur
            if nxt == dst:
                return PathResult(path=_reconstruct(prev, dst), distance=len(prev) - 1)
            queue.append(nxt)
    return PathResult(path=None, distance=-1)


def bidirectional_bfs_path(graph: SocialGraph, src: str, dst: str) -> PathResult:
    """Bidirectional BFS; returns a shortest path between ``src`` and ``dst``."""
    if src == dst:
        return PathResult(path=[src], distance=0)
    if not graph.has_user(src) or not graph.has_user(dst):
        return PathResult(path=None, distance=-1)

    f_frontier = {src}
    b_frontier = {dst}
    f_prev: Dict[str, Optional[str]] = {src: None}
    b_prev: Dict[str, Optional[str]] = {dst: None}

    def expand(frontier, own_prev, other_prev):
        new_frontier = set()
        for cur in frontier:
            for nxt in graph.connections(cur):
                if nxt in own_prev:
                    continue
                own_prev[nxt] = cur
                new_frontier.add(nxt)
                if nxt in other_prev:
                    return new_frontier, nxt
        return new_frontier, None

    while f_frontier and b_frontier:
        # Always expand the smaller frontier to bound work.
        if len(f_frontier) > len(b_frontier):
            f_frontier, b_frontier = b_frontier, f_frontier
            f_prev, b_prev = b_prev, f_prev

        f_frontier, meet = expand(f_frontier, f_prev, b_prev)
        if meet is not None:
            path = _reconstruct(f_prev, meet)[:-1] + _reconstruct(b_prev, meet)[::-1]
            return PathResult(path=path, distance=len(path) - 1)

    return PathResult(path=None, distance=-1)


def shortest_path(graph: SocialGraph, src: str, dst: str) -> PathResult:
    return bidirectional_bfs_path(graph, src, dst)


def _reconstruct(prev: Dict[str, Optional[str]], target: str) -> List[str]:
    path = []
    cur: Optional[str] = target
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path
