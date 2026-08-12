import os

import pytest

os.environ["DATABASE"] = "test_tasks.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FAKE_REDIS"] = "1"
import app as task_app

task_app.init_db()


@pytest.fixture()
def client():
    task_app.app.config["TESTING"] = True
    with task_app.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    yield
    task_app.limiter.reset()
    with task_app.get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM users")
        conn.commit()


def register_and_login(client, username="alice", password="password123"):
    resp = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert resp.status_code == 201
    resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_task(client):
    token = register_and_login(client)
    resp = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=auth(token)
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["id"] > 0
    assert "created_at" in data


def test_create_task_missing_title(client):
    token = register_and_login(client)
    resp = client.post("/tasks", json={}, headers=auth(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()

    resp = client.post("/tasks", json={"title": ""}, headers=auth(token))
    assert resp.status_code == 400

    resp = client.post("/tasks", headers=auth(token))
    assert resp.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client):
    token = register_and_login(client)
    client.post("/tasks", json={"title": "first"}, headers=auth(token))
    client.post("/tasks", json={"title": "second"}, headers=auth(token))
    resp = client.get("/tasks", headers=auth(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 2
    assert [t["title"] for t in data["data"]] == ["second", "first"]


def test_get_task(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Get task"}, headers=auth(token)
    ).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth(token))
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Get task"


def test_get_task_not_found(client):
    token = register_and_login(client)
    resp = client.get("/tasks/9999", headers=auth(token))
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Old"}, headers=auth(token)
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New", "status": "done"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


def test_update_task_partial(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Partial"}, headers=auth(token)
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Partial"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    token = register_and_login(client)
    resp = client.put(
        "/tasks/9999", json={"title": "x"}, headers=auth(token)
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_empty_list(client):
    token = register_and_login(client)
    resp = client.get("/tasks", headers=auth(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"] == []
    assert data["next_cursor"] is None
    assert data["total"] == 0


# ── Auth tests ─────────────────────────────────────────────────


def test_register_creates_user(client):
    resp = client.post(
        "/auth/register", json={"username": "bob", "password": "password123"}
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "bob"
    assert data["id"] > 0
    with task_app.get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = 'bob'"
        ).fetchone()
    assert user is not None
    assert user["password_hash"] != "password123"


def test_register_requires_fields(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400

    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400

    resp = client.post("/auth/register", json={"password": "password123"})
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register_and_login(client, username="alice")
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_login_returns_token(client):
    register_and_login(client, username="carol")
    resp = client.post(
        "/auth/login", json={"username": "carol", "password": "password123"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert data["username"] == "carol"


def test_login_invalid_credentials(client):
    register_and_login(client, username="dave")
    resp = client.post(
        "/auth/login", json={"username": "dave", "password": "wrong"}
    )
    assert resp.status_code == 401

    resp = client.post(
        "/auth/login", json={"username": "nobody", "password": "password123"}
    )
    assert resp.status_code == 401


def test_login_requires_fields(client):
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 400

    resp = client.post("/auth/login", json={"username": "bob"})
    assert resp.status_code == 400


def test_tasks_require_auth(client):
    resp = client.post("/tasks", json={"title": "x"})
    assert resp.status_code == 401

    resp = client.get("/tasks")
    assert resp.status_code == 401

    resp = client.get("/tasks/1")
    assert resp.status_code == 401

    resp = client.put("/tasks/1", json={"title": "x"})
    assert resp.status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = auth("not-a-valid-jwt")
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401

    resp = client.post("/tasks", json={"title": "x"}, headers=headers)
    assert resp.status_code == 401


def test_users_only_see_own_tasks(client):
    token_a = register_and_login(client, username="alice")
    token_b = register_and_login(client, username="bob")
    task = client.post(
        "/tasks", json={"title": "alice's task"}, headers=auth(token_a)
    ).get_json()

    resp = client.get("/tasks", headers=auth(token_b))
    assert resp.status_code == 200
    assert resp.get_json()["data"] == []

    resp = client.get(f"/tasks/{task['id']}", headers=auth(token_b))
    assert resp.status_code == 404

    resp = client.put(
        f"/tasks/{task['id']}", json={"title": "hacked"}, headers=auth(token_b)
    )
    assert resp.status_code == 404

    with task_app.get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task["id"],)
        ).fetchone()
    assert row["title"] == "alice's task"
