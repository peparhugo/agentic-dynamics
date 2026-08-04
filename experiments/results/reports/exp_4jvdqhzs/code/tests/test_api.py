import jwt


def test_register_and_login_returns_jwt(client):
    credentials = {"username": "alice", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=credentials).status_code == 201
    response = client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200
    assert response.get_json()["data"]["token_type"] == "Bearer"


def test_duplicate_registration_is_conflict(client):
    credentials = {"username": "alice", "password": "password123"}
    client.post("/api/v1/auth/register", json=credentials)
    response = client.post("/api/v1/auth/register", json=credentials)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "username_exists"


def test_input_validation(client):
    response = client.post("/api/v1/auth/register", json={"username": "x", "password": "short"})
    assert response.status_code == 422
    assert set(response.get_json()["error"]["details"]) == {"username", "password"}


def test_items_require_authentication(client):
    response = client.get("/api/v1/items")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"


def test_invalid_token_is_rejected(client):
    response = client.get("/api/v1/items", headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_token"


def test_expired_token_is_rejected(app, client):
    with app.app_context():
        app.extensions["users"]["alice"] = {"username": "alice", "password_hash": "unused"}
        token = jwt.encode({"sub": "alice", "exp": 0}, app.config["JWT_SECRET"], algorithm="HS256")
    response = client.get("/api/v1/items", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "token_expired"


def test_create_get_and_delete_item(client, auth_headers):
    created = client.post("/api/v1/items", json={"name": "Notebook"}, headers=auth_headers)
    assert created.status_code == 201
    item_id = created.get_json()["data"]["id"]
    assert client.get(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 200
    assert client.delete(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 404


def test_item_validation(client, auth_headers):
    response = client.post("/api/v1/items", json={"name": "  "}, headers=auth_headers)
    assert response.status_code == 422
    assert "name" in response.get_json()["error"]["details"]


def test_pagination(client, auth_headers):
    for number in range(5):
        client.post("/api/v1/items", json={"name": f"Item {number}"}, headers=auth_headers)
    response = client.get("/api/v1/items?page=2&per_page=2", headers=auth_headers)
    body = response.get_json()
    assert [item["name"] for item in body["data"]] == ["Item 2", "Item 3"]
    assert body["meta"] == {"page": 2, "per_page": 2, "total": 5}


def test_invalid_pagination(client, auth_headers):
    response = client.get("/api/v1/items?page=nope", headers=auth_headers)
    assert response.status_code == 422


def test_audit_logging(client, auth_headers):
    created = client.post("/api/v1/items", json={"name": "Audited"}, headers=auth_headers)
    item_id = created.get_json()["data"]["id"]
    client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    response = client.get("/api/v1/audit-logs", headers=auth_headers)
    actions = [record["action"] for record in response.get_json()["data"]]
    assert actions == ["user.register", "user.login", "item.create", "item.delete"]


def test_rate_limiting():
    from app import create_app

    client = create_app({"TESTING": True, "RATE_LIMIT": 2, "RATE_WINDOW_SECONDS": 60}).test_client()
    client.get("/api/v1/items")
    client.get("/api/v1/items")
    response = client.get("/api/v1/items")
    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_api_versioning_and_json_404(client):
    response = client.get("/api/v2/items")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"]["code"] == "not_found"


def test_requires_json_content_type(client):
    response = client.post("/api/v1/auth/register", data="not json")
    assert response.status_code == 415
    assert response.get_json()["error"]["code"] == "unsupported_media_type"
