import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.db"),
            "JWT_SECRET": "test-secret",
            "RATE_LIMIT": 100,
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="user@example.com"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})


def token(client, email="user@example.com"):
    register(client, email)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return response.get_json()["data"]["access_token"]


def auth(value):
    return {"Authorization": f"Bearer {value}"}


def test_register_and_duplicate_email(client):
    assert register(client).status_code == 201
    response = register(client)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "email_exists"


def test_registration_validation(client):
    response = client.post("/api/v1/auth/register", json={"email": "bad", "password": "short"})
    assert response.status_code == 422
    assert set(response.get_json()["error"]["details"]) == {"email", "password"}


def test_login_rejects_bad_credentials(client):
    register(client)
    response = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "wrongpass"})
    assert response.status_code == 401


def test_items_require_authentication(client):
    response = client.get("/api/v1/items")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"


def test_create_and_get_item(client):
    access_token = token(client)
    created = client.post("/api/v1/items", headers=auth(access_token), json={"name": "First", "description": "Details"})
    assert created.status_code == 201
    item_id = created.get_json()["data"]["id"]
    fetched = client.get(f"/api/v1/items/{item_id}", headers=auth(access_token))
    assert fetched.get_json()["data"]["name"] == "First"


def test_item_validation_rejects_unknown_fields(client):
    response = client.post("/api/v1/items", headers=auth(token(client)), json={"name": "Item", "owner_id": 99})
    assert response.status_code == 422
    assert response.get_json()["error"]["details"]["unknown_fields"] == ["owner_id"]


def test_list_items_is_paginated(client):
    access_token = token(client)
    for number in range(3):
        client.post("/api/v1/items", headers=auth(access_token), json={"name": f"Item {number}"})
    response = client.get("/api/v1/items?page=2&per_page=2", headers=auth(access_token))
    body = response.get_json()
    assert len(body["data"]) == 1
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 3, "pages": 2}


def test_invalid_pagination(client):
    response = client.get("/api/v1/items?page=zero", headers=auth(token(client)))
    assert response.status_code == 422


def test_update_and_delete_item(client):
    access_token = token(client)
    item_id = client.post("/api/v1/items", headers=auth(access_token), json={"name": "Old"}).get_json()["data"]["id"]
    updated = client.patch(f"/api/v1/items/{item_id}", headers=auth(access_token), json={"name": "New"})
    assert updated.get_json()["data"]["name"] == "New"
    assert client.delete(f"/api/v1/items/{item_id}", headers=auth(access_token)).status_code == 204
    assert client.get(f"/api/v1/items/{item_id}", headers=auth(access_token)).status_code == 404


def test_users_cannot_access_each_others_items(client):
    first = token(client, "first@example.com")
    item_id = client.post("/api/v1/items", headers=auth(first), json={"name": "Private"}).get_json()["data"]["id"]
    second = token(client, "second@example.com")
    assert client.get(f"/api/v1/items/{item_id}", headers=auth(second)).status_code == 404


def test_audit_logs_record_authenticated_requests(client):
    access_token = token(client)
    client.get("/api/v1/items", headers=auth(access_token))
    response = client.get("/api/v1/audit-logs", headers=auth(access_token))
    assert response.status_code == 200
    assert any(row["path"] == "/api/v1/items" and row["status"] == 200 for row in response.get_json()["data"])


def test_rate_limit_returns_headers(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "limited.db"), "JWT_SECRET": "test", "RATE_LIMIT": 1})
    client = app.test_client()
    first = client.get("/api/v1/items")
    second = client.get("/api/v1/items")
    assert first.headers["X-RateLimit-Remaining"] == "0"
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_malformed_json_uses_standard_error(client):
    response = client.post("/api/v1/auth/register", data="{", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_json"
