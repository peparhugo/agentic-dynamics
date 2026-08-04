import json


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestItemsCRUD:
    def test_create_item(self, client, registered_user):
        token = registered_user["access_token"]
        resp = client.post("/api/v1/items", json={
            "name": "Test Item",
            "description": "A test item",
        }, headers=_auth_header(token))
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["data"]["name"] == "Test Item"
        assert data["data"]["id"] is not None

    def test_create_item_no_auth(self, client):
        resp = client.post("/api/v1/items", json={"name": "Test"})
        assert resp.status_code == 401

    def test_create_item_validation(self, client, registered_user):
        token = registered_user["access_token"]
        resp = client.post("/api/v1/items", json={}, headers=_auth_header(token))
        assert resp.status_code == 400

    def test_get_item(self, client, registered_user):
        token = registered_user["access_token"]
        create_resp = client.post("/api/v1/items", json={"name": "Get Me"}, headers=_auth_header(token))
        item_id = create_resp.get_json()["data"]["id"]

        resp = client.get(f"/api/v1/items/{item_id}", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Get Me"

    def test_get_item_not_found(self, client, registered_user):
        token = registered_user["access_token"]
        resp = client.get("/api/v1/items/99999", headers=_auth_header(token))
        assert resp.status_code == 404

    def test_update_item(self, client, registered_user):
        token = registered_user["access_token"]
        create_resp = client.post("/api/v1/items", json={"name": "Original"}, headers=_auth_header(token))
        item_id = create_resp.get_json()["data"]["id"]

        resp = client.put(f"/api/v1/items/{item_id}", json={"name": "Updated"}, headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Updated"

    def test_update_item_validation(self, client, registered_user):
        token = registered_user["access_token"]
        create_resp = client.post("/api/v1/items", json={"name": "Original"}, headers=_auth_header(token))
        item_id = create_resp.get_json()["data"]["id"]

        resp = client.put(f"/api/v1/items/{item_id}", json={"name": ""}, headers=_auth_header(token))
        assert resp.status_code == 400

    def test_delete_item(self, client, registered_user):
        token = registered_user["access_token"]
        create_resp = client.post("/api/v1/items", json={"name": "Delete Me"}, headers=_auth_header(token))
        item_id = create_resp.get_json()["data"]["id"]

        resp = client.delete(f"/api/v1/items/{item_id}", headers=_auth_header(token))
        assert resp.status_code == 200

        resp = client.get(f"/api/v1/items/{item_id}", headers=_auth_header(token))
        assert resp.status_code == 404

    def test_delete_item_not_found(self, client, registered_user):
        token = registered_user["access_token"]
        resp = client.delete("/api/v1/items/99999", headers=_auth_header(token))
        assert resp.status_code == 404


class TestItemsIsolation:
    def test_user_cannot_access_other_users_items(self, client, app):
        with app.app_context():
            r1 = client.post("/api/v1/auth/register", json={
                "username": "user1",
                "email": "user1@example.com",
                "password": "password123",
            }).get_json()
            r2 = client.post("/api/v1/auth/register", json={
                "username": "user2",
                "email": "user2@example.com",
                "password": "password123",
            }).get_json()

        token1 = r1["access_token"]
        token2 = r2["access_token"]

        item_resp = client.post("/api/v1/items", json={"name": "User1 Item"}, headers=_auth_header(token1))
        item_id = item_resp.get_json()["data"]["id"]

        resp = client.get(f"/api/v1/items/{item_id}", headers=_auth_header(token2))
        assert resp.status_code == 403

        resp = client.put(f"/api/v1/items/{item_id}", json={"name": "Hacked"}, headers=_auth_header(token2))
        assert resp.status_code == 403

        resp = client.delete(f"/api/v1/items/{item_id}", headers=_auth_header(token2))
        assert resp.status_code == 403


class TestItemsPagination:
    def test_pagination_defaults(self, client, registered_user):
        token = registered_user["access_token"]
        resp = client.get("/api/v1/items", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert "pagination" in data
        assert "data" in data
        assert data["pagination"]["page"] == 1

    def test_pagination_custom_per_page(self, client, registered_user):
        token = registered_user["access_token"]
        resp = client.get("/api/v1/items?per_page=5&page=1", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["per_page"] == 5

    def test_pagination_over_max_per_page(self, client, app):
        token = app.test_client().post("/api/v1/auth/register", json={
            "username": "paguser",
            "email": "pag@example.com",
            "password": "password123",
        }).get_json()["access_token"]

        resp = client.get("/api/v1/items?per_page=500", headers=_auth_header(token))
        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["per_page"] <= 100

    def test_pagination_invalid_page(self, client, registered_user):
        token = registered_user["access_token"]
        resp = client.get("/api/v1/items?page=-1", headers=_auth_header(token))
        assert resp.status_code in (200, 400)

    def test_pagination_with_many_items(self, client, registered_user):
        token = registered_user["access_token"]
        for i in range(25):
            client.post("/api/v1/items", json={"name": f"Item {i}"}, headers=_auth_header(token))

        page1 = client.get("/api/v1/items?per_page=10&page=1", headers=_auth_header(token))
        page2 = client.get("/api/v1/items?per_page=10&page=2", headers=_auth_header(token))
        page3 = client.get("/api/v1/items?per_page=10&page=3", headers=_auth_header(token))

        p1 = page1.get_json()
        p2 = page2.get_json()
        p3 = page3.get_json()

        assert len(p1["data"]) == 10
        assert len(p2["data"]) == 10
        assert len(p3["data"]) == 5
        assert p1["pagination"]["total"] == 25
        assert p1["pagination"]["pages"] == 3

    def test_pagination_sorting(self, client, registered_user):
        token = registered_user["access_token"]
        client.post("/api/v1/items", json={"name": "B Item"}, headers=_auth_header(token))
        client.post("/api/v1/items", json={"name": "A Item"}, headers=_auth_header(token))

        resp_asc = client.get("/api/v1/items?sort_by=name&order=asc", headers=_auth_header(token))
        items = resp_asc.get_json()["data"]
        assert items[0]["name"] == "A Item"
        assert items[1]["name"] == "B Item"

    def test_pagination_name_filter(self, client, registered_user):
        token = registered_user["access_token"]
        client.post("/api/v1/items", json={"name": "Alpha"}, headers=_auth_header(token))
        client.post("/api/v1/items", json={"name": "Beta"}, headers=_auth_header(token))
        client.post("/api/v1/items", json={"name": "Gamma"}, headers=_auth_header(token))

        resp = client.get("/api/v1/items?name=bet", headers=_auth_header(token))
        data = resp.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Beta"


class TestErrorHandling:
    def test_404_on_nonexistent_route(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_405_method_not_allowed(self, client):
        resp = client.patch("/api/v1/auth/login")
        assert resp.status_code == 405

    def test_400_on_invalid_json(self, client):
        resp = client.post("/api/v1/auth/login", data="not json", content_type="application/json")
        assert resp.status_code == 400
