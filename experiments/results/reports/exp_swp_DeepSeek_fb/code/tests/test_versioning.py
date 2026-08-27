def test_health_under_v1(client):
    assert client.get("/v1/health").status_code == 200


def test_auth_routes_under_v1(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "versioned", "email": "v@example.com", "password": "password123"},
    )
    assert resp.status_code == 201


def test_items_routes_under_v1(client, user_headers):
    resp = client.post("/v1/items", json={"name": "v1-item"}, headers=user_headers)
    assert resp.status_code == 201


def test_non_v1_items_route_404(client, user_headers):
    resp = client.post("/items", json={"name": "no-version"}, headers=user_headers)
    assert resp.status_code == 404


def test_health_version_field(client):
    data = client.get("/v1/health").get_json()
    assert data["version"] == "v1"
