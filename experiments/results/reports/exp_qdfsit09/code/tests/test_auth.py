from .conftest import register


def test_register_returns_user_and_token(client):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["username"] == "bob"
    assert body["token"]
    assert "password" not in body["user"]


def test_register_rejects_duplicate_and_short_password(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert client.post("/api/auth/register", json={"username": "x", "email": "x@example.com", "password": "short"}).status_code == 400


def test_login_accepts_username_or_email(client):
    register(client)
    assert client.post("/api/auth/login", json={"username": "bob", "password": "password123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "bob@example.com", "password": "password123"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "bob", "password": "wrong"}).status_code == 401


def test_protected_endpoint_requires_valid_token(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401
