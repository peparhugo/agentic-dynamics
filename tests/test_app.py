import json

import pytest

import app as app_module


@pytest.fixture
def client(tmp_path):
    app_module.app.config["STORAGE_FILE"] = str(tmp_path / "tasks.json")
    app_module.app.config["USERS_FILE"] = str(tmp_path / "users.json")
    app_module.app.config["TESTING"] = True
    app_module.app.config["SECRET_KEY"] = "test-secret-key-for-hmac-sha256!"
    app_module.init_storage()
    return app_module.app.test_client()


@pytest.fixture
def storage_file():
    return app_module.app.config["STORAGE_FILE"]


@pytest.fixture
def users_file():
    return app_module.app.config["USERS_FILE"]


def _register(client, username, password="secret-password"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def _login(client, username, password="secret-password"):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def _token(client, username, password="secret-password"):
    _register(client, username, password)
    resp = _login(client, username, password)
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, title):
    return client.post("/tasks", json={"title": title}, headers=_auth(token))


# ── Auth ─────────────────────────────────────────────────────────


def test_register_creates_user(client, users_file):
    resp = _register(client, "alice")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert "id" in data
    with open(users_file) as f:
        users = json.load(f)
    assert [u["username"] for u in users] == ["alice"]


def test_register_requires_username_and_password(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={"password": "secret-password"})
    assert resp.status_code == 400


def test_register_rejects_duplicate_username(client):
    assert _register(client, "alice").status_code == 201
    resp = _register(client, "alice")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_password_stored_hashed(client, users_file):
    _register(client, "alice", password="hunter2hunter")
    with open(users_file) as f:
        users = json.load(f)
    stored = users[0]["password_hash"]
    assert stored != "hunter2hunter"
    assert app_module.verify_password("hunter2hunter", stored)
    assert not app_module.verify_password("wrong", stored)


def test_login_returns_jwt_token(client):
    _register(client, "alice")
    resp = _login(client, "alice")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "alice"
    assert isinstance(data["token"], str) and data["token"]


def test_login_rejects_invalid_credentials(client):
    _register(client, "alice")
    resp = _login(client, "alice", password="wrong-password")
    assert resp.status_code == 401
    resp = _login(client, "nobody")
    assert resp.status_code == 401


def test_login_requires_username_and_password(client):
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── Task endpoints require auth ──────────────────────────────────


def test_list_tasks_requires_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Nope"})
    assert resp.status_code == 401


