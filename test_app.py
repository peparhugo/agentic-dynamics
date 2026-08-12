import os
import tempfile
import pytest
from unittest.mock import Mock

import fakeredis
import redis
from limits.storage.redis import RedisStorage
from limits.strategies import STRATEGIES

DATABASE = os.environ.get("TEST_DATABASE")

if DATABASE is None:
    _tmpdir = tempfile.mkdtemp()
    DATABASE = os.path.join(_tmpdir, "test_todos.db")

os.environ["DATABASE"] = DATABASE
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

import app as app_module

app_module.DATABASE = DATABASE
app_module.init_db()

# Run Flask-Limiter against an in-process Redis emulation (fakeredis) so the
# rate limiting tests do not require a live Redis server.
#
# The limiter is already initialized (init_app ran at import). Re-running
# init_app would register a *second* set of request hooks, so instead we swap
# the storage and strategy on the existing limiter instance. The storage stays
# a genuine RedisStorage (fakeredis just emulates the Redis server protocol),
# matching the production Redis backend.
_REDIS_POOL = redis.ConnectionPool(connection_class=fakeredis.FakeRedisConnection)
_RATE_LIMIT_STORAGE = RedisStorage(
    "redis://localhost:6379/0", connection_pool=_REDIS_POOL
)
app_module.limiter._storage = _RATE_LIMIT_STORAGE
app_module.limiter._limiter = STRATEGIES[app_module.limiter._strategy](
    _RATE_LIMIT_STORAGE
)


@pytest.fixture(autouse=True)
def clean_db():
    yield
    app_module.limiter.reset()
    _restore_default_rate_limit()
    with app_module.get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM users")
        conn.commit()


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="secret"):
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────


def test_register(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] > 0
    assert data["username"] == "alice"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_requires_fields(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={"password": "secret"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 400
    assert resp.get_json()["error"]


def test_login_returns_token(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    assert resp.get_json()["token"]


def test_login_wrong_password(client):
    register(client)
    resp = login(client, password="wrong")
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = login(client, username="nobody")
    assert resp.status_code == 401


def test_tasks_require_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    resp = client.post("/tasks", json={"title": "x"})
    assert resp.status_code == 401
    resp = client.get("/tasks/1")
    assert resp.status_code == 401
    resp = client.put("/tasks/1", json={"title": "x"})
    assert resp.status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not.a.valid.token"}
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401
    resp = client.post("/tasks", json={"title": "x"}, headers=headers)
    assert resp.status_code == 401


def test_tasks_reject_malformed_header(client):
    headers = {"Authorization": "Token abc123"}
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401


# ── Task tests (authenticated) ────────────────────────────────


def test_create_task(client):
    register(client)
    resp = client.post("/tasks", json={"title": "buy milk"}, headers=auth_headers(client))
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] > 0
    assert data["title"] == "buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_requires_title(client):
    register(client)
    headers = auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"]


def test_create_task_rejects_blank_title(client):
    register(client)
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400


def test_list_tasks_ordered_desc(client):
    register(client)
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "first"}, headers=headers)
    client.post("/tasks", json={"title": "second"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert [t["title"] for t in body["data"]] == ["second", "first"]


def test_list_tasks_only_own(client):
    register(client, username="alice")
    register(client, username="bob")
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    client.post("/tasks", json={"title": "alice task"}, headers=alice)
    client.post("/tasks", json={"title": "bob task"}, headers=bob)

    resp = client.get("/tasks", headers=alice)
    assert [t["title"] for t in resp.get_json()["data"]] == ["alice task"]
    resp = client.get("/tasks", headers=bob)
    assert [t["title"] for t in resp.get_json()["data"]] == ["bob task"]


def test_get_task(client):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "hello"}, headers=headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "hello"


def test_get_task_not_found(client):
    register(client)
    headers = auth_headers(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"]


def test_get_other_users_task_not_found(client):
    register(client, username="alice")
    register(client, username="bob")
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post("/tasks", json={"title": "private"}, headers=alice).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob)
    assert resp.status_code == 404


def test_update_task_title(client):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "old"}, headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "pending"


def test_update_task_status(client):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "task"}, headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"


