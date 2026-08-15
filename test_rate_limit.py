import pytest

import app as app_module


def test_rate_limit_allows_under_quota(client, auth):
    for _ in range(20):
        resp = client.get("/tasks", headers=auth)
        assert resp.status_code == 200


def test_rate_limit_exceeded_returns_429(client, auth):
    for _ in range(100):
        resp = client.get("/tasks", headers=auth)
        assert resp.status_code == 200
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 429
    assert resp.get_json()["error"] == "rate limit exceeded"


def test_rate_limit_sets_retry_after_header(client, auth):
    for _ in range(100):
        client.get("/tasks", headers=auth)
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 429
    retry_after = resp.headers.get("Retry-After")
    assert retry_after is not None
    assert int(retry_after) >= 1


def test_rate_limit_is_per_user(client, auth, bob_auth):
    for _ in range(100):
        client.get("/tasks", headers=auth)
    assert client.get("/tasks", headers=auth).status_code == 429
    assert client.get("/tasks", headers=bob_auth).status_code == 200


def test_rate_limit_applies_to_auth_endpoints(client):
    body = {"username": "nobody", "password": "pw"}
    for _ in range(100):
        client.post("/auth/login", json=body)
    resp = client.post("/auth/login", json=body)
    assert resp.status_code == 429


def test_rate_limit_applies_to_all_task_methods(client, auth):
    for _ in range(100):
        client.get("/tasks", headers=auth)
    resp = client.post("/tasks", json={"title": "x"}, headers=auth)
    assert resp.status_code == 429


def test_rate_limit_uses_redis_storage():
    from flask_limiter.extension import Limiter

    assert isinstance(app_module.limiter, Limiter)
    assert app_module.limiter._storage_uri == "redis://localhost:6379"
