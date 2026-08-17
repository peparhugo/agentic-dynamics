import time

from task_api.auth import create_token

from .conftest import auth_header


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_register_normalizes_email_and_does_not_expose_password(client):
    response = client.post(
        "/auth/register",
        json={"name": "Alice", "email": " Alice@EXAMPLE.com ", "password": "password123"},
    )
    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "alice@example.com"
    assert "password" not in response.get_data(as_text=True)


def test_register_validates_body(client):
    assert client.post("/auth/register", data="bad", content_type="text/plain").status_code == 400
    assert client.post("/auth/register", json={"name": "", "email": "bad", "password": "short"}).status_code == 400
    assert client.post("/auth/register", json={"name": "A", "email": "a@example.com", "password": "short"}).status_code == 400


def test_duplicate_registration_is_case_insensitive(client, register):
    register()
    response = client.post(
        "/auth/register",
        json={"name": "Other", "email": "ALICE@example.com", "password": "password123"},
    )
    assert response.status_code == 409


def test_login_and_current_user(client, user):
    account, token = user
    response = client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.get_json()["user"] == account


def test_login_rejects_invalid_credentials(client, register):
    register()
    response = client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert "token" not in response.get_data(as_text=True)


def test_auth_rejects_missing_tampered_and_expired_tokens(app, client, user):
    _, token = user
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth_header(token + "x")).status_code == 401
    with app.app_context():
        app.config["JWT_TTL_SECONDS"] = -1
        expired = create_token(1)
    assert time.time() > 0
    assert client.get("/auth/me", headers=auth_header(expired)).status_code == 401
