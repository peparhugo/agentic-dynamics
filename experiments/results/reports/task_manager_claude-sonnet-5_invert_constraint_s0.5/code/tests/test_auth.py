def test_register_success(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["email"] == "alice@example.com"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]
    assert body["access_token"]
    assert body["refresh_token"]


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_short_username(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "ab", "email": "ab@example.com", "password": "password123"},
    )
    assert resp.status_code == 400


def test_register_invalid_email(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "not-an-email", "password": "password123"},
    )
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "123"},
    )
    assert resp.status_code == 400


def test_register_duplicate_username(client, auth_user):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "different@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client, auth_user):
    resp = client.post(
        "/api/auth/register",
        json={"username": "different", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_login_with_username(client, auth_user):
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["access_token"]
    assert body["user"]["username"] == "alice"


def test_login_with_email(client, auth_user):
    resp = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert resp.status_code == 200


def test_login_wrong_password(client, auth_user):
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "wrongpassword"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/api/auth/login", json={"username": "nobody", "password": "password123"}
    )
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "alice"


def test_refresh_token(client, auth_user):
    user, _ = auth_user
    login_resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    )
    refresh_token = login_resp.get_json()["refresh_token"]
    resp = client.post(
        "/api/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["access_token"]


def test_access_token_cannot_be_used_to_refresh(client, auth_headers):
    resp = client.post("/api/auth/refresh", headers=auth_headers)
    assert resp.status_code == 422
