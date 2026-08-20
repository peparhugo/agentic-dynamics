import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "test.db"))
    app_module.init_db()
    app_module.migrate()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def token(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    return resp.get_json()["token"]


@pytest.fixture()
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, title, headers):
    return client.post("/tasks", json={"title": title}, headers=headers)


# ── Auth tests ────────────────────────────────────────────────

def test_register_success(client):
    resp = client.post("/auth/register", json={"username": "bob", "password": "pw"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "bob"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_username_409(client):
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    resp = client.post("/auth/register", json={"username": "bob", "password": "other"})
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_missing_fields_400(client):
    assert client.post("/auth/register", json={"username": "bob"}).status_code == 400
    assert client.post("/auth/register", json={"password": "pw"}).status_code == 400
    assert client.post("/auth/register", json={}).status_code == 400


def test_login_success_returns_token(client):
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "pw"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert data["user_id"] == 1


def test_login_wrong_password_401(client):
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "nope"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user_401(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "pw"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


# ── Auth enforcement tests ────────────────────────────────────

def test_tasks_require_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/tasks", headers=bad).status_code == 401


def test_tasks_reject_missing_bearer_scheme(client):
    bad = {"Authorization": "not-bearer-format"}
    assert client.get("/tasks", headers=bad).status_code == 401


# ── Task tests (authenticated) ────────────────────────────────

def test_create_task(client, auth_headers):
    resp = _create(client, "Buy milk", auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["id"] == 1
    assert data["owner_id"] == 1
    assert "created_at" in data


def test_create_task_missing_title_400(client, auth_headers):
    resp = client.post("/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title_400(client, auth_headers):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_by_created_at_desc(client, auth_headers):
    _create(client, "first", auth_headers)
    _create(client, "second", auth_headers)
    _create(client, "third", auth_headers)
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    tasks = resp.get_json()["data"]
    assert [t["title"] for t in tasks] == ["third", "second", "first"]


def test_get_single_task(client, auth_headers):
    created = _create(client, "Buy milk", auth_headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Buy milk"


def test_get_task_not_found_404(client, auth_headers):
    resp = client.get("/tasks/999", headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client, auth_headers):
    created = _create(client, "Old title", auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "New title"}, headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client, auth_headers):
    created = _create(client, "Buy milk", auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "done"}, headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Buy milk"


def test_update_task_title_and_status(client, auth_headers):
    created = _create(client, "Old title", auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "in_progress"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "in_progress"


def test_update_task_not_found_404(client, auth_headers):
    resp = client.put("/tasks/999", json={"title": "nope"}, headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── User isolation tests ──────────────────────────────────────

def test_users_see_only_their_own_tasks(client):
    client.post("/auth/register", json={"username": "alice", "password": "pw"})
    client.post("/auth/register", json={"username": "bob", "password": "pw"})

    alice = client.post("/auth/login", json={"username": "alice", "password": "pw"}).get_json()["token"]
    bob = client.post("/auth/login", json={"username": "bob", "password": "pw"}).get_json()["token"]

    alice_headers = {"Authorization": f"Bearer {alice}"}
    bob_headers = {"Authorization": f"Bearer {bob}"}

    alice_task = _create(client, "alice task", alice_headers).get_json()
    bob_task = _create(client, "bob task", bob_headers).get_json()

    alice_list = client.get("/tasks", headers=alice_headers).get_json()["data"]
    bob_list = client.get("/tasks", headers=bob_headers).get_json()["data"]

    assert [t["title"] for t in alice_list] == ["alice task"]
    assert [t["title"] for t in bob_list] == ["bob task"]

    assert client.get(f"/tasks/{bob_task['id']}", headers=alice_headers).status_code == 404
    assert client.get(f"/tasks/{alice_task['id']}", headers=bob_headers).status_code == 404


def test_user_cannot_update_another_users_task(client):
    client.post("/auth/register", json={"username": "alice", "password": "pw"})
    client.post("/auth/register", json={"username": "bob", "password": "pw"})

    alice = client.post("/auth/login", json={"username": "alice", "password": "pw"}).get_json()["token"]
    bob = client.post("/auth/login", json={"username": "bob", "password": "pw"}).get_json()["token"]

    alice_headers = {"Authorization": f"Bearer {alice}"}
    bob_headers = {"Authorization": f"Bearer {bob}"}

    alice_task = _create(client, "alice task", alice_headers).get_json()
    resp = client.put(
        f"/tasks/{alice_task['id']}", json={"title": "hijacked"}, headers=bob_headers
    )
    assert resp.status_code == 404

    still = client.get(f"/tasks/{alice_task['id']}", headers=alice_headers).get_json()
    assert still["title"] == "alice task"