def test_update_task_both(client):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "a"}, headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "b", "status": "in_progress"},
        headers=headers,
    )
    data = resp.get_json()
    assert data["title"] == "b"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    register(client)
    headers = auth_headers(client)
    resp = client.put("/tasks/999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"]


def test_update_other_users_task_not_found(client):
    register(client, username="alice")
    register(client, username="bob")
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post("/tasks", json={"title": "private"}, headers=alice).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "hacked"}, headers=bob)
    assert resp.status_code == 404


# ── Notification trigger tests ────────────────────────────────


def _mock_email_task(monkeypatch):
    mock_task = Mock()
    mock_task.delay = Mock()
    monkeypatch.setattr(app_module, "send_notification_email", mock_task)
    return mock_task.delay


def test_update_task_to_completed_triggers_notification(client, monkeypatch):
    register(client)
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "publish report"}, headers=headers
    ).get_json()
    delay = _mock_email_task(monkeypatch)

    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    delay.assert_called_once_with("alice@example.com", "publish report")


def test_update_task_not_completed_does_not_notify(client, monkeypatch):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "task"}, headers=headers).get_json()
    delay = _mock_email_task(monkeypatch)

    client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=headers
    )

    delay.assert_not_called()


def test_already_completed_task_not_notified_again(client, monkeypatch):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "task"}, headers=headers).get_json()
    delay = _mock_email_task(monkeypatch)

    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )

    delay.assert_called_once()


def test_notification_uses_registered_email(client, monkeypatch):
    register(client)
    register(client, username="bob", password="secret")
    headers = auth_headers(client)
    bob_headers = auth_headers(client, username="bob")
    delay = _mock_email_task(monkeypatch)

    created = client.post("/tasks", json={"title": "bob task"}, headers=bob_headers).get_json()
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=bob_headers
    )

    delay.assert_called_once_with("bob@example.com", "bob task")


def test_missing_task_does_not_notify(client, monkeypatch):
    register(client)
    headers = auth_headers(client)
    delay = _mock_email_task(monkeypatch)

    resp = client.put("/tasks/999", json={"status": "completed"}, headers=headers)

    assert resp.status_code == 404
    delay.assert_not_called()


def test_send_notification_email_task(capsys):
    from tasks import send_notification_email

    result = send_notification_email("alice@example.com", "buy milk")

    assert result == {"email": "alice@example.com", "task_title": "buy milk"}
    out = capsys.readouterr().out
    assert "alice@example.com" in out
    assert "buy milk" in out


# ── Rate limiting tests ───────────────────────────────────────


def _apply_rate_limit(per_minute):
    """Swap the active application-wide rate limit at runtime.

    Avoids re-running Flask's setup phase (no re-init_app needed once the
    app has served its first request) while keeping the counters in the same
    fakeredis-backed storage.
    """
    from flask_limiter._limits import ApplicationLimit

    app_module.limiter.limit_manager.set_application_limits(
        [ApplicationLimit(f"{per_minute} per minute").bind(app_module.limiter)]
    )
    app_module.limiter.reset()


def _restore_default_rate_limit():
    _apply_rate_limit(100)


def set_rate_limit(per_minute):
    """Set the application-wide budget and clear existing counters."""
    _apply_rate_limit(per_minute)


def test_rate_limit_uses_redis_storage():
    from limits.storage.redis import RedisStorage

    assert isinstance(app_module.limiter.storage, RedisStorage)


def test_rate_limit_default_is_100_per_minute():
    assert app_module.RATE_LIMIT_PER_MINUTE == 100
    limits = app_module.limiter.limit_manager.application_limits
    assert len(limits) == 1
    assert limits[0].limit.amount == 100


def test_rate_limit_exceeded_returns_429_with_retry_after(client):
    set_rate_limit(2)
    register(client)
    token = login(client).get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/tasks", headers=headers).status_code == 200
    assert client.get("/tasks", headers=headers).status_code == 200
    blocked = client.get("/tasks", headers=headers)

    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_rate_limit_applies_to_auth_endpoints(client):
    set_rate_limit(3)
    codes = [
        client.post(
            "/auth/login", json={"username": "x", "password": "y"}
        ).status_code
        for _ in range(4)
    ]

    assert codes == [401, 401, 401, 429]


