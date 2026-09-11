"""taskman: a tiny stdlib-only task manager.

Design (see DESIGN.md for the full note):
  * ``TaskManager`` owns an insertion-ordered ``dict`` of task id -> task record.
  * Task ids are ``uuid4`` hex strings, so they are unique across processes and survive save/load.
  * All validation happens *before* any mutation, so a rejected update leaves state untouched.
  * ``due_at`` is validated with ``datetime.fromisoformat`` but stored as the original string,
    preserving an exact JSON round-trip.
  * ``list_tasks`` relies on Python's stable sort: sort by ``-priority`` keeps creation order
    for equal priorities (dict insertion order is creation order).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

VALID_STATUSES = ("todo", "doing", "done")


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, dict] = {}

    def add_task(
        self,
        title,
        *,
        priority=3,
        tags=None,
        depends_on=None,
        due_at=None,
    ) -> str:
        self._validate_priority(priority)
        due_at = self._validate_due_at(due_at)
        depends_on = self._validate_depends_on(depends_on, exclude=None)
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "tags": list(tags) if tags else [],
            "depends_on": list(depends_on),
            "due_at": due_at,
            "created_at": datetime.now().isoformat(),
        }
        return task_id

    def get_task(self, task_id) -> dict:
        return self._tasks[task_id]

    def update_task(
        self,
        task_id,
        *,
        title=None,
        priority=None,
        tags=None,
        depends_on=None,
        due_at=None,
        status=None,
    ) -> dict:
        if task_id not in self._tasks:
            raise KeyError(task_id)
        updates: dict = {}
        if title is not None:
            updates["title"] = title
        if priority is not None:
            self._validate_priority(priority)
            updates["priority"] = priority
        if tags is not None:
            updates["tags"] = list(tags)
        if due_at is not None:
            updates["due_at"] = self._validate_due_at(due_at)
        if status is not None:
            self._validate_status(status)
            updates["status"] = status
        if depends_on is not None:
            deps = self._validate_depends_on(depends_on, exclude=task_id)
            self._check_cycle(task_id, deps)
            updates["depends_on"] = deps
        self._tasks[task_id].update(updates)
        return self._tasks[task_id]

    def delete_task(self, task_id) -> None:
        if task_id not in self._tasks:
            raise KeyError(task_id)
        for other in self._tasks.values():
            if task_id in other["depends_on"]:
                raise ValueError(f"task {other['id']} depends on {task_id}; delete it first")
        del self._tasks[task_id]

    def set_status(self, task_id, status) -> dict:
        if task_id not in self._tasks:
            raise KeyError(task_id)
        self._validate_status(status)
        self._tasks[task_id]["status"] = status
        return self._tasks[task_id]

    def list_tasks(self, *, status=None, priority=None, tag=None) -> list[dict]:
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t["status"] == status]
        if priority is not None:
            tasks = [t for t in tasks if t["priority"] == priority]
        if tag is not None:
            tasks = [t for t in tasks if tag in t["tags"]]
        return sorted(tasks, key=lambda t: -t["priority"])

    def ready_tasks(self) -> list[dict]:
        ready = []
        for task in self._tasks.values():
            if task["status"] == "done":
                continue
            if all(self._tasks[d]["status"] == "done" for d in task["depends_on"]):
                ready.append(task)
        return sorted(ready, key=lambda t: -t["priority"])

    def save(self, path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"tasks": list(self._tasks.values())}, fh)

    @classmethod
    def load(cls, path) -> "TaskManager":
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        manager = cls()
        for record in payload["tasks"]:
            manager._tasks[record["id"]] = record
        return manager

    @staticmethod
    def _validate_status(status) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status!r}")

    @staticmethod
    def _validate_priority(priority) -> None:
        if not isinstance(priority, int) or isinstance(priority, bool) or not 1 <= priority <= 5:
            raise ValueError(f"priority must be an int in 1..5, got {priority!r}")

    @staticmethod
    def _validate_due_at(due_at):
        if due_at is None:
            return None
        try:
            datetime.fromisoformat(due_at)
        except (TypeError, ValueError):
            raise ValueError(f"unparseable due_at: {due_at!r}")
        return due_at

    def _validate_depends_on(self, depends_on, *, exclude) -> list:
        if depends_on is None:
            return []
        deps = list(depends_on)
        for dep in deps:
            if dep == exclude:
                raise ValueError("a task cannot depend on itself")
            if dep not in self._tasks:
                raise ValueError(f"unknown dependency: {dep!r}")
        if len(set(deps)) != len(deps):
            raise ValueError("duplicate dependencies")
        return deps

    def _check_cycle(self, task_id, deps) -> None:
        graph = {}
        for tid, task in self._tasks.items():
            graph[tid] = list(task["depends_on"])
        graph[task_id] = list(deps)

        visiting: set = set()
        visited: set = set()

        def visit(node):
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for neighbour in graph.get(node, []):
                if visit(neighbour):
                    return True
            visiting.discard(node)
            visited.add(node)
            return False

        for node in list(graph):
            if visit(node):
                raise ValueError("dependency cycle detected")


__all__ = ["TaskManager"]
