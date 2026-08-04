"""Tests for category endpoints."""

import json

from ..models import db, Category


def _register_and_get_token(client, username="catuser", email="cat@example.com"):
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": username,
            "email": email,
            "password": "password",
        }),
        content_type="application/json",
    )
    return resp.get_json()["access_token"]


class TestListCategories:
    def test_list_empty(self, client):
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["categories"] == []
        assert data["total"] == 0

    def test_list_with_data(self, client, db):
        db.session.add_all([
            Category(name="Bug"),
            Category(name="Feature"),
            Category(name="Documentation"),
        ])
        db.session.commit()

        resp = client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 3
        assert len(data["categories"]) == 3

    def test_list_pagination(self, client, db):
        for i in range(25):
            db.session.add(Category(name=f"Category {i}"))
        db.session.commit()

        resp = client.get("/api/categories?per_page=10&page=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["categories"]) == 10
        assert data["pages"] == 3
        assert data["total"] == 25

        resp = client.get("/api/categories?per_page=10&page=2")
        assert resp.status_code == 200
        assert len(resp.get_json()["categories"]) == 10

        resp = client.get("/api/categories?per_page=10&page=3")
        assert resp.status_code == 200
        assert len(resp.get_json()["categories"]) == 5


class TestGetCategory:
    def test_get_existing(self, client, db):
        cat = Category(name="Bug")
        db.session.add(cat)
        db.session.commit()

        resp = client.get(f"/api/categories/{cat.id}")
        assert resp.status_code == 200
        assert resp.get_json()["category"]["name"] == "Bug"

    def test_get_nonexistent(self, client):
        resp = client.get("/api/categories/999")
        assert resp.status_code == 404


class TestCreateCategory:
    def test_create_success(self, client):
        token = _register_and_get_token(client)

        resp = client.post(
            "/api/categories",
            data=json.dumps({"name": "Bug", "description": "Bug reports"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["category"]["name"] == "Bug"
        assert data["category"]["description"] == "Bug reports"

    def test_create_unauthenticated(self, client):
        resp = client.post(
            "/api/categories",
            data=json.dumps({"name": "Bug"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_create_duplicate_name(self, client):
        token = _register_and_get_token(client)
        client.post(
            "/api/categories",
            data=json.dumps({"name": "Bug"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.post(
            "/api/categories",
            data=json.dumps({"name": "Bug"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_create_missing_name(self, client):
        token = _register_and_get_token(client)
        resp = client.post(
            "/api/categories",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


class TestUpdateCategory:
    def test_update_success(self, client, db):
        token = _register_and_get_token(client)
        cat = Category(name="Bug")
        db.session.add(cat)
        db.session.commit()

        resp = client.put(
            f"/api/categories/{cat.id}",
            data=json.dumps({"name": "BugFix", "description": "Updated desc"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["category"]["name"] == "BugFix"

    def test_update_nonexistent(self, client):
        token = _register_and_get_token(client)
        resp = client.put(
            "/api/categories/999",
            data=json.dumps({"name": "Bug"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestDeleteCategory:
    def test_delete_success(self, client, db):
        token = _register_and_get_token(client)
        cat = Category(name="Bug")
        db.session.add(cat)
        db.session.commit()

        resp = client.delete(
            f"/api/categories/{cat.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert db.session.get(Category, cat.id) is None

    def test_delete_nonexistent(self, client):
        token = _register_and_get_token(client)
        resp = client.delete(
            "/api/categories/999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
