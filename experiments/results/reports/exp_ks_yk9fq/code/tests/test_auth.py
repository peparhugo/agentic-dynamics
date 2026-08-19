from tests.helpers import register_user, login


def test_register_success(client):
    resp = register_user(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["message"] == "User registered"
    assert data["token"]
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]


def test_register_duplicate_username(client):
    register_user(client)
    resp = register_user(client, email="other@example.com")
    assert resp.status_code == 409
    assert "already exists" in resp.get_json()["error"]


def test_register_duplicate_email(client):
    register_user(client)
    resp = register_user(client, username="other")
    assert resp.status_code == 409
    assert "already exists" in resp.get_json()["error"]


def test_register_validation_errors(client):
    resp = client.post("/api/auth/register", json={})
    assert resp.status_code == 400
    details = resp.get_json()["details"]
    assert "username" in details
    assert "email" in details
    assert "password" in details


def test_register_short_password(client):
    resp = register_user(client, password="123")
    assert resp.status_code == 400
    assert "password" in resp.get_json()["details"]


def test_register_invalid_email(client):
    resp = register_user(client, email="not-an-email")
    assert resp.status_code == 400
    assert "email" in resp.get_json()["details"]


def test_login_success_by_username(client, user):
    resp = login(client, "alice", "password123")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["token"]
    assert data["user"]["username"] == "alice"


def test_login_success_by_email(client, user):
    resp = login(client, "alice@example.com", "password123")
    assert resp.status_code == 200
    assert resp.get_json()["token"]


def test_login_wrong_password(client, user):
    resp = login(client, "alice", "wrongpass")
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = login(client, "ghost", "password123")
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 400


def test_me_with_token(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "alice"


def test_me_without_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_invalid_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


def test_me_malformed_header(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Token abc"})
    assert resp.status_code == 401
