from .conftest import register


def test_register_returns_user_and_token(client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "alice@example.com"
    assert response.get_json()["token"]


def test_duplicate_email_is_rejected(client):
    register(client)
    assert register(client, "other", "ALICE@example.com").status_code == 409


def test_registration_validates_password(client):
    assert register(client, password="short").status_code == 400


def test_login_accepts_email_and_rejects_bad_password(client):
    register(client)
    assert client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "alice@example.com", "password": "password123"}).status_code == 200


def test_protected_endpoint_requires_bearer_token(client):
    assert client.get("/api/tasks").status_code == 401
