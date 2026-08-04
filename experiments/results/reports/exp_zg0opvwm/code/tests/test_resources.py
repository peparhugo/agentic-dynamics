def test_list_items_empty(client, auth_headers):
    resp = client.get("/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 0


def test_create_item(client, auth_headers):
    resp = client.post(
        "/v1/items",
        json={"name": "Test Item", "description": "A test item"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Test Item"
    assert data["description"] == "A test item"
    assert data["owner_id"] is not None
    assert "id" in data


def test_create_item_no_auth(client):
    resp = client.post("/v1/items", json={"name": "Test"})
    assert resp.status_code == 401


def test_create_item_invalid(client, auth_headers):
    resp = client.post("/v1/items", json={"name": ""}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_item_missing_name(client, auth_headers):
    resp = client.post("/v1/items", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_get_item(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Get Test", "description": "For getting"},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    resp = client.get(f"/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Get Test"


def test_get_item_not_found(client, auth_headers):
    resp = client.get("/v1/items/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_get_item_no_auth(client):
    resp = client.get("/v1/items/1")
    assert resp.status_code == 401


def test_update_item(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Old Name", "description": "Old Desc"},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    resp = client.put(
        f"/v1/items/{item_id}",
        json={"name": "New Name", "description": "New Desc"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "New Name"
    assert data["description"] == "New Desc"


def test_update_item_not_found(client, auth_headers):
    resp = client.put(
        "/v1/items/99999",
        json={"name": "Nope"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_item_not_owner(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Owner Item"},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    client.post(
        "/v1/auth/register",
        json={"username": "otheruser", "email": "other@example.com", "password": "secure123"},
    )
    login_resp = client.post(
        "/v1/auth/login",
        json={"username": "otheruser", "password": "secure123"},
    )
    other_headers = {
        "Authorization": f"Bearer {login_resp.get_json()['access_token']}"
    }

    resp = client.put(
        f"/v1/items/{item_id}",
        json={"name": "Stolen"},
        headers=other_headers,
    )
    assert resp.status_code == 403


def test_delete_item(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Delete Me"},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    resp = client.delete(f"/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200

    get_resp = client.get(f"/v1/items/{item_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_item_not_found(client, auth_headers):
    resp = client.delete("/v1/items/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_item_not_owner(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Owner Delete"},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    client.post(
        "/v1/auth/register",
        json={"username": "otherdel", "email": "otherdel@example.com", "password": "secure123"},
    )
    login_resp = client.post(
        "/v1/auth/login",
        json={"username": "otherdel", "password": "secure123"},
    )
    other_headers = {
        "Authorization": f"Bearer {login_resp.get_json()['access_token']}"
    }

    resp = client.delete(f"/v1/items/{item_id}", headers=other_headers)
    assert resp.status_code == 403
