import pytest


def register(client, email="new@example.com", password="password123"):
    return client.post("/v1/auth/register", json={"email": email, "password": password})


def test_health_and_versioning(client):
    assert client.get("/v1/health").get_json() == {"status": "ok"}
    assert client.get("/health").status_code == 404
    assert client.get("/v1/health?extra=1").status_code == 400


def test_registration_login_and_duplicate(client):
    response = register(client, email="Person@Example.com")
    assert response.status_code == 201
    assert response.get_json()["user"]["email"] == "person@example.com"
    assert register(client, email="person@example.com").status_code == 409

    response = client.post(
        "/v1/auth/login",
        json={"email": "person@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert {"access_token", "refresh_token", "token_type"} <= response.get_json().keys()


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"email": "bad", "password": "password123"}, 400),
        ({"email": "a@example.com", "password": "short"}, 400),
        ({"email": "a@example.com"}, 400),
        ({"email": "a@example.com", "password": "password123", "x": 1}, 400),
    ],
)
def test_registration_validation(client, payload, status):
    assert client.post("/v1/auth/register", json=payload).status_code == status


def test_json_content_type_is_required(client):
    response = client.post("/v1/auth/register", data="not json")
    assert response.status_code == 415
    assert response.is_json


def test_login_errors_and_rate_limit(client):
    register(client)
    payload = {"email": "new@example.com", "password": "wrongpass"}
    for _ in range(5):
        assert client.post("/v1/auth/login", json=payload).status_code == 401
    response = client.post("/v1/auth/login", json=payload)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


def test_login_rate_limit_is_per_ip(client):
    payload = {"email": "none@example.com", "password": "wrongpass"}
    for _ in range(5):
        client.post("/v1/auth/login", json=payload, environ_base={"REMOTE_ADDR": "1.1.1.1"})
    assert client.post(
        "/v1/auth/login", json=payload, environ_base={"REMOTE_ADDR": "2.2.2.2"}
    ).status_code == 401


def test_authentication_is_required(client):
    response = client.get("/v1/items")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"
    assert client.get(
        "/v1/items", headers={"Authorization": "Bearer nonsense"}
    ).status_code == 401


def test_refresh_rotation_and_logout(client, auth):
    first = client.post("/v1/auth/refresh", json={"refresh_token": auth["refresh"]})
    assert first.status_code == 200
    assert client.post(
        "/v1/auth/refresh", json={"refresh_token": auth["refresh"]}
    ).status_code == 401

    tokens = first.get_json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.post(
        "/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    ).status_code == 204
    assert client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).status_code == 401


def test_refresh_rejects_access_token(client, auth):
    response = client.post("/v1/auth/refresh", json={"refresh_token": auth["access"]})
    assert response.status_code == 401


def test_item_crud_and_audit_log(client, auth):
    headers = auth["headers"]
    created = client.post(
        "/v1/items", json={"name": " First ", "description": "Description"}, headers=headers
    )
    assert created.status_code == 201
    item_id = created.get_json()["id"]
    assert created.get_json()["name"] == "First"
    assert client.get(f"/v1/items/{item_id}", headers=headers).status_code == 200

    updated = client.patch(
        f"/v1/items/{item_id}", json={"name": "Updated"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.get_json()["name"] == "Updated"
    assert client.delete(f"/v1/items/{item_id}", headers=headers).status_code == 204
    assert client.get(f"/v1/items/{item_id}", headers=headers).status_code == 404

    logs = client.get("/v1/audit-logs?per_page=100", headers=headers).get_json()["items"]
    actions = [entry["action"] for entry in logs]
    assert actions == ["register", "create", "update", "delete"]


def test_items_are_owner_scoped(client, auth):
    created = client.post("/v1/items", json={"name": "Private"}, headers=auth["headers"])
    item_id = created.get_json()["id"]
    other = register(client, "other@example.com").get_json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"/v1/items/{item_id}", headers=other_headers).status_code == 404
    assert client.patch(
        f"/v1/items/{item_id}", json={"name": "Stolen"}, headers=other_headers
    ).status_code == 404
    assert client.delete(f"/v1/items/{item_id}", headers=other_headers).status_code == 404


@pytest.mark.parametrize(
    "method,payload",
    [
        ("post", {}),
        ("post", {"name": ""}),
        ("post", {"name": "ok", "unknown": True}),
    ],
)
def test_item_create_validation(client, auth, method, payload):
    assert getattr(client, method)("/v1/items", json=payload, headers=auth["headers"]).status_code == 400


def test_empty_item_patch_is_rejected(client, auth):
    item = client.post("/v1/items", json={"name": "Item"}, headers=auth["headers"]).get_json()
    assert client.patch(
        f"/v1/items/{item['id']}", json={}, headers=auth["headers"]
    ).status_code == 400


def test_pagination_defaults_and_limits(client, auth):
    for number in range(25):
        client.post("/v1/items", json={"name": f"Item {number}"}, headers=auth["headers"])
    first = client.get("/v1/items", headers=auth["headers"]).get_json()
    assert len(first["items"]) == 20
    assert first["pagination"] == {"page": 1, "per_page": 20, "total": 25, "pages": 2}
    second = client.get("/v1/items?page=2&per_page=10", headers=auth["headers"]).get_json()
    assert len(second["items"]) == 10
    assert client.get("/v1/items?per_page=101", headers=auth["headers"]).status_code == 400
    assert client.get("/v1/items?page=x", headers=auth["headers"]).status_code == 400
    assert client.get("/v1/items?sort=name", headers=auth["headers"]).status_code == 400


def test_method_and_not_found_errors_are_json(client):
    method = client.put("/v1/health")
    missing = client.get("/v1/missing")
    assert method.status_code == 405 and method.is_json
    assert missing.status_code == 404 and missing.is_json
