"""Behavioral contract for the flash-ladder `taskman` task.

The ladder's quality signal: the implementation under test must satisfy these behaviours, and
the scorer re-runs THIS file (restored pristine from the ladder base) against each cell's
exported tree. The file lives in the repo's own suite, so it uses ``importorskip`` — outside a
cell (where ``taskman`` does not exist) it skips cleanly instead of failing collection.

Contract: a pure-Python, stdlib-only package ``taskman`` exposing ``TaskManager``:
  * ``add_task(title, *, priority=3, tags=None, depends_on=None, due_at=None) -> str`` (unique
    id); defaults: status ``todo``, priority ``3``, empty tags/deps, ``None`` due date;
  * ``get_task`` / ``update_task`` / ``delete_task`` / ``set_status`` — unknown ids raise
    ``KeyError``; statuses are ``todo``/``doing``/``done`` (else ``ValueError``); ``delete_task``
    refuses (``ValueError``) while other tasks depend on it;
  * ``priority`` outside 1..5 and unparseable ``due_at`` raise ``ValueError``; unknown
    ``depends_on`` ids raise ``ValueError``; dependency cycles raise ``ValueError`` leaving
    state unchanged;
  * ``list_tasks(*, status=None, priority=None, tag=None)`` ordered priority desc (ties keep
    creation order); ``ready_tasks()`` = not-done tasks whose dependencies are all done;
  * ``save(path)`` / ``TaskManager.load(path)`` JSON round-trip.
"""

from __future__ import annotations

import json

import pytest

taskman = pytest.importorskip("taskman")
TaskManager = taskman.TaskManager

pytestmark = pytest.mark.fast


def test_add_and_get_defaults():
    manager = TaskManager()
    task_id = manager.add_task("write docs")
    task = manager.get_task(task_id)
    assert task["id"] == task_id
    assert task["title"] == "write docs"
    assert task["status"] == "todo"
    assert task["priority"] == 3
    assert task["tags"] == []
    assert task["depends_on"] == []
    assert task["due_at"] is None
    assert isinstance(task["created_at"], str) and task["created_at"]


def test_ids_are_unique():
    manager = TaskManager()
    ids = {manager.add_task(f"task {i}") for i in range(20)}
    assert len(ids) == 20


def test_priority_validation():
    manager = TaskManager()
    for bad in (0, 6, -1, 99):
        with pytest.raises(ValueError):
            manager.add_task("bad", priority=bad)
    assert manager.get_task(manager.add_task("ok", priority=5))["priority"] == 5
    assert manager.get_task(manager.add_task("low", priority=1))["priority"] == 1


def test_due_at_validation_and_round_trip():
    manager = TaskManager()
    task_id = manager.add_task("timed", due_at="2030-01-02T03:04:05+00:00")
    assert manager.get_task(task_id)["due_at"] == "2030-01-02T03:04:05+00:00"
    with pytest.raises(ValueError):
        manager.add_task("bad", due_at="not-a-date")


def test_update_fields_and_unknown_id():
    manager = TaskManager()
    task_id = manager.add_task("x")
    manager.update_task(task_id, title="y", priority=1, tags=["a"])
    task = manager.get_task(task_id)
    assert task["title"] == "y"
    assert task["priority"] == 1
    assert task["tags"] == ["a"]
    with pytest.raises(KeyError):
        manager.update_task("missing", title="z")


def test_set_status_valid_and_invalid():
    manager = TaskManager()
    task_id = manager.add_task("x")
    for status in ("todo", "doing", "done"):
        manager.set_status(task_id, status)
        assert manager.get_task(task_id)["status"] == status
    with pytest.raises(ValueError):
        manager.set_status(task_id, "archived")
    with pytest.raises(KeyError):
        manager.set_status("missing", "done")


def test_delete_refuses_while_dependents_exist():
    manager = TaskManager()
    first = manager.add_task("first")
    second = manager.add_task("second", depends_on=[first])
    with pytest.raises(ValueError):
        manager.delete_task(first)
    manager.delete_task(second)
    manager.delete_task(first)
    with pytest.raises(KeyError):
        manager.get_task(first)


def test_unknown_dependency_is_rejected():
    manager = TaskManager()
    with pytest.raises(ValueError):
        manager.add_task("x", depends_on=["does-not-exist"])


def test_cycle_detection_leaves_state_unchanged():
    manager = TaskManager()
    first = manager.add_task("first")
    second = manager.add_task("second", depends_on=[first])
    with pytest.raises(ValueError):
        manager.update_task(first, depends_on=[second])
    assert manager.get_task(first)["depends_on"] == []
    assert manager.get_task(second)["depends_on"] == [first]


def test_ready_tasks_respects_dependencies():
    manager = TaskManager()
    first = manager.add_task("first")
    second = manager.add_task("second", depends_on=[first])
    assert {t["id"] for t in manager.ready_tasks()} == {first}
    manager.set_status(first, "done")
    assert {t["id"] for t in manager.ready_tasks()} == {second}
    manager.set_status(second, "done")
    assert manager.ready_tasks() == []


def test_list_tasks_filters():
    manager = TaskManager()
    infra = manager.add_task("infra", tags=["infra"], priority=5)
    docs = manager.add_task("docs", tags=["docs"], priority=1)
    manager.set_status(docs, "doing")
    assert {t["id"] for t in manager.list_tasks(status="doing")} == {docs}
    assert {t["id"] for t in manager.list_tasks(priority=5)} == {infra}
    assert {t["id"] for t in manager.list_tasks(tag="infra")} == {infra}
    assert {t["id"] for t in manager.list_tasks()} == {infra, docs}


def test_list_tasks_orders_by_priority_desc():
    manager = TaskManager()
    low = manager.add_task("low", priority=1)
    high = manager.add_task("high", priority=5)
    mid = manager.add_task("mid", priority=3)
    assert [t["id"] for t in manager.list_tasks()] == [high, mid, low]


def test_save_load_round_trip(tmp_path):
    manager = TaskManager()
    first = manager.add_task("first", priority=4, tags=["x"], due_at="2031-05-06T07:08:09+00:00")
    second = manager.add_task("second", depends_on=[first])
    manager.set_status(first, "doing")
    path = tmp_path / "tasks.json"
    manager.save(str(path))
    assert isinstance(json.loads(path.read_text()), dict)
    loaded = TaskManager.load(str(path))
    assert loaded.get_task(first) == manager.get_task(first)
    assert loaded.get_task(second)["depends_on"] == [first]
    assert {t["id"] for t in loaded.list_tasks()} == {first, second}
