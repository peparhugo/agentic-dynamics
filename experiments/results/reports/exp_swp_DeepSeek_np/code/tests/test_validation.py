from tests.conftest import auth_headers


def test_register_invalid_email(client):
    resp = client.post("/v1/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert resp.status_code == 422
    data = resp.get_json()
    assert "email" in data["fields"]


def test_register_short_password(client):
    resp = client.post("/v1/auth/register", json={"email": "a@b.com", "password": "short"})
    assert resp.status_code == 422
    assert "password" in resp.get_json()["fields"]


def test_register_missing_fields(client):
    resp = client.post("/v1/auth/register", json={})
    assert resp.status_code == 422
    fields = resp.get_json()["fields"]
    assert "email" in fields
    assert "password" in fields


def test_register_missing_password_field(client):
    resp = client.post("/v1/auth/register", json={"email": "a@b.com"})
    assert resp.status_code == 422


def test_login_missing_fields(client):
    resp = client.post("/v1/auth/login", json={"email": "a@b.com"})
    assert resp.status_code == 422
    assert "password" in resp.get_json()["fields"]


def test_register_non_object_body(client):
    resp = client.post("/v1/auth/register", json=["not", "an", "object"])
    assert resp.status_code == 422


def test_create_item_validation(client):
    headers = auth_headers(client)
    resp = client.post("/v1/items", json={}, headers=headers)
    assert resp.status_code == 422
    assert "name" in resp.get_json()["fields"]


def test_create_item_blank_name(client):
    headers = auth_headers(client)
    resp = client.post("/v1/items", json={"name": "   "}, headers=headers)
    assert resp.status_code == 422


def test_update_item_invalid(client):
    headers = auth_headers(client)
    created = client.post("/v1/items", json={"name": "Thing"}, headers=headers)
    item_id = created.get_json()["item"]["id"]

    resp = client.patch(f"/v1/items/{item_id}", json={"name": 123}, headers=headers)
    assert resp.status_code == 422

    resp = client.patch(f"/v1/items/{item_id}", json={}, headers=headers)
    assert resp.status_code == 422


def test_pagination_invalid_params(client):
    headers = auth_headers(client)
    resp = client.get("/v1/items?page=abc", headers=headers)
    assert resp.status_code == 422

    resp = client.get("/v1/items?per_page=xyz", headers=headers)
    assert resp.status_code == 422
