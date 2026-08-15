import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.app.config["DATABASE"] = str(tmp_path / "tasks.db")
    app_module.app.config["TESTING"] = True
    app_module.init_db()
    with app_module.app.test_client() as client:
        yield client


def create_task(client, title, status=None):
    payload = {"title": title}
    if status is not None:
        payload["status"] = status
    return client.post("/tasks", json=payload)


def test_create_task_defaults_to_pending(client):
    resp = create_task(client, "Buy milk")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert body["created_at"]


def test_create_task_missing_title_returns_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title_returns_400(client):
    resp = create_task(client, "   ")
    assert resp.status_code == 400


def test_create_task_with_status_done(client):
    resp = create_task(client, "Ship package", status="done")
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "done"


def test_create_task_invalid_status_returns_422(client):
    resp = create_task(client, "Do thing", status="archived")
    assert resp.status_code == 422


def test_list_tasks_orders_by_created_at_desc(client):
    create_task(client, "First")
    create_task(client, "Second")
    create_task(client, "Third")
    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Third", "Second", "First"]


def test_get_task(client):
    create_task(client, "Read book")
    resp = client.get("/tasks/1")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Read book"


def test_get_task_not_found_returns_404(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    create_task(client, "Old title")
    resp = client.put("/tasks/1", json={"title": "New title"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client):
    create_task(client, "Task")
    resp = client.put("/tasks/1", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"


def test_update_task_invalid_status_returns_422(client):
    create_task(client, "Task")
    resp = client.put("/tasks/1", json={"status": "in-progress"})
    assert resp.status_code == 422


def test_update_task_not_found_returns_404(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404


def test_created_at_is_iso8601_text(client):
    create_task(client, "Stored datetime")
    with app_module.get_db() as conn:
        row = conn.execute("SELECT created_at FROM tasks WHERE id = 1").fetchone()
    assert isinstance(row["created_at"], str)
