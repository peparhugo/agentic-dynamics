import jwt

from conftest import TEST_SECRET


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_register_success(client):
    resp = client.post(
        "/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["username"] == "bob"
    assert "password_hash" not in data["user"]
    assert data["user"]["id"] >= 1


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    assert "required" in resp.get_json()["error"]


def test_register_invalid_email(client):
    resp = client.post(
        "/auth/register",
        json={"username": "bob", "email": "not-an-email", "password": "password123"},
    )
    assert resp.status_code == 400
    assert "email" in resp.get_json()["error"]


def test_register_short_password(client):
    resp = client.post(
        "/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "short"},
    )
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    client.post(
        "/auth/register",
        json={"username": "dup", "email": "a@example.com", "password": "password123"},
    )
    resp = client.post(
        "/auth/register",
        json={"username": "dup", "email": "b@example.com", "password": "password123"},
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


def test_login_success_with_username(client):
    client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    resp = client.post(
        "/auth/login", json={"identifier": "carol", "password": "password123"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"]["username"] == "carol"
    assert data["token"]
    payload = jwt.decode(data["token"], TEST_SECRET, algorithms=["HS256"])
    assert payload["sub"] == str(data["user"]["id"])


def test_login_success_with_email(client):
    client.post(
        "/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": "password123"},
    )
    resp = client.post(
        "/auth/login", json={"identifier": "dave@example.com", "password": "password123"}
    )
    assert resp.status_code == 200


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={"username": "erin", "email": "erin@example.com", "password": "password123"},
    )
    resp = client.post(
        "/auth/login", json={"identifier": "erin", "password": "wrongpassword"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/auth/login", json={"identifier": "ghost", "password": "password123"}
    )
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_valid_token(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "alice"


def test_invalid_token_rejected(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 401


def test_tampered_token_rejected(client, register_user):
    register_user()
    resp = client.get(
        "/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}
    )
    assert resp.status_code == 401


def test_malformed_auth_header(client):
    resp = client.get("/auth/me", headers={"Authorization": "Basic abc123"})
    assert resp.status_code == 401
