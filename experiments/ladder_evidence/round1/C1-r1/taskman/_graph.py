"""Dependency-graph helpers: cycle detection and deterministic ordering.

These functions are pure: they take a mapping of ``task_id -> dependency ids``
and return plain data.  Keeping graph reasoning out of the manager means the
manager can validate a *candidate* projection without ever mutating its own
journal -- the property that guarantees a rejected edit leaves state unchanged.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from ._model import Task

#: DFS colouring used by :func:`find_cycle`.
_WHITE = 0
_GRAY = 1  # on the current DFS path -> a back-edge means a cycle
_BLACK = 2


def find_cycle(dependencies: Mapping[str, Sequence[str]]) -> list[str] | None:
    """Return a dependency cycle as a list of ids, or ``None`` when acyclic.

    Edges point from a task to the tasks it depends on, so a cycle is any closed
    walk ``a -> b -> ... -> a`` (equivalently: ``a`` transitively depends on
    itself).  The search is an iterative three-colour DFS: a child already GRAY is
    an ancestor still on the current path, i.e. the back-edge that closes a cycle.
    Iterative (not recursive) so a deep chain can never hit the recursion limit.

    The returned list is a valid cycle in edge order, e.g. ``["b", "a"]`` for a
    two-node ``a <-> b`` loop; callers only use it for a readable error message.
    """
    colour: dict[str, int] = {}
    parent: dict[str, str] = {}
    for root in dependencies:
        if colour.get(root, _WHITE) != _WHITE:
            continue
        colour[root] = _GRAY
        stack: list[tuple[str, Iterable[str]]] = [(root, iter(dependencies.get(root, ())))]
        while stack:
            node, children = stack[-1]
            for child in children:
                state = colour.get(child, _WHITE)
                if state == _GRAY:
                    # Walk the DFS parent chain from ``node`` back to ``child``.
                    cycle = [node]
                    cursor = node
                    while cursor != child:
                        cursor = parent[cursor]
                        cycle.append(cursor)
                    return cycle
                if state == _WHITE:
                    colour[child] = _GRAY
                    parent[child] = node
                    stack.append((child, iter(dependencies.get(child, ()))))
                    break
            else:
                # Every child explored without finding a cycle; finalise this node.
                colour[node] = _BLACK
                stack.pop()
    return None


def order_tasks(tasks: Iterable[Task]) -> list[Task]:
    """Order tasks priority-descending, tie-broken by creation order.

    ``-priority`` puts the highest priority first; the secondary ``seq`` key makes
    the sort a stable, total order that matches the contract's "ties keep creation
    order" requirement without relying on Python's sort stability over an
    unspecified input order.
    """
    return sorted(tasks, key=lambda task: (-task.priority, task.seq))
