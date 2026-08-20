import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db))
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture()
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_headers(client):
    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "secret"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth ──────────────────────────────────────────────────────

def test_register(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["id"] == 1
    assert "password_hash" not in data


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/register", json={"username": "alice", "password": "other"})
    assert resp.status_code == 409


def test_register_missing_fields(client):
    assert client.post("/auth/register", json={"username": "alice"}).status_code == 400
    assert client.post("/auth/register", json={"password": "secret"}).status_code == 400
    assert client.post("/auth/register", json={}).status_code == 400


def test_login_returns_token(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "secret"})
    assert resp.status_code == 401


# ── Tasks (protected) ─────────────────────────────────────────

def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/tasks", headers=headers).status_code == 401
    assert client.post("/tasks", json={"title": "x"}, headers=headers).status_code == 401


def test_create_task(client, auth_headers):
    resp = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Write tests"
    assert data["status"] == "pending"
    assert "created_at" in data
    assert data["owner_id"] == 1


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client, auth_headers):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
    assert resp.status_code == 400


def test_list_tasks(client, auth_headers):
    client.post("/tasks", json={"title": "first"}, headers=auth_headers)
    client.post("/tasks", json={"title": "second"}, headers=auth_headers)
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert len(tasks) == 2
    assert tasks[0]["title"] == "second"
    assert tasks[1]["title"] == "first"


def test_get_task(client, auth_headers):
    client.post("/tasks", json={"title": "hello"}, headers=auth_headers)
    resp = client.get("/tasks/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "hello"


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/tasks/999", headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task(client, auth_headers):
    client.post("/tasks", json={"title": "old"}, headers=auth_headers)
    resp = client.put("/tasks/1", json={"title": "new", "status": "done"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "done"


def test_update_task_partial(client, auth_headers):
    client.post("/tasks", json={"title": "old"}, headers=auth_headers)
    resp = client.put("/tasks/1", json={"status": "in progress"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "old"
    assert data["status"] == "in progress"


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/tasks/999", json={"title": "x"}, headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── Per-user isolation ────────────────────────────────────────

def test_users_see_only_their_own_tasks(client, auth_headers, other_headers):
    client.post("/tasks", json={"title": "alice task"}, headers=auth_headers)
    client.post("/tasks", json={"title": "bob task"}, headers=other_headers)

    alice_tasks = client.get("/tasks", headers=auth_headers).get_json()
    bob_tasks = client.get("/tasks", headers=other_headers).get_json()

    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_user_cannot_access_other_users_task(client, auth_headers, other_headers):
    client.post("/tasks", json={"title": "alice task"}, headers=auth_headers)
    resp = client.get("/tasks/1", headers=other_headers)
    assert resp.status_code == 404
    resp = client.put("/tasks/1", json={"title": "stolen"}, headers=other_headers)
    assert resp.status_code == 404
