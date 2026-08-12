import json
import os
import tempfile

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATA_FILE = str(tmp_path / "tasks.json")
    app_module.init_store()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def authed_client(client):
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )
    assert resp.status_code == 201
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    token = login.get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


def _token_for(client, username, password):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.get_json()["token"]


# ── Auth: register ────────────────────────────────────────────


def test_register_user(client):
    resp = client.post("/auth/register", json={"username": "bob", "password": "pw"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "bob"
    assert data["id"] == 1
    assert "password_hash" not in data
    assert "password" not in data


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    resp = client.post("/auth/register", json={"username": "bob", "password": "other"})
    assert resp.status_code == 409
    assert resp.get_json() == {"error": "username already taken"}


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={"password": "pw"})
    assert resp.status_code == 400


# ── Auth: login ───────────────────────────────────────────────


def test_login_returns_token(client):
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "pw"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "bob"
    assert data["id"] == 1
    assert data["token"]


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "invalid credentials"}


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "nobody", "password": "pw"})
    assert resp.status_code == 401


# ── Auth: password hashing ────────────────────────────────────


def test_passwords_are_hashed(authed_client):
    app_module.app.config["TESTING"] = True
    with open(app_module.DATA_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    user = data["users"][0]
    assert user["password_hash"] != "secret"
    assert user["password_hash"].startswith("scrypt") or user["password_hash"].startswith(
        "pbkdf2"
    )


# ── Tasks: auth required ──────────────────────────────────────


def test_tasks_require_token(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    resp = client.post("/tasks", json={"title": "X"})
    assert resp.status_code == 401
    resp = client.get("/tasks/1")
    assert resp.status_code == 401
    resp = client.put("/tasks/1", json={"title": "X"})
    assert resp.status_code == 401


def test_tasks_invalid_token(client):
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer not-a-real-token"
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "missing or invalid token"}


def test_tasks_malformed_auth_header(client):
    client.environ_base["HTTP_AUTHORIZATION"] = "Token abc"
    resp = client.get("/tasks")
    assert resp.status_code == 401


# ── Tasks: CRUD ───────────────────────────────────────────────


def test_create_task(authed_client):
    resp = authed_client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["id"] == 1
    assert data["created_at"]
    assert data["owner_id"] == 1


def test_create_task_missing_title(authed_client):
    resp = authed_client.post("/tasks", json={})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "title is required"}


def test_create_task_blank_title(authed_client):
    resp = authed_client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "title is required"}


def test_list_tasks_ordered_desc(authed_client):
    authed_client.post("/tasks", json={"title": "first"})
    authed_client.post("/tasks", json={"title": "second"})
    resp = authed_client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["second", "first"]
    assert [t["id"] for t in tasks] == [2, 1]


def test_get_task(authed_client):
    created = authed_client.post("/tasks", json={"title": "Get me"}).get_json()
    resp = authed_client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Get me"


def test_get_task_not_found(authed_client):
    resp = authed_client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_update_task(authed_client):
    created = authed_client.post("/tasks", json={"title": "Old"}).get_json()
    resp = authed_client.put(
        f"/tasks/{created['id']}", json={"title": "New", "status": "done"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"


def test_update_task_title_only(authed_client):
    created = authed_client.post("/tasks", json={"title": "Old"}).get_json()
    resp = authed_client.put(f"/tasks/{created['id']}", json={"title": "New"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "pending"


def test_update_task_status_only(authed_client):
    created = authed_client.post("/tasks", json={"title": "Old"}).get_json()
    resp = authed_client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Old"
    assert data["status"] == "done"


def test_update_task_not_found(authed_client):
    resp = authed_client.put("/tasks/999", json={"title": "Nope"})
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


# ── Tasks: ownership isolation ────────────────────────────────


def test_users_only_see_own_tasks(client):
    alice = client.post("/auth/register", json={"username": "alice", "password": "pw"})
    bob = client.post("/auth/register", json={"username": "bob", "password": "pw"})

    alice_token = _token_for(client, "alice", "pw")
    bob_token = _token_for(client, "bob", "pw")

    alice_id = alice.get_json()["id"]
    bob_id = bob.get_json()["id"]

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    alice_task = client.post("/tasks", json={"title": "Alice's task"}).get_json()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    bob_task = client.post("/tasks", json={"title": "Bob's task"}).get_json()

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    alice_list = client.get("/tasks").get_json()
    assert [t["title"] for t in alice_list] == ["Alice's task"]
    assert alice_list[0]["owner_id"] == alice_id

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    bob_list = client.get("/tasks").get_json()
    assert [t["title"] for t in bob_list] == ["Bob's task"]
    assert bob_list[0]["owner_id"] == bob_id

    resp = client.get(f"/tasks/{alice_task['id']}")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}

    resp = client.put(
        f"/tasks/{alice_task['id']}", json={"title": "hacked", "status": "done"}
    )
    assert resp.status_code == 404

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    assert client.get(f"/tasks/{alice_task['id']}").get_json()["title"] == "Alice's task"


# ── Migration ─────────────────────────────────────────────────


def test_legacy_data_migrated_without_breaking():
    with tempfile.TemporaryDirectory() as tmp:
        data_file = str(tmp) + "/tasks.json"
        legacy = {
            "tasks": [
                {
                    "id": 1,
                    "title": "legacy task",
                    "status": "pending",
                    "created_at": "2020-01-01T00:00:00",
                }
            ],
            "next_id": 2,
        }
        with open(data_file, "w", encoding="utf-8") as fh:
            json.dump(legacy, fh)

        app_module.DATA_FILE = data_file
        app_module.init_store()
        with open(data_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["tasks"][0]["title"] == "legacy task"
        assert data["tasks"][0]["status"] == "pending"
        assert data["tasks"][0]["owner_id"] is None
        assert data["next_id"] == 2
        assert data["users"] == []


# ── Storage ───────────────────────────────────────────────────


def test_storage_persists_to_flat_file(authed_client):
    authed_client.post("/tasks", json={"title": "Persist me"})
    assert os.path.exists(app_module.DATA_FILE)
    with open(app_module.DATA_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["tasks"][0]["title"] == "Persist me"
    assert data["tasks"][0]["owner_id"] == 1
