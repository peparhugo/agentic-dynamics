import json
import os

import pytest

import app as app_module


# ── Auth: register ─────────────────────────────────────────────

def test_register_success(client):
    resp = client.post(
        "/auth/register", json={"username": "carol", "password": "pw"}
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "carol"
    assert "token" in data


def test_register_missing_fields(client):
    assert client.post("/auth/register", json={}).status_code == 400
    assert client.post("/auth/register", json={"username": "x"}).status_code == 400
    assert client.post("/auth/register", json={"password": "x"}).status_code == 400


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "dave", "password": "pw"})
    resp = client.post("/auth/register", json={"username": "dave", "password": "pw"})
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_hashes_password(client):
    client.post("/auth/register", json={"username": "eve", "password": "pw"})
    with open(app_module.DATA_FILE) as f:
        store = json.load(f)
    user = next(u for u in store["users"] if u["username"] == "eve")
    assert "password_hash" in user
    assert user["password_hash"] != "pw"


# ── Auth: login ────────────────────────────────────────────────

def test_login_success(client):
    client.post("/auth/register", json={"username": "frank", "password": "pw"})
    resp = client.post(
        "/auth/login", json={"username": "frank", "password": "pw"}
    )
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "frank", "password": "pw"})
    resp = client.post(
        "/auth/login", json={"username": "frank", "password": "nope"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/auth/login", json={"username": "ghost", "password": "pw"}
    )
    assert resp.status_code == 401


# ── Auth: protecting /tasks ────────────────────────────────────

def test_tasks_require_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/tasks", headers=headers).status_code == 401
    assert client.post("/tasks", json={"title": "x"}, headers=headers).status_code == 401


def test_tasks_reject_garbage_header(client):
    headers = {"Authorization": "Basic abc"}
    assert client.get("/tasks", headers=headers).status_code == 401


# ── Tasks: CRUD (authed) ───────────────────────────────────────

def test_create_task(client, auth):
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=auth)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["id"] == 1


def test_create_task_missing_title(client, auth):
    resp = client.post("/tasks", json={}, headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client, auth):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth)
    assert resp.status_code == 400


def test_list_tasks_ordered_desc(client, auth):
    client.post("/tasks", json={"title": "first"}, headers=auth)
    client.post("/tasks", json={"title": "second"}, headers=auth)
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()["data"]]
    assert titles == ["second", "first"]


def test_get_task(client, auth):
    created = client.post("/tasks", json={"title": "alpha"}, headers=auth).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "alpha"


def test_get_task_not_found(client, auth):
    resp = client.get("/tasks/999", headers=auth)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task(client, auth):
    created = client.post("/tasks", json={"title": "alpha"}, headers=auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "beta", "status": "done"}, headers=auth
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "beta"
    assert data["status"] == "done"


def test_update_task_partial(client, auth):
    created = client.post("/tasks", json={"title": "alpha"}, headers=auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth
    )
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert data["title"] == "alpha"


def test_update_task_not_found(client, auth):
    resp = client.put("/tasks/999", json={"title": "x"}, headers=auth)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_persists_to_flat_file(client, auth):
    client.post("/tasks", json={"title": "persisted"}, headers=auth)
    with open(app_module.DATA_FILE) as f:
        store = json.load(f)
    assert any(t["title"] == "persisted" for t in store["tasks"])


# ── Ownership isolation ────────────────────────────────────────

def test_users_only_see_own_tasks(client, auth, bob_auth):
    client.post("/tasks", json={"title": "alice task"}, headers=auth)
    client.post("/tasks", json={"title": "bob task"}, headers=bob_auth)

    alice_titles = [t["title"] for t in client.get("/tasks", headers=auth).get_json()["data"]]
    bob_titles = [t["title"] for t in client.get("/tasks", headers=bob_auth).get_json()["data"]]

    assert alice_titles == ["alice task"]
    assert bob_titles == ["bob task"]


def test_cannot_read_others_task(client, auth, bob_auth):
    created = client.post("/tasks", json={"title": "private"}, headers=auth).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob_auth)
    assert resp.status_code == 404


def test_cannot_update_others_task(client, auth, bob_auth):
    created = client.post("/tasks", json={"title": "private"}, headers=auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "hacked"}, headers=bob_auth
    )
    assert resp.status_code == 404


# ── Migration ──────────────────────────────────────────────────

def test_migration_assigns_legacy_tasks(tmp_path):
    store = {
        "tasks": [
            {
                "id": 1,
                "title": "old task",
                "status": "pending",
                "created_at": "2020-01-01T00:00:00",
            }
        ],
        "next_id": 2,
    }
    data_file = str(tmp_path / "old.json")
    with open(data_file, "w") as f:
        json.dump(store, f)

    app_module.DATA_FILE = data_file
    app_module.init_store()

    with open(data_file) as f:
        migrated = json.load(f)
    assert migrated["tasks"][0]["owner_id"] is not None
    assert "users" in migrated
    assert any(u["username"] == "legacy" for u in migrated["users"])
    assert migrated["tasks"][0]["title"] == "old task"
