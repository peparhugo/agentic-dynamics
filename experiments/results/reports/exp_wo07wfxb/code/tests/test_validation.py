def test_register_empty_payload(client):
    resp = client.post("/api/v1/auth/register", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_register_invalid_username_type(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": 12345, "password": "password123"},
    )
    assert resp.status_code == 400


def test_create_item_empty_name(auth_headers, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "", "description": "desc"},
    )
    assert resp.status_code == 400


def test_create_item_name_too_long(auth_headers, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "x" * 201, "description": "desc"},
    )
    assert resp.status_code == 400


def test_update_item_empty_name(auth_headers, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "Test", "description": "desc"},
    )
    item_id = resp.get_json()["item"]["id"]
    resp = client.put(
        f"/api/v1/items/{item_id}",
        headers=auth_headers,
        json={"name": ""},
    )
    assert resp.status_code == 400


def test_login_missing_password(client):
    resp = client.post("/api/v1/auth/login", json={"username": "test"})
    assert resp.status_code == 400


def test_invalid_json(client):
    resp = client.post(
        "/api/v1/auth/register",
        data="not json",
        content_type="application/json",
    )
    assert resp.status_code == 400
