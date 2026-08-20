import pytest

import app as app_module
from conftest import set_default_limit


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "test.db"))
    app_module.init_db()
    app_module.migrate()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_exceeding_limit_returns_429_with_retry_after(client, auth_headers):
    set_default_limit("3 per minute")

    for _ in range(3):
        assert client.get("/tasks", headers=auth_headers).status_code == 200

    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") is not None


def test_rate_limit_applies_to_auth_endpoints(client):
    set_default_limit("3 per minute")

    for i in range(3):
        assert (
            client.post(
                "/auth/register", json={"username": f"user{i}", "password": "pw"}
            ).status_code
            == 201
        )

    resp = client.post(
        "/auth/register", json={"username": "blocked", "password": "pw"}
    )
    assert resp.status_code == 429


def test_rate_limit_is_per_user(client):
    client.post("/auth/register", json={"username": "alice", "password": "pw"})
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    alice_token = client.post(
        "/auth/login", json={"username": "alice", "password": "pw"}
    ).get_json()["token"]
    bob_token = client.post(
        "/auth/login", json={"username": "bob", "password": "pw"}
    ).get_json()["token"]

    set_default_limit("2 per minute")

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    assert client.get("/tasks", headers=alice_headers).status_code == 200
    assert client.get("/tasks", headers=alice_headers).status_code == 200
    assert client.get("/tasks", headers=alice_headers).status_code == 429

    assert client.get("/tasks", headers=bob_headers).status_code == 200
