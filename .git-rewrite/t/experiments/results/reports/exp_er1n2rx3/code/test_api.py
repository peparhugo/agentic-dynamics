import json

import pytest

from app import create_app
from config import TestConfig
from models import db as _db, User, Task, TaskStatus, TaskPriority


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def auth_headers(client):
    client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "secret123"},
    )
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user_headers(client):
    client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "secret456"},
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "secret456"},
    )
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_tasks(client, auth_headers):
    tasks_data = [
        {"title": "Fix login bug", "status": "in_progress", "priority": "high", "category": "backend"},
        {"title": "Write docs", "status": "todo", "priority": "low", "category": "docs"},
        {"title": "Deploy to prod", "status": "done", "priority": "critical", "category": "devops"},
        {"title": "Design homepage", "status": "todo", "priority": "medium", "category": "frontend"},
        {"title": "Code review PR #42", "status": "todo", "priority": "medium", "category": "backend"},
        {"title": "Setup CI pipeline", "status": "done", "priority": "high", "category": "devops"},
        {"title": "Update dependencies", "status": "in_progress", "priority": "medium", "category": "backend"},
        {"title": "Write unit tests", "status": "todo", "priority": "high", "category": "backend"},
        {"title": "Refresh tokens", "status": "todo", "priority": "critical", "category": "security"},
        {"title": "Backup database", "status": "done", "priority": "low", "category": "devops"},
        {"title": "Research GraphQL", "status": "todo", "priority": "low", "category": "research"},
        {"title": "Fix SQL injection", "status": "in_progress", "priority": "critical", "category": "security"},
        {"title": "Add dark mode", "status": "todo", "priority": "low", "category": "frontend"},
        {"title": "Refactor auth module", "status": "todo", "priority": "medium", "category": "backend"},
        {"title": "Monitor server load", "status": "done", "priority": "medium", "category": "devops"},
        {"title": "Audit dependencies", "status": "todo", "priority": "high", "category": "security"},
        {"title": "DB migration script", "status": "in_progress", "priority": "high", "category": "backend"},
        {"title": "Session timeout", "status": "todo", "priority": "low", "category": "security"},
        {"title": "Rate limiting", "status": "todo", "priority": "medium", "category": "backend"},
        {"title": "Health check endpoint", "status": "done", "priority": "low", "category": "devops"},
        {"title": "User profile page", "status": "todo", "priority": "low", "category": "frontend"},
        {"title": "API versioning", "status": "in_progress", "priority": "high", "category": "backend"},
        {"title": "Cache layer", "status": "todo", "priority": "medium", "category": "backend"},
        {"title": "Error tracking", "status": "todo", "priority": "high", "category": "devops"},
        {"title": "Log aggregation", "status": "done", "priority": "low", "category": "devops"},
    ]
    created = []
    for td in tasks_data:
        resp = client.post("/api/tasks", json=td, headers=auth_headers)
        created.append(resp.get_json()["task"])
    return created


