from .conftest import register


def test_register_returns_user_and_token(client):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["token"]


def test_register_normalizes_email_and_rejects_duplicate(client):
    register(client, email="Alice@Example.com")
    response = register(client, email=" alice@example.com ")
    assert response.status_code == 409


def test_register_validates_required_fields(client):
    assert client.post("/api/auth/register", json={}).status_code == 400
    assert client.post("/api/auth/register", json={"email": "a@b.com", "password": "short", "name": "A"}).status_code == 400
    assert client.post("/api/auth/register", json={"email": "a@b.com", "password": "password123"}).status_code == 400


def test_login_and_me(client):
    register(client)
    response = client.post("/api/auth/login", json={"email": "ALICE@EXAMPLE.COM", "password": "password123"})
    assert response.status_code == 200
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {response.get_json()['token']}"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["name"] == "Alice"


def test_login_rejects_bad_credentials(client):
    register(client)
    assert client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass"}).status_code == 401


def test_protected_endpoint_requires_valid_token(client):
    assert client.get("/api/tasks").status_code == 401
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer invalid"
    assert client.get("/api/tasks").status_code == 401
