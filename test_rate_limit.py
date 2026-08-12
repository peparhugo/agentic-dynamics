import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATA_FILE = str(tmp_path / "tasks.json")
    app_module.init_store()
    app_module.limiter.reset()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def authed_client(client):
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )
    assert resp.status_code == 201
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    token = login.get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


def test_authenticated_user_limited_to_100_per_minute(authed_client):
    for _ in range(100):
        resp = authed_client.get("/tasks")
        assert resp.status_code == 200
    resp = authed_client.get("/tasks")
    assert resp.status_code == 429
    body = resp.get_json()
    assert body["error"] == "rate limit exceeded"
    assert int(resp.headers["Retry-After"]) > 0


def test_limit_is_per_user(authed_client, client):
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    bob_login = client.post("/auth/login", json={"username": "bob", "password": "pw"})
    bob_token = bob_login.get_json()["token"]

    for _ in range(100):
        assert authed_client.get("/tasks").status_code == 200

    assert authed_client.get("/tasks").status_code == 429

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    resp = client.get("/tasks")
    assert resp.status_code == 200


def test_auth_endpoints_are_rate_limited(client):
    for _ in range(100):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "x"})
        assert resp.status_code == 401
    resp = client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


def test_register_endpoint_is_rate_limited(client):
    for index in range(100):
        resp = client.post(
            "/auth/register",
            json={"username": f"user{index}", "password": "secret"},
        )
        assert resp.status_code == 201
    resp = client.post(
        "/auth/register", json={"username": "overflow", "password": "secret"}
    )
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


def test_write_endpoints_are_rate_limited(authed_client):
    for index in range(100):
        resp = authed_client.post("/tasks", json={"title": f"task {index}"})
        assert resp.status_code == 201
    resp = authed_client.post("/tasks", json={"title": "overflow"})
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


def test_rate_limit_uses_redis_storage():
    from limits.storage.redis import RedisStorage

    assert isinstance(app_module.limiter.storage, RedisStorage)
