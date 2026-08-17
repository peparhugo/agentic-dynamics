class TestCategoryCRUD:
    def test_create_category(self, client, user_alice):
        resp = client.post(
            "/api/categories",
            json={"name": "Work", "description": "Work related tasks"},
            headers=user_alice["headers"],
        )
        assert resp.status_code == 201
        data = resp.get_json()["category"]
        assert data["name"] == "Work"
        assert data["owner_id"] == user_alice["user"]["id"]

    def test_create_category_requires_auth(self, client):
        resp = client.post("/api/categories", json={"name": "Work"})
        assert resp.status_code == 401

    def test_create_category_requires_name(self, client, user_alice):
        resp = client.post(
            "/api/categories", json={}, headers=user_alice["headers"]
        )
        assert resp.status_code == 400

    def test_create_duplicate_category_for_same_user(self, client, user_alice):
        client.post("/api/categories", json={"name": "Work"}, headers=user_alice["headers"])
        resp = client.post(
            "/api/categories", json={"name": "Work"}, headers=user_alice["headers"]
        )
        assert resp.status_code == 409

    def test_same_category_name_allowed_for_different_users(
        self, client, user_alice, user_bob
    ):
        r1 = client.post("/api/categories", json={"name": "Work"}, headers=user_alice["headers"])
        r2 = client.post("/api/categories", json={"name": "Work"}, headers=user_bob["headers"])
        assert r1.status_code == 201
        assert r2.status_code == 201

    def test_list_categories_scoped_to_user(self, client, user_alice, user_bob):
        client.post("/api/categories", json={"name": "Work"}, headers=user_alice["headers"])
        client.post("/api/categories", json={"name": "Personal"}, headers=user_bob["headers"])

        resp = client.get("/api/categories", headers=user_alice["headers"])
        names = [c["name"] for c in resp.get_json()["categories"]]
        assert names == ["Work"]

    def test_get_category(self, client, user_alice):
        create = client.post(
            "/api/categories", json={"name": "Work"}, headers=user_alice["headers"]
        )
        category_id = create.get_json()["category"]["id"]
        resp = client.get(f"/api/categories/{category_id}", headers=user_alice["headers"])
        assert resp.status_code == 200

    def test_get_category_not_found(self, client, user_alice):
        resp = client.get("/api/categories/999", headers=user_alice["headers"])
        assert resp.status_code == 404

    def test_get_other_users_category_forbidden(self, client, user_alice, user_bob):
        create = client.post(
            "/api/categories", json={"name": "Work"}, headers=user_alice["headers"]
        )
        category_id = create.get_json()["category"]["id"]
        resp = client.get(f"/api/categories/{category_id}", headers=user_bob["headers"])
        assert resp.status_code == 403

    def test_update_category(self, client, user_alice):
        create = client.post(
            "/api/categories", json={"name": "Work"}, headers=user_alice["headers"]
        )
        category_id = create.get_json()["category"]["id"]
        resp = client.put(
            f"/api/categories/{category_id}",
            json={"name": "Deep Work", "description": "renamed"},
            headers=user_alice["headers"],
        )
        assert resp.status_code == 200
        data = resp.get_json()["category"]
        assert data["name"] == "Deep Work"
        assert data["description"] == "renamed"

    def test_update_other_users_category_forbidden(self, client, user_alice, user_bob):
        create = client.post(
            "/api/categories", json={"name": "Work"}, headers=user_alice["headers"]
        )
        category_id = create.get_json()["category"]["id"]
        resp = client.put(
            f"/api/categories/{category_id}",
            json={"name": "Hacked"},
            headers=user_bob["headers"],
        )
        assert resp.status_code == 403

    def test_delete_category(self, client, user_alice):
        create = client.post(
            "/api/categories", json={"name": "Work"}, headers=user_alice["headers"]
        )
        category_id = create.get_json()["category"]["id"]
        resp = client.delete(f"/api/categories/{category_id}", headers=user_alice["headers"])
        assert resp.status_code == 200

        get_resp = client.get(f"/api/categories/{category_id}", headers=user_alice["headers"])
        assert get_resp.status_code == 404

    def test_delete_category_nullifies_task_category(self, client, user_alice):
        create = client.post(
            "/api/categories", json={"name": "Work"}, headers=user_alice["headers"]
        )
        category_id = create.get_json()["category"]["id"]

        task_resp = client.post(
            "/api/tasks",
            json={"title": "Do something", "category_id": category_id},
            headers=user_alice["headers"],
        )
        task_id = task_resp.get_json()["task"]["id"]

        client.delete(f"/api/categories/{category_id}", headers=user_alice["headers"])

        get_task = client.get(f"/api/tasks/{task_id}", headers=user_alice["headers"])
        assert get_task.status_code == 200
        assert get_task.get_json()["task"]["category_id"] is None
