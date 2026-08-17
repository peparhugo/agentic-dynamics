from tests.conftest import auth_headers


def test_register_success(client):
    res = client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "secret123"},
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["username"] == "carol"
    assert body["email"] == "carol@example.com"
    assert body["is_admin"] is False
    assert "password_hash" not in body
    assert "password" not in body


def test_register_requires_username(client):
    res = client.post(
        "/auth/register",
        json={"email": "x@example.com", "password": "secret123"},
    )
    assert res.status_code == 400
    assert res.get_json()["error"] == "username is required"


def test_register_requires_valid_email(client):
    res = client.post(
        "/auth/register",
        json={"username": "carol", "email": "not-an-email", "password": "secret123"},
    )
    assert res.status_code == 400
    assert "valid email" in res.get_json()["error"]


def test_register_short_password(client):
    res = client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "short"},
    )
    assert res.status_code == 400
    assert "at least 6 characters" in res.get_json()["error"]


def test_register_duplicate_username(client):
    client.post(
        "/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": "secret123"},
    )
    res = client.post(
        "/auth/register",
        json={"username": "dave", "email": "dave2@example.com", "password": "secret123"},
    )
    assert res.status_code == 409
    assert res.get_json()["error"] == "username already taken"


def test_register_duplicate_email(client):
    client.post(
        "/auth/register",
        json={"username": "erin", "email": "erin@example.com", "password": "secret123"},
    )
    res = client.post(
        "/auth/register",
        json={"username": "erin2", "email": "ERIN@example.com", "password": "secret123"},
    )
    assert res.status_code == 409
    assert res.get_json()["error"] == "email already registered"


def test_register_emails_normalized_to_lowercase(client):
    res = client.post(
        "/auth/register",
        json={"username": "frank", "email": "Frank@Example.com", "password": "secret123"},
    )
    assert res.status_code == 201
    assert res.get_json()["email"] == "frank@example.com"


def test_login_success_returns_tokens(client):
    client.post(
        "/auth/register",
        json={"username": "grace", "email": "grace@example.com", "password": "secret123"},
    )
    res = client.post(
        "/auth/login", json={"username": "grace", "password": "secret123"}
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == "grace"


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={"username": "hank", "email": "hank@example.com", "password": "secret123"},
    )
    res = client.post(
        "/auth/login", json={"username": "hank", "password": "wrongpass"}
    )
    assert res.status_code == 401
    assert res.get_json()["error"] == "invalid credentials"


def test_login_unknown_user(client):
    res = client.post(
        "/auth/login", json={"username": "ghost", "password": "whatever"}
    )
    assert res.status_code == 401


def test_login_missing_fields(client):
    res = client.post("/auth/login", json={"username": "grace"})
    assert res.status_code == 400


def test_refresh_token_issues_new_access_token(client):
    client.post(
        "/auth/register",
        json={"username": "iris", "email": "iris@example.com", "password": "secret123"},
    )
    login = client.post(
        "/auth/login", json={"username": "iris", "password": "secret123"}
    ).get_json()
    res = client.post(
        "/auth/refresh", headers=auth_headers(login["refresh_token"])
    )
    assert res.status_code == 200
    assert res.get_json()["access_token"]


def test_refresh_rejects_access_token(client):
    client.post(
        "/auth/register",
        json={"username": "jack", "email": "jack@example.com", "password": "secret123"},
    )
    login = client.post(
        "/auth/login", json={"username": "jack", "password": "secret123"}
    ).get_json()
    res = client.post(
        "/auth/refresh", headers=auth_headers(login["access_token"])
    )
    assert res.status_code == 401


def test_me_returns_current_user(client):
    client.post(
        "/auth/register",
        json={"username": "kate", "email": "kate@example.com", "password": "secret123"},
    )
    token = client.post(
        "/auth/login", json={"username": "kate", "password": "secret123"}
    ).get_json()["access_token"]
    res = client.get("/auth/me", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.get_json()["username"] == "kate"


def test_me_requires_token(client):
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_invalid_token_rejected(client):
    res = client.get("/auth/me", headers=auth_headers("not.a.jwt"))
    assert res.status_code == 401


def test_missing_auth_header(client):
    res = client.get("/auth/me", headers={})
    assert res.status_code == 401
