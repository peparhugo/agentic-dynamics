def test_create_item(client, auth_headers):
    resp = client.post("/api/v1/items", json={"name": "My Item", "description": "A thing"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "My Item"
    assert data["owner_id"] == 1


def test_create_item_no_auth(client):
    resp = client.post("/api/v1/items", json={"name": "Item"})
    assert resp.status_code == 401


def test_create_item_no_name(client, auth_headers):
    resp = client.post("/api/v1/items", json={"description": "desc"}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_item_empty_body(client, auth_headers):
    resp = client.post("/api/v1/items", headers=auth_headers, data="not json", content_type="application/json")
    assert resp.status_code == 400


def test_list_items_empty(client, auth_headers):
    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"] == []
    assert data["pagination"]["total"] == 0


def test_list_items(client, auth_headers):
    for i in range(5):
        client.post("/api/v1/items", json={"name": f"Item {i}"}, headers=auth_headers)
    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["pagination"]["total"] == 5


def test_list_items_pagination(client, auth_headers):
    for i in range(10):
        client.post("/api/v1/items", json={"name": f"Item {i}"}, headers=auth_headers)
    resp = client.get("/api/v1/items?page=1&per_page=3", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 3
    assert data["pagination"]["total"] == 10
    assert data["pagination"]["has_next"] is True
    assert data["pagination"]["next_url"] is not None
    assert data["pagination"]["has_prev"] is False


def test_list_items_page_two(client, auth_headers):
    for i in range(10):
        client.post("/api/v1/items", json={"name": f"Item {i}"}, headers=auth_headers)
    resp = client.get("/api/v1/items?page=2&per_page=3", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 3
    assert data["pagination"]["has_prev"] is True
    assert data["pagination"]["prev_url"] is not None


def test_get_item(client, auth_headers):
    resp = client.post("/api/v1/items", json={"name": "Target"}, headers=auth_headers)
    item_id = resp.get_json()["id"]
    resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Target"


def test_get_item_not_found(client, auth_headers):
    resp = client.get("/api/v1/items/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_get_item_wrong_owner(client, auth_headers, db, app):
    from app.models.user import User, Item

    with app.app_context():
        other = User(username="other", email="other@test.com")
        other.set_password("pass")
        db.session.add(other)
        db.session.commit()

        item = Item(name="Others", owner_id=other.id)
        db.session.add(item)
        db.session.commit()

        other_id = other.id
        item_id = item.id

    resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_update_item(client, auth_headers):
    resp = client.post("/api/v1/items", json={"name": "Old"}, headers=auth_headers)
    item_id = resp.get_json()["id"]
    resp = client.put(f"/api/v1/items/{item_id}", json={"name": "New"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "New"


def test_delete_item(client, auth_headers):
    resp = client.post("/api/v1/items", json={"name": "ToDelete"}, headers=auth_headers)
    item_id = resp.get_json()["id"]
    resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Item deleted"

    resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 404
