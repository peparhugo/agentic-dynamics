def test_invalid_json_body(client):
    resp = client.post(
        "/v1/auth/register", data="not-json", content_type="application/json"
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_non_object_json_body(client):
    resp = client.post(
        "/v1/auth/register", json=["a", "b"], content_type="application/json"
    )
    assert resp.status_code == 400


def test_refresh_requires_token_field(client):
    resp = client.post("/v1/auth/refresh", json={})
    assert resp.status_code == 400


def test_login_non_string_credentials(client):
    resp = client.post("/v1/auth/login", json={"username": 123, "password": 456})
    assert resp.status_code == 400


def test_register_username_invalid_chars(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "bad name!", "email": "x@example.com", "password": "password123"},
    )
    assert resp.status_code == 400


def test_item_description_wrong_type(client, user_headers):
    resp = client.post(
        "/v1/items", json={"name": "ok", "description": 123}, headers=user_headers
    )
    assert resp.status_code == 400
