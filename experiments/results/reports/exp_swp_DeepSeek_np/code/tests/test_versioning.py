from tests.conftest import auth_headers


def test_auth_routes_are_versioned(client):
    assert client.post(
        "/v1/auth/register", json={"email": "a@b.com", "password": "password123"}
    ).status_code == 201
    assert client.post(
        "/auth/register", json={"email": "a@b.com", "password": "password123"}
    ).status_code == 404


def test_items_routes_are_versioned(client):
    headers = auth_headers(client)
    assert client.get("/v1/items", headers=headers).status_code == 200
    assert client.get("/items", headers=headers).status_code == 404


def test_login_route_is_versioned(client):
    assert client.post("/v1/auth/login", json={}).status_code == 422
    assert client.post("/auth/login", json={}).status_code == 404
