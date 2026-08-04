"""Tests for task endpoints."""

import json
from datetime import datetime, timedelta, timezone

from ..models import db, Task, User, Category


def _register_user(client, username="taskuser", email="task@example.com"):
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({
            "username": username,
            "email": email,
            "password": "password",
        }),
        content_type="application/json",
    )
    data = resp.get_json()
    return data["access_token"], data["user"]["id"]


def _create_task(client, token, title="Test Task", **overrides):
    payload = {
        "title": title,
        "description": "A test task",
        "status": "todo",
        "priority": "medium",
    }
    payload.update(overrides)
    return client.post(
        "/api/tasks",
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )


class TestCreateTask:
    def test_create_basic(self, client, db):
        token, user_id = _register_user(client)

        resp = _create_task(client, token, "My Task")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["title"] == "My Task"
        assert data["task"]["status"] == "todo"
        assert data["task"]["priority"] == "medium"
        assert data["task"]["owner_id"] == user_id
        assert data["task"]["category"] is None
        assert data["task"]["due_date"] is None
        assert data["task"]["assignees"] == []

    def test_create_with_all_fields(self, client, db):
        token, user_id = _register_user(client)

        cat = Category(name="Feature")
        db.session.add(cat)
        db.session.commit()

        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        resp = _create_task(client, token,
            title="Full Task",
            description="Detailed description",
            status="in_progress",
            priority="high",
            due_date=future,
            category_id=cat.id,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Full Task"
        assert task["description"] == "Detailed description"
        assert task["status"] == "in_progress"
        assert task["priority"] == "high"
        assert task["category_id"] == cat.id
        assert task["due_date"] is not None
        assert task["created_at"] is not None
        assert task["updated_at"] is not None

    def test_create_with_assignees(self, client, db):
        token, user_id = _register_user(client)

        user2 = User(username="user2", email="user2@example.com")
        user2.set_password("pass")
        user3 = User(username="user3", email="user3@example.com")
        user3.set_password("pass")
        db.session.add_all([user2, user3])
        db.session.commit()

        resp = _create_task(client, token,
            title="Team Task",
            assignee_ids=[user2.id, user3.id],
        )
        assert resp.status_code == 201
        assignees = resp.get_json()["task"]["assignees"]
        assert len(assignees) == 2
        assert {a["id"] for a in assignees} == {user2.id, user3.id}

    def test_create_missing_title(self, client):
        token, _ = _register_user(client)
        resp = client.post(
            "/api/tasks",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_create_invalid_status(self, client):
        token, _ = _register_user(client)
        resp = _create_task(client, token, title="Bad Status", status="invalid_status")
        assert resp.status_code == 400

    def test_create_invalid_priority(self, client):
        token, _ = _register_user(client)
        resp = _create_task(client, token, title="Bad Priority", priority="extreme")
        assert resp.status_code == 400

    def test_create_invalid_due_date(self, client):
        token, _ = _register_user(client)
        resp = _create_task(client, token, title="Bad Date", due_date="not-a-date")
        assert resp.status_code == 400

    def test_create_invalid_category(self, client):
        token, _ = _register_user(client)
        resp = _create_task(client, token, title="Bad Cat", category_id=999)
        assert resp.status_code == 400

    def test_create_invalid_assignee(self, client):
        token, _ = _register_user(client)
        resp = _create_task(client, token, title="Bad Assignee", assignee_ids=[999])
        assert resp.status_code == 400

    def test_create_unauthenticated(self, client):
        resp = client.post(
            "/api/tasks",
            data=json.dumps({"title": "Task"}),
            content_type="application/json",
        )
        assert resp.status_code == 401


class TestGetTask:
    def test_get_existing(self, client):
        token, _ = _register_user(client)
        create_resp = _create_task(client, token, "Readable Task")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Readable Task"

    def test_get_nonexistent(self, client):
        resp = client.get("/api/tasks/999")
        assert resp.status_code == 404


class TestListTasks:
    def test_list_empty(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["tasks"] == []
        assert data["total"] == 0

    def test_list_with_data(self, client):
        token, _ = _register_user(client)
        for i in range(5):
            _create_task(client, token, f"Task {i}")

        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 5
        assert len(data["tasks"]) == 5

    def test_pagination(self, client):
        token, _ = _register_user(client)
        for i in range(30):
            _create_task(client, token, f"Task {i}")

        resp = client.get("/api/tasks?per_page=10&page=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tasks"]) == 10
        assert data["pages"] == 3
        assert data["total"] == 30

        resp = client.get("/api/tasks?per_page=10&page=3")
        assert len(resp.get_json()["tasks"]) == 10

    def test_per_page_limit(self, client):
        token, _ = _register_user(client)
        for i in range(50):
            _create_task(client, token, f"Task {i}")

        resp = client.get("/api/tasks?per_page=200")
        assert resp.status_code == 200
        assert len(resp.get_json()["tasks"]) == 50


class TestFilterTasks:
    def setup_method(self):
        pass

    def test_filter_by_status(self, client, db):
        token, _ = _register_user(client)

        _create_task(client, token, "Todo Task", status="todo")
        _create_task(client, token, "In Progress", status="in_progress")
        _create_task(client, token, "Done Task", status="done")

        resp = client.get("/api/tasks?status=todo")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tasks"][0]["title"] == "Todo Task"

    def test_filter_by_multiple_statuses(self, client, db):
        token, _ = _register_user(client)

        _create_task(client, token, "T1", status="todo")
        _create_task(client, token, "T2", status="in_progress")
        _create_task(client, token, "T3", status="done")

        resp = client.get("/api/tasks?status=todo,done")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 2

    def test_filter_by_priority(self, client):
        token, _ = _register_user(client)
        _create_task(client, token, "Low", priority="low")
        _create_task(client, token, "Medium", priority="medium")
        _create_task(client, token, "High", priority="high")
        _create_task(client, token, "Urgent", priority="urgent")

        resp = client.get("/api/tasks?priority=high,urgent")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 2

    def test_filter_by_category(self, client, db):
        token, _ = _register_user(client)
        cat1 = Category(name="Bug")
        cat2 = Category(name="Feature")
        db.session.add_all([cat1, cat2])
        db.session.commit()

        _create_task(client, token, "Bug Fix", category_id=cat1.id)
        _create_task(client, token, "New Feature", category_id=cat2.id)
        _create_task(client, token, "Other", category_id=None)

        resp = client.get(f"/api/tasks?category_id={cat1.id}")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 1
        assert resp.get_json()["tasks"][0]["title"] == "Bug Fix"

    def test_filter_by_owner(self, client, db):
        token1, user1_id = _register_user(client, "user_a", "a@b.com")
        token2, user2_id = _register_user(client, "user_b", "c@d.com")

        _create_task(client, token1, "User A Task")
        _create_task(client, token2, "User B Task")

        resp = client.get(f"/api/tasks?owner_id={user1_id}")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 1
        assert resp.get_json()["tasks"][0]["title"] == "User A Task"

    def test_filter_by_assignee(self, client, db):
        token1, user1_id = _register_user(client, "owner", "owner@b.com")

        user2 = User(username="assignee1", email="assignee1@b.com")
        user2.set_password("pass")
        user3 = User(username="assignee2", email="assignee2@b.com")
        user3.set_password("pass")
        db.session.add_all([user2, user3])
        db.session.commit()

        resp = _create_task(client, token1, title="Assigned Task", assignee_ids=[user2.id])
        assert resp.status_code == 201

        _create_task(client, token1, title="Unassigned Task")

        resp = client.get(f"/api/tasks?assignee_id={user2.id}")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 1
        assert resp.get_json()["tasks"][0]["title"] == "Assigned Task"

    def test_filter_by_due_date_range(self, client):
        token, _ = _register_user(client)

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        today = datetime.now(timezone.utc).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        _create_task(client, token, "Past Task", due_date=past)
        _create_task(client, token, "Future Task", due_date=future)

        resp = client.get(f"/api/tasks?due_after={today}")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 1
        assert resp.get_json()["tasks"][0]["title"] == "Future Task"

        resp = client.get(f"/api/tasks?due_before={today}")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 1
        assert resp.get_json()["tasks"][0]["title"] == "Past Task"

    def test_search(self, client):
        token, _ = _register_user(client)

        _create_task(client, token, "Fix the login bug", description="Critical authentication issue")
        _create_task(client, token, "Update documentation")
        _create_task(client, token, "Refactor auth module")

        resp = client.get("/api/tasks?search=bug")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 1

        resp = client.get("/api/tasks?search=auth")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 2

    def test_sorting(self, client):
        token, _ = _register_user(client)
        _create_task(client, token, "B Task")
        _create_task(client, token, "A Task")

        resp = client.get("/api/tasks?sort_by=title&sort_order=asc")
        assert resp.status_code == 200
        tasks = resp.get_json()["tasks"]
        assert tasks[0]["title"] == "A Task"
        assert tasks[1]["title"] == "B Task"

        resp = client.get("/api/tasks?sort_by=title&sort_order=desc")
        tasks = resp.get_json()["tasks"]
        assert tasks[0]["title"] == "B Task"
        assert tasks[1]["title"] == "A Task"


class TestUpdateTask:
    def test_update_success(self, client):
        token, _ = _register_user(client)
        create_resp = _create_task(client, token, "Original Title")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.put(
            f"/api/tasks/{task_id}",
            data=json.dumps({"title": "Updated Title", "status": "done"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        task = resp.get_json()["task"]
        assert task["title"] == "Updated Title"
        assert task["status"] == "done"

    def test_update_nonexistent(self, client):
        token, _ = _register_user(client)
        resp = client.put(
            "/api/tasks/999",
            data=json.dumps({"title": "X"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_update_not_owner(self, client, db):
        token1, _ = _register_user(client, "owner", "owner@b.com")
        token2, _ = _register_user(client, "other", "other@b.com")

        create_resp = _create_task(client, token1, "Owned Task")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.put(
            f"/api/tasks/{task_id}",
            data=json.dumps({"title": "Hijacked"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 403

    def test_update_clear_due_date(self, client):
        token, _ = _register_user(client)
        future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        create_resp = _create_task(client, token, "Dated Task", due_date=future)
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.put(
            f"/api/tasks/{task_id}",
            data=json.dumps({"due_date": None}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["due_date"] is None

    def test_update_assignees(self, client, db):
        token, owner_id = _register_user(client)
        user2 = User(username="u2", email="u2@b.com")
        user2.set_password("pass")
        db.session.add(user2)
        db.session.commit()

        create_resp = _create_task(client, token, "Task")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.put(
            f"/api/tasks/{task_id}",
            data=json.dumps({"assignee_ids": [user2.id]}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.get_json()["task"]["assignees"]) == 1

    def test_update_invalid_status(self, client):
        token, _ = _register_user(client)
        create_resp = _create_task(client, token, "Task")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.put(
            f"/api/tasks/{task_id}",
            data=json.dumps({"status": "fakestatus"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


class TestDeleteTask:
    def test_delete_success(self, client):
        token, _ = _register_user(client)
        create_resp = _create_task(client, token, "To Delete")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.delete(
            f"/api/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        get_resp = client.get(f"/api/tasks/{task_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent(self, client):
        token, _ = _register_user(client)
        resp = client.delete(
            "/api/tasks/999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_delete_not_owner(self, client):
        token1, _ = _register_user(client, "owner", "o@b.com")
        token2, _ = _register_user(client, "other", "x@b.com")

        create_resp = _create_task(client, token1, "Owner Task")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.delete(
            f"/api/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 403


class TestAssignAndUnassign:
    def test_assign_users(self, client, db):
        token, _ = _register_user(client)
        user2 = User(username="assignee", email="assignee@b.com")
        user2.set_password("pass")
        db.session.add(user2)
        db.session.commit()

        create_resp = _create_task(client, token, "Task")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.post(
            f"/api/tasks/{task_id}/assign",
            data=json.dumps({"user_ids": [user2.id]}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.get_json()["task"]["assignees"]) == 1

    def test_unassign_users(self, client, db):
        token, _ = _register_user(client)
        user2 = User(username="assignee", email="assignee@b.com")
        user2.set_password("pass")
        db.session.add(user2)
        db.session.commit()

        create_resp = _create_task(client, token, "Task", assignee_ids=[user2.id])
        task_id = create_resp.get_json()["task"]["id"]
        assert len(create_resp.get_json()["task"]["assignees"]) == 1

        resp = client.post(
            f"/api/tasks/{task_id}/unassign",
            data=json.dumps({"user_ids": [user2.id]}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.get_json()["task"]["assignees"]) == 0

    def test_assign_not_owner(self, client, db):
        token1, _ = _register_user(client, "owner", "owner@c.com")
        token2, _ = _register_user(client, "other", "other@c.com")

        user3 = User(username="u3", email="u3@c.com")
        user3.set_password("pass")
        db.session.add(user3)
        db.session.commit()

        create_resp = _create_task(client, token1, "Task")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.post(
            f"/api/tasks/{task_id}/assign",
            data=json.dumps({"user_ids": [user3.id]}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert resp.status_code == 403

    def test_assign_nonexistent_task(self, client):
        token, _ = _register_user(client)
        resp = client.post(
            "/api/tasks/999/assign",
            data=json.dumps({"user_ids": [1]}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_assign_nonexistent_user(self, client):
        token, _ = _register_user(client)
        create_resp = _create_task(client, token, "Task")
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.post(
            f"/api/tasks/{task_id}/assign",
            data=json.dumps({"user_ids": [9999]}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
