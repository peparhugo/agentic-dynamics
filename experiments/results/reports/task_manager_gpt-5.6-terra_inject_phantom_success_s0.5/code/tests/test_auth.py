from .conftest import register


def test_register_and_login(client):
    created = register(client)
    assert created["user"]["email"] == "owner@example.com"
    assert created["token"]

    response = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_registration_and_login_validation(client):
    assert client.post("/api/auth/register", json={"email": "bad", "password": "short"}).status_code == 400
    register(client)
    assert client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong"}).status_code == 401


def test_protected_endpoint_requires_valid_token(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401
