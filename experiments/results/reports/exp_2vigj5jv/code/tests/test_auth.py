from .conftest import register


def test_register_returns_user_and_token(client):
    response = register(client)
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["user"]["username"] == "alice"
    assert payload["token"]
    assert "password" not in payload["user"]


def test_register_validates_password_and_duplicates(client):
    assert register(client, password="short").status_code == 400
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_login_accepts_username_or_email(client):
    register(client)
    assert client.post("/api/auth/login", json={"username": "alice", "password": "password123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "alice@example.com", "password": "password123"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_protected_endpoints_require_valid_bearer_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_me_returns_authenticated_user(client, auth):
    response = client.get("/api/auth/me", headers=auth)
    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "alice@example.com"
