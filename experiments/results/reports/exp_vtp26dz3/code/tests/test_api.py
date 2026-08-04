from app import create_app, create_token


def test_health_is_public(client):
    assert client.get("/health").json == {"status": "ok"}


def test_token_issued_for_valid_credentials(client):
    response = client.post("/api/v1/auth/token", json={"username": "alice", "password": "correct-horse"})
    assert response.status_code == 200
    assert response.json["token_type"] == "Bearer"


def test_invalid_credentials_rejected(client):
    response = client.post("/api/v1/auth/token", json={"username": "alice", "password": "wrong"})
    assert response.status_code == 401
    assert response.json["error"]["code"] == "invalid_credentials"


def test_authentication_is_required(client):
    response = client.get("/api/v1/items")
    assert response.status_code == 401


def test_expired_token_rejected(client, app):
    token = create_token("alice", app.config["JWT_SECRET"], -1)
    response = client.get("/api/v1/items", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_validation_errors_are_structured(client, auth_headers):
    response = client.post("/api/v1/items", json={"name": "", "price": -1}, headers=auth_headers)
    assert response.status_code == 400
    assert set(response.json["error"]["details"]) == {"name", "price"}


def test_crud_and_pagination(client, auth_headers):
    first = client.post("/api/v1/items", json={"name": "First", "price": 1.5}, headers=auth_headers)
    client.post("/api/v1/items", json={"name": "Second", "price": 2}, headers=auth_headers)
    response = client.get("/api/v1/items?page=2&per_page=1", headers=auth_headers)
    assert response.json["pagination"] == {"page": 2, "per_page": 1, "total": 2, "pages": 2}
    item_id = first.json["data"]["id"]
    assert client.get(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 200
    assert client.put(f"/api/v1/items/{item_id}", json={"name": "Updated", "price": 3}, headers=auth_headers).status_code == 200
    assert client.delete(f"/api/v1/items/{item_id}", headers=auth_headers).status_code == 204


def test_rate_limit_returns_retry_after():
    app = create_app({"TESTING": True, "RATE_LIMIT": 1, "RATE_LIMIT_WINDOW_SECONDS": 60})
    client = app.test_client()
    assert client.get("/health").status_code == 200
    response = client.get("/health")
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_audit_log_records_actor_and_status(app, client, auth_headers):
    client.get("/api/v1/items", headers=auth_headers)
    event = app.extensions["audit_log"][-1]
    assert event["actor"] == "alice"
    assert event["status"] == 200


def test_unversioned_api_route_is_not_found(client):
    response = client.get("/api/items")
    assert response.status_code == 404
    assert response.is_json
