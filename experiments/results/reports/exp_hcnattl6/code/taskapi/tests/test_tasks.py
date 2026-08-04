class TestTaskCreate:
    def test_create_task_basic(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "My new task",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["title"] == "My new task"
        assert data["task"]["status"] == "todo"
        assert data["task"]["priority"] == "medium"
        assert data["task"]["id"] is not None

    def test_create_task_full(self, client, auth_headers, category_id):
        resp = client.post("/api/tasks", json={
            "title": "Full task",
            "description": "With all fields",
            "status": "in_progress",
            "priority": "high",
            "category_id": category_id,
            "due_date": "2026-12-25T00:00:00",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["description"] == "With all fields"
        assert data["task"]["status"] == "in_progress"
        assert data["task"]["priority"] == "high"
        assert data["task"]["category_id"] == category_id
        assert data["task"]["due_date"] == "2026-12-25T00:00:00"

    def test_create_task_no_title(self, client, auth_headers):
        resp = client.post("/api/tasks", json={"title": ""}, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_task_invalid_status(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad status", "status": "invalid",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_task_invalid_priority(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad priority", "priority": "critical",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_task_unauthorized(self, client):
        resp = client.post("/api/tasks", json={"title": "No auth"})
        assert resp.status_code == 401


class TestTaskGet:
    def test_get_task_by_owner(self, client, auth_headers, task_id):
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["id"] == task_id

    def test_get_task_not_found(self, client, auth_headers):
        resp = client.get("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_task_wrong_user(self, client, second_user_headers, task_id):
        resp = client.get(f"/api/tasks/{task_id}", headers=second_user_headers)
        assert resp.status_code == 403

    def test_get_task_by_assigned_user(self, client, auth_headers, second_user_headers, task_id):
        client.put(f"/api/tasks/{task_id}", json={
            "assigned_to": None,
        }, headers=auth_headers)
        from app.database import get_db
        from flask import current_app
        import pytest
        resp = client.get(f"/api/tasks/{task_id}", headers=second_user_headers)
        assert resp.status_code == 403

    def test_get_assigned_task_by_assignee(self, client, auth_headers, second_user_headers):
        resp = client.post("/api/tasks", json={
            "title": "Assigned Task",
            "assigned_to": 2,
        }, headers=auth_headers)
        task_id = resp.get_json()["task"]["id"]
        resp = client.get(f"/api/tasks/{task_id}", headers=second_user_headers)
        assert resp.status_code == 200


class TestTaskUpdate:
    def test_update_task_title(self, client, auth_headers, task_id):
        resp = client.put(f"/api/tasks/{task_id}", json={
            "title": "Updated Title",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Updated Title"

    def test_update_task_status(self, client, auth_headers, task_id):
        resp = client.put(f"/api/tasks/{task_id}", json={
            "status": "done",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["status"] == "done"

    def test_update_task_empty_title(self, client, auth_headers, task_id):
        resp = client.put(f"/api/tasks/{task_id}", json={
            "title": "",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_update_task_no_fields(self, client, auth_headers, task_id):
        resp = client.put(f"/api/tasks/{task_id}", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_update_task_not_found(self, client, auth_headers):
        resp = client.put("/api/tasks/99999", json={"title": "nope"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_update_task_by_non_owner(self, client, second_user_headers, task_id):
        resp = client.put(f"/api/tasks/{task_id}", json={
            "title": "Hijack",
        }, headers=second_user_headers)
        assert resp.status_code == 403

    def test_update_task_clear_due_date(self, client, auth_headers, task_id):
        resp = client.put(f"/api/tasks/{task_id}", json={
            "due_date": None,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["due_date"] is None


class TestTaskDelete:
    def test_delete_task(self, client, auth_headers, task_id):
        resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_task_not_found(self, client, auth_headers):
        resp = client.delete("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_task_by_non_owner(self, client, second_user_headers, task_id):
        resp = client.delete(f"/api/tasks/{task_id}", headers=second_user_headers)
        assert resp.status_code == 403


class TestTaskList:
    def test_list_tasks(self, client, auth_headers, task_id):
        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["items"]) >= 1
        assert data["pagination"]["total"] >= 1
        assert data["pagination"]["page"] == 1

    def test_list_tasks_pagination(self, client, auth_headers):
        for i in range(25):
            client.post("/api/tasks", json={
                "title": f"Task {i}",
            }, headers=auth_headers)

        resp = client.get("/api/tasks?per_page=10&page=1", headers=auth_headers)
        data = resp.get_json()
        assert len(data["items"]) == 10
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["pages"] > 1

        resp = client.get("/api/tasks?per_page=10&page=2", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["page"] == 2

    def test_list_tasks_filter_by_status(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Todo task", "status": "todo",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Done task", "status": "done",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?status=done", headers=auth_headers)
        data = resp.get_json()
        for item in data["items"]:
            assert item["status"] == "done"

    def test_list_tasks_filter_by_priority(self, client, auth_headers):
        resp = client.get("/api/tasks?priority=high", headers=auth_headers)
        data = resp.get_json()
        for item in data["items"]:
            assert item["priority"] == "high"

    def test_list_tasks_search(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Buy groceries",
            "description": "Milk, eggs, bread",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Write code",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?q=groceries", headers=auth_headers)
        data = resp.get_json()
        assert len(data["items"]) >= 1
        assert any("groceries" in item["title"] for item in data["items"])

        resp = client.get("/api/tasks?q=Milk", headers=auth_headers)
        data = resp.get_json()
        assert len(data["items"]) >= 1

    def test_list_tasks_sorting(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "A Task"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "B Task"}, headers=auth_headers)

        resp = client.get("/api/tasks?sort_by=title&sort_order=asc", headers=auth_headers)
        data = resp.get_json()
        titles = [item["title"] for item in data["items"]]
        assert titles == sorted(titles)

    def test_list_tasks_only_returns_own_tasks(self, client, auth_headers, second_user_headers):
        client.post("/api/tasks", json={
            "title": "My task only",
        }, headers=auth_headers)

        resp = client.get("/api/tasks", headers=auth_headers)
        data = resp.get_json()
        for item in data["items"]:
            assert item["created_by"] == 1

    def test_list_tasks_overdue(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Overdue task",
            "due_date": "2020-01-01T00:00:00",
            "status": "todo",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Future task",
            "due_date": "2099-01-01T00:00:00",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?overdue=true", headers=auth_headers)
        data = resp.get_json()
        for item in data["items"]:
            assert item["title"] == "Overdue task"

    def test_list_tasks_per_page_max(self, client, auth_headers):
        resp = client.get("/api/tasks?per_page=200", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["per_page"] == 100

    def test_list_tasks_negative_page_clamped(self, client, auth_headers):
        resp = client.get("/api/tasks?page=-5", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["page"] == 1
