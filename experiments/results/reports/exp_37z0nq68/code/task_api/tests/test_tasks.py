"""Tests for the tasks blueprint."""


def _create_task(client, headers, **overrides):
    payload = {
        "title": "Default Task",
        "description": "A test task",
        "status": "pending",
        "priority": "medium",
        "category": "general",
    }
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


class TestCreateTask:
    def test_create_task_success(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Write tests")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["title"] == "Write tests"
        assert data["task"]["status"] == "pending"
        assert data["task"]["priority"] == "medium"
        assert data["task"]["category"] == "general"
        assert data["task"]["assignee_ids"] == []
        assert data["task"]["id"] is not None

    def test_create_task_with_all_fields(self, client, auth_header):
        resp = _create_task(
            client,
            auth_header,
            title="Full task",
            description="With everything",
            status="in_progress",
            priority="high",
            category="bug",
            due_date="2026-12-25T10:00:00",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["status"] == "in_progress"
        assert data["task"]["priority"] == "high"
        assert data["task"]["category"] == "bug"
        assert data["task"]["due_date"] == "2026-12-25T10:00:00"

    def test_create_task_with_assignees(self, client, auth_header, auth_header2):
        user2_id = auth_header2[1]["id"]
        resp = _create_task(client, auth_header, title="Assigned task", assignee_ids=[user2_id])
        assert resp.status_code == 201
        assert resp.get_json()["task"]["assignee_ids"] == [user2_id]

    def test_create_task_invalid_assignee(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Bad assignee", assignee_ids=[99999])
        assert resp.status_code == 400
        assert "invalid" in resp.get_json()["error"]

    def test_create_task_no_title(self, client, auth_header):
        resp = client.post("/api/tasks", json={"title": ""}, headers=auth_header)
        assert resp.status_code == 400

    def test_create_task_invalid_priority(self, client, auth_header):
        resp = _create_task(client, auth_header, priority="critical")
        assert resp.status_code == 400

    def test_create_task_invalid_status(self, client, auth_header):
        resp = _create_task(client, auth_header, status="done")
        assert resp.status_code == 400

    def test_create_task_invalid_due_date(self, client, auth_header):
        resp = _create_task(client, auth_header, due_date="not-a-date")
        assert resp.status_code == 400

    def test_create_task_no_auth(self, client):
        resp = client.post("/api/tasks", json={"title": "No auth"})
        assert resp.status_code == 401

    def test_create_task_title_too_long(self, client, auth_header):
        resp = _create_task(client, auth_header, title="x" * 201)
        assert resp.status_code == 400

    def test_create_task_null_due_date(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Null date", due_date=None)
        assert resp.status_code == 201
        assert resp.get_json()["task"]["due_date"] is None

    def test_create_task_assignee_ids_not_list(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Bad assignee type", assignee_ids="not-a-list")
        assert resp.status_code == 400


class TestListTasks:
    def test_list_empty(self, client, auth_header):
        resp = client.get("/api/tasks", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["tasks"] == []
        assert data["pagination"]["total"] == 0

    def test_list_returns_own_tasks(self, client, auth_header):
        _create_task(client, auth_header, title="Task 1")
        _create_task(client, auth_header, title="Task 2")
        resp = client.get("/api/tasks", headers=auth_header)
        assert resp.get_json()["pagination"]["total"] == 2

    def test_list_shows_assigned_tasks(self, client, auth_header, auth_header2):
        headers2 = auth_header2[0]
        user1_id = 1
        _create_task(client, auth_header, title="Assigned", assignee_ids=[auth_header2[1]["id"]])
        resp = client.get("/api/tasks", headers=headers2)
        assert resp.get_json()["pagination"]["total"] == 1
        assert resp.get_json()["tasks"][0]["title"] == "Assigned"

    def test_list_include_assigned_false(self, client, auth_header, auth_header2):
        headers2 = auth_header2[0]
        user2 = auth_header2[1]
        _create_task(client, auth_header, title="Creator task", assignee_ids=[user2["id"]])
        _create_task(client, headers2, title="Own task")
        resp = client.get("/api/tasks?include_assigned=false", headers=headers2)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Own task"

    def test_list_only_assigned(self, client, auth_header, auth_header2):
        headers2 = auth_header2[0]
        user2 = auth_header2[1]
        _create_task(client, auth_header, title="Creator task", assignee_ids=[user2["id"]])
        _create_task(client, headers2, title="Own task")
        resp = client.get("/api/tasks?include_assigned=only_assigned", headers=headers2)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Creator task"

    def test_list_no_auth(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 401

    def test_filter_by_status(self, client, auth_header):
        _create_task(client, auth_header, title="Pending", status="pending")
        _create_task(client, auth_header, title="Completed", status="completed")
        resp = client.get("/api/tasks?status=completed", headers=auth_header)
        assert resp.get_json()["pagination"]["total"] == 1
        assert resp.get_json()["tasks"][0]["status"] == "completed"

    def test_filter_by_priority(self, client, auth_header):
        _create_task(client, auth_header, title="Low", priority="low")
        _create_task(client, auth_header, title="Urgent", priority="urgent")
        resp = client.get("/api/tasks?priority=urgent", headers=auth_header)
        assert resp.get_json()["pagination"]["total"] == 1
        assert resp.get_json()["tasks"][0]["priority"] == "urgent"

    def test_filter_by_category(self, client, auth_header):
        _create_task(client, auth_header, title="Bug", category="bug")
        _create_task(client, auth_header, title="Feature", category="feature")
        resp = client.get("/api/tasks?category=bug", headers=auth_header)
        assert resp.get_json()["pagination"]["total"] == 1
        assert resp.get_json()["tasks"][0]["category"] == "bug"

    def test_search_title(self, client, auth_header):
        _create_task(client, auth_header, title="Fix login bug")
        _create_task(client, auth_header, title="Add signup form")
        resp = client.get("/api/tasks?search=login", headers=auth_header)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_search_description(self, client, auth_header):
        _create_task(client, auth_header, title="Task A", description="critical: data loss")
        _create_task(client, auth_header, title="Task B", description="minor: style tweak")
        resp = client.get("/api/tasks?search=data loss", headers=auth_header)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_combined_filters(self, client, auth_header):
        _create_task(client, auth_header, title="Bug", status="pending", priority="high", category="bug")
        _create_task(client, auth_header, title="Feature", status="completed", priority="low", category="feature")
        resp = client.get("/api/tasks?status=pending&priority=high&category=bug", headers=auth_header)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_sort_by_title_asc(self, client, auth_header):
        _create_task(client, auth_header, title="Zebra")
        _create_task(client, auth_header, title="Apple")
        resp = client.get("/api/tasks?sort_by=title&sort_order=asc", headers=auth_header)
        tasks = resp.get_json()["tasks"]
        assert tasks[0]["title"] == "Apple"
        assert tasks[1]["title"] == "Zebra"

    def test_sort_by_due_date_desc(self, client, auth_header):
        _create_task(client, auth_header, title="Later", due_date="2026-12-25T00:00:00")
        _create_task(client, auth_header, title="Sooner", due_date="2026-01-01T00:00:00")
        resp = client.get("/api/tasks?sort_by=due_date&sort_order=desc", headers=auth_header)
        tasks = resp.get_json()["tasks"]
        assert tasks[0]["title"] == "Later"

    def test_sort_defaults(self, client, auth_header):
        _create_task(client, auth_header, title="First")
        _create_task(client, auth_header, title="Second")
        resp = client.get("/api/tasks?sort_by=invalid_col&sort_order=invalid", headers=auth_header)
        assert resp.status_code == 200


class TestPagination:
    def test_pagination_metadata(self, client, auth_header):
        for i in range(25):
            _create_task(client, auth_header, title=f"Task {i}")
        resp = client.get("/api/tasks?page=2&per_page=10", headers=auth_header)
        data = resp.get_json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 10
        assert data["pagination"]["total"] == 25
        assert data["pagination"]["pages"] == 3
        assert data["pagination"]["has_prev"] is True
        assert data["pagination"]["has_next"] is True
        assert len(data["tasks"]) == 10

    def test_pagination_first_page(self, client, auth_header):
        for i in range(5):
            _create_task(client, auth_header, title=f"Task {i}")
        resp = client.get("/api/tasks?page=1&per_page=3", headers=auth_header)
        data = resp.get_json()
        assert not data["pagination"]["has_prev"]
        assert data["pagination"]["has_next"]
        assert len(data["tasks"]) == 3

    def test_pagination_last_page(self, client, auth_header):
        for i in range(5):
            _create_task(client, auth_header, title=f"Task {i}")
        resp = client.get("/api/tasks?page=2&per_page=3", headers=auth_header)
        data = resp.get_json()
        assert data["pagination"]["has_prev"]
        assert not data["pagination"]["has_next"]
        assert len(data["tasks"]) == 2

    def test_per_page_capped_at_100(self, client, auth_header):
        resp = client.get("/api/tasks?per_page=200", headers=auth_header)
        assert resp.get_json()["pagination"]["per_page"] == 100


class TestGetTask:
    def test_get_own_task(self, client, auth_header):
        resp = _create_task(client, auth_header, title="My task")
        task_id = resp.get_json()["task"]["id"]
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "My task"

    def test_get_assigned_task(self, client, auth_header, auth_header2):
        headers2 = auth_header2[0]
        user2 = auth_header2[1]
        resp = _create_task(client, auth_header, title="Shared task", assignee_ids=[user2["id"]])
        task_id = resp.get_json()["task"]["id"]
        resp = client.get(f"/api/tasks/{task_id}", headers=headers2)
        assert resp.status_code == 200

    def test_get_nonexistent_task(self, client, auth_header):
        resp = client.get("/api/tasks/99999", headers=auth_header)
        assert resp.status_code == 404

    def test_get_task_no_auth(self, client):
        resp = client.get("/api/tasks/1")
        assert resp.status_code == 401


class TestUpdateTask:
    def test_update_task_success(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Old title")
        task_id = resp.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"title": "New title", "status": "completed", "priority": "high"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["task"]["title"] == "New title"
        assert data["task"]["status"] == "completed"
        assert data["task"]["priority"] == "high"

    def test_update_task_clear_due_date(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Due", due_date="2026-12-25T00:00:00")
        task_id = resp.get_json()["task"]["id"]
        resp = client.put(f"/api/tasks/{task_id}", json={"due_date": None}, headers=auth_header)
        assert resp.get_json()["task"]["due_date"] is None

    def test_update_task_assignees(self, client, auth_header, auth_header2):
        user2 = auth_header2[1]
        resp = _create_task(client, auth_header, title="Assignee update")
        task_id = resp.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"assignee_ids": [user2["id"]]},
            headers=auth_header,
        )
        assert resp.get_json()["task"]["assignee_ids"] == [user2["id"]]

    def test_update_task_clear_assignees(self, client, auth_header, auth_header2):
        user2 = auth_header2[1]
        resp = _create_task(client, auth_header, title="Clear assignees", assignee_ids=[user2["id"]])
        task_id = resp.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"assignee_ids": []},
            headers=auth_header,
        )
        assert resp.get_json()["task"]["assignee_ids"] == []

    def test_update_task_invalid_assignee(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Bad assignee update")
        task_id = resp.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"assignee_ids": [99999]},
            headers=auth_header,
        )
        assert resp.status_code == 400

    def test_update_task_not_owner(self, client, auth_header, auth_header2):
        headers2 = auth_header2[0]
        user2 = auth_header2[1]
        resp = _create_task(client, auth_header, title="Owner task", assignee_ids=[user2["id"]])
        task_id = resp.get_json()["task"]["id"]
        resp = client.put(f"/api/tasks/{task_id}", json={"title": "Hijacked"}, headers=headers2)
        assert resp.status_code == 403

    def test_update_task_nonexistent(self, client, auth_header):
        resp = client.put("/api/tasks/99999", json={"title": "Nope"}, headers=auth_header)
        assert resp.status_code == 404


class TestDeleteTask:
    def test_delete_task_success(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Delete me")
        task_id = resp.get_json()["task"]["id"]
        resp = client.delete(f"/api/tasks/{task_id}", headers=auth_header)
        assert resp.status_code == 200
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_header)
        assert resp.status_code == 404

    def test_delete_task_not_owner(self, client, auth_header, auth_header2):
        headers2 = auth_header2[0]
        user2 = auth_header2[1]
        resp = _create_task(client, auth_header, title="Owner task", assignee_ids=[user2["id"]])
        task_id = resp.get_json()["task"]["id"]
        resp = client.delete(f"/api/tasks/{task_id}", headers=headers2)
        assert resp.status_code == 403

    def test_delete_task_nonexistent(self, client, auth_header):
        resp = client.delete("/api/tasks/99999", headers=auth_header)
        assert resp.status_code == 404


class TestEdgeCases:
    def test_task_defaults(self, client, auth_header):
        resp = client.post("/api/tasks", json={"title": "Minimal"}, headers=auth_header)
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["status"] == "pending"
        assert task["priority"] == "medium"
        assert task["category"] == "general"
        assert task["description"] == ""

    def test_category_strip_and_lower(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Cat test", category="  BuG  ")
        assert resp.get_json()["task"]["category"] == "bug"

    def test_empty_update_body(self, client, auth_header):
        resp = _create_task(client, auth_header, title="Unchanged")
        task_id = resp.get_json()["task"]["id"]
        resp = client.put(f"/api/tasks/{task_id}", json={"title": "Unchanged"}, headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Unchanged"
