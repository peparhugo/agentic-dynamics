def test_register_success(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "username is required" in data["errors"]
    assert "email is required" in data["errors"]
    assert "password is required" in data["errors"]


def test_register_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "abc"},
    )
    assert resp.status_code == 400
    assert any("password" in e for e in resp.get_json()["errors"])


def test_register_invalid_email(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "not-an-email", "password": "secret123"},
    )
    assert resp.status_code == 400
    assert "email is invalid" in resp.get_json()["errors"]


def test_register_duplicate_username(client):
    client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "other@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice2", "email": "alice@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


def test_login_success(client):
    client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "secret123"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert data["user"]["username"] == "alice"


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/api/auth/login", json={"username": "ghost", "password": "secret123"}
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 400


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_user(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
