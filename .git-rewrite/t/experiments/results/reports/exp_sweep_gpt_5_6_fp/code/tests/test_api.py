import pytest

from app import AuditLog, Item, create_app, db


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "test-secret",
        "RATELIMIT_ENABLED": False,
    })
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="user@example.com", password="password1"):
    return client.post("/v1/auth/register", json={"email": email, "password": password})


def login(client, email="user@example.com", password="password1"):
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def auth(client):
    register(client)
    payload = login(client).get_json()
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload["refresh_token"]


def test_register_and_duplicate(client):
    response = register(client, " USER@example.com ")
    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "user@example.com"
    assert register(client).status_code == 409


@pytest.mark.parametrize("payload", [
    {},
    {"email": "bad", "password": "password1"},
    {"email": "a@b.com", "password": "short"},
    {"email": "a@b.com", "password": "password1", "extra": True},
])
def test_register_validation(client, payload):
    assert client.post("/v1/auth/register", json=payload).status_code == 422


def test_json_content_type_validation(client):
    assert client.post("/v1/auth/register", data="x").status_code == 415
    assert client.post("/v1/auth/register", data="[]", content_type="application/json").status_code == 400


def test_login_and_protected_endpoint(client):
    register(client)
    assert login(client, password="wrongpass").status_code == 401
    response = login(client)
    assert response.status_code == 200
    token = response.get_json()["access_token"]
    assert client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/v1/users/me").status_code == 401


def test_refresh_rotation_and_logout(client):
    _, refresh = auth(client)
    headers = {"Authorization": f"Bearer {refresh}"}
    response = client.post("/v1/auth/refresh", headers=headers)
    assert response.status_code == 200
    assert client.post("/v1/auth/refresh", headers=headers).status_code == 401
    new_refresh = response.get_json()["refresh_token"]
    new_headers = {"Authorization": f"Bearer {new_refresh}"}
    assert client.post("/v1/auth/logout", headers=new_headers).status_code == 204
    assert client.post("/v1/auth/refresh", headers=new_headers).status_code == 401


def test_item_crud_and_auditing(client, app):
    headers, _ = auth(client)
    created = client.post("/v1/items", json={"name": "One", "description": "First"}, headers=headers)
    assert created.status_code == 201
    item_id = created.get_json()["item"]["id"]
    assert client.get(f"/v1/items/{item_id}", headers=headers).status_code == 200
    updated = client.patch(f"/v1/items/{item_id}", json={"name": "Two"}, headers=headers)
    assert updated.status_code == 200
    assert updated.get_json()["item"]["name"] == "Two"
    assert client.delete(f"/v1/items/{item_id}", headers=headers).status_code == 204
    assert client.get(f"/v1/items/{item_id}", headers=headers).status_code == 404
    with app.app_context():
        actions = [row.action for row in db.session.scalars(db.select(AuditLog).where(AuditLog.resource == "item"))]
        assert actions == ["create", "update", "delete"]


@pytest.mark.parametrize("method,payload", [
    ("post", {}),
    ("post", {"name": ""}),
    ("post", {"name": "x", "description": 2}),
    ("post", {"name": "x", "other": 2}),
])
def test_item_validation(client, method, payload):
    headers, _ = auth(client)
    assert getattr(client, method)("/v1/items", json=payload, headers=headers).status_code == 422


def test_update_validation(client):
    headers, _ = auth(client)
    item_id = client.post("/v1/items", json={"name": "One"}, headers=headers).get_json()["item"]["id"]
    assert client.patch(f"/v1/items/{item_id}", json={}, headers=headers).status_code == 422
    assert client.put(f"/v1/items/{item_id}", json={"description": "x"}, headers=headers).status_code == 422


def test_items_are_private(client):
    first_headers, _ = auth(client)
    item_id = client.post("/v1/items", json={"name": "Private"}, headers=first_headers).get_json()["item"]["id"]
    register(client, "other@example.com")
    token = login(client, "other@example.com").get_json()["access_token"]
    second_headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/v1/items/{item_id}", headers=second_headers).status_code == 404
    assert client.get("/v1/items", headers=second_headers).get_json()["items"] == []


def test_pagination_defaults_and_limits(client, app):
    headers, _ = auth(client)
    with app.app_context():
        db.session.add_all(Item(name=str(i), owner_id=1) for i in range(25))
        db.session.commit()
    response = client.get("/v1/items", headers=headers)
    assert len(response.get_json()["items"]) == 20
    assert response.get_json()["pagination"]["total"] == 25
    assert len(client.get("/v1/items?page=2&per_page=10", headers=headers).get_json()["items"]) == 10
    assert client.get("/v1/items?per_page=101", headers=headers).status_code == 422
    assert client.get("/v1/items?page=nope", headers=headers).status_code == 422


def test_audit_logs_are_paginated(client):
    headers, _ = auth(client)
    response = client.get("/v1/audit-logs", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["pagination"]["per_page"] == 20
    assert {entry["resource"] for entry in response.get_json()["items"]} == {"user", "session"}


def test_versioning_and_http_errors(client):
    assert client.get("/v1/health").status_code == 200
    response = client.get("/health")
    assert response.status_code == 404
    assert response.is_json


def test_rate_limit():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "test-secret",
        "RATELIMIT_ENABLED": True,
        "RATELIMIT_STORAGE_URI": "memory://",
    })
    client = app.test_client()
    for _ in range(5):
        assert login(client).status_code == 401
    response = login(client)
    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "rate_limit_exceeded"
    assert "Retry-After" in response.headers
