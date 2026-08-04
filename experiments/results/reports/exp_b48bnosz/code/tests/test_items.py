from app.extensions import db
from app.models import Item


def create_item(client, auth, **overrides):
    payload = {"name": "Widget", "description": "A widget", "price": 9.99}
    payload.update(overrides)
    return client.post("/api/v1/items", json=payload, headers=auth)


class TestCreate:
    def test_create(self, client, auth):
        resp = create_item(client, auth)
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["name"] == "Widget"
        assert data["price"] == 9.99

    def test_requires_auth(self, client):
        resp = client.post("/api/v1/items", json={"name": "x", "price": 1})
        assert resp.status_code == 401

    def test_missing_name_rejected(self, client, auth):
        resp = client.post("/api/v1/items", json={"price": 1}, headers=auth)
        assert resp.status_code == 422
        assert "name" in resp.get_json()["error"]["details"]

    def test_negative_price_rejected(self, client, auth):
        resp = create_item(client, auth, price=-5)
        assert resp.status_code == 422

    def test_unknown_fields_ignored(self, client, auth):
        resp = create_item(client, auth, owner_id=999, evil="x")
        assert resp.status_code == 201
        assert resp.get_json()["data"]["owner_id"] != 999


class TestReadUpdateDelete:
    def test_get(self, client, auth):
        item_id = create_item(client, auth).get_json()["data"]["id"]
        resp = client.get(f"/api/v1/items/{item_id}", headers=auth)
        assert resp.status_code == 200

    def test_get_missing_404(self, client, auth):
        resp = client.get("/api/v1/items/9999", headers=auth)
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "not_found"

    def test_update(self, client, auth):
        item_id = create_item(client, auth).get_json()["data"]["id"]
        resp = client.patch(f"/api/v1/items/{item_id}", json={"name": "Gadget"}, headers=auth)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Gadget"

    def test_empty_update_rejected(self, client, auth):
        item_id = create_item(client, auth).get_json()["data"]["id"]
        resp = client.patch(f"/api/v1/items/{item_id}", json={}, headers=auth)
        assert resp.status_code == 400

    def test_delete(self, client, auth, app):
        item_id = create_item(client, auth).get_json()["data"]["id"]
        resp = client.delete(f"/api/v1/items/{item_id}", headers=auth)
        assert resp.status_code == 204
        assert db.session.get(Item, item_id) is None


class TestOwnership:
    def test_other_user_cannot_update(self, client, auth):
        item_id = create_item(client, auth).get_json()["data"]["id"]
        client.post(
            "/api/v1/auth/register",
            json={"email": "other@example.com", "password": "password123"},
        )
        other = client.post(
            "/api/v1/auth/login",
            json={"email": "other@example.com", "password": "password123"},
        ).get_json()
        resp = client.patch(
            f"/api/v1/items/{item_id}",
            json={"name": "Stolen"},
            headers={"Authorization": f"Bearer {other['access_token']}"},
        )
        assert resp.status_code == 403

    def test_admin_can_update_any(self, client, auth, admin_auth):
        item_id = create_item(client, auth).get_json()["data"]["id"]
        resp = client.patch(
            f"/api/v1/items/{item_id}", json={"name": "Moderated"}, headers=admin_auth
        )
        assert resp.status_code == 200
