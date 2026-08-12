import importlib

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_tasks.db")
    monkeypatch.setenv("DATABASE", db_file)
    app = importlib.import_module("app")
    monkeypatch.setattr(app, "DATABASE", db_file)
    app.init_db()
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c


@pytest.fixture()
def auth(client):
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )
    assert resp.status_code == 201
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _register(client, username, password):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def _login(client, username, password):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def _create(client, title, headers=None):
    return client.post("/tasks", json={"title": title}, headers=headers)


# --- auth endpoint tests ---


def test_register_creates_user(client):
    resp = _register(client, "alice", "secret")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["id"] == 1
    assert "token" in data


def test_register_requires_username(client):
    resp = client.post("/auth/register", json={"password": "secret"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_requires_password(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username_returns_409(client):
    _register(client, "alice", "secret")
    resp = _register(client, "alice", "other")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_empty_username_returns_400(client):
    resp = _register(client, "   ", "secret")
    assert resp.status_code == 400


def test_login_returns_token(client):
    _register(client, "alice", "secret")
    resp = _login(client, "alice", "secret")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "alice"
    assert "token" in data


def test_login_invalid_password_returns_401(client):
    _register(client, "alice", "secret")
    resp = _login(client, "alice", "wrong")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user_returns_401(client):
    resp = _login(client, "nobody", "secret")
    assert resp.status_code == 401


# --- task auth protection tests ---


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


def test_list_tasks_requires_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401


def test_get_task_requires_auth(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 401


def test_update_task_requires_auth(client):
    resp = client.put("/tasks/1", json={"title": "x"})
    assert resp.status_code == 401


def test_invalid_token_returns_401(client):
    resp = client.get(
        "/tasks", headers={"Authorization": "Bearer not-a-valid-token"}
    )
    assert resp.status_code == 401


def test_malformed_auth_header_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "Token abc"})
    assert resp.status_code == 401


# --- existing task tests, now authenticated ---


def test_create_task(client, auth):
    resp = _create(client, "Buy milk", auth)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title_returns_400(client, auth):
    resp = client.post("/tasks", json={}, headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title_returns_400(client, auth):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_missing_body_returns_400(client, auth):
    resp = client.post("/tasks", data="", headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_assigns_incrementing_ids(client, auth):
    for i in range(1, 4):
        resp = _create(client, f"task {i}", auth)
        assert resp.status_code == 201
        assert resp.get_json()["id"] == i


def test_list_tasks_ordered_by_created_at_desc(client, auth):
    for i in range(1, 4):
        _create(client, f"task {i}", auth)
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert [t["title"] for t in data] == ["task 3", "task 2", "task 1"]


def test_list_tasks_empty(client, auth):
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_task(client, auth):
    created = _create(client, "Buy milk", auth).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"


def test_get_task_not_found_returns_404(client, auth):
    resp = client.get("/tasks/999", headers=auth)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client, auth):
    created = _create(client, "Buy milk", auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Buy almond milk", "status": "done"},
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy almond milk"
    assert data["status"] == "done"


def test_update_task_title_only(client, auth):
    created = _create(client, "Buy milk", auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "New title"}, headers=auth
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status_only(client, auth):
    created = _create(client, "Buy milk", auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "in_progress"


def test_update_task_not_found_returns_404(client, auth):
    resp = client.put("/tasks/999", json={"title": "x"}, headers=auth)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# --- ownership tests ---


def test_users_only_see_their_own_tasks(client, auth):
    bob = _register(client, "bob", "secret").get_json()
    bob_auth = {"Authorization": f"Bearer {bob['token']}"}
    _create(client, "alice task", auth)
    _create(client, "bob task", bob_auth)
    resp = client.get("/tasks", headers=auth)
    assert [t["title"] for t in resp.get_json()] == ["alice task"]
    resp = client.get("/tasks", headers=bob_auth)
    assert [t["title"] for t in resp.get_json()] == ["bob task"]


def test_user_cannot_get_others_task(client, auth):
    bob = _register(client, "bob", "secret").get_json()
    bob_auth = {"Authorization": f"Bearer {bob['token']}"}
    created = _create(client, "alice task", auth).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob_auth)
    assert resp.status_code == 404


def test_user_cannot_update_others_task(client, auth):
    bob = _register(client, "bob", "secret").get_json()
    bob_auth = {"Authorization": f"Bearer {bob['token']}"}
    created = _create(client, "alice task", auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "hijacked"}, headers=bob_auth
    )
    assert resp.status_code == 404
