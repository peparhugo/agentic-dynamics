def test_login_returns_jwt(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["token_type"] == "Bearer"
    assert len(body["access_token"].split(".")) == 3


def test_authentication_is_required(client):
    response = client.get("/api/v1/items")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"


def test_items_are_paginated(client, auth_headers):
    response = client.get("/api/v1/items?page=1&per_page=2", headers=auth_headers)

    body = response.get_json()

    assert response.status_code == 200
    assert len(body["data"]) == 2
    assert body["meta"] == {"page": 1, "per_page": 2, "total": 3, "pages": 2}


def test_create_item_validates_input(client, auth_headers):
    response = client.post("/api/v1/items", json={"name": ""}, headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_create_item_returns_created_resource(client, auth_headers):
    response = client.post("/api/v1/items", json={"name": "Eraser", "quantity": 5}, headers=auth_headers)

    assert response.status_code == 201
    assert response.get_json()["data"] == {"id": 4, "name": "Eraser", "quantity": 5}


def test_invalid_pagination_returns_json_error(client, auth_headers):
    response = client.get("/api/v1/items?page=0", headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_pagination"


def test_rate_limit_returns_429():
    app = __import__("app").create_app(
        {
            "TESTING": True,
            "JWT_SECRET": "test-secret",
            "RATE_LIMIT_REQUESTS": 1,
            "RATE_LIMIT_STORE": {},
            "AUDIT_LOG": [],
        }
    )
    client = app.test_client()

    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"}).status_code == 200
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})

    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "rate_limit_exceeded"


def test_audit_log_records_api_requests(client, auth_headers):
    client.get("/api/v1/items", headers=auth_headers)
    response = client.get("/api/v1/audit-logs", headers=auth_headers)

    assert response.status_code == 200
    records = response.get_json()["data"]
    paths = [record["path"] for record in records]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/items" in paths
    assert all("status_code" in record for record in records)


def test_unknown_version_returns_json_404(client):
    response = client.get("/api/v2/items")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"
