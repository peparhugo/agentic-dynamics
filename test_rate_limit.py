import pytest

import app as app_module

LIMIT = 5


@pytest.fixture(autouse=True)
def low_rate_limit(monkeypatch):
    monkeypatch.setenv("RATELIMIT_APP_LIMIT", f"{LIMIT} per minute")
    yield


def register(client, username, password):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username, password):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def auth_headers(client, username, password="secret"):
    register(client, username, password)
    resp = login(client, username, password)
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


def test_default_limit_is_100_per_minute(monkeypatch):
    monkeypatch.delenv("RATELIMIT_APP_LIMIT", raising=False)
    assert app_module.app_rate_limit() == "100 per minute"


def test_rate_limit_enforced_per_user(client):
    headers = auth_headers(client, "rl_alice")
    for _ in range(LIMIT):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429


def test_429_includes_retry_after(client):
    headers = auth_headers(client, "rl_bob")
    for _ in range(LIMIT):
        client.get("/tasks", headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0


def test_rate_limit_is_per_user(client):
    alice = auth_headers(client, "rl_carol")
    bob = auth_headers(client, "rl_dave")
    for _ in range(LIMIT):
        client.get("/tasks", headers=alice)
    assert client.get("/tasks", headers=alice).status_code == 429
    assert client.get("/tasks", headers=bob).status_code == 200
    assert client.get("/tasks", headers=bob).status_code == 200


def test_rate_limit_applies_to_all_endpoints(client):
    for _ in range(LIMIT):
        resp = login(client, "rl_eve", "wrong")
        assert resp.status_code == 401
    resp = login(client, "rl_eve", "wrong")
    assert resp.status_code == 429
