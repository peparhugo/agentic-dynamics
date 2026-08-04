def test_create_item(client, auth_headers):
    resp = client.post("/api/v1/items", json={
        "name": "Widget",
        "description": "A useful widget",
        "price": 19.99,
        "category": "Tools",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["name"] == "Widget"
    assert data["price"] == 19.99
    assert data["category"] == "Tools"
    assert "id" in data
    assert "created_at" in data


def test_create_item_validation(client, auth_headers):
    resp = client.post("/api/v1/items", json={
        "name": "",
        "price": "not-a-number",
    }, headers=auth_headers)
    assert resp.status_code == 422


def test_list_items(client, auth_headers):
    for i in range(5):
        client.post("/api/v1/items", json={
            "name": f"Item {i}",
            "price": float(i * 10),
            "category": "Test",
        }, headers=auth_headers)

    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["meta"]["total"] == 5
    assert data["meta"]["page"] == 1


def test_list_items_pagination(client, auth_headers):
    for i in range(15):
        client.post("/api/v1/items", json={
            "name": f"Item {i}",
            "price": float(i),
            "category": "Test",
        }, headers=auth_headers)

    resp = client.get("/api/v1/items?per_page=5&page=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["meta"]["page"] == 2
    assert data["meta"]["pages"] == 3


def test_get_item(client, auth_headers, sample_item):
    resp = client.get(f"/api/v1/items/{sample_item['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "Test Item"


def test_get_item_not_found(client, auth_headers):
    resp = client.get("/api/v1/items/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_get_item_not_owned(client, auth_headers):
    client.post("/api/register", json={
        "username": "other",
        "email": "other@example.com",
        "password": "password123",
    })
    resp2 = client.post("/api/login", json={
        "email": "other@example.com",
        "password": "password123",
    })
    other_token = resp2.get_json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    create_resp = client.post("/api/v1/items", json={
        "name": "Private",
        "price": 5.0,
        "category": "Test",
    }, headers=auth_headers)
    item_id = create_resp.get_json()["data"]["id"]

    resp = client.get(f"/api/v1/items/{item_id}", headers=other_headers)
    assert resp.status_code == 404


def test_update_item(client, auth_headers, sample_item):
    resp = client.put(f"/api/v1/items/{sample_item['id']}", json={
        "name": "Updated Name",
        "price": 29.99,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["name"] == "Updated Name"
    assert data["price"] == 29.99
    assert data["description"] == "A sample item"


def test_delete_item(client, auth_headers, sample_item):
    resp = client.delete(f"/api/v1/items/{sample_item['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Item deleted"

    resp = client.get(f"/api/v1/items/{sample_item['id']}", headers=auth_headers)
    assert resp.status_code == 404


def test_unauthenticated_access(client):
    resp = client.get("/api/v1/items")
    assert resp.status_code == 401
