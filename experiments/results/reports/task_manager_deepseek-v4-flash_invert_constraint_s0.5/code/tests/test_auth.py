def test_register_success(client):
    resp = client.post(
        "/api/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    body = resp.get_json()
    assert resp.status_code == 201
    assert body["user"]["username"] == "alice"
    assert body["user"]["email"] == "alice@example.com"
    assert "password_hash" not in body["user"]
    assert "access_token" in body


def test_register_duplicate_username(client):
    first = client.post(
        "/api/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/register",
        json={"username": "alice", "email": "alice2@example.com", "password": "secret123"},
    )
    assert second.status_code == 409
    assert second.get_json()["error"] == "username already taken"


def test_register_duplicate_email(client):
    first = client.post(
        "/api/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/register",
        json={"username": "bob", "email": "alice@example.com", "password": "secret123"},
    )
    assert second.status_code == 409
    assert second.get_json()["error"] == "email already registered"


def test_register_missing_fields(client):
    resp = client.post("/api/register", json={"password": "secret123"})
    assert resp.status_code == 400
    errors = resp.get_json()["errors"]
    assert "username is required" in errors
    assert "a valid email is required" in errors


def test_register_short_password(client):
    resp = client.post(
        "/api/register",
        json={"username": "alice", "email": "alice@example.com", "password": "123"},
    )
    assert resp.status_code == 400
    assert "password must be at least 6 characters" in resp.get_json()["errors"]


def test_register_no_json(client):
    resp = client.post("/api/register", data={})
    assert resp.status_code == 400


def test_login_success_with_username(client):
    client.post(
        "/api/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/login", json={"username": "alice", "password": "secret123"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user"]["username"] == "alice"
    assert "access_token" in body


def test_login_success_with_email(client):
    client.post(
        "/api/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/login", json={"email": "alice@example.com", "password": "secret123"}
    )
    assert resp.status_code == 200


def test_login_invalid_password(client):
    client.post(
        "/api/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/login", json={"username": "alice", "password": "wrongpass"}
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid credentials"


def test_login_unknown_user(client):
    resp = client.post(
        "/api/login", json={"username": "nobody", "password": "whatever1"}
    )
    assert resp.status_code == 401


def test_me(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/api/me", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "alice"


def test_me_requires_auth(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401


def test_protected_endpoint_requires_valid_token(client):
    resp = client.get(
        "/api/tasks", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code in (401, 422)
