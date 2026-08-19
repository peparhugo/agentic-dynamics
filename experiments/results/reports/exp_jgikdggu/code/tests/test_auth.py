from tests.conftest import register_user, login_user


def test_register_success(client):
    resp = register_user(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert "access_token" in data
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert "password_hash" not in data["user"]


def test_register_duplicate_username(client):
    register_user(client)
    resp = register_user(client, email="other@example.com")
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    register_user(client)
    resp = register_user(client, username="bob")
    assert resp.status_code == 409


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "username" in data["errors"]
    assert "email" in data["errors"]
    assert "password" in data["errors"]


def test_register_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "123"},
    )
    assert resp.status_code == 400


def test_register_invalid_email(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "not-an-email", "password": "secret123"},
    )
    assert resp.status_code == 400


def test_login_success(client):
    register_user(client)
    resp = login_user(client)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert data["user"]["username"] == "alice"


def test_login_with_email(client):
    register_user(client)
    resp = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "secret123"}
    )
    assert resp.status_code == 200


def test_login_wrong_password(client):
    register_user(client)
    resp = login_user(client, password="wrongpass")
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = login_user(client, identifier="ghost")
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client):
    token = register_user(client).get_json()["access_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "alice"


def test_me_with_invalid_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer badtoken"})
    assert resp.status_code in (401, 422)
