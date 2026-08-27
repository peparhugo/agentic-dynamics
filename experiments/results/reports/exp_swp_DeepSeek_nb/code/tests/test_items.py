def test_create_item(client, auth_headers):
    resp = client.post("/v1/items", json={"name": "Widget", "description": "A widget"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Widget"
    assert data["description"] == "A widget"
    assert data["id"] is not None


def test_get_item(client, auth_headers):
    created = client.post("/v1/items", json={"name": "Widget"}, headers=auth_headers).get_json()
    resp = client.get(f"/v1/items/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Widget"


def test_list_items_empty(client, auth_headers):
    resp = client.get("/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 0


def test_update_item(client, auth_headers):
    created = client.post("/v1/items", json={"name": "Widget"}, headers=auth_headers).get_json()
    resp = client.put(
        f"/v1/items/{created['id']}",
        json={"name": "Updated", "description": "new desc"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Updated"
    assert data["description"] == "new desc"


def test_patch_item(client, auth_headers):
    created = client.post("/v1/items", json={"name": "Widget"}, headers=auth_headers).get_json()
    resp = client.patch(
        f"/v1/items/{created['id']}", json={"name": "Patched"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Patched"


def test_delete_item(client, auth_headers):
    created = client.post("/v1/items", json={"name": "Widget"}, headers=auth_headers).get_json()
    resp = client.delete(f"/v1/items/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200

    gone = client.get(f"/v1/items/{created['id']}", headers=auth_headers)
    assert gone.status_code == 404


def test_get_missing_item(client, auth_headers):
    resp = client.get("/v1/items/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_cannot_access_other_users_item(client, tokens, auth_headers):
    other = client.post(
        "/v1/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "password123"},
    )
    assert other.status_code == 201
    other_login = client.post(
        "/v1/auth/login", json={"username": "bob", "password": "password123"}
    ).get_json()
    other_headers = {"Authorization": f"Bearer {other_login['access_token']}"}

    mine = client.post("/v1/items", json={"name": "secret"}, headers=auth_headers).get_json()

    # Other user should not be able to see, update, or delete my item.
    assert client.get(f"/v1/items/{mine['id']}", headers=other_headers).status_code == 404
    assert client.put(
        f"/v1/items/{mine['id']}", json={"name": "hacked"}, headers=other_headers
    ).status_code == 404
    assert client.delete(f"/v1/items/{mine['id']}", headers=other_headers).status_code == 404


def test_items_require_auth(client):
    assert client.get("/v1/items").status_code == 401
    assert client.post("/v1/items", json={"name": "x"}).status_code == 401


def test_items_reject_invalid_token(client):
    resp = client.get("/v1/items", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


def test_items_reject_missing_header(client):
    assert client.get("/v1/items").status_code == 401


def test_create_item_validation(client, auth_headers):
    assert client.post("/v1/items", json={}, headers=auth_headers).status_code == 422
    assert client.post("/v1/items", json={"name": ""}, headers=auth_headers).status_code == 422
    assert client.post("/v1/items", json={"name": 123}, headers=auth_headers).status_code == 422
