import os
import tempfile
from unittest import mock

import fakeredis
from fakeredis._connection import FakeRedisConnection
import pytest
import redis.connection
from limits.storage import RedisStorage
from limits.strategies import STRATEGIES as LIMIT_STRATEGIES

import app as task_app


@pytest.fixture()
def client():
    task_app.app.config["TESTING"] = True
    task_app.RATE_LIMIT = "100 per minute"
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    task_app.DATABASE = db_path
    task_app.init_db()
    pool = redis.connection.ConnectionPool(
        connection_class=FakeRedisConnection,
        server=fakeredis.FakeServer(),
    )
    storage = RedisStorage("redis://localhost:6379/0", connection_pool=pool)
    strategy_cls = LIMIT_STRATEGIES[task_app.limiter._strategy]
    task_app.limiter._storage = storage
    task_app.limiter._limiter = strategy_cls(storage)
    task_app.limiter._storage_dead = False
    with task_app.app.test_client() as c:
        yield c
    os.unlink(db_path)


def register_and_login(client, username="alice", password="secret-pass"):
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


# ── Auth ────────────────────────────────────────────────────────


def test_register(client):
    resp = client.post(
        "/auth/register", json={"username": "bob", "password": "hunter22"}
    )
    assert resp.status_code == 201
    assert resp.get_json()["username"] == "bob"


def test_register_requires_username_and_password(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register_and_login(client, username="dup")
    resp = client.post(
        "/auth/register", json={"username": "dup", "password": "another-pass"}
    )
    assert resp.status_code == 409


def test_login_returns_token(client):
    register_and_login(client)
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": "secret-pass"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["token"]


def test_login_invalid_credentials(client):
    resp = client.post(
        "/auth/login", json={"username": "nobody", "password": "wrong"}
    )
    assert resp.status_code == 401


# ── Missing / invalid tokens ────────────────────────────────────


def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = auth("not-a-real-token")
    assert client.get("/tasks", headers=headers).status_code == 401


# ── Tasks with auth ─────────────────────────────────────────────


def test_create_task(client):
    token = register_and_login(client)
    resp = client.post(
        "/tasks", json={"title": "Write code"}, headers=auth(token)
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Write code"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert data["created_at"]


def test_create_task_missing_title(client):
    token = register_and_login(client)
    resp = client.post("/tasks", json={}, headers=auth(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_by_created_at_desc(client):
    token = register_and_login(client)
    for title in ["first", "second", "third"]:
        client.post("/tasks", json={"title": title}, headers=auth(token))
    resp = client.get("/tasks", headers=auth(token))
    assert resp.status_code == 200
    tasks = resp.get_json()["data"]
    assert [t["title"] for t in tasks] == ["third", "second", "first"]


def test_get_task(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Find me"}, headers=auth(token)
    ).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth(token))
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Find me"


def test_get_task_not_found(client):
    token = register_and_login(client)
    resp = client.get("/tasks/9999", headers=auth(token))
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_update_task(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Old title"}, headers=auth(token)
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "done"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


# ── Notification trigger ────────────────────────────────────────


def test_update_task_to_completed_triggers_notification(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=auth(token)
    ).get_json()
    with mock.patch.object(task_app.send_notification_email, "delay") as delay:
        resp = client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    delay.assert_called_once_with("alice", "Ship feature")


def test_update_task_not_completed_does_not_trigger_notification(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Keep working"}, headers=auth(token)
    ).get_json()
    with mock.patch.object(task_app.send_notification_email, "delay") as delay:
        resp = client.put(
            f"/tasks/{created['id']}",
            json={"status": "in_progress"},
            headers=auth(token),
        )
    assert resp.status_code == 200
    delay.assert_not_called()


def test_completing_already_completed_task_does_not_retrigger(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Done deal"}, headers=auth(token)
    ).get_json()
    with mock.patch.object(task_app.send_notification_email, "delay") as delay:
        client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )
        delay.reset_mock()
        resp = client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )
    assert resp.status_code == 200
    delay.assert_not_called()


def test_update_task_not_found_does_not_trigger_notification(client):
    token = register_and_login(client)
    with mock.patch.object(task_app.send_notification_email, "delay") as delay:
        resp = client.put(
            "/tasks/9999",
            json={"status": "completed"},
            headers=auth(token),
        )
    assert resp.status_code == 404
    delay.assert_not_called()


def test_update_task_partial(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Keep me"}, headers=auth(token)
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Keep me"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    token = register_and_login(client)
    resp = client.put(
        "/tasks/9999", json={"title": "nope"}, headers=auth(token)
    )
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


# ── Ownership isolation ─────────────────────────────────────────


def test_users_see_only_their_own_tasks(client):
    alice_token = register_and_login(client, username="alice")
    bob_token = register_and_login(client, username="bob")

    alice_task = client.post(
        "/tasks", json={"title": "Alice's task"}, headers=auth(alice_token)
    ).get_json()
    client.post(
        "/tasks", json={"title": "Bob's task"}, headers=auth(bob_token)
    )

    alice_list = client.get("/tasks", headers=auth(alice_token)).get_json()["data"]
    assert [t["title"] for t in alice_list] == ["Alice's task"]

    bob_list = client.get("/tasks", headers=auth(bob_token)).get_json()["data"]
    assert [t["title"] for t in bob_list] == ["Bob's task"]

    assert (
        client.get(f"/tasks/{alice_task['id']}", headers=auth(bob_token)).status_code
        == 404
    )
    resp = client.put(
        f"/tasks/{alice_task['id']}",
        json={"title": "hacked"},
        headers=auth(bob_token),
    )
    assert resp.status_code == 404


# ── Pagination ─────────────────────────────────────────────────


def test_list_tasks_returns_paginated_shape(client):
    token = register_and_login(client)
    client.post("/tasks", json={"title": "solo"}, headers=auth(token))
    resp = client.get("/tasks", headers=auth(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body) == {"data", "next_cursor", "total"}
    assert isinstance(body["data"], list)
    assert body["next_cursor"] is None
    assert body["total"] == 1


def test_list_tasks_cursor_pagination(client):
    token = register_and_login(client)
    for i in range(1, 6):
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth(token))

    seen_ids = []
    cursor = None
    while True:
        query = "?limit=2"
        if cursor is not None:
            query += f"&cursor={cursor}"
        resp = client.get(f"/tasks{query}", headers=auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) <= 2
        seen_ids.extend(t["id"] for t in body["data"])
        if body["next_cursor"] is None:
            break
        cursor = body["next_cursor"]

    assert len(seen_ids) == 5
    assert len(set(seen_ids)) == 5
    assert seen_ids == sorted(seen_ids, reverse=True)


def test_list_tasks_default_limit_and_total(client):
    token = register_and_login(client)
    for i in range(1, 26):
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth(token))
    resp = client.get("/tasks", headers=auth(token))
    body = resp.get_json()
    assert body["total"] == 25
    assert len(body["data"]) == 20
    assert body["next_cursor"] is not None


def test_list_tasks_limit_max_clamped_to_100(client):
    task_app.RATE_LIMIT = "1000 per minute"
    token = register_and_login(client)
    for i in range(1, 121):
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth(token))
    resp = client.get("/tasks?limit=1000", headers=auth(token))
    body = resp.get_json()
    assert len(body["data"]) == 100
    assert body["next_cursor"] is not None
    assert body["total"] == 120


def test_list_tasks_next_cursor_null_on_last_page(client):
    token = register_and_login(client)
    for i in range(1, 4):
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth(token))
    resp = client.get("/tasks?limit=5", headers=auth(token))
    body = resp.get_json()
    assert len(body["data"]) == 3
    assert body["next_cursor"] is None


