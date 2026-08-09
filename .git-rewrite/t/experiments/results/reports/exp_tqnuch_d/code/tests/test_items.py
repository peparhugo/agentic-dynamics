import pytest


def _create_item(client, headers, **kwargs):
    defaults = {"name": "Test Item", "description": "A test item", "price": 9.99}
    defaults.update(kwargs)
    return client.post("/api/v1/items", json=defaults, headers=headers)


class TestCreateItem:
    def test_create_item_success(self, client, auth_headers):
        resp = _create_item(client, auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["name"] == "Test Item"
        assert data["price"] == 9.99
        assert "id" in data
        assert "owner_id" in data

    def test_create_item_unauthorized(self, client):
        resp = client.post(
            "/api/v1/items",
            json={"name": "Item", "price": 1.0},
        )
        assert resp.status_code == 401

    def test_create_item_missing_name(self, client, auth_headers):
        resp = client.post("/api/v1/items", json={"price": 1.0}, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_item_negative_price(self, client, auth_headers):
        resp = client.post(
            "/api/v1/items",
            json={"name": "Bad", "price": -5.0},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_item_price_rounding(self, client, auth_headers):
        resp = client.post(
            "/api/v1/items",
            json={"name": "Precise", "price": 9.999},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["price"] == 10.00


class TestGetItem:
    def test_get_item_success(self, client, auth_headers):
        create_resp = _create_item(client, auth_headers)
        item_id = create_resp.get_json()["data"]["id"]

        resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["id"] == item_id

    def test_get_item_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/items/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestListItems:
    def test_list_items_empty(self, client):
        resp = client.get("/api/v1/items")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []
        assert resp.get_json()["pagination"]["total"] == 0

    def test_list_items_with_data(self, client, auth_headers):
        for i in range(5):
            _create_item(client, auth_headers, name=f"Item {i}")

        resp = client.get("/api/v1/items")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 5
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["page"] == 1

    def test_list_items_paginated(self, client, auth_headers):
        for i in range(25):
            _create_item(client, auth_headers, name=f"Item {i}")

        resp = client.get("/api/v1/items?page=1&per_page=10")
        data = resp.get_json()
        assert len(data["data"]) == 10
        assert data["pagination"]["total"] == 25
        assert data["pagination"]["pages"] == 3
        assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False

        resp2 = client.get("/api/v1/items?page=3&per_page=10")
        data2 = resp2.get_json()
        assert len(data2["data"]) == 5
        assert data2["pagination"]["has_next"] is False

    def test_list_items_filter_by_owner(self, client, auth_headers, register_user):
        _create_item(client, auth_headers, name="Mine")
        resp2 = register_user(username="other", email="other@example.com")
        other_headers = {"Authorization": f"Bearer {resp2.get_json()['access_token']}"}
        _create_item(client, other_headers, name="Theirs")

        resp = client.get("/api/v1/items?owner_id=2")
        data = resp.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Theirs"

    def test_list_items_filter_by_name(self, client, auth_headers):
        _create_item(client, auth_headers, name="Alpha")
        _create_item(client, auth_headers, name="Beta")
        _create_item(client, auth_headers, name="Gamma")

        resp = client.get("/api/v1/items?name=alp")
        data = resp.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Alpha"


class TestUpdateItem:
    def test_update_item_success(self, client, auth_headers):
        create_resp = _create_item(client, auth_headers)
        item = create_resp.get_json()["data"]

        resp = client.put(
            f"/api/v1/items/{item['id']}",
            json={"name": "Updated", "price": 19.99},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        updated = resp.get_json()["data"]
        assert updated["name"] == "Updated"
        assert updated["price"] == 19.99

    def test_update_item_not_owner(self, client, auth_headers, register_user):
        create_resp = _create_item(client, auth_headers)
        item_id = create_resp.get_json()["data"]["id"]

        resp2 = register_user(username="other2", email="other2@example.com")
        other_headers = {"Authorization": f"Bearer {resp2.get_json()['access_token']}"}

        resp = client.put(
            f"/api/v1/items/{item_id}",
            json={"name": "Stolen"},
            headers=other_headers,
        )
        assert resp.status_code == 403

    def test_update_item_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/v1/items/99999",
            json={"name": "Ghost"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestDeleteItem:
    def test_delete_item_success(self, client, auth_headers):
        create_resp = _create_item(client, auth_headers)
        item_id = create_resp.get_json()["data"]["id"]

        resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert "deleted" in resp.get_json()["message"]

        get_resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_item_not_owner(self, client, auth_headers, register_user):
        create_resp = _create_item(client, auth_headers)
        item_id = create_resp.get_json()["data"]["id"]

        resp2 = register_user(username="other3", email="other3@example.com")
        other_headers = {"Authorization": f"Bearer {resp2.get_json()['access_token']}"}

        resp = client.delete(f"/api/v1/items/{item_id}", headers=other_headers)
        assert resp.status_code == 403

    def test_delete_item_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/items/99999", headers=auth_headers)
        assert resp.status_code == 404
