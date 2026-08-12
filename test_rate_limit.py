import importlib


def build_app(monkeypatch, tmp_path, rate_limit):
    monkeypatch.setenv("DATABASE", str(tmp_path / "test.db"))
    monkeypatch.setenv("RATE_LIMIT", rate_limit)
    monkeypatch.setenv("FAKEREDIS", "1")

    import app as app_module

    importlib.reload(app_module)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(client, username="alice", password="secret"):
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_authenticated_user_hits_rate_limit(monkeypatch, tmp_path):
    client = build_app(monkeypatch, tmp_path, "4 per minute")
    register(client)
    headers = auth_header(client)

    for _ in range(4):
        assert client.get("/tasks", headers=headers).status_code == 200

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429


def test_rate_limit_response_has_retry_after(monkeypatch, tmp_path):
    client = build_app(monkeypatch, tmp_path, "4 per minute")
    register(client)
    headers = auth_header(client)

    for _ in range(4):
        client.get("/tasks", headers=headers)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0
    assert resp.get_json() == {"error": "rate limit exceeded"}


def test_auth_endpoints_are_rate_limited(monkeypatch, tmp_path):
    client = build_app(monkeypatch, tmp_path, "3 per minute")

    for i in range(3):
        resp = client.post(
            "/auth/register", json={"username": f"user{i}", "password": "secret"}
        )
        assert resp.status_code == 201

    resp = client.post(
        "/auth/register", json={"username": "user3", "password": "secret"}
    )
    assert resp.status_code == 429


def test_rate_limits_are_per_user(monkeypatch, tmp_path):
    client = build_app(monkeypatch, tmp_path, "4 per minute")
    register(client, "alice")
    register(client, "bob")
    alice_headers = auth_header(client, "alice")
    bob_headers = auth_header(client, "bob")

    for _ in range(4):
        assert client.get("/tasks", headers=alice_headers).status_code == 200
    assert client.get("/tasks", headers=alice_headers).status_code == 429

    for _ in range(4):
        assert client.get("/tasks", headers=bob_headers).status_code == 200
    assert client.get("/tasks", headers=bob_headers).status_code == 429


def test_default_limit_is_100_per_minute(monkeypatch, tmp_path):
    client = build_app(monkeypatch, tmp_path, "100 per minute")
    register(client)
    headers = auth_header(client)

    for _ in range(100):
        assert client.get("/tasks", headers=headers).status_code == 200

    assert client.get("/tasks", headers=headers).status_code == 429
