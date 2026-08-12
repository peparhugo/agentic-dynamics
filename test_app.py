import time

import pytest


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(client, username="alice", password="secret"):
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def alice(client):
    register(client)
    return client


# ── Auth ──────────────────────────────────────────────────────

def test_register_creates_user(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["username"] == "alice"
    assert "password_hash" not in data


def test_register_duplicate_username_returns_409(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_missing_fields_returns_400(client):
    resp = register(client, username="", password="")
    assert resp.status_code == 400
    resp = register(client, username="bob", password="")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_login_returns_token(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    assert resp.get_json()["token"]


def test_login_invalid_credentials_returns_401(client):
    register(client)
    resp = login(client, password="wrong")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user_returns_401(client):
    resp = login(client, username="nobody")
    assert resp.status_code == 401


# ── Protected endpoints ───────────────────────────────────────

def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_with_invalid_token_returns_401(client):
    headers = {"Authorization": "Bearer not.a.token"}
    assert client.get("/tasks", headers=headers).status_code == 401


def test_tasks_with_bearer_prefix_missing_returns_401(client):
    register(client)
    token = login(client).get_json()["token"]
    assert client.get("/tasks", headers={"Authorization": token}).status_code == 401


# ── Task CRUD (authenticated) ─────────────────────────────────

def test_post_create_task(alice):
    resp = alice.post("/tasks", json={"title": "write code"}, headers=auth_header(alice))
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "write code"
    assert data["status"] == "pending"
    assert data["owner_id"] == 1
    assert data["created_at"]


def test_post_missing_title_returns_400(alice):
    resp = alice.post("/tasks", json={}, headers=auth_header(alice))
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"]


def test_post_empty_title_returns_400(alice):
    resp = alice.post("/tasks", json={"title": "   "}, headers=auth_header(alice))
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_get_list_ordered_by_created_at_desc(alice):
    alice.post("/tasks", json={"title": "first"}, headers=auth_header(alice))
    time.sleep(0.01)
    alice.post("/tasks", json={"title": "second"}, headers=auth_header(alice))
    time.sleep(0.01)
    alice.post("/tasks", json={"title": "third"}, headers=auth_header(alice))

    resp = alice.get("/tasks", headers=auth_header(alice))
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


def test_get_single_task(alice):
    created = alice.post(
        "/tasks", json={"title": "single"}, headers=auth_header(alice)
    ).get_json()
    resp = alice.get(f"/tasks/{created['id']}", headers=auth_header(alice))
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "single"


def test_get_task_not_found_returns_404(alice):
    resp = alice.get("/tasks/999", headers=auth_header(alice))
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_put_update_title(alice):
    created = alice.post(
        "/tasks", json={"title": "old"}, headers=auth_header(alice)
    ).get_json()
    resp = alice.put(
        f"/tasks/{created['id']}", json={"title": "new"}, headers=auth_header(alice)
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "pending"


def test_put_update_status(alice):
    created = alice.post(
        "/tasks", json={"title": "t"}, headers=auth_header(alice)
    ).get_json()
    resp = alice.put(
        f"/tasks/{created['id']}", json={"status": "done"}, headers=auth_header(alice)
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"


def test_put_update_title_and_status(alice):
    created = alice.post(
        "/tasks", json={"title": "t"}, headers=auth_header(alice)
    ).get_json()
    resp = alice.put(
        f"/tasks/{created['id']}",
        json={"title": "new", "status": "in_progress"},
        headers=auth_header(alice),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "in_progress"


def test_put_task_not_found_returns_404(alice):
    resp = alice.put("/tasks/999", json={"title": "nope"}, headers=auth_header(alice))
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── Per-user isolation ────────────────────────────────────────

def test_users_only_see_their_own_tasks(client):
    register(client, "alice")
    register(client, "bob")

    alice_headers = auth_header(client, "alice")
    bob_headers = auth_header(client, "bob")

    alice_task = client.post(
        "/tasks", json={"title": "alice task"}, headers=alice_headers
    ).get_json()
    client.post("/tasks", json={"title": "bob task"}, headers=bob_headers)

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()
    assert [t["title"] for t in alice_tasks] == ["alice task"]

    resp = client.get(f"/tasks/{alice_task['id']}", headers=bob_headers)
    assert resp.status_code == 404

    resp = client.put(
        f"/tasks/{alice_task['id']}", json={"title": "hacked"}, headers=bob_headers
    )
    assert resp.status_code == 404

    assert client.get("/tasks", headers=bob_headers).get_json()[0]["title"] == "bob task"
