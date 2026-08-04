import jwt


def test_register_and_login(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password123"},
    )
    assert response.status_code == 201
    assert response.get_json() == {"username": "alice"}

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    assert response.status_code == 200
    assert response.get_json()["token_type"] == "Bearer"


def test_registration_validation_and_conflict(client):
    response = client.post(
        "/api/v1/auth/register", json={"username": "x", "password": "short"}
    )
    assert response.status_code == 400
    assert set(response.get_json()["error"]["details"]) == {"username", "password"}

    payload = {"username": "alice", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_rejects_bad_credentials(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "password123"}
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_credentials"


def test_protected_endpoint_requires_valid_token(client):
    assert client.get("/api/v1/items").status_code == 401
    response = client.get(
        "/api/v1/items", headers={"Authorization": "Bearer invalid"}
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_token"


def test_expired_token_is_rejected(app, client):
    app.extensions["users"]["alice"] = {"password_hash": "unused"}
    token = jwt.encode({"sub": "alice", "exp": 1}, "test-secret", algorithm="HS256")
    response = client.get(
        "/api/v1/items", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "token_expired"


def test_item_crud(client, auth_headers):
    response = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"title": "First", "description": "Example"},
    )
    assert response.status_code == 201
    item_id = response.get_json()["id"]

    response = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert response.get_json()["title"] == "First"

    response = client.patch(
        f"/api/v1/items/{item_id}", headers=auth_headers, json={"title": "Updated"}
    )
    assert response.status_code == 200
    assert response.get_json()["title"] == "Updated"

    assert client.delete(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 404


def test_item_input_validation(client, auth_headers):
    response = client.post("/api/v1/items", headers=auth_headers, json={"title": ""})
    assert response.status_code == 400
    assert "title" in response.get_json()["error"]["details"]


def test_items_are_scoped_to_owner(client, auth_headers):
    item_id = client.post(
        "/api/v1/items", headers=auth_headers, json={"title": "Private"}
    ).get_json()["id"]
    client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "password123"},
    )
    bob_headers = {"Authorization": f"Bearer {login.get_json()['access_token']}"}
    assert client.get(f"/api/v1/items/{item_id}", headers=bob_headers).status_code == 404


def test_pagination(client, auth_headers):
    for number in range(3):
        client.post(
            "/api/v1/items", headers=auth_headers, json={"title": f"Item {number}"}
        )
    response = client.get("/api/v1/items?page=2&per_page=2", headers=auth_headers)
    body = response.get_json()
    assert response.status_code == 200
    assert len(body["data"]) == 1
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 3, "pages": 2}

    assert client.get("/api/v1/items?page=0", headers=auth_headers).status_code == 400


def test_rate_limiting():
    from app import create_app

    client = create_app(
        {"TESTING": True, "JWT_SECRET": "test", "RATE_LIMIT": 2}
    ).test_client()
    assert client.get("/missing").status_code == 404
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.headers["X-RateLimit-Remaining"] == "0"
    response = client.get("/missing")
    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_json_errors_and_versioned_routes(client):
    response = client.get("/api/v2/items")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"]["code"] == "not_found"


def test_audit_log_records_actor_without_secrets(app, client, auth_headers, caplog):
    with caplog.at_level("INFO", logger="api.audit"):
        response = client.post(
            "/api/v1/items",
            headers=auth_headers,
            json={"title": "Audited", "description": "secret body"},
        )
    event = app.extensions["audit_events"][-1]
    assert event["actor"] == "alice"
    assert event["status"] == 201
    assert "secret body" not in caplog.text
    assert response.headers["X-RateLimit-Limit"] == "100"
