import pytest

from app import db, models


def _create(client, title="Buy groceries", **overrides):
    payload = {"title": title}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload)


# --- Creation -----------------------------------------------------------

def test_create_task_defaults(client):
    res = _create(client)
    assert res.status_code == 201
    data = res.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy groceries"
    assert data["description"] == ""
    assert data["status"] == "todo"
    assert data["priority"] == "medium"
    assert data["due_date"] is None
    assert data["created_at"]
    assert data["updated_at"]


def test_create_task_with_all_fields(client):
    res = _create(
        client,
        title="Ship report",
        description="Q3 report",
        status="in_progress",
        priority="high",
        due_date="2026-08-20",
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["title"] == "Ship report"
    assert data["description"] == "Q3 report"
    assert data["status"] == "in_progress"
    assert data["priority"] == "high"
    assert data["due_date"] == "2026-08-20"


def test_create_task_title_required(client):
    res = _create(client, title="")
    assert res.status_code == 400
    assert "title" in res.get_json()["error"]


def test_create_task_title_stripped(client):
    res = _create(client, title="   hello   ")
    assert res.status_code == 201
    assert res.get_json()["title"] == "hello"


def test_create_task_invalid_status(client):
    res = _create(client, status="nope")
    assert res.status_code == 400


def test_create_task_invalid_priority(client):
    res = _create(client, priority="urgent")
    assert res.status_code == 400


def test_create_task_invalid_body(client):
    res = client.post("/api/tasks", json=[1, 2, 3])
    assert res.status_code == 400


# --- Retrieval ----------------------------------------------------------

def test_get_task(client):
    _create(client)
    res = client.get("/api/tasks/1")
    assert res.status_code == 200
    assert res.get_json()["title"] == "Buy groceries"


def test_get_task_not_found(client):
    res = client.get("/api/tasks/999")
    assert res.status_code == 404


def test_list_tasks_empty(client):
    res = client.get("/api/tasks")
    assert res.status_code == 200
    assert res.get_json() == []


def test_list_tasks_multiple(client):
    _create(client, title="A")
    _create(client, title="B", priority="high")
    res = client.get("/api/tasks")
    assert res.status_code == 200
    assert [t["title"] for t in res.get_json()] == ["A", "B"]


def test_list_tasks_filter_by_status(client):
    _create(client, title="A", status="done")
    _create(client, title="B")
    res = client.get("/api/tasks?status=done")
    titles = [t["title"] for t in res.get_json()]
    assert titles == ["A"]


def test_list_tasks_filter_by_priority(client):
    _create(client, title="A", priority="low")
    _create(client, title="B", priority="high")
    res = client.get("/api/tasks?priority=high")
    titles = [t["title"] for t in res.get_json()]
    assert titles == ["B"]


def test_list_tasks_sort_desc(client):
    _create(client, title="A")
    _create(client, title="B")
    res = client.get("/api/tasks?sort=title&order=desc")
    titles = [t["title"] for t in res.get_json()]
    assert titles == ["B", "A"]


def test_list_tasks_invalid_sort(client):
    res = client.get("/api/tasks?sort=bogus")
    assert res.status_code == 400


def test_list_tasks_invalid_order(client):
    res = client.get("/api/tasks?order=sideways")
    assert res.status_code == 400


# --- Update -------------------------------------------------------------

def test_put_task(client):
    _create(client)
    res = client.put(
        "/api/tasks/1",
        json={"title": "New", "status": "done", "priority": "low"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"
    assert data["priority"] == "low"


def test_put_task_not_found(client):
    res = client.put("/api/tasks/999", json={"title": "x"})
    assert res.status_code == 404


def test_patch_task_partial(client):
    _create(client, priority="high")
    res = client.patch("/api/tasks/1", json={"status": "in_progress"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "in_progress"
    assert data["priority"] == "high"


def test_patch_task_not_found(client):
    res = client.patch("/api/tasks/999", json={"title": "x"})
    assert res.status_code == 404


def test_patch_task_invalid_status(client):
    _create(client)
    res = client.patch("/api/tasks/1", json={"status": "bogus"})
    assert res.status_code == 400


def test_update_task_clears_title_validation(client):
    _create(client)
    res = client.put("/api/tasks/1", json={"title": "   "})
    assert res.status_code == 400


# --- Deletion -----------------------------------------------------------

def test_delete_task(client):
    _create(client)
    res = client.delete("/api/tasks/1")
    assert res.status_code == 204
    assert client.get("/api/tasks/1").status_code == 404


def test_delete_task_not_found(client):
    res = client.delete("/api/tasks/999")
    assert res.status_code == 404


# --- Health -------------------------------------------------------------

def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


# --- Migrations ---------------------------------------------------------

def test_migrations_are_recorded(app):
    with app.app_context():
        rows = db.get_db().execute(
            "SELECT name FROM schema_migrations ORDER BY id"
        ).fetchall()
    names = [row["name"] for row in rows]
    assert "0001_create_tasks.sql" in names


def test_migrations_idempotent(app):
    with app.app_context():
        first = db.get_db().execute(
            "SELECT COUNT(*) AS c FROM schema_migrations"
        ).fetchone()["c"]
        newly = db.apply_migrations(db.get_db())
        second = db.get_db().execute(
            "SELECT COUNT(*) AS c FROM schema_migrations"
        ).fetchone()["c"]
    assert newly == []
    assert first == second


def test_model_validation_status():
    with pytest.raises(ValueError):
        models._validate({"status": "bogus"})


def test_model_validation_priority():
    with pytest.raises(ValueError):
        models._validate({"priority": "bogus"})
