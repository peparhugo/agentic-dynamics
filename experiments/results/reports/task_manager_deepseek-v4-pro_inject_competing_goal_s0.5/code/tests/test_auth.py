from datetime import datetime, timedelta, timezone

import jwt


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_success(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["id"] is not None
    assert "token" in data
    assert "password_hash" not in data["user"]


def test_register_normalizes_email(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "Bob@Example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["user"]["email"] == "bob@example.com"


def test_register_duplicate_username(client, make_user):
    make_user("alice", email="alice@example.com")
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "other@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client, make_user):
    make_user("alice", email="alice@example.com")
    resp = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_invalid_email(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "not-an-email", "password": "password123"},
    )
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": "short"},
    )
    assert resp.status_code == 400


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"username": "eve"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "details" in data
    assert "email" in data["details"]
    assert "password" in data["details"]


def test_login_by_username(client, make_user):
    make_user("alice", email="alice@example.com", password="password123")
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_by_email(client, make_user):
    make_user("alice", email="alice@example.com", password="password123")
    resp = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert resp.status_code == 200


def test_login_wrong_password(client, make_user):
    make_user("alice", email="alice@example.com", password="password123")
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/api/auth/login", json={"username": "ghost", "password": "password123"}
    )
    assert resp.status_code == 401


def test_login_missing_credentials(client):
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 400


def test_me_returns_user(client, make_user):
    user = make_user("alice")
    resp = client.get("/api/auth/me", headers=_headers(user["token"]))
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "alice"


def test_me_missing_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_malformed_header(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Token abc123"})
    assert resp.status_code == 401


def test_me_invalid_token(client):
    resp = client.get("/api/auth/me", headers=_headers("not-a-real-token"))
    assert resp.status_code == 401


def test_me_expired_token(client, app):
    payload = {
        "sub": "1",
        "iat": datetime.now(timezone.utc) - timedelta(seconds=7200),
        "exp": datetime.now(timezone.utc) - timedelta(seconds=3600),
    }
    token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")
    resp = client.get("/api/auth/me", headers=_headers(token))
    assert resp.status_code == 401
    assert "expired" in resp.get_json()["error"].lower()


def test_me_token_for_deleted_user(client, make_user, app):
    user = make_user("alice")
    from app.models import User
    from app.extensions import db

    with app.app_context():
        db.session.delete(db.session.get(User, user["user"]["id"]))
        db.session.commit()

    resp = client.get("/api/auth/me", headers=_headers(user["token"]))
    assert resp.status_code == 401
