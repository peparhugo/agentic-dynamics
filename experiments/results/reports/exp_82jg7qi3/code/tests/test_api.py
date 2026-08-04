from datetime import datetime, timedelta, timezone

import jwt

from app import create_app


def test_health_and_versioning(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "version": "v1"}
    assert client.get("/api/v2/health").status_code == 404


def test_registration_login_and_duplicate_validation(client):
    response = client.post("/api/v1/auth/register", json={"username": "alice", "password": "password123"})
    assert response.status_code == 201
    assert "password" not in response.json
    assert client.post(
        "/api/v1/auth/register", json={"username": "alice", "password": "password123"}
    ).status_code == 409

    login = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password123"})
    assert login.status_code == 200
    assert login.json["token_type"] == "Bearer"
    assert login.json["access_token"]


def test_invalid_credentials_and_protected_endpoint(client):
    client.post("/api/v1/auth/register", json={"username": "alice", "password": "password123"})
    bad_login = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrongpass"})
    assert bad_login.status_code == 401
    response = client.get("/api/v1/items")
    assert response.status_code == 401
    assert response.json["error"]["code"] == "authentication_required"


def test_expired_jwt_is_rejected(app, client):
    client.post("/api/v1/auth/register", json={"username": "alice", "password": "password123"})
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jwt.encode(
        {"sub": "1", "iat": past, "exp": past + timedelta(seconds=1)},
        app.config["JWT_SECRET"],
        algorithm="HS256",
    )
    response = client.get("/api/v1/items", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json["error"]["code"] == "invalid_token"


def test_item_crud_and_audit_log(client, auth):
    created = client.post(
        "/api/v1/items", json={"name": "First", "description": "A record"}, headers=auth
    )
    assert created.status_code == 201
    item_id = created.json["id"]
    assert client.get(f"/api/v1/items/{item_id}", headers=auth).json["name"] == "First"

    updated = client.patch(f"/api/v1/items/{item_id}", json={"name": "Updated"}, headers=auth)
    assert updated.status_code == 200
    assert updated.json["name"] == "Updated"

    logs = client.get("/api/v1/audit-logs", headers=auth)
    actions = {entry["action"] for entry in logs.json["data"]}
    assert {"register", "login", "create", "update"} <= actions

    assert client.delete(f"/api/v1/items/{item_id}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/items/{item_id}", headers=auth).status_code == 404


def test_users_cannot_access_each_others_items(client, auth):
    item_id = client.post("/api/v1/items", json={"name": "Private"}, headers=auth).json["id"]
    client.post("/api/v1/auth/register", json={"username": "other", "password": "password123"})
    login = client.post("/api/v1/auth/login", json={"username": "other", "password": "password123"})
    other_auth = {"Authorization": f"Bearer {login.json['access_token']}"}
    assert client.get(f"/api/v1/items/{item_id}", headers=other_auth).status_code == 404


def test_pagination(client, auth):
    for number in range(3):
        client.post("/api/v1/items", json={"name": f"Item {number}"}, headers=auth)
    response = client.get("/api/v1/items?page=2&per_page=2", headers=auth)
    assert response.status_code == 200
    assert len(response.json["data"]) == 1
    assert response.json["pagination"] == {"page": 2, "per_page": 2, "total": 3, "pages": 2}


def test_input_validation_and_json_errors(client, auth):
    response = client.post("/api/v1/items", json={"name": "", "extra": True}, headers=auth)
    assert response.status_code == 422
    assert response.json["error"]["code"] == "validation_error"
    assert client.post("/api/v1/items", data="not json", headers=auth).status_code == 415
    assert client.get("/api/v1/items?page=nope", headers=auth).status_code == 422


def test_rate_limiting(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "limited.sqlite3"),
        "RATE_LIMIT": 2,
        "RATE_WINDOW_SECONDS": 60,
    })
    client = app.test_client()
    assert client.get("/api/v1/health").status_code == 200
    second = client.get("/api/v1/health")
    assert second.headers["X-RateLimit-Remaining"] == "0"
    limited = client.get("/api/v1/health")
    assert limited.status_code == 429
    assert limited.json["error"]["code"] == "rate_limit_exceeded"
    assert int(limited.headers["Retry-After"]) >= 1


def test_http_errors_use_consistent_schema(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json["error"]["code"] == "not_found"