def test_get_task_requires_auth(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 401


def test_update_task_requires_auth(client):
    resp = client.put("/tasks/1", json={"title": "Nope"})
    assert resp.status_code == 401


def test_invalid_token_returns_401(client):
    resp = client.get("/tasks", headers=_auth("not-a-real-token"))
    assert resp.status_code == 401


def test_missing_bearer_prefix_returns_401(client):
    token = _token(client, "alice")
    resp = client.get("/tasks", headers={"Authorization": token})
    assert resp.status_code == 401


# ── Task CRUD ────────────────────────────────────────────────────


def test_create_task(client):
    token = _token(client, "alice")
    resp = _create(client, token, "Write report")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Write report"
    assert data["status"] == "pending"
    assert data["owner_id"]
    assert data["created_at"]


def test_create_task_returns_400_when_title_missing(client):
    token = _token(client, "alice")
    resp = client.post("/tasks", json={}, headers=_auth(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_returns_400_when_title_empty(client):
    token = _token(client, "alice")
    resp = client.post("/tasks", json={"title": ""}, headers=_auth(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_by_created_at_desc(client):
    token = _token(client, "alice")
    _create(client, token, "First")
    _create(client, token, "Second")
    resp = client.get("/tasks", headers=_auth(token))
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["Second", "First"]
    assert [t["created_at"] for t in tasks] == sorted(
        [t["created_at"] for t in tasks], reverse=True
    )


def test_get_task(client):
    token = _token(client, "alice")
    created = _create(client, token, "Buy milk").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_returns_404_when_not_found(client):
    token = _token(client, "alice")
    resp = client.get("/tasks/999", headers=_auth(token))
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    token = _token(client, "alice")
    created = _create(client, token, "Old title").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    token = _token(client, "alice")
    created = _create(client, token, "Do it").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "done"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Do it"


def test_update_task_title_and_status(client):
    token = _token(client, "alice")
    created = _create(client, token, "A").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "B", "status": "in_progress"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "B"
    assert data["status"] == "in_progress"


def test_update_task_returns_404_when_not_found(client):
    token = _token(client, "alice")
    resp = client.put(
        "/tasks/999", json={"title": "X"}, headers=_auth(token)
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_returns_400_when_title_emptied(client):
    token = _token(client, "alice")
    created = _create(client, token, "A").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": ""},
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── Ownership isolation ──────────────────────────────────────────


def test_each_user_sees_only_their_own_tasks(client):
    alice = _token(client, "alice")
    bob = _token(client, "bob")
    _create(client, alice, "Alice task")
    _create(client, bob, "Bob task")

    alice_tasks = client.get("/tasks", headers=_auth(alice)).get_json()
    assert [t["title"] for t in alice_tasks] == ["Alice task"]

    bob_tasks = client.get("/tasks", headers=_auth(bob)).get_json()
    assert [t["title"] for t in bob_tasks] == ["Bob task"]


def test_user_cannot_get_others_task(client):
    alice = _token(client, "alice")
    bob = _token(client, "bob")
    created = _create(client, alice, "Alice private").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=_auth(bob))
    assert resp.status_code == 404
    resp = client.get(f"/tasks/{created['id']}", headers=_auth(alice))
    assert resp.status_code == 200


def test_user_cannot_update_others_task(client):
    alice = _token(client, "alice")
    bob = _token(client, "bob")
    created = _create(client, alice, "Alice private").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Hijacked"},
        headers=_auth(bob),
    )
    assert resp.status_code == 404
    resp = client.get(f"/tasks/{created['id']}", headers=_auth(alice))
    assert resp.get_json()["title"] == "Alice private"


# ── Persistence & migration ──────────────────────────────────────


def test_data_stored_in_flat_file(client, storage_file):
    token = _token(client, "alice")
    _create(client, token, "Persist me")
    with open(storage_file) as f:
        stored = json.load(f)
    assert isinstance(stored, list)
    assert stored[0]["title"] == "Persist me"
    assert stored[0]["id"] == 1
    assert stored[0]["owner_id"]


def test_data_persists_across_requests(client):
    token = _token(client, "alice")
    _create(client, token, "One")
    _create(client, token, "Two")
    tasks = client.get("/tasks", headers=_auth(token)).get_json()
    assert [t["title"] for t in tasks] == ["Two", "One"]


def test_no_sqlite_database_file_created(client, tmp_path):
    token = _token(client, "alice")
    _create(client, token, "No db")
    files = {p.name for p in tmp_path.iterdir()}
    assert not any(name.endswith(".db") for name in files)


def test_migration_assigns_owner_to_existing_tasks(tmp_path):
    app_module.app.config["STORAGE_FILE"] = str(tmp_path / "tasks.json")
    app_module.app.config["USERS_FILE"] = str(tmp_path / "users.json")
    app_module.app.config["SECRET_KEY"] = "migration-secret-for-hmac-sha256!"
    with open(tmp_path / "tasks.json", "w") as f:
        json.dump(
            [
                {
                    "id": 1,
                    "title": "Legacy task",
                    "status": "pending",
                    "created_at": "2023-01-01T00:00:00",
                }
            ],
            f,
        )
    app_module.init_storage()
    with open(tmp_path / "tasks.json") as f:
        tasks = json.load(f)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Legacy task"
    assert tasks[0]["owner_id"] is not None
    with open(tmp_path / "users.json") as f:
        users = json.load(f)
    assert users[0]["username"] == "legacy"
    assert users[0]["id"] == tasks[0]["owner_id"]
