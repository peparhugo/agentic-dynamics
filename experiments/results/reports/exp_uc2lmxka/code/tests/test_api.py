from app import get_db


def test_health_and_api_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert response.headers["X-API-Version"] == "1"


def test_register_login_and_protected_route(client):
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "User@Example.com", "password": "password123"},
    )
    assert registered.status_code == 201
    assert registered.get_json()["email"] == "user@example.com"

    denied = client.get("/api/v1/items")
    assert denied.status_code == 401
    assert denied.get_json()["error"]["code"] == "authentication_required"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.get_json()["token_type"] == "Bearer"
    headers = {"Authorization": f"Bearer {login.get_json()['access_token']}"}
    assert client.get("/api/v1/items", headers=headers).status_code == 200


def test_registration_validation_and_duplicate(client):
    invalid = client.post(
        "/api/v1/auth/register",
        json={"email": "invalid", "password": "short", "admin": True},
    )
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "validation_error"

    payload = {"email": "a@example.com", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409


def test_json_content_type_and_malformed_body(client):
    response = client.post("/api/v1/auth/register", data="email=x")
    assert response.status_code == 415
    malformed = client.post(
        "/api/v1/auth/register", data="{", content_type="application/json"
    )
    assert malformed.status_code == 400


def test_item_crud(client, auth_headers):
    created = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "First", "description": "A test item"},
    )
    assert created.status_code == 201
    item_id = created.get_json()["id"]

    fetched = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert fetched.get_json()["name"] == "First"
    updated = client.patch(
        f"/api/v1/items/{item_id}", headers=auth_headers, json={"name": "Updated"}
    )
    assert updated.status_code == 200
    assert updated.get_json()["name"] == "Updated"
    assert updated.get_json()["description"] == "A test item"
    assert client.delete(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 404


def test_items_are_scoped_to_owner(client, auth_headers):
    item = client.post("/api/v1/items", headers=auth_headers, json={"name": "Private"}).get_json()
    client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "password123"})
    login = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {login.get_json()['access_token']}"}
    assert client.get(f"/api/v1/items/{item['id']}", headers=other_headers).status_code == 404


def test_pagination(client, auth_headers):
    for number in range(3):
        client.post("/api/v1/items", headers=auth_headers, json={"name": f"Item {number}"})
    response = client.get("/api/v1/items?page=2&per_page=2", headers=auth_headers)
    body = response.get_json()
    assert [item["name"] for item in body["data"]] == ["Item 2"]
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 3, "pages": 2}
    assert client.get("/api/v1/items?per_page=101", headers=auth_headers).status_code == 422


def test_invalid_token(client):
    response = client.get("/api/v1/items", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_token"


def test_rate_limit(tmp_path):
    from app import create_app

    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "limited.sqlite"),
            "JWT_SECRET": "test-secret",
            "RATE_LIMIT": 2,
            "RATE_LIMIT_WINDOW": 60,
        }
    )
    client = app.test_client()
    assert client.get("/api/v1/missing").status_code == 404
    second = client.get("/api/v1/missing")
    assert second.headers["X-RateLimit-Remaining"] == "0"
    limited = client.get("/api/v1/missing")
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0


def test_audit_log_records_requests(app, client, auth_headers):
    client.post("/api/v1/items", headers=auth_headers, json={"name": "Audited"})
    with app.app_context():
        logs = get_db().execute(
            "SELECT action, status, user_id FROM audit_logs ORDER BY id"
        ).fetchall()
    assert any(row["action"] == "create_item" and row["status"] == 201 for row in logs)
    assert logs[-1]["user_id"] is not None


def test_unknown_api_route_uses_json_error(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"]["code"] == "not_found"