class TestAuth:
    def test_register_success(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "jane", "email": "jane@example.com", "password": "password123"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["username"] == "jane"
        assert data["user"]["email"] == "jane@example.com"
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

    def test_register_duplicate_username(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "jane", "email": "jane@a.com", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/register",
            json={"username": "jane", "email": "jane@b.com", "password": "password123"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "username" in data["errors"]

    def test_register_duplicate_email(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "a", "email": "dup@example.com", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/register",
            json={"username": "b", "email": "dup@example.com", "password": "password123"},
        )
        assert resp.status_code == 400
        assert "email" in resp.get_json()["errors"]

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 400
        errors = resp.get_json()["errors"]
        assert "username" in errors
        assert "email" in errors
        assert "password" in errors

    def test_register_empty_body(self, client):
        resp = client.post("/api/auth/register", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "u", "email": "u@e.com", "password": "12345"},
        )
        assert resp.status_code == 400
        assert "password" in resp.get_json()["errors"]

    def test_login_success(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "jane", "email": "jane@example.com", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["username"] == "jane"

    def test_login_wrong_password(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "jane", "email": "jane@example.com", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

    def test_register_whitespace_trimming(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "  trimmed  ", "email": "trim@example.com", "password": "password123"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["user"]["username"] == "trimmed"


class TestTaskCRUD:
    def test_create_task(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "My Task", "description": "Do something"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "My Task"
        assert task["status"] == "todo"
        assert task["priority"] == "medium"
        assert task["category"] == "general"

    def test_create_task_with_all_fields(self, client, second_user_headers, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Full task",
                "description": "Desc",
                "status": "in_progress",
                "priority": "critical",
                "category": "backend",
                "due_date": "2026-12-31T23:59:59+00:00",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Full task"
        assert task["status"] == "in_progress"
        assert task["priority"] == "critical"
        assert task["category"] == "backend"
        assert task["due_date"] is not None

    def test_create_task_no_title(self, client, auth_headers):
        resp = client.post("/api/tasks", json={}, headers=auth_headers)
        assert resp.status_code == 400
        assert "title" in resp.get_json()["errors"]

    def test_create_task_empty_title(self, client, auth_headers):
        resp = client.post(
            "/api/tasks", json={"title": "   "}, headers=auth_headers
        )
        assert resp.status_code == 400

    def test_create_task_invalid_status(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Task", "status": "invalid_status"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "status" in resp.get_json()["errors"]

    def test_create_task_invalid_priority(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Task", "priority": "super_high"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "priority" in resp.get_json()["errors"]

    def test_create_task_nonexistent_assignee(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Task", "assigned_to": 9999},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "assigned_to" in resp.get_json()["errors"]

    def test_create_task_requires_auth(self, client):
        resp = client.post("/api/tasks", json={"title": "Task"})
        assert resp.status_code == 401

    def test_get_task(self, client, auth_headers):
        create_resp = client.post(
            "/api/tasks", json={"title": "Read me"}, headers=auth_headers
        )
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Read me"

    def test_get_task_not_found(self, client, auth_headers):
        resp = client.get("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_task_requires_auth(self, client):
        resp = client.get("/api/tasks/1")
        assert resp.status_code == 401

    def test_update_task_full(self, client, auth_headers):
        create_resp = client.post(
            "/api/tasks", json={"title": "Original"}, headers=auth_headers
        )
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.put(
            f"/api/tasks/{task_id}",
            json={
                "title": "Updated",
                "status": "done",
                "priority": "low",
                "category": "docs",
                "description": "New desc",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        task = resp.get_json()["task"]
        assert task["title"] == "Updated"
        assert task["status"] == "done"
        assert task["priority"] == "low"
        assert task["category"] == "docs"
        assert task["description"] == "New desc"

    def test_update_task_partial(self, client, auth_headers):
        create_resp = client.post(
            "/api/tasks", json={"title": "Original"}, headers=auth_headers
        )
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"title": "Only title"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        task = resp.get_json()["task"]
        assert task["title"] == "Only title"
        assert task["status"] == "todo"

    def test_update_task_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/tasks/99999",
            json={"title": "Nope"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_update_task_empty_title(self, client, auth_headers):
        create_resp = client.post(
            "/api/tasks", json={"title": "Original"}, headers=auth_headers
        )
        task_id = create_resp.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"title": "   "},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_delete_task(self, client, auth_headers):
        create_resp = client.post(
            "/api/tasks", json={"title": "Delete me"}, headers=auth_headers
        )
        task_id = create_resp.get_json()["task"]["id"]

        resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Task deleted."

        resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_task_not_found(self, client, auth_headers):
        resp = client.delete("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_task_requires_auth(self, client):
        resp = client.delete("/api/tasks/1")
        assert resp.status_code == 401

    def test_create_task_with_assignment(self, client, second_user_headers, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Assign to bob", "assigned_to": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.get_json()["task"]["assigned_to"] == 2

    def test_task_created_by_is_set(self, client, auth_headers):
        resp = client.post(
            "/api/tasks", json={"title": "Who made me?"}, headers=auth_headers
        )
        assert resp.get_json()["task"]["created_by"] == 1

    def test_task_has_timestamps(self, client, auth_headers):
        resp = client.post(
            "/api/tasks", json={"title": "Timestamped"}, headers=auth_headers
        )
        task = resp.get_json()["task"]
        assert task["created_at"] is not None
        assert task["updated_at"] is not None

    def test_update_task_changes_updated_at(self, client, auth_headers, db):
        resp = client.post(
            "/api/tasks", json={"title": "Stamp"}, headers=auth_headers
        )
        task_id = resp.get_json()["task"]["id"]

        import time
        time.sleep(0.1)

        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"title": "Stamped"},
            headers=auth_headers,
        )
        updated = resp.get_json()["task"]
        assert updated["updated_at"] != updated["created_at"]

    def test_set_due_date_null(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "With due", "due_date": "2026-06-15T10:00:00+00:00"},
            headers=auth_headers,
        )
        task_id = resp.get_json()["task"]["id"]
        assert resp.get_json()["task"]["due_date"] is not None

        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"due_date": None},
            headers=auth_headers,
        )
        assert resp.get_json()["task"]["due_date"] is None

    def test_create_task_invalid_due_date(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Bad date", "due_date": "not-a-date"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "due_date" in resp.get_json()["errors"]


class TestTaskListing:
    def test_list_tasks_empty(self, client, auth_headers):
        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["tasks"] == []
        assert data["pagination"]["total"] == 0

    def test_list_tasks_with_data(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["total"] == 25
        assert len(data["tasks"]) == 20
        assert data["pagination"]["page"] == 1

    def test_list_tasks_pagination_page_2(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?page=2&per_page=10", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 10
        assert data["pagination"]["has_prev"] is True
        assert data["pagination"]["has_next"] is True
        assert len(data["tasks"]) == 10

    def test_list_tasks_last_page(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?per_page=10&page=3", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["has_next"] is False
        assert len(data["tasks"]) == 5

    def test_list_tasks_page_out_of_range(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?page=999&per_page=10", headers=auth_headers)
        data = resp.get_json()
        assert data["tasks"] == []
        assert data["pagination"]["total"] == 25

    def test_list_tasks_invalid_page(self, client, auth_headers):
        resp = client.get("/api/tasks?page=-1", headers=auth_headers)
        assert resp.status_code == 200

    def test_list_tasks_per_page_min_clamped(self, client, auth_headers):
        resp = client.get("/api/tasks?per_page=0", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["per_page"] == 1

    def test_list_tasks_per_page_max_clamped(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?per_page=200", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["per_page"] == 100

    def test_filter_by_status(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?status=todo", headers=auth_headers)
        data = resp.get_json()
        for task in data["tasks"]:
            assert task["status"] == "todo"
        assert data["pagination"]["total"] > 0

    def test_filter_by_status_done(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?status=done", headers=auth_headers)
        data = resp.get_json()
        assert all(t["status"] == "done" for t in data["tasks"])
        assert data["pagination"]["total"] == 6

    def test_filter_by_priority(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?priority=critical", headers=auth_headers)
        data = resp.get_json()
        assert all(t["priority"] == "critical" for t in data["tasks"])
        assert data["pagination"]["total"] == 3

    def test_filter_by_category(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?category=devops", headers=auth_headers)
        data = resp.get_json()
        assert all(t["category"] == "devops" for t in data["tasks"])
        assert data["pagination"]["total"] == 7

    def test_filter_by_assigned_to(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?assigned_to=1", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["total"] == 0

        client.post(
            "/api/tasks",
            json={"title": "Assigned task", "assigned_to": 1},
            headers=auth_headers,
        )
        resp = client.get("/api/tasks?assigned_to=1", headers=auth_headers)
        assert resp.get_json()["pagination"]["total"] == 1

    def test_search_by_title(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?search=Fix", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["total"] == 2
        titles = [t["title"] for t in data["tasks"]]
        assert all("fix" in t.lower() for t in titles)

    def test_search_by_description(self, client, auth_headers, seed_tasks):
        client.post(
            "/api/tasks",
            json={"title": "Some task", "description": "find this needle"},
            headers=auth_headers,
        )
        resp = client.get("/api/tasks?search=needle", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["total"] >= 1
        assert any("Some task" == t["title"] for t in data["tasks"])

    def test_search_no_results(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?search=zzzzz_nonexistent_zzzzz", headers=auth_headers)
        data = resp.get_json()
        assert data["pagination"]["total"] == 0
        assert data["tasks"] == []

    def test_combined_filters(self, client, auth_headers, seed_tasks):
        resp = client.get(
            "/api/tasks?status=todo&priority=high&category=backend",
            headers=auth_headers,
        )
        data = resp.get_json()
        for t in data["tasks"]:
            assert t["status"] == "todo"
            assert t["priority"] == "high"
            assert t["category"] == "backend"
        assert data["pagination"]["total"] == 1

    def test_sort_by_priority_asc(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?sort_by=priority&sort_order=asc", headers=auth_headers)
        data = resp.get_json()
        priorities = [t["priority"] for t in data["tasks"]]
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_indices = [priority_order[p] for p in priorities]
        for i in range(len(sorted_indices) - 1):
            assert sorted_indices[i] <= sorted_indices[i + 1]

    def test_sort_by_due_date(self, client, auth_headers):
        client.post(
            "/api/tasks",
            json={"title": "Later", "due_date": "2026-12-31T00:00:00+00:00"},
            headers=auth_headers,
        )
        client.post(
            "/api/tasks",
            json={"title": "Sooner", "due_date": "2026-01-01T00:00:00+00:00"},
            headers=auth_headers,
        )
        resp = client.get("/api/tasks?sort_by=due_date&sort_order=asc", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        due_dates = [t["due_date"] for t in tasks if t["due_date"]]
        assert due_dates == sorted(due_dates)

    def test_sort_by_invalid_column_falls_back(self, client, auth_headers, seed_tasks):
        resp = client.get("/api/tasks?sort_by=nonexistent_col", headers=auth_headers)
        assert resp.status_code == 200

    def test_list_tasks_requires_auth(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 401


class TestEdgeCases:
    def test_task_model_to_dict(self, app, db):
        with app.app_context():
            user = User(username="test", email="test@test.com")
            user.set_password("password")
            db.session.add(user)
            db.session.commit()

            task = Task(
                title="Model test",
                description="Desc",
                status="todo",
                priority="medium",
                category="test",
                created_by=user.id,
            )
            db.session.add(task)
            db.session.commit()

            d = task.to_dict()
            assert d["id"] is not None
            assert d["title"] == "Model test"
            assert d["status"] == "todo"
            assert d["priority"] == "medium"
            assert d["category"] == "test"
            assert d["due_date"] is None
            assert d["created_by"] == user.id
            assert d["assigned_to"] is None
            assert d["created_at"] is not None
            assert d["updated_at"] is not None

            user_dict = user.to_dict()
            assert "password" not in user_dict
            assert "password_hash" not in user_dict
            assert user_dict["username"] == "test"

    def test_user_password_hashing(self, app, db):
        with app.app_context():
            user = User(username="pw", email="pw@test.com")
            user.set_password("mypassword")
            assert user.check_password("mypassword") is True
            assert user.check_password("wrong") is False
            assert user.password_hash != "mypassword"

    def test_user_relationships(self, app, db):
        with app.app_context():
            u1 = User(username="creator", email="c@test.com")
            u1.set_password("pw")
            u2 = User(username="assignee", email="a@test.com")
            u2.set_password("pw")
            db.session.add_all([u1, u2])
            db.session.commit()

            task = Task(
                title="Related",
                created_by=u1.id,
                assigned_to=u2.id,
            )
            db.session.add(task)
            db.session.commit()

            assert task.creator.id == u1.id
            assert task.assignee.id == u2.id
            assert u1.created_tasks.count() == 1
            assert u2.assigned_tasks.count() == 1

    def test_jwt_token_required_no_header(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 401

    def test_jwt_token_required_malformed_header(self, client):
        resp = client.get("/api/tasks", headers={"Authorization": "NotBearer token"})
        assert resp.status_code == 401

    def test_jwt_token_required_invalid_token(self, client):
        resp = client.get(
            "/api/tasks",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 422

    def test_different_users_tasks_visible(self, client, auth_headers, second_user_headers):
        client.post(
            "/api/tasks", json={"title": "Alice task"}, headers=auth_headers
        )
        client.post(
            "/api/tasks", json={"title": "Bob task"}, headers=second_user_headers
        )

        resp_alice = client.get("/api/tasks", headers=auth_headers)
        resp_bob = client.get("/api/tasks", headers=second_user_headers)
        assert resp_alice.get_json()["pagination"]["total"] == 2
        assert resp_bob.get_json()["pagination"]["total"] == 2

    def test_register_empty_json_body(self, client):
        resp = client.post(
            "/api/auth/register",
            data="",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_login_empty_json_body(self, client):
        resp = client.post(
            "/api/auth/login",
            data="",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_delete_then_recreate(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Keep me"}, headers=auth_headers)
        resp = client.post(
            "/api/tasks", json={"title": "Temp"}, headers=auth_headers
        )
        task_id = resp.get_json()["task"]["id"]
        client.delete(f"/api/tasks/{task_id}", headers=auth_headers)

        resp = client.post(
            "/api/tasks", json={"title": "New"}, headers=auth_headers
        )
        assert resp.get_json()["task"]["id"] == task_id + 1

    def test_update_with_none_values(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Has assignee", "assigned_to": 1},
            headers=auth_headers,
        )
        task_id = resp.get_json()["task"]["id"]
        resp = client.put(
            f"/api/tasks/{task_id}",
            json={"assigned_to": None},
            headers=auth_headers,
        )
        assert resp.get_json()["task"]["assigned_to"] is None
