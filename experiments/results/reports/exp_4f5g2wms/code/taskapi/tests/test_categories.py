class TestCreateCategory:
    def test_create_category(self, client, auth_header):
        resp = client.post(
            "/categories",
            json={"name": "Project Alpha", "description": "Alpha project tasks"},
            headers=auth_header,
        )
        assert resp.status_code == 201
        cat = resp.get_json()["category"]
        assert cat["name"] == "Project Alpha"
        assert cat["description"] == "Alpha project tasks"

    def test_create_category_name_only(self, client, auth_header):
        resp = client.post(
            "/categories", json={"name": "Minimal"}, headers=auth_header
        )
        assert resp.status_code == 201
        assert resp.get_json()["category"]["description"] == ""

    def test_create_category_missing_name(self, client, auth_header):
        resp = client.post("/categories", json={}, headers=auth_header)
        assert resp.status_code == 400

    def test_create_category_empty_name(self, client, auth_header):
        resp = client.post(
            "/categories", json={"name": "   "}, headers=auth_header
        )
        assert resp.status_code == 400

    def test_create_category_duplicate_name(self, client, auth_header, sample_category):
        resp = client.post(
            "/categories",
            json={"name": sample_category["name"]},
            headers=auth_header,
        )
        assert resp.status_code == 409

    def test_create_category_unauthorized(self, client):
        resp = client.post("/categories", json={"name": "Test"})
        assert resp.status_code == 401


class TestListCategories:
    def test_list_categories(self, client, auth_header, sample_category, sample_category2):
        resp = client.get("/categories", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["categories"]) >= 2
        assert "pagination" in data

    def test_list_categories_empty(self, client, auth_header):
        resp = client.get("/categories", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["total"] == 0

    def test_list_categories_pagination(self, client, auth_header, sample_category):
        resp = client.get("/categories?page=1&per_page=1", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["per_page"] == 1
        assert len(data["categories"]) <= 1

    def test_list_categories_search(self, client, auth_header, sample_category, sample_category2):
        resp = client.get("/categories?q=Work", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert all("work" in c["name"].lower() for c in data["categories"])


class TestGetCategory:
    def test_get_category(self, client, auth_header, sample_category):
        resp = client.get(
            f"/categories/{sample_category['id']}", headers=auth_header
        )
        assert resp.status_code == 200
        assert resp.get_json()["category"]["id"] == sample_category["id"]

    def test_get_category_not_found(self, client, auth_header):
        resp = client.get("/categories/9999", headers=auth_header)
        assert resp.status_code == 404

    def test_get_category_wrong_user(self, client, bob_header, sample_category):
        resp = client.get(
            f"/categories/{sample_category['id']}", headers=bob_header
        )
        assert resp.status_code == 404


class TestUpdateCategory:
    def test_update_category_name(self, client, auth_header, sample_category):
        resp = client.put(
            f"/categories/{sample_category['id']}",
            json={"name": "Updated Work"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.get_json()["category"]["name"] == "Updated Work"

    def test_update_category_duplicate_name(self, client, auth_header, sample_category, sample_category2):
        resp = client.put(
            f"/categories/{sample_category['id']}",
            json={"name": sample_category2["name"]},
            headers=auth_header,
        )
        assert resp.status_code == 409

    def test_update_category_not_found(self, client, auth_header):
        resp = client.put(
            "/categories/9999", json={"name": "Nope"}, headers=auth_header
        )
        assert resp.status_code == 404

    def test_update_category_no_fields(self, client, auth_header, sample_category):
        resp = client.put(
            f"/categories/{sample_category['id']}", json={}, headers=auth_header
        )
        assert resp.status_code == 400


class TestDeleteCategory:
    def test_delete_category(self, client, auth_header, sample_category):
        resp = client.delete(
            f"/categories/{sample_category['id']}", headers=auth_header
        )
        assert resp.status_code == 200

        resp = client.get(f"/categories/{sample_category['id']}", headers=auth_header)
        assert resp.status_code == 404

    def test_delete_category_not_found(self, client, auth_header):
        resp = client.delete("/categories/9999", headers=auth_header)
        assert resp.status_code == 404

    def test_delete_category_sets_task_category_null(
        self, client, auth_header, sample_category, sample_task
    ):
        resp = client.delete(
            f"/categories/{sample_category['id']}", headers=auth_header
        )
        assert resp.status_code == 200

        resp = client.get(f"/tasks/{sample_task['id']}", headers=auth_header)
        assert resp.get_json()["task"]["category_id"] is None
