def register(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login(client, identifier="alice", password="password123"):
    return client.post(
        "/v1/auth/login",
        json={"username": identifier, "password": password},
    )


def test_register_creates_user(client):
    resp = register(client)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert "password_hash" not in body
    assert "password" not in body


def test_register_duplicate_username(client):
    register(client)
    resp = register(client, email="other@example.com")
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    register(client)
    resp = register(client, username="bob")
    assert resp.status_code == 409


def test_register_invalid_email(client):
    resp = register(client, email="not-an-email")
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = register(client, password="short")
    assert resp.status_code == 400


def test_register_missing_fields(client):
    resp = client.post("/v1/auth/register", json={"username": "alice"})
    assert resp.status_code == 400


def test_login_success_returns_tokens(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] > 0


def test_login_with_email(client):
    register(client)
    resp = client.post(
        "/v1/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["access_token"]


def test_login_wrong_password(client):
    register(client)
    resp = login(client, password="wrong-password")
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = login(client)
    assert resp.status_code == 401


def test_login_missing_password(client):
    resp = client.post("/v1/auth/login", json={"username": "alice"})
    assert resp.status_code == 400


def test_login_missing_identifier(client):
    resp = client.post("/v1/auth/login", json={"password": "password123"})
    assert resp.status_code == 400


def test_refresh_returns_new_access_token(client):
    register(client)
    refresh_token = login(client).get_json()["refresh_token"]
    resp = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["access_token"]
    assert body["access_token"] != refresh_token


def test_refresh_rejects_access_token(client):
    register(client)
    access_token = login(client).get_json()["access_token"]
    resp = client.post("/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


def test_refresh_invalid_token(client):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert resp.status_code == 401


def test_refresh_missing_token(client):
    resp = client.post("/v1/auth/refresh", json={})
    assert resp.status_code == 400
