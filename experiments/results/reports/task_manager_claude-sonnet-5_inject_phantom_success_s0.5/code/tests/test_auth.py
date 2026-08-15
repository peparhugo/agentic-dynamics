from tests.conftest import auth_header, register_user


def test_register_success(client):
    resp = register_user(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert "password" not in data["user"]
    assert "access_token" in data


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"username": "alice"})
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
        json={"username": "alice", "email": "alice@example.com", "password": "short"},
    )
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register_user(client)
    resp = register_user(client, email="other@example.com")
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    register_user(client)
    resp = register_user(client, username="other")
    assert resp.status_code == 409


def test_login_with_username(client):
    register_user(client)
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_login_with_email(client):
    register_user(client)
    resp = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert resp.status_code == 200


def test_login_wrong_password(client):
    register_user(client)
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/auth/login", json={"username": "ghost", "password": "password123"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_token(client):
    resp = register_user(client)
    token = resp.get_json()["access_token"]
    me_resp = client.get("/api/auth/me", headers=auth_header(token))
    assert me_resp.status_code == 200
    assert me_resp.get_json()["user"]["username"] == "alice"


def test_invalid_token_rejected(client):
    resp = client.get("/api/auth/me", headers=auth_header("not-a-real-token"))
    assert resp.status_code == 401
