from tests.conftest import auth_headers, register_user


def create_category(client, token, name="Work"):
    return client.post("/api/categories", json={"name": name}, headers=auth_headers(token))


class TestCreateCategory:
    def test_create_category(self, client, user_token):
        resp = create_category(client, user_token)
        assert resp.status_code == 201
        assert resp.get_json()["name"] == "Work"

    def test_create_category_requires_auth(self, client):
        resp = client.post("/api/categories", json={"name": "Work"})
        assert resp.status_code == 401

    def test_create_category_missing_name(self, client, user_token):
        resp = client.post("/api/categories", json={}, headers=auth_headers(user_token))
        assert resp.status_code == 422

    def test_create_duplicate_category(self, client, user_token):
        create_category(client, user_token)
        resp = create_category(client, user_token)
        assert resp.status_code == 409

    def test_same_category_name_different_users_allowed(self, client, user_token, second_user_token):
        create_category(client, user_token)
        resp = create_category(client, second_user_token)
        assert resp.status_code == 201


class TestListCategories:
    def test_list_categories(self, client, user_token):
        create_category(client, user_token, "Work")
        create_category(client, user_token, "Home")
        resp = client.get("/api/categories", headers=auth_headers(user_token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total_items"] == 2

    def test_list_categories_scoped_to_user(self, client, user_token, second_user_token):
        create_category(client, user_token, "Work")
        resp = client.get("/api/categories", headers=auth_headers(second_user_token))
        assert resp.get_json()["items"] == []


class TestGetUpdateDeleteCategory:
    def test_get_category(self, client, user_token):
        cat_id = create_category(client, user_token).get_json()["id"]
        resp = client.get(f"/api/categories/{cat_id}", headers=auth_headers(user_token))
        assert resp.status_code == 200

    def test_get_category_not_found(self, client, user_token):
        resp = client.get("/api/categories/999", headers=auth_headers(user_token))
        assert resp.status_code == 404

    def test_get_other_users_category_forbidden(self, client, user_token, second_user_token):
        cat_id = create_category(client, user_token).get_json()["id"]
        resp = client.get(f"/api/categories/{cat_id}", headers=auth_headers(second_user_token))
        assert resp.status_code == 404

    def test_update_category(self, client, user_token):
        cat_id = create_category(client, user_token).get_json()["id"]
        resp = client.put(
            f"/api/categories/{cat_id}", json={"name": "Renamed"}, headers=auth_headers(user_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Renamed"

    def test_delete_category(self, client, user_token):
        cat_id = create_category(client, user_token).get_json()["id"]
        resp = client.delete(f"/api/categories/{cat_id}", headers=auth_headers(user_token))
        assert resp.status_code == 204
        resp = client.get(f"/api/categories/{cat_id}", headers=auth_headers(user_token))
        assert resp.status_code == 404

    def test_delete_category_nullifies_task_reference(self, client, user_token):
        cat_id = create_category(client, user_token).get_json()["id"]
        task_resp = client.post(
            "/api/tasks",
            json={"title": "Task A", "category_id": cat_id},
            headers=auth_headers(user_token),
        )
        task_id = task_resp.get_json()["id"]

        client.delete(f"/api/categories/{cat_id}", headers=auth_headers(user_token))

        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers(user_token))
        assert resp.get_json()["category_id"] is None
