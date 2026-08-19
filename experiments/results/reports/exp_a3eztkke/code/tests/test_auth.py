def test_register_success(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert "password_hash" not in data
    assert data["id"] is not None


def test_register_duplicate_username(client):
    payload = {"username": "alice", "email": "alice@example.com", "password": "password123"}
    client.post("/api/auth/register", json=payload)
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "other@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    payload = {"username": "alice", "email": "alice@example.com", "password": "password123"}
    client.post("/api/auth/register", json=payload)
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "email" in data.get("fields", {})
    assert "password" in data.get("fields", {})


def test_register_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "123"},
    )
    assert resp.status_code == 400


def test_login_success(client):
    client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["access_token"]
    assert data["user"]["username"] == "alice"


def test_login_with_email(client):
    client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert resp.status_code == 200


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/api/auth/login", json={"username": "nobody", "password": "password123"}
    )
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = client.get("/api/auth/me", headers=auth_headers(user_id))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["id"] == user_id


def test_me_with_invalid_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401
