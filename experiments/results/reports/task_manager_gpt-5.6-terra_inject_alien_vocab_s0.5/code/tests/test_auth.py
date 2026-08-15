from conftest import register


def test_register_returns_user_and_token(client):
    response = register(client, "Ada@Example.COM", name="Ada")

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["user"] == {"id": 1, "email": "ada@example.com", "name": "Ada"}
    assert payload["token"].count(".") == 2


def test_registration_rejects_invalid_and_duplicate_data(client):
    assert client.post("/api/auth/register", json={"email": "a"}).status_code == 400
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_login_accepts_correct_credentials_and_rejects_bad_ones(client):
    register(client, password="secure123")

    assert client.post("/api/auth/login", json={"email": "owner@example.com", "password": "secure123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrongpass"}).status_code == 401


def test_protected_route_requires_valid_bearer_token(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
