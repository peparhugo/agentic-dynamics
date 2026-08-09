import sqlite3


def test_health_and_version_header(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "version": "v1"}
    assert response.headers["API-Version"] == "1"


def test_register_and_login(client):
    response = client.post("/api/v1/auth/register", json={"username": "alice", "password": "password123"})
    assert response.status_code == 201
    assert response.json["username"] == "alice"
    response = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password123"})
    assert response.status_code == 200
    assert response.json["token_type"] == "Bearer"
    assert response.json["access_token"]


def test_duplicate_registration(client):
    payload = {"username": "alice", "password": "password123"}
    client.post("/api/v1/auth/register", json=payload)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json["error"]["code"] == "username_taken"


def test_invalid_credentials(client):
    response = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "password123"})
    assert response.status_code == 401
    assert response.json["error"]["code"] == "invalid_credentials"


def test_authentication_required(client):
    response = client.get("/api/v1/items")
    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"


def test_invalid_token(client):
    response = client.get("/api/v1/items", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.json["error"]["code"] == "invalid_token"


def test_registration_validation(client):
    response = client.post("/api/v1/auth/register", json={"username": "x", "password": "short", "admin": True})
    assert response.status_code == 422
    assert set(response.json["error"]["details"]) == {"admin"}


def test_content_type_validation(client):
    response = client.post("/api/v1/auth/register", data="not json")
    assert response.status_code == 415


def test_item_crud(client, auth):
    headers = auth()
    created = client.post("/api/v1/items", json={"name": "Book", "description": "Read me"}, headers=headers)
    assert created.status_code == 201
    item_id = created.json["id"]
    assert client.get(f"/api/v1/items/{item_id}", headers=headers).json["name"] == "Book"
    updated = client.patch(f"/api/v1/items/{item_id}", json={"name": "Notebook"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json["name"] == "Notebook"
    assert client.delete(f"/api/v1/items/{item_id}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/items/{item_id}", headers=headers).status_code == 404


def test_item_validation(client, auth):
    response = client.post("/api/v1/items", json={"name": ""}, headers=auth())
    assert response.status_code == 422
    assert "name" in response.json["error"]["details"]


def test_owner_isolation(client, auth):
    alice = auth("alice")
    item_id = client.post("/api/v1/items", json={"name": "Private"}, headers=alice).json["id"]
    bob = auth("bob")
    assert client.get(f"/api/v1/items/{item_id}", headers=bob).status_code == 404
    assert client.delete(f"/api/v1/items/{item_id}", headers=bob).status_code == 404


def test_pagination(client, auth):
    headers = auth()
    for number in range(5):
        client.post("/api/v1/items", json={"name": f"Item {number}"}, headers=headers)
    response = client.get("/api/v1/items?page=2&per_page=2", headers=headers)
    assert response.status_code == 200
    assert [item["name"] for item in response.json["data"]] == ["Item 2", "Item 3"]
    assert response.json["pagination"] == {"page": 2, "per_page": 2, "total": 5, "pages": 3}


def test_invalid_pagination(client, auth):
    response = client.get("/api/v1/items?page=zero", headers=auth())
    assert response.status_code == 422


def test_rate_limiting(app):
    app.config.update(RATE_LIMIT=2, RATE_LIMIT_WINDOW=60)
    client = app.test_client()
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    response = client.get("/api/v1/health")
    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_audit_logging(client, auth, app):
    headers = auth()
    item_id = client.post("/api/v1/items", json={"name": "Logged"}, headers=headers).json["id"]
    client.patch(f"/api/v1/items/{item_id}", json={"description": "changed"}, headers=headers)
    client.delete(f"/api/v1/items/{item_id}", headers=headers)
    db = sqlite3.connect(app.config["DATABASE"])
    actions = [row[0] for row in db.execute("SELECT action FROM audit_logs ORDER BY id")]
    db.close()
    assert actions == ["register", "login", "create", "update", "delete"]


def test_unknown_route_has_json_error(client):
    response = client.get("/api/v1/missing")
    assert response.status_code == 404
    assert response.is_json
    assert response.json["error"]["code"] == "not_found"
