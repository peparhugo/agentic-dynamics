import pytest
import redis

from app import create_app
from test_app import (  # noqa: F401
    RATELIMIT_TEST_STORAGE_URI,
    auth_headers,
    client,
    create,
    login,
    register,
)


@pytest.fixture
def limited_client(tmp_path, monkeypatch):
    """A client whose per-user rate limit is small, so tests can exhaust it
    with a handful of requests instead of firing 100+ real ones."""
    storage_file = tmp_path / "tasks.json"
    monkeypatch.setenv("TASKS_FILE", str(storage_file))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", RATELIMIT_TEST_STORAGE_URI)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    redis.Redis.from_url(RATELIMIT_TEST_STORAGE_URI).flushdb()
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_default_rate_limit_is_100_per_minute(client):
    assert client.application.config["RATE_LIMIT_PER_MINUTE"] == 100


def test_requests_under_limit_all_succeed(limited_client):
    register(limited_client, "alice", "password1")
    token = login(limited_client, "alice", "password1").get_json()["token"]
    headers = auth_headers(token)

    resp = limited_client.get("/tasks", headers=headers)
    assert resp.status_code == 200


def test_exceeding_limit_returns_429_with_retry_after(limited_client):
    register(limited_client, "alice", "password1")
    token = login(limited_client, "alice", "password1").get_json()["token"]
    headers = auth_headers(token)

    # login (1) + register (1) already used 2 of the 5 unauthenticated-key
    # budget; the authenticated user's own budget is still fresh though,
    # since it's keyed separately (by user id, not by IP).
    responses = [limited_client.get("/tasks", headers=headers) for _ in range(6)]
    statuses = [r.status_code for r in responses]

    assert 429 in statuses
    blocked = responses[statuses.index(429)]
    assert "error" in blocked.get_json()
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) >= 0


def test_rate_limit_applies_to_auth_endpoints(limited_client):
    responses = [
        limited_client.post(
            "/auth/login", json={"username": "ghost", "password": "wrong"}
        )
        for _ in range(6)
    ]
    statuses = [r.status_code for r in responses]

    assert 429 in statuses


def test_rate_limit_is_independent_per_user(limited_client):
    register(limited_client, "alice", "password1")
    register(limited_client, "bob", "password2")
    alice_headers = auth_headers(
        login(limited_client, "alice", "password1").get_json()["token"]
    )
    bob_headers = auth_headers(
        login(limited_client, "bob", "password2").get_json()["token"]
    )

    # Exhaust alice's budget.
    alice_statuses = [
        limited_client.get("/tasks", headers=alice_headers).status_code
        for _ in range(6)
    ]
    assert 429 in alice_statuses

    # Bob has his own budget and is unaffected by alice's usage.
    resp = limited_client.get("/tasks", headers=bob_headers)
    assert resp.status_code == 200


def test_rate_limit_covers_task_creation_too(limited_client):
    register(limited_client, "alice", "password1")
    token = login(limited_client, "alice", "password1").get_json()["token"]
    headers = auth_headers(token)

    responses = [create(limited_client, headers, f"task {i}") for i in range(6)]
    statuses = [r.status_code for r in responses]

    assert 429 in statuses
