import pytest

from app import AuditLog, create_app, db


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "test-secret",
        "RATELIMIT_ENABLED": True,
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
    tokens = login(client).get_json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}, tokens


def test_registration_login_and_me(client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json()["email"] == "user@example.com"
    assert register(client).status_code == 409
    tokens = login(client).get_json()
    response = client.get("/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200
    assert response.get_json()["email"] == "user@example.com"


@pytest.mark.parametrize("payload,status", [
    ({"email": "bad", "password": "password1"}, 422),
    ({"email": "a@b.com", "password": "short"}, 422),
    ({"email": "a@b.com"}, 400),
])
def test_registration_validation(client, payload, status):
    assert client.post("/v1/auth/register", json=payload).status_code == status


def test_authentication_errors(client):
    assert client.get("/v1/items").status_code == 401
    register(client)
    assert login(client, password="incorrect").status_code == 401


def test_login_rate_limit(client):
    for _ in range(5):
        assert login(client, email="missing@example.com").status_code == 401
    assert login(client, email="missing@example.com").status_code == 429


def test_refresh_rotation_and_logout(client):
    headers, tokens = auth(client)
    refresh_headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    response = client.post("/v1/auth/refresh", headers=refresh_headers)
    assert response.status_code == 200
    assert client.post("/v1/auth/refresh", headers=refresh_headers).status_code == 401
    assert client.delete("/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/v1/users/me", headers=headers).status_code == 401


def test_item_crud_and_audit(client, app):
    headers, _ = auth(client)
    response = client.post("/v1/items", headers=headers, json={"name": "one", "description": "first"})
    assert response.status_code == 201
    item_id = response.get_json()["id"]
    assert client.get(f"/v1/items/{item_id}", headers=headers).status_code == 200
    response = client.patch(f"/v1/items/{item_id}", headers=headers, json={"name": "two"})
    assert response.status_code == 200
    assert response.get_json()["name"] == "two"
    assert client.delete(f"/v1/items/{item_id}", headers=headers).status_code == 204
    assert client.get(f"/v1/items/{item_id}", headers=headers).status_code == 404
    logs = client.get("/v1/audit-logs", headers=headers).get_json()["items"]
    actions = {(row["action"], row["resource_type"]) for row in logs}
    assert {("create", "user"), ("login", "session"), ("create", "item"), ("update", "item"), ("delete", "item")} <= actions
    with app.app_context():
        assert db.session.query(AuditLog).count() == 5


def test_item_validation(client):
    headers, _ = auth(client)
    assert client.post("/v1/items", headers=headers, json={"name": ""}).status_code == 422
    assert client.post("/v1/items", headers=headers, data="x", content_type="text/plain").status_code == 415
    assert client.post("/v1/items", headers=headers, json={"name": "ok", "extra": 1}).status_code == 400


def test_item_ownership(client):
    headers1, _ = auth(client)
    item_id = client.post("/v1/items", headers=headers1, json={"name": "private"}).get_json()["id"]
    register(client, "other@example.com")
    token = login(client, "other@example.com").get_json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/v1/items/{item_id}", headers=headers2).status_code == 404
    assert client.patch(f"/v1/items/{item_id}", headers=headers2, json={"name": "stolen"}).status_code == 404
    assert client.delete(f"/v1/items/{item_id}", headers=headers2).status_code == 404


def test_pagination(client):
    headers, _ = auth(client)
    for number in range(25):
        assert client.post("/v1/items", headers=headers, json={"name": str(number)}).status_code == 201
    first = client.get("/v1/items", headers=headers).get_json()
    second = client.get("/v1/items?page=2", headers=headers).get_json()
    assert len(first["items"]) == 20
    assert len(second["items"]) == 5
    assert first["pagination"] == {"page": 1, "per_page": 20, "total": 25, "pages": 2}
    assert client.get("/v1/items?per_page=101", headers=headers).status_code == 400
    assert client.get("/v1/items?page=nope", headers=headers).status_code == 400


def test_not_found_and_method_errors(client):
    response = client.get("/v1/unknown")
    assert response.status_code == 404
    assert "error" in response.get_json()
    assert client.put("/v1/auth/login").status_code == 405
