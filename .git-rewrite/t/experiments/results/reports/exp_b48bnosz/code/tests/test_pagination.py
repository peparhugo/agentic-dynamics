from app.extensions import db
from app.models import Item


def seed_items(user, n):
    for i in range(n):
        db.session.add(Item(name=f"item-{i:03d}", price=i, owner_id=user.id))
    db.session.commit()


class TestPagination:
    def test_default_page(self, client, auth, user):
        seed_items(user, 25)
        resp = client.get("/api/v1/items", headers=auth)
        body = resp.get_json()
        assert resp.status_code == 200
        assert len(body["data"]) == 20  # DEFAULT_PAGE_SIZE
        assert body["meta"] == {
            "page": 1,
            "per_page": 20,
            "total_items": 25,
            "total_pages": 2,
        }
        assert body["links"]["next"] is not None
        assert body["links"]["prev"] is None

    def test_second_page(self, client, auth, user):
        seed_items(user, 25)
        resp = client.get("/api/v1/items?page=2&per_page=20", headers=auth)
        body = resp.get_json()
        assert len(body["data"]) == 5
        assert body["links"]["next"] is None
        assert "page=1" in body["links"]["prev"]

    def test_per_page_cap(self, client, auth, user):
        resp = client.get("/api/v1/items?per_page=101", headers=auth)
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_pagination"

    def test_invalid_page_rejected(self, client, auth, user):
        resp = client.get("/api/v1/items?page=0", headers=auth)
        assert resp.status_code == 422

    def test_filter_by_owner(self, client, auth, user, admin):
        seed_items(user, 3)
        seed_items(admin, 2)
        resp = client.get(f"/api/v1/items?owner_id={admin.id}", headers=auth)
        assert resp.get_json()["meta"]["total_items"] == 2
