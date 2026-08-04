class TestCategoryCreate:
    def test_create_category(self, client, auth_headers):
        resp = client.post("/api/categories", json={
            "name": "Personal",
            "color": "#00FF00",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["category"]["name"] == "Personal"
        assert data["category"]["color"] == "#00FF00"

    def test_create_category_default_color(self, client, auth_headers):
        resp = client.post("/api/categories", json={
            "name": "DefaultColor",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.get_json()["category"]["color"] == "#3B82F6"

    def test_create_duplicate_category(self, client, auth_headers):
        client.post("/api/categories", json={
            "name": "Duplicate",
        }, headers=auth_headers)
        resp = client.post("/api/categories", json={
            "name": "Duplicate",
        }, headers=auth_headers)
        assert resp.status_code == 409

    def test_create_category_no_name(self, client, auth_headers):
        resp = client.post("/api/categories", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_category_unauthorized(self, client):
        resp = client.post("/api/categories", json={"name": "NoAuth"})
        assert resp.status_code == 401


class TestCategoryList:
    def test_list_categories(self, client, auth_headers, category_id):
        resp = client.get("/api/categories", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["categories"]) >= 1

    def test_list_categories_empty(self, client, auth_headers):
        resp = client.get("/api/categories", headers=auth_headers)
        assert resp.status_code == 200


class TestCategoryGet:
    def test_get_category(self, client, auth_headers, category_id):
        resp = client.get(f"/api/categories/{category_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["category"]["id"] == category_id

    def test_get_category_not_found(self, client, auth_headers):
        resp = client.get("/api/categories/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestCategoryUpdate:
    def test_update_category(self, client, auth_headers, category_id):
        resp = client.put(f"/api/categories/{category_id}", json={
            "name": "Updated Category",
            "color": "#000000",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["category"]["name"] == "Updated Category"
        assert data["category"]["color"] == "#000000"

    def test_update_category_name_only(self, client, auth_headers, category_id):
        resp = client.put(f"/api/categories/{category_id}", json={
            "name": "Renamed",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["category"]["name"] == "Renamed"

    def test_update_category_not_found(self, client, auth_headers):
        resp = client.put("/api/categories/99999", json={
            "name": "Nope",
        }, headers=auth_headers)
        assert resp.status_code == 404

    def test_update_category_duplicate_name(self, client, auth_headers, category_id):
        client.post("/api/categories", json={
            "name": "Existing",
        }, headers=auth_headers)
        resp = client.put(f"/api/categories/{category_id}", json={
            "name": "Existing",
        }, headers=auth_headers)
        assert resp.status_code == 409

    def test_update_category_no_fields(self, client, auth_headers, category_id):
        resp = client.put(f"/api/categories/{category_id}", json={}, headers=auth_headers)
        assert resp.status_code == 400


class TestCategoryDelete:
    def test_delete_category(self, client, auth_headers):
        create_resp = client.post("/api/categories", json={
            "name": "ToDelete",
        }, headers=auth_headers)
        cat_id = create_resp.get_json()["category"]["id"]

        resp = client.delete(f"/api/categories/{cat_id}", headers=auth_headers)
        assert resp.status_code == 200

        resp = client.get(f"/api/categories/{cat_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_category_not_found(self, client, auth_headers):
        resp = client.delete("/api/categories/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_category_nulls_task_refs(self, client, auth_headers, category_id):
        client.post("/api/tasks", json={
            "title": "Categorized Task",
            "category_id": category_id,
        }, headers=auth_headers)

        client.delete(f"/api/categories/{category_id}", headers=auth_headers)

        resp = client.get("/api/tasks", headers=auth_headers)
        for item in resp.get_json()["items"]:
            assert item["category_id"] is None
