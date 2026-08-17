from tests.conftest import auth_header, register_user


def test_register_success(client):
    resp = register_user(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]
    assert "token" in data


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"username": "alice"})
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = register_user(client, password="123")
    assert resp.status_code == 400


def test_register_invalid_email(client):
    resp = register_user(client, email="not-an-email")
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register_user(client)
    resp = register_user(client, email="alice2@example.com")
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    register_user(client)
    resp = register_user(client, username="alice2")
    assert resp.status_code == 409


def test_login_success(client):
    register_user(client)
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert data["user"]["username"] == "alice"


def test_login_with_email(client):
    register_user(client)
    resp = client.post("/api/auth/login", json={"username": "alice@example.com", "password": "secret123"})
    assert resp.status_code == 200


def test_login_wrong_password(client):
    register_user(client)
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/auth/login", json={"username": "ghost", "password": "secret123"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token(client):
    resp = client.get("/api/auth/me", headers=auth_header("not-a-real-token"))
    assert resp.status_code == 401


def test_me_with_valid_token(client):
    token = register_user(client).get_json()["token"]
    resp = client.get("/api/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "alice"
