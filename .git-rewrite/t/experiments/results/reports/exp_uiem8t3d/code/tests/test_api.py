import jwt

from app import create_app


def test_register_login_and_protected_route(client):
    response = client.get("/api/v1/items")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"

    response = client.post("/api/v1/auth/register", json={"username": "alice", "password": "password123"})
    assert response.status_code == 201
    assert response.get_json()["data"] == {"username": "alice"}

    duplicate = client.post("/api/v1/auth/register", json={"username": "alice", "password": "password123"})
    assert duplicate.status_code == 409

    bad_login = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong-pass"})
    assert bad_login.status_code == 401

    login = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password123"})
    token = login.get_json()["data"]["access_token"]
    assert client.get("/api/v1/items", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_invalid_and_expired_tokens(client, app):
    client.post("/api/v1/auth/register", json={"username": "alice", "password": "password123"})
    assert client.get("/api/v1/items", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    expired = jwt.encode({"sub": "alice", "exp": 1}, app.config["JWT_SECRET"], algorithm="HS256")
    response = client.get("/api/v1/items", headers={"Authorization": f"Bearer {expired}"})
    assert response.get_json()["error"]["code"] == "token_expired"


def test_item_crud_and_validation(client, auth_headers, app):
    invalid = client.post("/api/v1/items", json={"name": ""}, headers=auth_headers)
    assert invalid.status_code == 400
    assert "name" in invalid.get_json()["error"]["details"]

    created = client.post("/api/v1/items", json={"name": "First", "description": "One"}, headers=auth_headers)
    assert created.status_code == 201
    item = created.get_json()["data"]
    assert item["owner"] == "alice"

    fetched = client.get(f"/api/v1/items/{item['id']}", headers=auth_headers)
    assert fetched.get_json()["data"]["name"] == "First"
    updated = client.patch(f"/api/v1/items/{item['id']}", json={"name": "Updated"}, headers=auth_headers)
    assert updated.get_json()["data"]["name"] == "Updated"
    assert client.delete(f"/api/v1/items/{item['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/items/{item['id']}", headers=auth_headers).status_code == 404
    assert [event["action"] for event in app.audit_events][-3:] == ["item.created", "item.updated", "item.deleted"]


def test_only_owner_can_modify(client, auth_headers):
    item = client.post("/api/v1/items", json={"name": "Alice's"}, headers=auth_headers).get_json()["data"]
    client.post("/api/v1/auth/register", json={"username": "bob", "password": "password123"})
    login = client.post("/api/v1/auth/login", json={"username": "bob", "password": "password123"})
    bob_headers = {"Authorization": f"Bearer {login.get_json()['data']['access_token']}"}
    assert client.patch(f"/api/v1/items/{item['id']}", json={"name": "Stolen"}, headers=bob_headers).status_code == 403


def test_pagination(client, auth_headers):
    for number in range(5):
        client.post("/api/v1/items", json={"name": f"Item {number}"}, headers=auth_headers)
    response = client.get("/api/v1/items?page=2&per_page=2", headers=auth_headers)
    body = response.get_json()
    assert [item["name"] for item in body["data"]] == ["Item 2", "Item 3"]
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 5, "pages": 3}
    assert client.get("/api/v1/items?page=nope", headers=auth_headers).status_code == 400


def test_content_type_unknown_routes_and_version_header(client, auth_headers):
    response = client.post("/api/v1/items", data="{}", headers=auth_headers)
    assert response.status_code == 415
    assert response.headers["X-API-Version"] == "1"
    missing = client.get("/api/v1/not-real")
    assert missing.status_code == 404
    assert missing.is_json


def test_rate_limit():
    app = create_app({"TESTING": True, "RATE_LIMIT": 2, "RATE_WINDOW_SECONDS": 60})
    client = app.test_client()
    assert client.get("/missing").status_code == 404
    assert client.get("/missing").status_code == 404
    response = client.get("/missing")
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.get_json()["error"]["code"] == "rate_limit_exceeded"