def test_rate_limit_is_per_user(client):
    set_rate_limit(5)
    register(client, username="alice")
    register(client, username="bob")
    alice_headers = auth_headers(client, username="alice")
    bob_headers = auth_headers(client, username="bob")

    for _ in range(5):
        assert client.get("/tasks", headers=alice_headers).status_code == 200
    assert client.get("/tasks", headers=alice_headers).status_code == 429
    assert client.get("/tasks", headers=bob_headers).status_code == 200


# ── Pagination tests ──────────────────────────────────────────


def create_tasks(client, headers, count):
    ids = []
    for i in range(count):
        resp = client.post(
            "/tasks", json={"title": f"task {i}"}, headers=headers
        )
        assert resp.status_code == 201
        ids.append(resp.get_json()["id"])
    return ids


def test_list_tasks_default_page_size(client):
    register(client)
    headers = auth_headers(client)
    create_tasks(client, headers, 25)

    body = client.get("/tasks", headers=headers).get_json()

    assert set(body) == {"data", "next_cursor", "total"}
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_list_tasks_cursor_pagination(client):
    register(client)
    headers = auth_headers(client)
    created_ids = create_tasks(client, headers, 25)

    page1 = client.get(
        "/tasks", query_string={"limit": 10}, headers=headers
    ).get_json()
    assert len(page1["data"]) == 10
    assert page1["next_cursor"] is not None

    page2 = client.get(
        "/tasks",
        query_string={"cursor": page1["next_cursor"], "limit": 10},
        headers=headers,
    ).get_json()
    assert len(page2["data"]) == 10
    assert page2["next_cursor"] is not None

    page3 = client.get(
        "/tasks",
        query_string={"cursor": page2["next_cursor"], "limit": 10},
        headers=headers,
    ).get_json()
    assert len(page3["data"]) == 5
    assert page3["next_cursor"] is None
    assert page3["total"] == 25

    seen = [t["id"] for t in page1["data"] + page2["data"] + page3["data"]]
    assert len(seen) == len(set(seen))
    assert sorted(seen) == sorted(set(seen))
    assert sorted(seen) == sorted(created_ids)


def test_list_tasks_cursor_is_last_item_id(client):
    register(client)
    headers = auth_headers(client)
    ids = create_tasks(client, headers, 5)

    body = client.get(
        "/tasks", query_string={"limit": 2}, headers=headers
    ).get_json()

    assert body["next_cursor"] == str(ids[-2])
    assert body["data"][0]["id"] == ids[-1]


def test_list_tasks_limit_clamped_to_max(client):
    set_rate_limit(150)
    register(client)
    headers = auth_headers(client)
    create_tasks(client, headers, 120)

    body = client.get(
        "/tasks", query_string={"limit": 500}, headers=headers
    ).get_json()

    assert len(body["data"]) == 100
    assert body["total"] == 120
    assert body["next_cursor"] is not None


def test_list_tasks_limit_defaults_on_invalid(client):
    register(client)
    headers = auth_headers(client)
    create_tasks(client, headers, 3)

    body = client.get(
        "/tasks", query_string={"limit": "abc"}, headers=headers
    ).get_json()
    assert len(body["data"]) == 3
    assert body["total"] == 3

    body = client.get(
        "/tasks", query_string={"limit": 0}, headers=headers
    ).get_json()
    assert len(body["data"]) == 3


def test_list_tasks_pagination_respects_owner(client):
    register(client, username="alice")
    register(client, username="bob")
    alice_headers = auth_headers(client, username="alice")
    bob_headers = auth_headers(client, username="bob")
    create_tasks(client, alice_headers, 3)
    create_tasks(client, bob_headers, 2)

    alice_body = client.get(
        "/tasks", query_string={"limit": 5}, headers=alice_headers
    ).get_json()
    bob_body = client.get(
        "/tasks", query_string={"limit": 5}, headers=bob_headers
    ).get_json()

    assert alice_body["total"] == 3
    assert bob_body["total"] == 2
    assert len(alice_body["data"]) == 3
    assert len(bob_body["data"]) == 2
    assert {t["id"] for t in alice_body["data"]}.isdisjoint(
        {t["id"] for t in bob_body["data"]}
    )
