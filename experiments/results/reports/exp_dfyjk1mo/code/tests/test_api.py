import jwt
import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app(
        {
            "TESTING": True,
            "JWT_SECRET": "test-secret",
            "API_USERNAME": "tester",
            "API_PASSWORD": "password",
            "RATE_LIMIT": 100,
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth(client):
    response = client.post(
        "/api/v1/auth/token", json={"username": "tester", "password": "password"}
    )
    return {"Authorization": f"Bearer {response.json['access_token']}"}


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_token_requires_valid_credentials(client):
    response = client.post("/api/v1/auth/token", json={"username": "tester", "password": "wrong"})
    assert response.status_code == 401
    assert response.json["error"]["code"] == "invalid_credentials"


def test_token_contains_subject(client):
    response = client.post(
        "/api/v1/auth/token", json={"username": "tester", "password": "password"}
    )
    claims = jwt.decode(response.json["access_token"], "test-secret", algorithms=["HS256"])
    assert claims["sub"] == "tester"


def test_items_require_authentication(client):
    response = client.get("/api/v1/items")
    assert response.status_code == 401


def test_create_and_get_item(client, auth):
    created = client.post("/api/v1/items", json={"name": "First"}, headers=auth)
    fetched = client.get(f"/api/v1/items/{created.json['id']}", headers=auth)
    assert created.status_code == 201
    assert fetched.json["name"] == "First"


def test_rejects_invalid_item(client, auth):
    response = client.post("/api/v1/items", json={"name": ""}, headers=auth)
    assert response.status_code == 422
    assert "name" in response.json["error"]["details"]


def test_rejects_unknown_fields(client, auth):
    response = client.post("/api/v1/items", json={"name": "First", "admin": True}, headers=auth)
    assert response.status_code == 422


def test_paginates_items(client, auth):
    for number in range(3):
        client.post("/api/v1/items", json={"name": f"Item {number}"}, headers=auth)
    response = client.get("/api/v1/items?page=2&per_page=2", headers=auth)
    assert len(response.json["data"]) == 1
    assert response.json["pagination"] == {"page": 2, "pages": 2, "per_page": 2, "total": 3}


def test_rejects_invalid_pagination(client, auth):
    response = client.get("/api/v1/items?page=zero", headers=auth)
    assert response.status_code == 422


def test_update_and_delete_item(client, auth):
    created = client.post("/api/v1/items", json={"name": "Before"}, headers=auth)
    item_url = f"/api/v1/items/{created.json['id']}"
    updated = client.patch(item_url, json={"name": "After"}, headers=auth)
    deleted = client.delete(item_url, headers=auth)
    assert updated.json["name"] == "After"
    assert deleted.status_code == 204
    assert client.get(item_url, headers=auth).status_code == 404


def test_rate_limiting():
    app = create_app({"TESTING": True, "RATE_LIMIT": 2, "RATE_WINDOW_SECONDS": 60})
    client = app.test_client()
    client.get("/api/v1/items")
    client.get("/api/v1/items")
    response = client.get("/api/v1/items")
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_requests_are_audited(client, app):
    client.get("/api/v1/items", headers={"X-Request-ID": "request-1"})
    event = app.extensions["audit_events"][-1]
    assert event["request_id"] == "request-1"
    assert event["status"] == 401


def test_errors_have_consistent_shape(client, auth):
    response = client.get("/api/v1/items/missing", headers=auth)
    assert response.json == {"error": {"code": "not_found", "message": "Item not found"}}
