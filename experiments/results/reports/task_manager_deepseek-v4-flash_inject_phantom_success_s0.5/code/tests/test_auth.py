import pytest

from conftest import auth_headers


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_register_success(client):
    resp = client.post(
        "/auth/register",
        json={"username": "newbie", "email": "newbie@example.com", "password": "s3cret-pass"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["access_token"]
    assert data["user"]["username"] == "newbie"
    assert data["user"]["email"] == "newbie@example.com"
    assert "password" not in data["user"]


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "email": "x@y.com", "password": "password123"},
        {"username": "ok", "email": "not-an-email", "password": "password123"},
        {"username": "ok", "email": "x@y.com", "password": "short"},
        {"username": "ok", "email": "x@y.com"},
        {},
    ],
)
def test_register_validation_errors(client, payload):
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    client.post(
        "/auth/register",
        json={"username": "dup", "email": "dup1@example.com", "password": "password123"},
    )
    resp = client.post(
        "/auth/register",
        json={"username": "dup", "email": "dup2@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    client.post(
        "/auth/register",
        json={"username": "one", "email": "same@example.com", "password": "password123"},
    )
    resp = client.post(
        "/auth/register",
        json={"username": "two", "email": "same@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_login_by_username(client):
    client.post(
        "/auth/register",
        json={"username": "login_user", "email": "lu@example.com", "password": "password123"},
    )
    resp = client.post("/auth/login", json={"username": "login_user", "password": "password123"})
    assert resp.status_code == 200
    assert resp.get_json()["access_token"]


def test_login_by_email(client):
    client.post(
        "/auth/register",
        json={"username": "login_user2", "email": "lu2@example.com", "password": "password123"},
    )
    resp = client.post("/auth/login", json={"email": "lu2@example.com", "password": "password123"})
    assert resp.status_code == 200


def test_login_invalid_credentials(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "whatever123"})
    assert resp.status_code == 401


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={"username": "victim", "email": "v@example.com", "password": "password123"},
    )
    resp = client.post("/auth/login", json={"username": "victim", "password": "password-wrong"})
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 400


def test_me_with_token(client, users):
    resp = client.get("/auth/me", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "alice"


def test_me_without_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_bad_token(client):
    resp = client.get("/auth/me", headers=auth_headers("not-a-real-token"))
    assert resp.status_code == 401
