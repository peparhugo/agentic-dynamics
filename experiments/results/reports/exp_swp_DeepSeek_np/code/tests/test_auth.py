from tests.conftest import auth_headers, login_user, register_user


def test_register_returns_tokens(client):
    resp = register_user(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "user@example.com"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_register_duplicate_email_conflict(client):
    assert register_user(client).status_code == 201
    resp = register_user(client)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "conflict"


def test_login_success(client):
    register_user(client)
    resp = login_user(client)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password_unauthorized(client):
    register_user(client)
    resp = login_user(client, password="wrongpassword")
    assert resp.status_code == 401


def test_login_unknown_user_unauthorized(client):
    resp = login_user(client, email="nobody@example.com")
    assert resp.status_code == 401


def test_refresh_with_valid_refresh_token(client):
    tokens = register_user(client).get_json()
    resp = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_with_access_token_rejected(client):
    tokens = register_user(client).get_json()
    resp = client.post("/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_refresh_missing_token_validation(client):
    resp = client.post("/v1/auth/refresh", json={})
    assert resp.status_code == 422


def test_me_requires_auth(client):
    resp = client.get("/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_user(client):
    headers = auth_headers(client)
    resp = client.get("/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "user@example.com"


def test_protected_route_requires_valid_token(client):
    resp = client.get("/v1/items")
    assert resp.status_code == 401

    resp = client.get("/v1/items", headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 401
