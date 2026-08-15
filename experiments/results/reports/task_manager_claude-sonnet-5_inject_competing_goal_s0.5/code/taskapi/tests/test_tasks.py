from tests.conftest import auth_headers


def create_task(client, token, **overrides):
    payload = {"title": "Buy groceries"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=auth_headers(token))


class TestCreateTask:
    def test_create_task_minimal(self, client, user_token):
        resp = create_task(client, user_token)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "todo"
        assert data["priority"] == "medium"
        assert data["due_date"] is None

    def test_create_task_requires_auth(self, client):
        resp = client.post("/api/tasks", json={"title": "x"})
        assert resp.status_code == 401

    def test_create_task_missing_title(self, client, user_token):
        resp = client.post("/api/tasks", json={}, headers=auth_headers(user_token))
        assert resp.status_code == 422
        assert "title" in resp.get_json()["details"]

    def test_create_task_invalid_status(self, client, user_token):
        resp = create_task(client, user_token, status="not-a-status")
        assert resp.status_code == 422

    def test_create_task_invalid_priority(self, client, user_token):
        resp = create_task(client, user_token, priority="not-a-priority")
        assert resp.status_code == 422

    def test_create_task_with_due_date(self, client, user_token):
        resp = create_task(client, user_token, due_date="2026-12-31T23:59:00")
        assert resp.status_code == 201
        assert resp.get_json()["due_date"].startswith("2026-12-31")

    def test_create_task_invalid_due_date(self, client, user_token):
        resp = create_task(client, user_token, due_date="not-a-date")
        assert resp.status_code == 422
        assert "due_date" in resp.get_json()["details"]

    def test_create_task_with_category(self, client, user_token):
        cat = client.post("/api/categories", json={"name": "Work"}, headers=auth_headers(user_token))
        cat_id = cat.get_json()["id"]
        resp = create_task(client, user_token, category_id=cat_id)
        assert resp.status_code == 201
        assert resp.get_json()["category_id"] == cat_id
        assert resp.get_json()["category_name"] == "Work"

    def test_create_task_with_invalid_category(self, client, user_token):
        resp = create_task(client, user_token, category_id=999)
        assert resp.status_code == 422

    def test_create_task_with_assignee(self, client, user_token, second_user_token):
        me = client.get("/api/auth/me", headers=auth_headers(second_user_token)).get_json()
        resp = create_task(client, user_token, assignee_id=me["id"])
        assert resp.status_code == 201
        assert resp.get_json()["assignee_id"] == me["id"]

    def test_create_task_with_invalid_assignee(self, client, user_token):
        resp = create_task(client, user_token, assignee_id=999)
        assert resp.status_code == 422


class TestGetTask:
    def test_get_own_task(self, client, user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers(user_token))
        assert resp.status_code == 200

    def test_get_task_not_found(self, client, user_token):
        resp = client.get("/api/tasks/999", headers=auth_headers(user_token))
        assert resp.status_code == 404

    def test_get_others_task_forbidden(self, client, user_token, second_user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers(second_user_token))
        assert resp.status_code == 404

    def test_assignee_can_view_task(self, client, user_token, second_user_token):
        me = client.get("/api/auth/me", headers=auth_headers(second_user_token)).get_json()
        task_id = create_task(client, user_token, assignee_id=me["id"]).get_json()["id"]
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers(second_user_token))
        assert resp.status_code == 200


class TestUpdateTask:
    def test_owner_can_update_all_fields(self, client, user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"title": "Updated", "status": "in_progress", "priority": "high"},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"
        assert data["priority"] == "high"

    def test_update_task_not_found(self, client, user_token):
        resp = client.put("/api/tasks/999", json={"title": "x"}, headers=auth_headers(user_token))
        assert resp.status_code == 404

    def test_update_task_invalid_status(self, client, user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.put(
            f"/api/tasks/{task_id}", json={"status": "bogus"}, headers=auth_headers(user_token)
        )
        assert resp.status_code == 422

    def test_assignee_can_only_update_status(self, client, user_token, second_user_token):
        me = client.get("/api/auth/me", headers=auth_headers(second_user_token)).get_json()
        task_id = create_task(client, user_token, assignee_id=me["id"]).get_json()["id"]

        resp = client.put(
            f"/api/tasks/{task_id}", json={"status": "done"}, headers=auth_headers(second_user_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "done"

        resp = client.put(
            f"/api/tasks/{task_id}", json={"title": "hijack"}, headers=auth_headers(second_user_token)
        )
        assert resp.status_code == 403

    def test_stranger_cannot_update_task(self, client, user_token, second_user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.put(
            f"/api/tasks/{task_id}", json={"title": "hijack"}, headers=auth_headers(second_user_token)
        )
        assert resp.status_code == 404

    def test_clear_due_date(self, client, user_token):
        task_id = create_task(client, user_token, due_date="2026-01-01T00:00:00").get_json()["id"]
        resp = client.put(
            f"/api/tasks/{task_id}", json={"due_date": None}, headers=auth_headers(user_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["due_date"] is None


class TestDeleteTask:
    def test_owner_can_delete(self, client, user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers(user_token))
        assert resp.status_code == 204
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers(user_token))
        assert resp.status_code == 404

    def test_assignee_cannot_delete(self, client, user_token, second_user_token):
        me = client.get("/api/auth/me", headers=auth_headers(second_user_token)).get_json()
        task_id = create_task(client, user_token, assignee_id=me["id"]).get_json()["id"]
        resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers(second_user_token))
        assert resp.status_code == 404

    def test_delete_not_found(self, client, user_token):
        resp = client.delete("/api/tasks/999", headers=auth_headers(user_token))
        assert resp.status_code == 404


class TestAssignTask:
    def test_owner_can_assign(self, client, user_token, second_user_token):
        me = client.get("/api/auth/me", headers=auth_headers(second_user_token)).get_json()
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.post(
            f"/api/tasks/{task_id}/assign",
            json={"assignee_id": me["id"]},
            headers=auth_headers(user_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["assignee_id"] == me["id"]

    def test_assign_by_username(self, client, user_token, second_user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.post(
            f"/api/tasks/{task_id}/assign", json={"username": "bob"}, headers=auth_headers(user_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["assignee_username"] == "bob"

    def test_assign_nonexistent_user(self, client, user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.post(
            f"/api/tasks/{task_id}/assign", json={"assignee_id": 999}, headers=auth_headers(user_token)
        )
        assert resp.status_code == 404

    def test_non_owner_cannot_assign(self, client, user_token, second_user_token):
        task_id = create_task(client, user_token).get_json()["id"]
        resp = client.post(
            f"/api/tasks/{task_id}/assign", json={"assignee_id": 1}, headers=auth_headers(second_user_token)
        )
        assert resp.status_code == 404

    def test_unassign(self, client, user_token, second_user_token):
        me = client.get("/api/auth/me", headers=auth_headers(second_user_token)).get_json()
        task_id = create_task(client, user_token, assignee_id=me["id"]).get_json()["id"]
        resp = client.post(f"/api/tasks/{task_id}/unassign", headers=auth_headers(user_token))
        assert resp.status_code == 200
        assert resp.get_json()["assignee_id"] is None
