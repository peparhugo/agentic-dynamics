import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import limits
import pytest

import app as app_module

RATE_LIMIT_ITEM = limits.parse(app_module.RATE_LIMIT)
RATE_LIMIT = RATE_LIMIT_ITEM.amount


@pytest.fixture()
def client(tmp_path):
    app_module.DATABASE = str(tmp_path / "test.db")
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def register(client, username="alice", password="secret123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(client, username="alice", password="secret123"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def preload_budget(key, hits):
    """Consume `hits` units of the shared 100/minute bucket for `key`.

    This drives the *same* storage the app's Limiter uses (application_limits,
    scope="global", same key_prefix), in a single round trip, so tests can
    reach "one request away from the limit" without firing ~100 sequential
    HTTP requests through the Flask test client. That matters here because
    this Redis instance is shared with other concurrent workloads on the
    host, and the default strategy is a fixed window keyed off the first
    hit's timestamp: a slow, many-request loop risks the window rolling
    over mid-test and silently resetting the counter, which would make the
    test flaky rather than exercising the real 429 boundary.
    """
    app_module.limiter.limiter.hit(
        RATE_LIMIT_ITEM, app_module.RATE_LIMIT_KEY_PREFIX, key, "global", cost=hits
    )


def anon_key(client):
    """The key rate_limit_key() assigns to unauthenticated requests."""
    with app_module.app.test_request_context():
        return app_module.get_remote_address()


def user_key(client, username="alice", password="secret123"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    with app_module.app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        return app_module.rate_limit_key()


# ── Authenticated endpoint ────────────────────────────────────────

def test_requests_under_limit_succeed(client):
    headers = auth_header(client)
    for _ in range(5):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200


def test_request_at_and_over_limit_boundary(client):
    key = user_key(client)
    # user_key() already registered/logged in; log in again to get a token
    # for making the real requests below.
    resp = login(client)
    headers = {"Authorization": f"Bearer {resp.get_json()['token']}"}

    preload_budget(key, RATE_LIMIT - 1)

    ok_resp = client.get("/tasks", headers=headers)
    assert ok_resp.status_code == 200  # exactly the 100th request

    blocked_resp = client.get("/tasks", headers=headers)
    assert blocked_resp.status_code == 429  # 101st request
    assert "error" in blocked_resp.get_json()


def test_429_response_has_retry_after_header(client):
    key = user_key(client)
    resp = login(client)
    headers = {"Authorization": f"Bearer {resp.get_json()['token']}"}

    preload_budget(key, RATE_LIMIT)

    blocked_resp = client.get("/tasks", headers=headers)
    assert blocked_resp.status_code == 429
    assert "Retry-After" in blocked_resp.headers
    assert int(blocked_resp.headers["Retry-After"]) >= 0


def test_limit_is_per_authenticated_user(client):
    alice_key = user_key(client, "alice", "secret123")
    bob_headers = auth_header(client, "bob", "secret456")

    preload_budget(alice_key, RATE_LIMIT)

    alice_login = login(client, "alice", "secret123")
    alice_headers = {"Authorization": f"Bearer {alice_login.get_json()['token']}"}

    # alice is now rate limited...
    assert client.get("/tasks", headers=alice_headers).status_code == 429
    # ...but bob's own budget is untouched
    assert client.get("/tasks", headers=bob_headers).status_code == 200


def test_rate_limit_shared_across_different_endpoints_for_same_user(client):
    key = user_key(client)
    resp = login(client)
    headers = {"Authorization": f"Bearer {resp.get_json()['token']}"}

    # spend almost the whole budget as if it came from a mix of endpoints
    preload_budget(key, RATE_LIMIT - 1)

    ok_resp = client.post("/tasks", json={"title": "x"}, headers=headers)
    assert ok_resp.status_code == 201  # 100th hit, still within budget

    blocked_resp = client.get("/tasks", headers=headers)
    assert blocked_resp.status_code == 429  # 101st hit, budget is shared app-wide


# ── Auth endpoints are rate limited too ───────────────────────────

def test_register_endpoint_is_rate_limited(client):
    key = anon_key(client)
    preload_budget(key, RATE_LIMIT)

    resp = client.post("/auth/register", json={"username": "dup", "password": "secret123"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_login_endpoint_is_rate_limited(client):
    register(client, "alice", "secret123")
    key = anon_key(client)
    preload_budget(key, RATE_LIMIT)

    resp = client.post("/auth/login", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_anonymous_auth_requests_do_not_affect_authenticated_users_budget(client):
    headers = auth_header(client, "alice", "secret123")

    key = anon_key(client)
    preload_budget(key, RATE_LIMIT)

    # anonymous callers hitting their own budget must not consume alice's
    # per-user budget
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