def test_list_tasks_cursor_respects_ownership(client):
    alice_token = register_and_login(client, username="alice")
    bob_token = register_and_login(client, username="bob")
    for i in range(1, 5):
        client.post("/tasks", json={"title": f"alice {i}"}, headers=auth(alice_token))
    for i in range(1, 4):
        client.post("/tasks", json={"title": f"bob {i}"}, headers=auth(bob_token))

    resp = client.get("/tasks?limit=2", headers=auth(alice_token))
    body = resp.get_json()
    assert body["total"] == 4
    assert all(t["title"].startswith("alice") for t in body["data"])

    resp = client.get("/tasks?limit=2", headers=auth(bob_token))
    body = resp.get_json()
    assert body["total"] == 3
    assert all(t["title"].startswith("bob") for t in body["data"])


def test_list_tasks_invalid_cursor_returns_400(client):
    token = register_and_login(client)
    client.post("/tasks", json={"title": "a"}, headers=auth(token))
    resp = client.get("/tasks?cursor=abc", headers=auth(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_invalid_limit_defaults(client):
    token = register_and_login(client)
    for i in range(1, 4):
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth(token))
    resp = client.get("/tasks?limit=banana", headers=auth(token))
    assert resp.status_code == 200
    assert len(resp.get_json()["data"]) == 3


# ── Rate limiting ───────────────────────────────────────────────


def test_rate_limit_exceeded_returns_429_with_retry_after(client):
    task_app.RATE_LIMIT = "3 per minute"
    token = register_and_login(client)
    for _ in range(3):
        resp = client.get("/tasks", headers=auth(token))
        assert resp.status_code == 200
    resp = client.get("/tasks", headers=auth(token))
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_is_per_user(client):
    alice_token = register_and_login(client, username="alice")
    bob_token = register_and_login(client, username="bob")
    task_app.RATE_LIMIT = "2 per minute"

    assert client.get("/tasks", headers=auth(alice_token)).status_code == 200
    assert client.get("/tasks", headers=auth(alice_token)).status_code == 200
    assert client.get("/tasks", headers=auth(alice_token)).status_code == 429
    assert client.get("/tasks", headers=auth(bob_token)).status_code == 200


def test_rate_limit_applies_to_auth_endpoints(client):
    task_app.RATE_LIMIT = "2 per minute"
    assert (
        client.post("/auth/register", json={"username": "a", "password": "p"}).status_code
        == 201
    )
    assert (
        client.post("/auth/register", json={"username": "b", "password": "p"}).status_code
        == 201
    )
    resp = client.post("/auth/register", json={"username": "c", "password": "p"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_applies_to_all_task_methods(client):
    task_app.RATE_LIMIT = "2 per minute"
    token = register_and_login(client)
    assert client.get("/tasks", headers=auth(token)).status_code == 200
    assert client.get("/tasks", headers=auth(token)).status_code == 200
    assert client.post("/tasks", json={"title": "x"}, headers=auth(token)).status_code == 429
