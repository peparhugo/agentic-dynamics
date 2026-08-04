from app.extensions import db
from app.models import AuditLog


def test_health_and_versioning(client):
    assert client.get("/v1/health").get_json() == {"status": "ok"}
    assert client.get("/health").status_code == 404


def test_registration_login_and_refresh(client):
    registration = client.post(
        "/v1/auth/register",
        json={"email": "Test@Example.com", "password": "password123"},
    )
    assert registration.status_code == 201
    payload = registration.get_json()
    assert payload["user"]["email"] == "test@example.com"
    assert payload["access_token"] and payload["refresh_token"]

    login = client.post(
        "/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    refresh = client.post(
        "/v1/auth/refresh",
        headers={"Authorization": f"Bearer {login.get_json()['refresh_token']}"},
    )
    assert refresh.status_code == 200
    assert refresh.get_json()["access_token"]


def test_auth_errors_and_input_validation(client, registered):
    assert client.get("/v1/items").status_code == 401
    assert client.post("/v1/auth/register", data="not json").status_code == 400
    assert client.post(
        "/v1/auth/register", json={"email": "bad", "password": "short"}
    ).status_code == 400
    assert client.post(
        "/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    ).status_code == 409
    assert client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "wrong"},
    ).status_code == 401


def test_login_is_limited_to_five_attempts_per_ip(client):
    for _ in range(5):
        response = client.post(
            "/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
            environ_base={"REMOTE_ADDR": "203.0.113.5"},
        )
        assert response.status_code == 401
    limited = client.post(
        "/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
        environ_base={"REMOTE_ADDR": "203.0.113.5"},
    )
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0

    other_ip = client.post(
        "/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
        environ_base={"REMOTE_ADDR": "203.0.113.6"},
    )
    assert other_ip.status_code == 401


def test_item_crud_and_audit_logging(client, auth_headers, app):
    created = client.post(
        "/v1/items", json={"name": "First", "description": "Details"}, headers=auth_headers
    )
    assert created.status_code == 201
    item_id = created.get_json()["item"]["id"]

    fetched = client.get(f"/v1/items/{item_id}", headers=auth_headers)
    assert fetched.status_code == 200
    updated = client.patch(
        f"/v1/items/{item_id}", json={"name": "Updated"}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.get_json()["item"]["name"] == "Updated"
    deleted = client.delete(f"/v1/items/{item_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/v1/items/{item_id}", headers=auth_headers).status_code == 404

    logs = client.get("/v1/audit-logs", headers=auth_headers).get_json()
    assert [entry["action"] for entry in logs["audit_logs"]] == [
        "delete",
        "update",
        "create",
        "create",
    ]
    with app.app_context():
        assert db.session.query(AuditLog).count() == 4


def test_items_are_private(client, auth_headers):
    item_id = client.post("/v1/items", json={"name": "Private"}, headers=auth_headers).get_json()[
        "item"
    ]["id"]
    second = client.post(
        "/v1/auth/register",
        json={"email": "second@example.com", "password": "password123"},
    ).get_json()
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    assert client.get(f"/v1/items/{item_id}", headers=second_headers).status_code == 404
    assert client.patch(
        f"/v1/items/{item_id}", json={"name": "Stolen"}, headers=second_headers
    ).status_code == 404
    assert client.delete(f"/v1/items/{item_id}", headers=second_headers).status_code == 404


def test_item_validation(client, auth_headers):
    assert client.post("/v1/items", json={}, headers=auth_headers).status_code == 400
    assert client.post(
        "/v1/items", json={"name": "x", "owner_id": 999}, headers=auth_headers
    ).status_code == 400
    created = client.post("/v1/items", json={"name": "Valid"}, headers=auth_headers)
    item_id = created.get_json()["item"]["id"]
    assert client.patch(f"/v1/items/{item_id}", json={}, headers=auth_headers).status_code == 400
    assert client.put(
        f"/v1/items/{item_id}", json={"description": "missing name"}, headers=auth_headers
    ).status_code == 400


def test_pagination_defaults_and_bounds(client, auth_headers):
    for number in range(25):
        assert client.post(
            "/v1/items", json={"name": f"Item {number}"}, headers=auth_headers
        ).status_code == 201
    first = client.get("/v1/items", headers=auth_headers).get_json()
    assert len(first["items"]) == 20
    assert first["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total": 25,
        "pages": 2,
        "has_next": True,
        "has_prev": False,
    }
    assert len(client.get("/v1/items?page=2", headers=auth_headers).get_json()["items"]) == 5
    assert client.get("/v1/items?per_page=100", headers=auth_headers).status_code == 200
    assert client.get("/v1/items?per_page=101", headers=auth_headers).status_code == 400
    assert client.get("/v1/items?page=zero", headers=auth_headers).status_code == 400


def test_json_errors_for_unknown_routes_and_methods(client):
    missing = client.get("/v1/missing")
    assert missing.status_code == 404
    assert missing.is_json
    assert missing.get_json()["error"]["code"] == "not_found"
    method = client.delete("/v1/health")
    assert method.status_code == 405
    assert method.is_json
