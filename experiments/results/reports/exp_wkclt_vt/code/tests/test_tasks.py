import pytest


class TestCreateTask:
    def test_create_task_success(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Test task",
            "description": "Do something useful",
            "status": "pending",
            "priority": "high",
            "category": "work",
            "due_date": "2025-12-31T12:00:00",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["title"] == "Test task"
        assert data["task"]["status"] == "pending"
        assert data["task"]["priority"] == "high"
        assert data["task"]["category"] == "work"
        assert data["task"]["due_date"] == "2025-12-31T12:00:00"
        assert data["task"]["creator_id"] is not None

    def test_create_task_defaults(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Minimal task",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["status"] == "pending"
        assert data["task"]["priority"] == "medium"
        assert data["task"]["category"] == "general"

    def test_create_task_no_title(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "description": "No title",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_task_invalid_status(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad status",
            "status": "nonexistent",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_task_invalid_priority(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad priority",
            "priority": "extreme",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_task_invalid_due_date(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad date",
            "due_date": "not-a-date",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_task_with_assignee(self, client, auth_headers, other_user_headers):
        me_resp = client.get("/api/auth/me", headers=other_user_headers)
        other_id = me_resp.get_json()["user"]["id"]

        resp = client.post("/api/tasks", json={
            "title": "Assigned task",
            "assignee_id": other_id,
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.get_json()["task"]["assignee_id"] == other_id

    def test_create_task_nonexistent_assignee(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad assignee",
            "assignee_id": 99999,
        }, headers=auth_headers)
        assert resp.status_code == 404

    def test_create_task_unauthorized(self, client):
        resp = client.post("/api/tasks", json={"title": "No auth"})
        assert resp.status_code == 401


class TestGetTask:
    def test_get_task_success(self, client, auth_headers):
        create_resp = client.post("/api/tasks", json={
            "title": "Get me",
        }, headers=auth_headers)
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Get me"

    def test_get_task_not_found(self, client, auth_headers):
        resp = client.get("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_task_unauthorized(self, client):
        resp = client.get("/api/tasks/1")
        assert resp.status_code == 401


class TestUpdateTask:
    def test_update_all_fields(self, client, auth_headers, other_user_headers):
        create = client.post("/api/tasks", json={"title": "Original"}, headers=auth_headers)
        task_id = create.get_json()["task"]["id"]

        me_resp = client.get("/api/auth/me", headers=other_user_headers)
        other_id = me_resp.get_json()["user"]["id"]

        resp = client.put(f"/api/tasks/{task_id}", json={
            "title": "Updated",
            "description": "New desc",
            "status": "in_progress",
            "priority": "urgent",
            "category": "personal",
            "due_date": "2026-06-15T09:00:00",
            "assignee_id": other_id,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()["task"]
        assert data["title"] == "Updated"
        assert data["description"] == "New desc"
        assert data["status"] == "in_progress"
        assert data["priority"] == "urgent"
        assert data["category"] == "personal"
        assert data["due_date"] == "2026-06-15T09:00:00"
        assert data["assignee_id"] == other_id

    def test_update_partial(self, client, auth_headers):
        create = client.post("/api/tasks", json={"title": "Original"}, headers=auth_headers)
        task_id = create.get_json()["task"]["id"]

        resp = client.put(f"/api/tasks/{task_id}", json={
            "status": "completed",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()["task"]
        assert data["status"] == "completed"
        assert data["title"] == "Original"

    def test_update_clear_due_date(self, client, auth_headers):
        create = client.post("/api/tasks", json={
            "title": "Dated",
            "due_date": "2025-06-01T00:00:00",
        }, headers=auth_headers)
        task_id = create.get_json()["task"]["id"]

        resp = client.put(f"/api/tasks/{task_id}", json={
            "due_date": None,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["due_date"] is None

    def test_update_clear_assignee(self, client, auth_headers, other_user_headers):
        other = client.get("/api/auth/me", headers=other_user_headers).get_json()
        create = client.post("/api/tasks", json={
            "title": "Assigned",
            "assignee_id": other["user"]["id"],
        }, headers=auth_headers)
        task_id = create.get_json()["task"]["id"]

        resp = client.put(f"/api/tasks/{task_id}", json={
            "assignee_id": None,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["assignee_id"] is None

    def test_update_invalid_status(self, client, auth_headers):
        create = client.post("/api/tasks", json={"title": "Test"}, headers=auth_headers)
        task_id = create.get_json()["task"]["id"]

        resp = client.put(f"/api/tasks/{task_id}", json={
            "status": "bogus",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_update_not_found(self, client, auth_headers):
        resp = client.put("/api/tasks/99999", json={"title": "nope"}, headers=auth_headers)
        assert resp.status_code == 404


class TestDeleteTask:
    def test_delete_task_success(self, client, auth_headers):
        create = client.post("/api/tasks", json={"title": "Delete me"}, headers=auth_headers)
        task_id = create.get_json()["task"]["id"]

        resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Task deleted"

        get_resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_task_not_found(self, client, auth_headers):
        resp = client.delete("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestListTasks:
    @pytest.fixture(autouse=True)
    def _setup(self, client, auth_headers, other_user_headers):
        tasks = [
            {"title": "Task A", "status": "pending", "priority": "high", "category": "work"},
            {"title": "Task B", "status": "in_progress", "priority": "medium", "category": "work"},
            {"title": "Task C", "status": "completed", "priority": "low", "category": "personal"},
            {"title": "Task D", "status": "pending", "priority": "urgent", "category": "personal"},
            {"title": "Task E", "status": "cancelled", "priority": "medium", "category": "general"},
            {"title": "Urgent report", "status": "pending", "priority": "high", "category": "work"},
            {"title": "Buy groceries", "status": "pending", "priority": "low", "category": "personal"},
        ]
        for t in tasks:
            client.post("/api/tasks", json=t, headers=auth_headers)

    def test_list_all(self, client, auth_headers):
        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 7

    def test_filter_by_status(self, client, auth_headers):
        resp = client.get("/api/tasks?status=pending", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 4
        for t in data["tasks"]:
            assert t["status"] == "pending"

    def test_filter_by_priority(self, client, auth_headers):
        resp = client.get("/api/tasks?priority=high", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 2

    def test_filter_by_category(self, client, auth_headers):
        resp = client.get("/api/tasks?category=personal", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 3

    def test_search_title(self, client, auth_headers):
        resp = client.get("/api/tasks?search=Urgent", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tasks"][0]["title"] == "Urgent report"

    def test_search_description(self, client, auth_headers, other_user_headers):
        task = client.get("/api/auth/me", headers=other_user_headers).get_json()
        client.post("/api/tasks", json={
            "title": "Something",
            "description": "Find the hidden needle",
            "assignee_id": task["user"]["id"],
        }, headers=auth_headers)

        resp = client.get("/api/tasks?search=needle", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 1

    def test_combined_filters(self, client, auth_headers):
        resp = client.get(
            "/api/tasks?status=pending&priority=high&category=work",
            headers=auth_headers,
        )
        data = resp.get_json()
        assert data["total"] == 2

    def test_pagination(self, client, auth_headers):
        resp = client.get("/api/tasks?page=1&per_page=3", headers=auth_headers)
        data = resp.get_json()
        assert data["page"] == 1
        assert len(data["tasks"]) == 3
        assert data["total"] == 7
        assert data["pages"] == 3
        assert data["has_next"] is True
        assert data["has_prev"] is False

    def test_pagination_page_2(self, client, auth_headers):
        resp = client.get("/api/tasks?page=2&per_page=3", headers=auth_headers)
        data = resp.get_json()
        assert data["page"] == 2
        assert len(data["tasks"]) == 3
        assert data["has_next"] is True
        assert data["has_prev"] is True

    def test_pagination_last_page(self, client, auth_headers):
        resp = client.get("/api/tasks?page=3&per_page=3", headers=auth_headers)
        data = resp.get_json()
        assert data["page"] == 3
        assert len(data["tasks"]) == 1
        assert data["has_next"] is False

    def test_per_page_capped(self, client, auth_headers):
        resp = client.get("/api/tasks?per_page=200", headers=auth_headers)
        data = resp.get_json()
        assert data["per_page"] == 100

    def test_filter_by_assignee(self, client, auth_headers, other_user_headers):
        other = client.get("/api/auth/me", headers=other_user_headers).get_json()
        client.post("/api/tasks", json={
            "title": "For other",
            "assignee_id": other["user"]["id"],
        }, headers=auth_headers)

        resp = client.get(
            f"/api/tasks?assignee_id={other['user']['id']}",
            headers=auth_headers,
        )
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tasks"][0]["title"] == "For other"

    def test_filter_by_creator_id(self, client, auth_headers, other_user_headers):
        other = client.get("/api/auth/me", headers=other_user_headers).get_json()
        resp = client.get(
            f"/api/tasks?creator_id={other['user']['id']}",
            headers=auth_headers,
        )
        data = resp.get_json()
        assert data["total"] == 0

    def test_due_before(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Overdue",
            "due_date": "2020-01-01T00:00:00",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Future",
            "due_date": "2030-01-01T00:00:00",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?due_before=2025-01-01", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] >= 1
        titles = {t["title"] for t in data["tasks"]}
        assert "Overdue" in titles

    def test_due_after(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Future task",
            "due_date": "2030-01-01T00:00:00",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?due_after=2025-01-01", headers=auth_headers)
        data = resp.get_json()
        titles = {t["title"] for t in data["tasks"]}
        assert "Future task" in titles

    def test_sort_by_priority_desc(self, client, auth_headers):
        resp = client.get("/api/tasks?sort_by=priority&sort_dir=desc&per_page=100", headers=auth_headers)
        data = resp.get_json()
        priorities = [t["priority"] for t in data["tasks"]]
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        for i in range(len(priorities) - 1):
            assert priority_order.get(priorities[i], 99) <= priority_order.get(priorities[i + 1], 99)

    def test_sort_by_created_asc(self, client, auth_headers):
        resp = client.get("/api/tasks?sort_by=created_at&sort_dir=asc", headers=auth_headers)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["tasks"]) >= 1

    def test_invalid_due_before(self, client, auth_headers):
        resp = client.get("/api/tasks?due_before=not-a-date", headers=auth_headers)
        assert resp.status_code == 400


class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}
