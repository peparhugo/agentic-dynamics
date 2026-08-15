import pytest

import app as app_module


@pytest.fixture
def client(tmp_path):
    app_module.DATABASE = str(tmp_path / "test.db")
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "hunter2"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def other_auth_headers(client):
    client.post("/auth/register", json={"username": "bob", "password": "hunter2"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "hunter2"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth: registration ───────────────────────────────────────


def test_register_user(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert isinstance(data["id"], int)
    assert "password" not in data
    assert "password_hash" not in data


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "hunter2"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    resp = client.post("/auth/register", json={"username": "alice", "password": "other"})
    assert resp.status_code == 409
    assert "error" in resp.get_json()


# ── Auth: login ───────────────────────────────────────────────


def test_login_success(client):
    client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "hunter2"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["token"], str) and data["token"]


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "hunter2"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


# ── Auth: protection on /tasks ───────────────────────────────


def test_tasks_requires_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_rejects_invalid_token(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_rejects_missing_bearer_prefix(client, auth_headers):
    token = auth_headers["Authorization"].split(" ", 1)[1]
    resp = client.get("/tasks", headers={"Authorization": token})
    assert resp.status_code == 401


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


def test_users_only_see_own_tasks(client, auth_headers):
    client.post("/tasks", json={"title": "alice task"}, headers=auth_headers)
    bob_headers = other_auth_headers(client)
    client.post("/tasks", json={"title": "bob task"}, headers=bob_headers)

    alice_tasks = client.get("/tasks", headers=auth_headers).get_json()
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()

    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_cannot_get_other_users_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "alice task"}, headers=auth_headers).get_json()
    bob_headers = other_auth_headers(client)
    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_cannot_update_other_users_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "alice task"}, headers=auth_headers).get_json()
    bob_headers = other_auth_headers(client)
    resp = client.put(f"/tasks/{created['id']}", json={"title": "hijacked"}, headers=bob_headers)
    assert resp.status_code == 404


# ── Tasks: existing behavior (now under auth) ────────────────


def test_create_task(client, auth_headers):
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client, auth_headers):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client, auth_headers):
    resp = client.post("/tasks", headers=auth_headers)
    assert resp.status_code == 400


def test_list_tasks_empty(client, auth_headers):
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc(client, auth_headers):
    client.post("/tasks", json={"title": "first"}, headers=auth_headers)
    client.post("/tasks", json={"title": "second"}, headers=auth_headers)
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["title"] == "second"
    assert data[1]["title"] == "first"


def test_get_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "task"
    assert data["status"] == "pending"


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/tasks/999", headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client, auth_headers):
    created = client.post("/tasks", json={"title": "old"}, headers=auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "pending"


def test_update_task_status(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "task"


def test_update_task_title_and_status(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "renamed", "status": "done"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "renamed"
    assert data["status"] == "done"


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/tasks/999", json={"title": "x"}, headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_ids_assigned_manually_incrementing(client, auth_headers):
    t1 = client.post("/tasks", json={"title": "a"}, headers=auth_headers).get_json()
    t2 = client.post("/tasks", json={"title": "b"}, headers=auth_headers).get_json()
    assert t2["id"] == t1["id"] + 1


# ── Migration: pre-existing data without owner_id ────────────


def test_migration_preserves_existing_tasks_without_owner(client, tmp_path):
    """Simulates a pre-auth database: a tasks table with no owner_id column."""
    import sqlite3

    legacy_db = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(legacy_db)
    conn.execute(
        "CREATE TABLE tasks ("
        "  id INTEGER PRIMARY KEY,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO tasks (id, title, status, created_at) VALUES (1, 'legacy task', 'pending', '2020-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    app_module.DATABASE = legacy_db
    app_module.init_db()

    conn = sqlite3.connect(legacy_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tasks WHERE id = 1").fetchone()
    conn.close()

    assert row["title"] == "legacy task"
    assert row["owner_id"] is None
