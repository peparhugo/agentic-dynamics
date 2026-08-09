import pytest

from app import create_app, create_token


@pytest.fixture
def app():
    return create_app({"TESTING": True, "SECRET_KEY": "test-secret", "DISABLE_RATE_LIMIT": True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_jwt(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"].count(".") == 2


def test_login_rejects_invalid_credentials(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_credentials"


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/v1/items")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "missing_token"


def test_protected_endpoint_rejects_invalid_token(client):
    response = client.get("/api/v1/items", headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_token"


def test_create_item_validates_input(client, auth_headers):
    response = client.post("/api/v1/items", json={"name": ""}, headers=auth_headers)

    assert response.status_code == 422
    body = response.get_json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["fields"]["name"] == "must be a non-empty str"


def test_create_and_paginate_items(client, auth_headers):
    for name in ["one", "two", "three"]:
        response = client.post("/api/v1/items", json={"name": name}, headers=auth_headers)
        assert response.status_code == 201

    response = client.get("/api/v1/items?page=2&per_page=2", headers=auth_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"] == [{"id": 3, "name": "three"}]
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 3, "pages": 2}


def test_pagination_validates_query_params(client, auth_headers):
    response = client.get("/api/v1/items?page=0", headers=auth_headers)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_rate_limit_returns_429():
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "RATE_LIMIT": 2, "RATE_LIMIT_WINDOW_SECONDS": 60})
    client = app.test_client()

    assert client.get("/api/v1/items").status_code == 401
    assert client.get("/api/v1/items").status_code == 401
    response = client.get("/api/v1/items")

    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "rate_limited"


def test_expired_token_is_rejected(client):
    token = create_token("admin", "test-secret", ttl_seconds=-1)
    response = client.get("/api/v1/items", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "token_expired"


def test_audit_logging_records_success_and_failure(app, client, auth_headers):
    client.post("/api/v1/items", json={"name": "audited"}, headers=auth_headers)
    client.post("/api/v1/items", json={"name": ""}, headers=auth_headers)

    assert any(event["action"] == "create_item" and event["status"] == "success" for event in app.audit_events)
    assert any(event["action"] == "request_failed" and event["status"] == "failure" for event in app.audit_events)


def test_api_versioning_uses_v1_prefix(client):
    assert client.get("/items").status_code == 404
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"}).status_code == 200
