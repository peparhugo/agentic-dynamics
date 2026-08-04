def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.get_json()["version"] == "1.0"


def test_create_item(client, auth_headers):
    resp = client.post("/api/v1/items", headers=auth_headers, json={
        "name": "Test Item", "description": "A test item"
    })
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["name"] == "Test Item"
    assert data["description"] == "A test item"
    assert "id" in data


def test_get_item(client, auth_headers):
    create_resp = client.post("/api/v1/items", headers=auth_headers, json={
        "name": "To Get", "description": "Get me"
    })
    item_id = create_resp.get_json()["data"]["id"]
    resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "To Get"


def test_get_nonexistent_item(client, auth_headers):
    resp = client.get("/api/v1/items/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_item(client, auth_headers):
    create_resp = client.post("/api/v1/items", headers=auth_headers, json={
        "name": "Old Name", "description": "Old desc"
    })
    item_id = create_resp.get_json()["data"]["id"]
    resp = client.put(f"/api/v1/items/{item_id}", headers=auth_headers, json={
        "name": "New Name", "description": "New desc"
    })
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["name"] == "New Name"
    assert data["description"] == "New desc"


def test_delete_item(client, auth_headers):
    create_resp = client.post("/api/v1/items", headers=auth_headers, json={
        "name": "To Delete", "description": "Delete me"
    })
    item_id = create_resp.get_json()["data"]["id"]
    resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    resp2 = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp2.status_code == 404


def test_list_items_unauthenticated(client):
    resp = client.get("/api/v1/items")
    assert resp.status_code == 401
