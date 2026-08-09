class TestCategoryCreate:
    def test_create_category(self, client, auth_headers):
        resp = client.post(
            "/api/categories",
            json={"name": "Bug", "description": "Bug fixes"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Bug"
        assert data["description"] == "Bug fixes"
        assert "id" in data

    def test_create_category_duplicate(self, client, auth_headers):
        client.post(
            "/api/categories", json={"name": "Dup"}, headers=auth_headers
        )
        resp = client.post(
            "/api/categories", json={"name": "Dup"}, headers=auth_headers
        )
        assert resp.status_code == 409

    def test_create_category_no_name(self, client, auth_headers):
        resp = client.post("/api/categories", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_category_unauthenticated(self, client):
        resp = client.post("/api/categories", json={"name": "Nope"})
        assert resp.status_code == 401


class TestCategoryRead:
    def test_list_categories(self, client, auth_headers):
        client.post(
            "/api/categories", json={"name": "A"}, headers=auth_headers
        )
        client.post(
            "/api/categories", json={"name": "B"}, headers=auth_headers
        )
        resp = client.get("/api/categories", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]["name"] <= data[1]["name"]

    def test_get_category(self, client, auth_headers):
        create = client.post(
            "/api/categories",
            json={"name": "Feature"},
            headers=auth_headers,
        )
        cat = create.get_json()
        resp = client.get(f"/api/categories/{cat['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Feature"

    def test_get_nonexistent_category(self, client, auth_headers):
        resp = client.get("/api/categories/nope", headers=auth_headers)
        assert resp.status_code == 404


class TestCategoryUpdate:
    def test_update_category(self, client, auth_headers):
        create = client.post(
            "/api/categories",
            json={"name": "Old"},
            headers=auth_headers,
        )
        cat = create.get_json()
        resp = client.put(
            f"/api/categories/{cat['id']}",
            json={"name": "New"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "New"

    def test_update_duplicate_name(self, client, auth_headers):
        client.post("/api/categories", json={"name": "First"}, headers=auth_headers)
        create = client.post(
            "/api/categories", json={"name": "Second"}, headers=auth_headers
        )
        cat = create.get_json()
        resp = client.put(
            f"/api/categories/{cat['id']}",
            json={"name": "First"},
            headers=auth_headers,
        )
        assert resp.status_code == 409


class TestCategoryDelete:
    def test_delete_category(self, client, auth_headers):
        create = client.post(
            "/api/categories", json={"name": "Remove"}, headers=auth_headers
        )
        cat = create.get_json()
        resp = client.delete(f"/api/categories/{cat['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Category deleted."

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete("/api/categories/nope", headers=auth_headers)
        assert resp.status_code == 404
