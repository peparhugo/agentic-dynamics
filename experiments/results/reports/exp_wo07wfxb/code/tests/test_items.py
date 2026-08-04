def test_create_item(auth_headers, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "Widget", "description": "A shiny widget"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["item"]["name"] == "Widget"
    assert data["item"]["description"] == "A shiny widget"
    assert "id" in data["item"]


def test_create_item_no_auth(client):
    resp = client.post(
        "/api/v1/items", json={"name": "Widget"}
    )
    assert resp.status_code == 401


def test_create_item_missing_name(auth_headers, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"description": "No name"},
    )
    assert resp.status_code == 400


def test_list_items(auth_headers, client):
    for i in range(5):
        client.post(
            "/api/v1/items",
            headers=auth_headers,
            json={"name": f"Item {i}", "description": f"Desc {i}"},
        )
    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["pagination"]["total"] == 5
    assert data["pagination"]["page"] == 1


def test_list_items_pagination(auth_headers, client):
    for i in range(25):
        client.post(
            "/api/v1/items",
            headers=auth_headers,
            json={"name": f"Item {i}", "description": f"Desc {i}"},
        )
    resp = client.get("/api/v1/items?page=3&per_page=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["pagination"]["page"] == 3
    assert data["pagination"]["pages"] == 5
    assert data["pagination"]["total"] == 25


def test_list_items_default_pagination(auth_headers, client):
    for i in range(30):
        client.post(
            "/api/v1/items",
            headers=auth_headers,
            json={"name": f"Item {i}", "description": f"Desc {i}"},
        )
    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 20


def test_list_items_invalid_page(auth_headers, client):
    resp = client.get("/api/v1/items?page=abc&per_page=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["pagination"]["page"] == 1


def test_get_item(auth_headers, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "Target", "description": "The one"},
    )
    item_id = resp.get_json()["item"]["id"]
    resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["item"]["name"] == "Target"


def test_get_item_not_found(auth_headers, client):
    resp = client.get("/api/v1/items/999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_item(auth_headers, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "Old", "description": "Old desc"},
    )
    item_id = resp.get_json()["item"]["id"]
    resp = client.put(
        f"/api/v1/items/{item_id}",
        headers=auth_headers,
        json={"name": "New", "description": "New desc"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["item"]["name"] == "New"
    assert resp.get_json()["item"]["description"] == "New desc"


def test_update_item_forbidden(auth_headers, auth_headers_2, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "Mine"},
    )
    item_id = resp.get_json()["item"]["id"]
    resp = client.put(
        f"/api/v1/items/{item_id}",
        headers=auth_headers_2,
        json={"name": "Stolen"},
    )
    assert resp.status_code == 403


def test_delete_item(auth_headers, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "Delete me"},
    )
    item_id = resp.get_json()["item"]["id"]
    resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["item"]["name"] == "Delete me"

    resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_item_forbidden(auth_headers, auth_headers_2, client):
    resp = client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"name": "Mine to delete"},
    )
    item_id = resp.get_json()["item"]["id"]
    resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers_2)
    assert resp.status_code == 403
