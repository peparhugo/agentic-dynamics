"""Tests for category CRUD and user scoping."""


def create_category(client, headers, name="Work", description="Job stuff"):
    return client.post("/api/categories", headers=headers,
                       json={"name": name, "description": description})


class TestCategoryCRUD:
    def test_create_category(self, client, auth):
        res = create_category(client, auth)
        assert res.status_code == 201
        cat = res.get_json()["category"]
        assert cat["name"] == "Work"
        assert cat["description"] == "Job stuff"

    def test_create_requires_name(self, client, auth):
        res = client.post("/api/categories", headers=auth, json={})
        assert res.status_code == 400

    def test_create_duplicate_name_same_user(self, client, auth):
        create_category(client, auth)
        res = create_category(client, auth)
        assert res.status_code == 409

    def test_same_name_allowed_for_different_users(self, client, auth, auth2):
        assert create_category(client, auth).status_code == 201
        assert create_category(client, auth2).status_code == 201

    def test_list_categories_sorted(self, client, auth):
        create_category(client, auth, name="Zeta")
        create_category(client, auth, name="Alpha")
        res = client.get("/api/categories", headers=auth)
        assert res.status_code == 200
        names = [c["name"] for c in res.get_json()["categories"]]
        assert names == ["Alpha", "Zeta"]

    def test_get_category(self, client, auth):
        cat_id = create_category(client, auth).get_json()["category"]["id"]
        res = client.get(f"/api/categories/{cat_id}", headers=auth)
        assert res.status_code == 200
        assert res.get_json()["category"]["id"] == cat_id

    def test_get_missing_category(self, client, auth):
        res = client.get("/api/categories/999", headers=auth)
        assert res.status_code == 404

    def test_update_category(self, client, auth):
        cat_id = create_category(client, auth).get_json()["category"]["id"]
        res = client.put(f"/api/categories/{cat_id}", headers=auth,
                         json={"name": "Personal", "description": "Home"})
        assert res.status_code == 200
        cat = res.get_json()["category"]
        assert cat["name"] == "Personal"
        assert cat["description"] == "Home"

    def test_update_to_duplicate_name(self, client, auth):
        create_category(client, auth, name="Work")
        cat_id = create_category(client, auth,
                                 name="Play").get_json()["category"]["id"]
        res = client.put(f"/api/categories/{cat_id}", headers=auth,
                         json={"name": "Work"})
        assert res.status_code == 409

    def test_delete_category(self, client, auth):
        cat_id = create_category(client, auth).get_json()["category"]["id"]
        res = client.delete(f"/api/categories/{cat_id}", headers=auth)
        assert res.status_code == 200
        assert client.get(f"/api/categories/{cat_id}",
                          headers=auth).status_code == 404

    def test_delete_category_detaches_tasks(self, client, auth):
        cat_id = create_category(client, auth).get_json()["category"]["id"]
        task = client.post("/api/tasks", headers=auth, json={
            "title": "Task", "category_id": cat_id}).get_json()["task"]
        assert task["category_id"] == cat_id

        client.delete(f"/api/categories/{cat_id}", headers=auth)
        res = client.get(f"/api/tasks/{task['id']}", headers=auth)
        assert res.status_code == 200
        assert res.get_json()["task"]["category_id"] is None


class TestCategoryScoping:
    def test_users_cannot_see_others_categories(self, client, auth, auth2):
        cat_id = create_category(client, auth).get_json()["category"]["id"]

        res = client.get("/api/categories", headers=auth2)
        assert res.get_json()["categories"] == []

        assert client.get(f"/api/categories/{cat_id}",
                          headers=auth2).status_code == 404
        assert client.put(f"/api/categories/{cat_id}", headers=auth2,
                          json={"name": "Hacked"}).status_code == 404
        assert client.delete(f"/api/categories/{cat_id}",
                             headers=auth2).status_code == 404
