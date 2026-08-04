def test_register_missing_fields(client):
    resp = client.post("/api/v1/register", json={"email": "x@x.com"})
    assert resp.status_code == 422
    assert "Validation failed" in resp.get_json()["error"]


def test_register_short_password(client):
    resp = client.post("/api/v1/register", json={
        "username": "user1", "email": "x@x.com", "password": "ab"
    })
    assert resp.status_code == 422


def test_register_invalid_email(client):
    resp = client.post("/api/v1/register", json={
        "username": "user1", "email": "not-an-email", "password": "password123"
    })
    assert resp.status_code == 422


def test_register_short_username(client):
    resp = client.post("/api/v1/register", json={
        "username": "ab", "email": "x@x.com", "password": "password123"
    })
    assert resp.status_code == 422


def test_login_missing_fields(client):
    resp = client.post("/api/v1/login", json={"email": "x@x.com"})
    assert resp.status_code == 422


def test_create_item_missing_name(client, auth_headers):
    resp = client.post("/api/v1/items", headers=auth_headers, json={
        "description": "No name"
    })
    assert resp.status_code == 422


def test_create_item_empty_name(client, auth_headers):
    resp = client.post("/api/v1/items", headers=auth_headers, json={
        "name": "", "description": "Empty name"
    })
    assert resp.status_code == 422


def test_create_item_long_name(client, auth_headers):
    resp = client.post("/api/v1/items", headers=auth_headers, json={
        "name": "x" * 300, "description": "Too long name"
    })
    assert resp.status_code == 422


def test_invalid_json_body(client):
    resp = client.post("/api/v1/register", data="not json", content_type="application/json")
    assert resp.status_code == 400
