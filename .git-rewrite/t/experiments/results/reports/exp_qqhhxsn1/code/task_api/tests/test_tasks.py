import pytest

from tests.conftest import _register_user, _auth_headers


def _create_task(client, headers, **overrides):
    payload = {
        "title": "Default Task",
        "description": "Default description",
        "status": "pending",
        "priority": "medium",
        "category": "general",
    }
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


class TestCreateTask:
    def test_create_task_basic(self, client, auth_headers):
        resp = _create_task(client, auth_headers, title="My Task")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["title"] == "My Task"
        assert data["task"]["status"] == "pending"
        assert data["task"]["priority"] == "medium"

    def test_create_task_with_all_fields(self, client, auth_headers):
        resp = _create_task(
            client,
            auth_headers,
            title="Full Task",
            description="A detailed task",
            status="in_progress",
            priority="high",
            category="bug",
            due_date="2027-12-31T12:00:00",
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Full Task"
        assert task["status"] == "in_progress"
        assert task["priority"] == "high"
        assert task["category"] == "bug"
        assert task["due_date"] is not None

    def test_create_task_missing_title(self, client, auth_headers):
        resp = client.post("/api/tasks", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_create_task_invalid_status(self, client, auth_headers):
        resp = _create_task(client, auth_headers, title="X", status="bogus")
        assert resp.status_code == 400

    def test_create_task_invalid_priority(self, client, auth_headers):
        resp = _create_task(client, auth_headers, title="X", priority="extreme")
        assert resp.status_code == 400

    def test_create_task_invalid_due_date(self, client, auth_headers):
        resp = _create_task(client, auth_headers, title="X", due_date="not-a-date")
        assert resp.status_code == 400

    def test_create_task_with_assignee(self, client, auth_headers):
        reg = _register_user(client, username="assignee1", email="assignee1@x.com", password="pass1234")
        assignee_id = reg.get_json()["user"]["id"]
        resp = _create_task(client, auth_headers, title="Assigned", assignee_id=assignee_id)
        assert resp.status_code == 201
        assert resp.get_json()["task"]["assignee_id"] == assignee_id

    def test_create_task_nonexistent_assignee(self, client, auth_headers):
        resp = _create_task(client, auth_headers, title="Bad", assignee_id=9999)
        assert resp.status_code == 404

    def test_create_task_unauthenticated(self, client):
        resp = client.post("/api/tasks", json={"title": "No Auth"})
        assert resp.status_code == 401


class TestGetTask:
    def test_get_task_by_id(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="Find Me")
        task_id = c.get_json()["task"]["id"]
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Find Me"

    def test_get_task_not_found(self, client, auth_headers):
        resp = client.get("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_task_unauthenticated(self, client):
        resp = client.get("/api/tasks/1")
        assert resp.status_code == 401


class TestListTasks:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["total"] == 0

    def test_list_with_tasks(self, client, auth_headers):
        for i in range(5):
            _create_task(client, auth_headers, title=f"Task {i}")
        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["total"] == 5
        assert len(resp.get_json()["tasks"]) == 5

    def test_pagination(self, client, auth_headers):
        for i in range(25):
            _create_task(client, auth_headers, title=f"Task {i}")
        resp = client.get("/api/tasks?per_page=10&page=2", headers=auth_headers)
        assert resp.status_code == 200
        pag = resp.get_json()["pagination"]
        assert pag["page"] == 2
        assert pag["per_page"] == 10
        assert pag["total"] == 25
        assert pag["pages"] == 3
        assert pag["has_next"] is True
        assert pag["has_prev"] is True

    def test_pagination_has_next_false(self, client, auth_headers):
        for i in range(5):
            _create_task(client, auth_headers, title=f"Task {i}")
        resp = client.get("/api/tasks?per_page=10&page=1", headers=auth_headers)
        assert resp.get_json()["pagination"]["has_next"] is False

    def test_pagination_clamp_page(self, client, auth_headers):
        _create_task(client, auth_headers, title="T")
        resp = client.get("/api/tasks?page=-1", headers=auth_headers)
        assert resp.get_json()["pagination"]["page"] == 1

    def test_pagination_clamp_per_page_max(self, client, auth_headers):
        resp = client.get("/api/tasks?per_page=9999", headers=auth_headers)
        assert resp.get_json()["pagination"]["per_page"] == 100

    def test_filter_by_status(self, client, auth_headers):
        _create_task(client, auth_headers, title="Pending", status="pending")
        _create_task(client, auth_headers, title="Done", status="completed")
        resp = client.get("/api/tasks?status=completed", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["total"] == 1
        assert data["tasks"][0]["title"] == "Done"

    def test_filter_by_multiple_statuses(self, client, auth_headers):
        _create_task(client, auth_headers, title="P", status="pending")
        _create_task(client, auth_headers, title="I", status="in_progress")
        _create_task(client, auth_headers, title="C", status="completed")
        resp = client.get("/api/tasks?status=pending,in_progress", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 2

    def test_filter_by_priority(self, client, auth_headers):
        _create_task(client, auth_headers, title="Low", priority="low")
        _create_task(client, auth_headers, title="Urgent", priority="urgent")
        resp = client.get("/api/tasks?priority=urgent", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_filter_by_category(self, client, auth_headers):
        _create_task(client, auth_headers, title="Bug", category="bug")
        _create_task(client, auth_headers, title="Feature", category="feature")
        resp = client.get("/api/tasks?category=bug,feature", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 2

    def test_filter_by_owner(self, client, auth_headers, auth_user_id):
        _create_task(client, auth_headers, title="Mine")
        resp = client.get(f"/api/tasks?owner_id={auth_user_id}", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_filter_by_assignee(self, client, auth_headers):
        reg = _register_user(client, username="worker", email="worker@x.com", password="pass1234")
        aid = reg.get_json()["user"]["id"]
        _create_task(client, auth_headers, title="Assigned", assignee_id=aid)
        _create_task(client, auth_headers, title="Unassigned")
        resp = client.get(f"/api/tasks?assignee_id={aid}", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_search_title(self, client, auth_headers):
        _create_task(client, auth_headers, title="Fix login bug")
        _create_task(client, auth_headers, title="Update docs")
        _create_task(client, auth_headers, title="Refactor auth")
        resp = client.get("/api/tasks?search=login", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_search_description(self, client, auth_headers):
        _create_task(client, auth_headers, title="Task A", description="database migration")
        _create_task(client, auth_headers, title="Task B", description="UI tweaks")
        resp = client.get("/api/tasks?search=database", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_search_case_insensitive(self, client, auth_headers):
        _create_task(client, auth_headers, title="IMPORTANT BUG")
        resp = client.get("/api/tasks?search=important", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_due_before_filter(self, client, auth_headers):
        _create_task(client, auth_headers, title="Old", due_date="2020-01-01T00:00:00")
        _create_task(client, auth_headers, title="Future", due_date="2099-12-31T00:00:00")
        resp = client.get("/api/tasks?due_before=2025-01-01T00:00:00", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1
        assert resp.get_json()["tasks"][0]["title"] == "Old"

    def test_due_after_filter(self, client, auth_headers):
        _create_task(client, auth_headers, title="Old", due_date="2020-01-01T00:00:00")
        _create_task(client, auth_headers, title="Future", due_date="2099-12-31T00:00:00")
        resp = client.get("/api/tasks?due_after=2050-01-01T00:00:00", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1
        assert resp.get_json()["tasks"][0]["title"] == "Future"

    def test_due_before_invalid(self, client, auth_headers):
        resp = client.get("/api/tasks?due_before=notadate", headers=auth_headers)
        assert resp.status_code == 400

    def test_sort_by(self, client, auth_headers):
        _create_task(client, auth_headers, title="B", priority="low")
        _create_task(client, auth_headers, title="A", priority="high")
        resp = client.get("/api/tasks?sort_by=title&sort_order=asc", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert tasks[0]["title"] == "A"
        assert tasks[1]["title"] == "B"


class TestUpdateTask:
    def test_update_title(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="Old")
        task_id = c.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"title": "Updated Title"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Updated Title"

    def test_update_status_valid_transition(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="pending")
        task_id = c.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"status": "in_progress"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["status"] == "in_progress"

    def test_update_status_invalid_transition(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="completed")
        task_id = c.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"status": "pending"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_update_all_fields(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="Original")
        task_id = c.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={
                "title": "Revamped",
                "description": "new desc",
                "status": "in_progress",
                "priority": "urgent",
                "category": "security",
                "due_date": "2030-06-15T09:00:00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        task = resp.get_json()["task"]
        assert task["title"] == "Revamped"
        assert task["description"] == "new desc"
        assert task["status"] == "in_progress"
        assert task["priority"] == "urgent"
        assert task["category"] == "security"
        assert task["due_date"] is not None

    def test_update_assignee(self, client, auth_headers):
        reg = _register_user(client, username="dev1", email="dev1@x.com", password="pass1234")
        c = _create_task(client, auth_headers, title="Assign Me")
        task_id = c.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"assignee_id": reg.get_json()["user"]["id"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["assignee_id"] == reg.get_json()["user"]["id"]

    def test_update_remove_assignee(self, client, auth_headers):
        reg = _register_user(client, username="dev2", email="dev2@x.com", password="pass1234")
        c = _create_task(client, auth_headers, title="T", assignee_id=reg.get_json()["user"]["id"])
        task_id = c.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"assignee_id": None},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["assignee_id"] is None

    def test_update_clear_due_date(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", due_date="2030-01-01T00:00:00")
        task_id = c.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"due_date": None},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["due_date"] is None

    def test_update_not_found(self, client, auth_headers):
        resp = client.put("/api/tasks/99999", json={"title": "Nope"}, headers=auth_headers)
        assert resp.status_code == 404


class TestPatchStatus:
    def test_patch_status_valid(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="pending")
        task_id = c.get_json()["task"]["id"]
        resp = client.patch(
            f"/api/tasks/{task_id}/status",
            json={"status": "in_progress"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["status"] == "in_progress"

    def test_patch_status_invalid(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="archived")
        task_id = c.get_json()["task"]["id"]
        resp = client.patch(
            f"/api/tasks/{task_id}/status",
            json={"status": "completed"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_patch_status_not_found(self, client, auth_headers):
        resp = client.patch(
            "/api/tasks/99999/status",
            json={"status": "pending"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestDeleteTask:
    def test_delete_task(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="To Delete")
        task_id = c.get_json()["task"]["id"]
        resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "task deleted"

    def test_delete_then_get_404(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="Gone")
        task_id = c.get_json()["task"]["id"]
        client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_not_found(self, client, auth_headers):
        resp = client.delete("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestStatusTransitions:
    def test_pending_to_in_progress(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="pending")
        tid = c.get_json()["task"]["id"]
        r = client.patch(f"/api/tasks/{tid}/status", json={"status": "in_progress"}, headers=auth_headers)
        assert r.status_code == 200

    def test_pending_to_archived(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="pending")
        tid = c.get_json()["task"]["id"]
        r = client.patch(f"/api/tasks/{tid}/status", json={"status": "archived"}, headers=auth_headers)
        assert r.status_code == 200

    def test_pending_to_completed_not_allowed(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="pending")
        tid = c.get_json()["task"]["id"]
        r = client.patch(f"/api/tasks/{tid}/status", json={"status": "completed"}, headers=auth_headers)
        assert r.status_code == 422

    def test_in_progress_to_completed(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="in_progress")
        tid = c.get_json()["task"]["id"]
        r = client.patch(f"/api/tasks/{tid}/status", json={"status": "completed"}, headers=auth_headers)
        assert r.status_code == 200

    def test_completed_to_archived(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="completed")
        tid = c.get_json()["task"]["id"]
        r = client.patch(f"/api/tasks/{tid}/status", json={"status": "archived"}, headers=auth_headers)
        assert r.status_code == 200

    def test_archived_to_pending(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", status="archived")
        tid = c.get_json()["task"]["id"]
        r = client.patch(f"/api/tasks/{tid}/status", json={"status": "pending"}, headers=auth_headers)
        assert r.status_code == 200


class TestCategoryNormalization:
    def test_category_lowercased(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", category="URGENT")
        assert c.get_json()["task"]["category"] == "urgent"

    def test_category_empty_defaults(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="T", category="")
        assert c.get_json()["task"]["category"] == "general"


class TestTaskOwnership:
    def test_task_owner_set(self, client, auth_headers, auth_user_id):
        c = _create_task(client, auth_headers, title="Mine")
        assert c.get_json()["task"]["owner_id"] == auth_user_id

    def test_task_owner_in_response(self, client, auth_headers):
        c = _create_task(client, auth_headers, title="With Owner")
        owner = c.get_json()["task"]["owner"]
        assert owner is not None
        assert owner["username"] == "testuser"
