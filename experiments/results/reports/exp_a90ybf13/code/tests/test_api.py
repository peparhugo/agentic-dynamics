from app import AUDIT_LOG


def test_login_returns_jwt(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["access_token"]
    assert body["token_type"] == "Bearer"


def test_protected_route_requires_bearer_token(client):
    response = client.get("/api/v1/items")

    assert response.status_code == 401
    assert response.get_json()["error"]["message"] == "Missing bearer token"


def test_items_are_paginated(client, auth_headers):
    response = client.get("/api/v1/items?page=1&per_page=2", headers=auth_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert len(body["data"]) == 2
    assert body["pagination"] == {"page": 1, "per_page": 2, "total": 3, "pages": 2}


def test_create_item_validates_input(client, auth_headers):
    response = client.post("/api/v1/items", json={"name": "", "description": "Useful"}, headers=auth_headers)

    assert response.status_code == 422
    assert response.get_json()["error"]["details"]["name"] == "must not be blank"


def test_create_item_returns_created_resource(client, auth_headers):
    response = client.post("/api/v1/items", json={"name": "Pencil", "description": "HB"}, headers=auth_headers)

    assert response.status_code == 201
    assert response.get_json()["data"]["name"] == "Pencil"


def test_rate_limit_returns_429(client):
    for _ in range(3):
        response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})
        assert response.status_code == 200

    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})

    assert response.status_code == 429
    assert response.headers["X-RateLimit-Remaining"] == "0"


def test_audit_log_records_api_request(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert AUDIT_LOG[-1]["path"] == "/api/v1/health"
    assert AUDIT_LOG[-1]["status_code"] == 200
