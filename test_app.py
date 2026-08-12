import os
import tempfile
from unittest import mock

import pytest

os.environ["RATE_LIMIT_STORAGE_URI"] = "memory://"

from app import app, init_db


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app.config.update(TESTING=True)

    import app as app_module
    app_module.DATABASE = path
    app_module.limiter.reset()
    init_db()

    with app.test_client() as c:
        yield c

    os.unlink(path)


def register(client, username="alice", password="secret"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username="alice", password="secret"):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def token(client):
    register(client)
    return login(client).get_json()["token"]


@pytest.fixture()
def auth(client, token):
    return auth_headers(token)


def test_create_task(client, auth):
    res = client.post("/tasks", json={"title": "write code"}, headers=auth)
    assert res.status_code == 201
    body = res.get_json()
    assert body["title"] == "write code"
    assert body["status"] == "pending"
    assert body["id"] == 1
    assert body["created_at"]


def test_create_task_missing_title(client, auth):
    res = client.post("/tasks", json={}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_create_task_empty_title(client, auth):
    res = client.post("/tasks", json={"title": "   "}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_create_task_no_json(client, auth):
    res = client.post("/tasks", data="not json", headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_list_tasks_ordered_desc(client, auth):
    client.post("/tasks", json={"title": "first"}, headers=auth)
    client.post("/tasks", json={"title": "second"}, headers=auth)
    res = client.get("/tasks", headers=auth)
    assert res.status_code == 200
    body = res.get_json()
    tasks = body["data"]
    assert len(tasks) == 2
    assert tasks[0]["title"] == "second"
    assert tasks[1]["title"] == "first"
    assert body["total"] == 2
    assert body["next_cursor"] is None


def test_get_task(client, auth):
    created = client.post("/tasks", json={"title": "hello"}, headers=auth).get_json()
    res = client.get(f"/tasks/{created['id']}", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["title"] == "hello"


def test_get_task_not_found(client, auth):
    res = client.get("/tasks/999", headers=auth)
    assert res.status_code == 404
    assert res.get_json()["error"]


def test_update_task_title_and_status(client, auth):
    created = client.post("/tasks", json={"title": "hello"}, headers=auth).get_json()
    res = client.put(
        f"/tasks/{created['id']}",
        json={"title": "updated", "status": "done"},
        headers=auth,
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["title"] == "updated"
    assert body["status"] == "done"


def test_update_task_not_found(client, auth):
    res = client.put("/tasks/999", json={"title": "x"}, headers=auth)
    assert res.status_code == 404
    assert res.get_json()["error"]


def test_update_task_partial(client, auth):
    created = client.post("/tasks", json={"title": "hello"}, headers=auth).get_json()
    res = client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["title"] == "hello"
    assert body["status"] == "in_progress"


def test_register_creates_user(client):
    res = register(client)
    assert res.status_code == 201
    body = res.get_json()
    assert body["username"] == "alice"
    assert "password" not in body


def test_register_duplicate_username(client):
    register(client)
    res = register(client)
    assert res.status_code == 409
    assert res.get_json()["error"]


def test_register_missing_username(client):
    res = client.post("/auth/register", json={"password": "secret"})
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_register_missing_password(client):
    res = client.post("/auth/register", json={"username": "alice"})
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_login_returns_token(client):
    register(client)
    res = login(client)
    assert res.status_code == 200
    body = res.get_json()
    assert body["token"]
    assert body["username"] == "alice"


def test_login_wrong_password(client):
    register(client)
    res = login(client, password="wrong")
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_login_unknown_user(client):
    res = login(client, username="nobody")
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_tasks_require_token(client):
    res = client.get("/tasks")
    assert res.status_code == 401
    res = client.post("/tasks", json={"title": "x"})
    assert res.status_code == 401


def test_tasks_invalid_token(client):
    headers = auth_headers("not-a-valid-token")
    res = client.get("/tasks", headers=headers)
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_tasks_missing_bearer_scheme(client, token):
    res = client.get("/tasks", headers={"Authorization": token})
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_user_sees_only_own_tasks(client):
    register(client, "alice")
    register(client, "bob")
    alice_token = login(client, "alice").get_json()["token"]
    bob_token = login(client, "bob").get_json()["token"]

    created = client.post(
        "/tasks",
        json={"title": "alice task"},
        headers=auth_headers(alice_token),
    ).get_json()

    bob_tasks = client.get("/tasks", headers=auth_headers(bob_token)).get_json()["data"]
    assert bob_tasks == []

    res = client.get(
        f"/tasks/{created['id']}", headers=auth_headers(bob_token)
    )
    assert res.status_code == 404

    res = client.put(
        f"/tasks/{created['id']}",
        json={"status": "done"},
        headers=auth_headers(bob_token),
    )
    assert res.status_code == 404

    alice_tasks = client.get("/tasks", headers=auth_headers(alice_token)).get_json()["data"]
    assert [t["id"] for t in alice_tasks] == [created["id"]]


def _patch_delay(monkeypatch):
    import app as app_module

    delay = mock.MagicMock()
    monkeypatch.setattr(app_module.send_notification_email, "delay", delay)
    return delay


def test_completing_task_triggers_notification(client, auth, monkeypatch):
    created = client.post(
        "/tasks", json={"title": "finish report"}, headers=auth
    ).get_json()
    delay = _patch_delay(monkeypatch)

    res = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth
    )

    assert res.status_code == 200
    assert res.get_json()["status"] == "completed"
    delay.assert_called_once_with("alice", "finish report")


def test_notification_uses_registered_email(client, monkeypatch):
    register(client, "bob", password="secret")
    res = client.post(
        "/auth/register",
        json={"username": "carol", "password": "secret", "email": "carol@example.com"},
    )
    assert res.status_code == 201
    assert res.get_json()["email"] == "carol@example.com"
    carol_token = login(client, "carol").get_json()["token"]
    carol_auth = auth_headers(carol_token)

    created = client.post(
        "/tasks", json={"title": "book meeting"}, headers=carol_auth
    ).get_json()
    delay = _patch_delay(monkeypatch)

    res = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=carol_auth
    )

    assert res.status_code == 200
    delay.assert_called_once_with("carol@example.com", "book meeting")


def test_no_notification_when_status_unchanged(client, auth, monkeypatch):
    created = client.post(
        "/tasks", json={"title": "just started"}, headers=auth
    ).get_json()
    delay = _patch_delay(monkeypatch)

    res = client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth
    )

    assert res.status_code == 200
    assert res.get_json()["status"] == "in_progress"
    delay.assert_not_called()


def test_no_duplicate_notification_when_already_completed(client, auth, monkeypatch):
    created = client.post(
        "/tasks", json={"title": "already done"}, headers=auth
    ).get_json()
    delay = _patch_delay(monkeypatch)

    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth
    )
    delay.assert_called_once_with("alice", "already done")

    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth
    )
    delay.assert_called_once_with("alice", "already done")


