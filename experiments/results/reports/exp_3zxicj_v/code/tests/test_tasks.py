import pytest


class TestTaskCreate:

    def test_create_task_success(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "My task",
            "description": "Do something useful",
            "status": "in_progress",
            "priority": "urgent",
            "category": "work",
            "due_date": "2026-08-15",
        }, headers=auth_headers)
        assert resp.status_code == 201
        t = resp.get_json()["task"]
        assert t["title"] == "My task"
        assert t["description"] == "Do something useful"
        assert t["status"] == "in_progress"
        assert t["priority"] == "urgent"
        assert t["category"] == "work"
        assert t["due_date"] == "2026-08-15"
        assert t["assigned_to"] is None
        assert t["id"] is not None
        assert t["created_at"] is not None
        assert t["updated_at"] is not None

    def test_create_task_defaults(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Minimal task",
        }, headers=auth_headers)
        assert resp.status_code == 201
        t = resp.get_json()["task"]
        assert t["status"] == "pending"
        assert t["priority"] == "medium"
        assert t["category"] == "general"
        assert t["description"] == ""

    def test_create_task_without_auth(self, client):
        resp = client.post("/api/tasks", json={"title": "No auth"})
        assert resp.status_code == 401

    def test_create_task_no_title(self, client, auth_headers):
        resp = client.post("/api/tasks", json={}, headers=auth_headers)
        assert resp.status_code == 422
        assert "Title" in resp.get_json()["error"]

    def test_create_task_invalid_status(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad status",
            "status": "invalid",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_task_invalid_priority(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad priority",
            "priority": "invalid",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_task_assign_to_user(self, client, auth_headers, second_user):
        assignee_id = second_user["user"]["id"]
        resp = client.post("/api/tasks", json={
            "title": "Assigned task",
            "assigned_to": assignee_id,
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.get_json()["task"]["assigned_to"] == assignee_id

    def test_create_task_assign_to_nonexistent_user(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad assign",
            "assigned_to": 99999,
        }, headers=auth_headers)
        assert resp.status_code == 422
        assert "not found" in resp.get_json()["error"]

    def test_create_task_invalid_json(self, client, auth_headers):
        resp = client.post("/api/tasks", data="bad", content_type="application/json", headers=auth_headers)
        assert resp.status_code == 400


class TestTaskGet:

    def test_get_task(self, client, auth_headers, created_task):
        resp = client.get(f"/api/tasks/{created_task['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["id"] == created_task["id"]

    def test_get_task_not_found(self, client, auth_headers):
        resp = client.get("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_task_without_auth(self, client, created_task):
        resp = client.get(f"/api/tasks/{created_task['id']}")
        assert resp.status_code == 401

    def test_get_task_accessible_by_assignee(self, client, second_user, auth_headers):
        assignee_id = second_user["user"]["id"]
        create_resp = client.post("/api/tasks", json={
            "title": "Shared task",
            "assigned_to": assignee_id,
        }, headers=auth_headers)
        task_id = create_resp.get_json()["task"]["id"]

        login_resp = client.post("/api/auth/login", json={
            "username": "user2",
            "password": "password123",
        })
        assignee_token = login_resp.get_json()["access_token"]

        resp = client.get(f"/api/tasks/{task_id}",
                          headers={"Authorization": f"Bearer {assignee_token}"})
        assert resp.status_code == 200
        assert resp.get_json()["task"]["id"] == task_id

    def test_get_task_not_accessible_by_stranger(self, client, auth_headers):
        client.post("/api/auth/register", json={
            "username": "stranger",
            "email": "stranger@example.com",
            "password": "password123",
        })
        login_resp = client.post("/api/auth/login", json={
            "username": "stranger",
            "password": "password123",
        })
        stranger_token = login_resp.get_json()["access_token"]

        create_resp = client.post("/api/tasks", json={
            "title": "Private task",
        }, headers=auth_headers)
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.get(f"/api/tasks/{task_id}",
                          headers={"Authorization": f"Bearer {stranger_token}"})
        assert resp.status_code == 404


class TestTaskUpdate:

    def test_update_task(self, client, auth_headers, created_task):
        resp = client.put(f"/api/tasks/{created_task['id']}", json={
            "title": "Updated title",
            "status": "completed",
            "priority": "low",
            "category": "done",
            "due_date": "2026-12-25",
            "description": "Updated description",
        }, headers=auth_headers)
        assert resp.status_code == 200
        t = resp.get_json()["task"]
        assert t["title"] == "Updated title"
        assert t["status"] == "completed"
        assert t["priority"] == "low"
        assert t["category"] == "done"
        assert t["due_date"] == "2026-12-25"
        assert t["description"] == "Updated description"
        assert t["updated_at"] != created_task["updated_at"]

    def test_update_task_partial(self, client, auth_headers, created_task):
        resp = client.put(f"/api/tasks/{created_task['id']}", json={
            "title": "Only title",
        }, headers=auth_headers)
        assert resp.status_code == 200
        t = resp.get_json()["task"]
        assert t["title"] == "Only title"
        assert t["status"] == created_task["status"]
        assert t["priority"] == created_task["priority"]

    def test_update_task_not_found(self, client, auth_headers):
        resp = client.put("/api/tasks/99999", json={"title": "Nope"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_update_task_invalid_status(self, client, auth_headers, created_task):
        resp = client.put(f"/api/tasks/{created_task['id']}", json={
            "status": "invalid",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_update_task_invalid_priority(self, client, auth_headers, created_task):
        resp = client.put(f"/api/tasks/{created_task['id']}", json={
            "priority": "invalid",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_update_task_without_auth(self, client, created_task):
        resp = client.put(f"/api/tasks/{created_task['id']}", json={"title": "X"})
        assert resp.status_code == 401


class TestTaskDelete:

    def test_delete_task(self, client, auth_headers):
        create_resp = client.post("/api/tasks", json={
            "title": "Delete me",
        }, headers=auth_headers)
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Task deleted"

        get_resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_task_not_found(self, client, auth_headers):
        resp = client.delete("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_task_only_by_creator(self, client, auth_headers, second_user):
        create_resp = client.post("/api/tasks", json={
            "title": "Creator task",
        }, headers=auth_headers)
        task_id = create_resp.get_json()["task"]["id"]

        login_resp = client.post("/api/auth/login", json={
            "username": "user2",
            "password": "password123",
        })
        other_token = login_resp.get_json()["access_token"]

        resp = client.delete(f"/api/tasks/{task_id}",
                             headers={"Authorization": f"Bearer {other_token}"})
        assert resp.status_code == 404

    def test_delete_task_without_auth(self, client, created_task):
        resp = client.delete(f"/api/tasks/{created_task['id']}")
        assert resp.status_code == 401


class TestTaskList:

    def test_list_tasks_default_pagination(self, client, auth_headers):
        for i in range(5):
            client.post("/api/tasks", json={"title": f"Task {i}"}, headers=auth_headers)
        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tasks"]) == 5
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["pages"] == 1

    def test_list_tasks_pagination(self, client, auth_headers):
        for i in range(5):
            client.post("/api/tasks", json={"title": f"Task {i}"}, headers=auth_headers)
        resp = client.get("/api/tasks?page=1&per_page=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tasks"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["pages"] == 3

        resp2 = client.get("/api/tasks?page=2&per_page=2", headers=auth_headers)
        assert len(resp2.get_json()["tasks"]) == 2

        resp3 = client.get("/api/tasks?page=3&per_page=2", headers=auth_headers)
        assert len(resp3.get_json()["tasks"]) == 1

    def test_list_tasks_filter_by_status(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Pending", "status": "pending"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Done", "status": "completed"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Doing", "status": "in_progress"}, headers=auth_headers)

        resp = client.get("/api/tasks?status=completed", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Done"

    def test_list_tasks_filter_by_priority(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "High", "priority": "high"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Low", "priority": "low"}, headers=auth_headers)

        resp = client.get("/api/tasks?priority=high", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "High"

    def test_list_tasks_filter_by_category(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "A", "category": "cat1"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "B", "category": "cat2"}, headers=auth_headers)

        resp = client.get("/api/tasks?category=cat1", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "A"

    def test_list_tasks_search(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Buy groceries"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Write code"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Buy milk", "description": "groceries list"}, headers=auth_headers)

        resp = client.get("/api/tasks?search=groc", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 2

    def test_list_tasks_sort(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "A"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "B"}, headers=auth_headers)

        resp = client.get("/api/tasks?sort_by=title&sort_order=asc", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert tasks[0]["title"] == "A"
        assert tasks[1]["title"] == "B"

        resp = client.get("/api/tasks?sort_by=title&sort_order=desc", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert tasks[0]["title"] == "B"
        assert tasks[1]["title"] == "A"

    def test_list_tasks_no_auth(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 401

    def test_list_tasks_only_shows_accessible(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "My task"}, headers=auth_headers)

        client.post("/api/auth/register", json={
            "username": "other",
            "email": "other@example.com",
            "password": "password123",
        })
        login_resp = client.post("/api/auth/login", json={
            "username": "other",
            "password": "password123",
        })
        other_token = login_resp.get_json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}
        client.post("/api/tasks", json={"title": "Their task"}, headers=other_headers)

        resp = client.get("/api/tasks", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "My task"

    def test_list_tasks_invalid_status_filter(self, client, auth_headers):
        resp = client.get("/api/tasks?status=invalid", headers=auth_headers)
        assert resp.status_code == 422

    def test_list_tasks_invalid_priority_filter(self, client, auth_headers):
        resp = client.get("/api/tasks?priority=invalid", headers=auth_headers)
        assert resp.status_code == 422
