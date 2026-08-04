import pytest

from api import create_app, get_db


@pytest.fixture()
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "JWT_SECRET": "test-secret",
        "RATE_LIMIT": 100,
    })


@pytest.fixture()
def client(app):
    return app.test_client()


def register_and_login(client, username="alice"):
    assert client.post("/api/v1/auth/register", json={
        "username": username, "password": "password123"
    }).status_code == 201
    response = client.post("/api/v1/auth/login", json={
        "username": username, "password": "password123"
    })
    return {"Authorization": f"Bearer {response.json['access_token']}"}


def test_authentication_flow_and_protected_route(client):
    assert client.get("/api/v1/items").status_code == 401
    headers = register_and_login(client)
    response = client.get("/api/v1/items", headers=headers)
    assert response.status_code == 200
    assert response.json["data"] == []


def test_registration_and_login_validation(client):
    response = client.post("/api/v1/auth/register", json={"username": "a", "password": "short"})
    assert response.status_code == 400
    register_and_login(client)
    assert client.post("/api/v1/auth/register", json={
        "username": "alice", "password": "password123"
    }).status_code == 409
    assert client.post("/api/v1/auth/login", json={
        "username": "alice", "password": "wrong-password"
    }).status_code == 401


def test_item_crud_and_audit_logging(client):
    headers = register_and_login(client)
    created = client.post("/api/v1/items", headers=headers, json={
        "name": "First", "description": "An item"
    })
    assert created.status_code == 201
    item_id = created.json["id"]
    assert client.get(f"/api/v1/items/{item_id}", headers=headers).json["name"] == "First"
    updated = client.patch(f"/api/v1/items/{item_id}", headers=headers, json={"name": "Updated"})
    assert updated.json["name"] == "Updated"
    logs = client.get("/api/v1/audit-logs", headers=headers).json["data"]
    assert {entry["action"] for entry in logs} >= {"user.register", "user.login", "item.create", "item.update"}
    assert client.delete(f"/api/v1/items/{item_id}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/items/{item_id}", headers=headers).status_code == 404


def test_items_are_isolated_by_user(client):
    alice = register_and_login(client, "alice")
    item_id = client.post("/api/v1/items", headers=alice, json={"name": "Private"}).json["id"]
    bob = register_and_login(client, "bobby")
    assert client.get(f"/api/v1/items/{item_id}", headers=bob).status_code == 404
    assert client.patch(f"/api/v1/items/{item_id}", headers=bob, json={"name": "Stolen"}).status_code == 404
    assert client.delete(f"/api/v1/items/{item_id}", headers=bob).status_code == 404


def test_pagination_and_input_validation(client):
    headers = register_and_login(client)
    for index in range(3):
        client.post("/api/v1/items", headers=headers, json={"name": f"Item {index}"})
    response = client.get("/api/v1/items?page=2&per_page=2", headers=headers)
    assert response.json["pagination"] == {"page": 2, "per_page": 2, "total": 3, "pages": 2}
    assert len(response.json["data"]) == 1
    assert client.get("/api/v1/items?page=zero", headers=headers).status_code == 400
    assert client.post("/api/v1/items", headers=headers, json={"name": "ok", "extra": True}).status_code == 400


def test_rate_limiting_and_version_headers(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "limited.db"),
        "JWT_SECRET": "test-secret",
        "RATE_LIMIT": 2,
    })
    client = app.test_client()
    first = client.get("/missing")
    assert first.headers["X-API-Version"] == "1"
    assert first.headers["X-RateLimit-Remaining"] == "1"
    client.get("/missing")
    limited = client.get("/missing")
    assert limited.status_code == 429
    assert limited.json["error"]["code"] == "rate_limit_exceeded"


def test_audit_records_are_persisted(app, client):
    register_and_login(client)
    with app.app_context():
        count = get_db().execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    assert count == 2
