import time

import jwt as pyjwt

from tests.conftest import make_user


def test_register_success(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["username"] == "alice"
    assert data["access_token"]
    assert data["refresh_token"]
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_register_missing_fields(client):
    resp = client.post("/v1/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_register_invalid_email(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "alice", "email": "not-an-email", "password": "password123"},
    )
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "short"},
    )
    assert resp.status_code == 400


def test_register_duplicate(client, user_id):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "user1", "email": "user1@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_login_success(client, user_id):
    resp = client.post(
        "/v1/auth/login", json={"username": "user1", "password": "password123"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["username"] == "user1"


def test_login_invalid_password(client, user_id):
    resp = client.post(
        "/v1/auth/login", json={"username": "user1", "password": "wrongpassword"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/v1/auth/login", json={"username": "nobody", "password": "password123"}
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/v1/auth/login", json={"username": "user1"})
    assert resp.status_code == 400


def test_me_without_token(client):
    resp = client.get("/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_token(client, user_headers):
    resp = client.get("/v1/auth/me", headers=user_headers)
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "user1"


def test_me_invalid_token(client):
    resp = client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "token_invalid"


def test_me_expired_token(app, client, user_id):
    token = pyjwt.encode(
        {
            "sub": str(user_id),
            "username": "user1",
            "role": "user",
            "type": "access",
            "iat": int(time.time()) - 1000,
            "exp": int(time.time()) - 100,
        },
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "token_expired"


def test_refresh_flow(client, user_id):
    login = client.post(
        "/v1/auth/login", json={"username": "user1", "password": "password123"}
    )
    refresh_token = login.get_json()["refresh_token"]

    resp = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["refresh_token"] != refresh_token

    reuse = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


def test_refresh_invalid_token(client):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": "does-not-exist"})
    assert resp.status_code == 401


def test_logout_revokes_refresh(client, user_id):
    login = client.post(
        "/v1/auth/login", json={"username": "user1", "password": "password123"}
    )
    refresh_token = login.get_json()["refresh_token"]
    access_token = login.get_json()["access_token"]

    resp = client.post(
        "/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200

    reuse = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


def test_disabled_user_login(app, client):
    from app.extensions import db
    from app.models import User

    make_user(app, username="disabled", email="disabled@example.com")
    with app.app_context():
        u = User.query.filter_by(username="disabled").first()
        u.is_active = False
        db.session.commit()

    resp = client.post(
        "/v1/auth/login", json={"username": "disabled", "password": "password123"}
    )
    assert resp.status_code == 401