def test_email_task_runs_and_sends_mock_email(capsys):
    from tasks import send_notification_email

    send_notification_email.apply(args=("bob@example.com", "Buy milk"))

    out = capsys.readouterr().out
    assert "bob@example.com" in out
    assert "Buy milk" in out
    assert "completed" in out


def _create_tasks(client, auth, n, prefix="task"):
    ids = []
    for i in range(n):
        res = client.post("/tasks", json={"title": f"{prefix} {i}"}, headers=auth)
        assert res.status_code == 201
        ids.append(res.get_json()["id"])
    return ids


def _reset_rate_limiter():
    import app as app_module

    app_module.limiter.reset()


def test_pagination_default_limit(client, auth):
    ids = _create_tasks(client, auth, 25)
    res = client.get("/tasks", headers=auth)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] == str(ids[5])
    assert [t["id"] for t in body["data"]] == ids[-1:4:-1]


def test_pagination_limit_param(client, auth):
    ids = _create_tasks(client, auth, 5)
    res = client.get("/tasks?limit=3", headers=auth)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["data"]) == 3
    assert body["total"] == 5
    assert body["next_cursor"] == str(ids[2])
    assert [t["id"] for t in body["data"]] == ids[-1:1:-1]


def test_pagination_max_limit_clamped(client, auth):
    _create_tasks(client, auth, 3)
    res = client.get("/tasks?limit=500", headers=auth)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["data"]) == 3
    assert body["next_cursor"] is None


def test_pagination_walks_all_pages(client, auth):
    ids = _create_tasks(client, auth, 25)
    seen = []
    cursor = None
    while True:
        url = "/tasks?limit=10" if cursor is None else f"/tasks?cursor={cursor}&limit=10"
        res = client.get(url, headers=auth)
        assert res.status_code == 200
        body = res.get_json()
        seen.extend(t["id"] for t in body["data"])
        if body["next_cursor"] is None:
            break
        cursor = body["next_cursor"]
    assert len(seen) == len(ids)
    assert seen == ids[::-1]


def test_pagination_last_page_next_cursor_null(client, auth):
    _create_tasks(client, auth, 25)
    first = client.get("/tasks?limit=20", headers=auth).get_json()
    assert first["next_cursor"] is not None
    second = client.get(
        f"/tasks?cursor={first['next_cursor']}&limit=20", headers=auth
    ).get_json()
    assert len(second["data"]) == 5
    assert second["next_cursor"] is None
    assert second["total"] == 25


def test_pagination_invalid_limit(client, auth):
    assert client.get("/tasks?limit=abc", headers=auth).status_code == 400
    assert client.get("/tasks?limit=0", headers=auth).status_code == 400
    assert client.get("/tasks?limit=-5", headers=auth).status_code == 400


def test_pagination_invalid_cursor(client, auth):
    assert client.get("/tasks?cursor=abc", headers=auth).status_code == 400


def test_rate_limit_returns_429_with_retry_after(client, auth):
    _reset_rate_limiter()
    for _ in range(100):
        assert client.get("/tasks", headers=auth).status_code == 200
    res = client.get("/tasks", headers=auth)
    assert res.status_code == 429
    assert res.get_json()["error"]
    assert res.headers.get("Retry-After") is not None
    assert int(res.headers.get("Retry-After")) > 0


def test_rate_limit_applies_to_auth_login(client):
    _reset_rate_limiter()
    for _ in range(100):
        client.post("/auth/login", json={"username": "alice", "password": "secret"})
    res = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert res.status_code == 429
    assert res.headers.get("Retry-After") is not None


def test_rate_limit_applies_to_auth_register(client):
    _reset_rate_limiter()
    for _ in range(100):
        client.post("/auth/register", json={"username": "x", "password": "y"})
    res = client.post("/auth/register", json={"username": "x", "password": "y"})
    assert res.status_code == 429
    assert res.headers.get("Retry-After") is not None


def test_rate_limit_is_per_user(client):
    register(client, "alice")
    register(client, "bob")
    alice_auth = auth_headers(login(client, "alice").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob").get_json()["token"])

    _reset_rate_limiter()

    for _ in range(100):
        assert client.get("/tasks", headers=alice_auth).status_code == 200
    assert client.get("/tasks", headers=alice_auth).status_code == 429
    assert client.get("/tasks", headers=bob_auth).status_code == 200
