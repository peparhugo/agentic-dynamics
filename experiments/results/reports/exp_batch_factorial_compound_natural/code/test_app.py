import json

import pytest


# ─── Auth tests ───


class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "newuser", "email": "new@example.com", "password": "secret123"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "User registered"
        assert "token" in data
        assert data["user"]["username"] == "newuser"

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "details" in data
        assert "username" in data["details"]
        assert "email" in data["details"]
        assert "password" in data["details"]

    def test_register_short_password(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "u", "email": "e@e.com", "password": "ab"},
        )
        assert resp.status_code == 400

    def test_register_duplicate_username(self, client):
        client.post("/auth/register", json={"username": "dup", "email": "a@a.com", "password": "secret123"})
        resp = client.post("/auth/register", json={"username": "dup", "email": "b@b.com", "password": "secret123"})
        assert resp.status_code == 409

    def test_register_duplicate_email(self, client):
        client.post("/auth/register", json={"username": "x", "email": "dup@a.com", "password": "secret123"})
        resp = client.post("/auth/register", json={"username": "y", "email": "dup@a.com", "password": "secret123"})
        assert resp.status_code == 409


class TestAuthLogin:
    def test_login_success(self, client, user_token, user_headers):
        resp = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "secret123"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == "test@example.com"

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={"username": "u1", "email": "e1@e.com", "password": "secret123"})
        resp = client.post("/auth/login", json={"email": "e1@e.com", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={"email": "no@one.com", "password": "pass"})
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 400

    def test_login_email_case_insensitive(self, client):
        client.post("/auth/register", json={"username": "u2", "email": "Case@Example.com", "password": "secret123"})
        resp = client.post("/auth/login", json={"email": "case@example.com", "password": "secret123"})
        assert resp.status_code == 200


def test_unauthorized_access(client):
    resp = client.get("/projects")
    assert resp.status_code == 401

    resp = client.get("/projects/1")
    assert resp.status_code == 401

    resp = client.post("/projects", json={"name": "test"})
    assert resp.status_code == 401


def test_invalid_token(client):
    resp = client.get("/projects", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


# ─── Project tests ───


class TestProjectCRUD:
    def test_create_project(self, client, user_headers):
        resp = client.post(
            "/projects", headers=user_headers, json={"name": "My Project", "description": "Desc"}
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["project"]["name"] == "My Project"
        assert data["project"]["description"] == "Desc"
        assert data["project"]["created_by"] == 1

    def test_create_project_no_name(self, client, user_headers):
        resp = client.post("/projects", headers=user_headers, json={"description": "No name"})
        assert resp.status_code == 400

    def test_get_project(self, client, user_headers, project_id):
        resp = client.get(f"/projects/{project_id}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Test Project"

    def test_get_nonexistent_project(self, client, user_headers):
        resp = client.get("/projects/99999", headers=user_headers)
        assert resp.status_code == 404

    def test_update_project_admin(self, client, user_headers, project_id):
        resp = client.put(
            f"/projects/{project_id}",
            headers=user_headers,
            json={"name": "Updated Project", "description": "Updated desc"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["project"]["name"] == "Updated Project"

    def test_update_project_non_admin(self, client, user2_headers, project_id):
        resp = client.put(
            f"/projects/{project_id}",
            headers=user2_headers,
            json={"name": "Hijack"},
        )
        assert resp.status_code == 403

    def test_delete_project_admin(self, client, user_headers):
        resp = client.post("/projects", headers=user_headers, json={"name": "ToDelete"})
        pid = resp.get_json()["project"]["id"]
        resp = client.delete(f"/projects/{pid}", headers=user_headers)
        assert resp.status_code == 200
        resp = client.get(f"/projects/{pid}", headers=user_headers)
        assert resp.status_code == 404

    def test_delete_project_non_admin(self, client, user2_headers, project_id):
        resp = client.delete(f"/projects/{project_id}", headers=user2_headers)
        assert resp.status_code == 403


class TestProjectList:
    def test_list_projects(self, client, user_headers, project_id):
        resp = client.get("/projects", headers=user_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert "items" in data
        assert "page" in data
        assert "pages" in data
        assert "per_page" in data

    def test_list_projects_pagination(self, client, user_headers):
        for i in range(5):
            client.post(
                "/projects", headers=user_headers, json={"name": f"Project {i}"}
            )
        resp = client.get("/projects?page=1&per_page=2", headers=user_headers)
        data = resp.get_json()
        assert len(data["items"]) == 2
        assert data["per_page"] == 2
        assert data["pages"] >= 3

    def test_list_projects_invalid_page_defaults(self, client, user_headers):
        resp = client.get("/projects?page=0&per_page=-5", headers=user_headers)
        data = resp.get_json()
        assert data["page"] == 1
        assert data["per_page"] == 1

    def test_search_projects(self, client, user_headers):
        client.post("/projects", headers=user_headers, json={"name": "Alpha Project", "description": "A special project"})
        client.post("/projects", headers=user_headers, json={"name": "Beta Project", "description": "Another thing"})
        resp = client.get("/projects?search=Alpha", headers=user_headers)
        data = resp.get_json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Alpha Project"

    def test_search_projects_no_results(self, client, user_headers):
        resp = client.get("/projects?search=zzznotfound", headers=user_headers)
        data = resp.get_json()
        assert data["total"] == 0

    def test_sort_projects(self, client, user_headers):
        client.post("/projects", headers=user_headers, json={"name": "B Project"})
        client.post("/projects", headers=user_headers, json={"name": "A Project"})
        resp = client.get("/projects?sort=name_asc", headers=user_headers)
        data = resp.get_json()
        assert data["items"][0]["name"] == "A Project"
        assert data["items"][1]["name"] == "B Project"


# ─── Member tests ───


class TestMembers:
    def test_initial_member_is_admin(self, client, user_headers, project_id):
        resp = client.get(f"/projects/{project_id}/members", headers=user_headers)
        data = resp.get_json()
        assert len(data["members"]) == 2  # admin + member added in fixture
        roles = {m["role"] for m in data["members"]}
        assert "admin" in roles

    def test_add_member(self, client, user_headers, project_id, user3_token):
        resp = client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["member"]["role"] == "viewer"
        assert data["member"]["user_id"] == 3

    def test_add_member_duplicate(self, client, user_headers, project_id, user2_headers):
        resp = client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 2, "role": "viewer"},
        )
        assert resp.status_code == 409

    def test_add_member_invalid_role(self, client, user_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "superadmin"},
        )
        assert resp.status_code == 400

    def test_add_member_missing_user_id(self, client, user_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"role": "member"},
        )
        assert resp.status_code == 400

    def test_add_member_nonexistent_user(self, client, user_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 99999, "role": "member"},
        )
        assert resp.status_code == 404

    def test_add_member_non_admin(self, client, user2_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/members",
            headers=user2_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        assert resp.status_code == 403

    def test_update_member_role(self, client, user_headers, project_id):
        members_resp = client.get(f"/projects/{project_id}/members", headers=user_headers)
        member = [m for m in members_resp.get_json()["members"] if m["role"] == "member"][0]

        resp = client.put(
            f"/projects/{project_id}/members/{member['id']}",
            headers=user_headers,
            json={"role": "admin"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["member"]["role"] == "admin"

    def test_update_member_invalid_role(self, client, user_headers, project_id):
        members_resp = client.get(f"/projects/{project_id}/members", headers=user_headers)
        member = [m for m in members_resp.get_json()["members"] if m["role"] == "member"][0]

        resp = client.put(
            f"/projects/{project_id}/members/{member['id']}",
            headers=user_headers,
            json={"role": "nobody"},
        )
        assert resp.status_code == 400

    def test_update_member_not_found(self, client, user_headers, project_id):
        resp = client.put(
            f"/projects/{project_id}/members/99999",
            headers=user_headers,
            json={"role": "admin"},
        )
        assert resp.status_code == 404

    def test_update_member_non_admin(self, client, user2_headers, project_id):
        members_resp = client.get(f"/projects/{project_id}/members", headers=user2_headers)
        member = [m for m in members_resp.get_json()["members"] if m["role"] == "member"][0]

        resp = client.put(
            f"/projects/{project_id}/members/{member['id']}",
            headers=user2_headers,
            json={"role": "admin"},
        )
        assert resp.status_code == 403

    def test_remove_member(self, client, user_headers, project_id, user3_token):
        client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        members_resp = client.get(f"/projects/{project_id}/members", headers=user_headers)
        member = [m for m in members_resp.get_json()["members"] if m["role"] == "viewer"][0]

        resp = client.delete(
            f"/projects/{project_id}/members/{member['id']}", headers=user_headers
        )
        assert resp.status_code == 200

    def test_remove_member_self(self, client, user_headers, project_id):
        members_resp = client.get(f"/projects/{project_id}/members", headers=user_headers)
        me = [m for m in members_resp.get_json()["members"] if m["user_id"] == 1][0]

        resp = client.delete(
            f"/projects/{project_id}/members/{me['id']}", headers=user_headers
        )
        assert resp.status_code == 400

    def test_list_members_project_not_found(self, client, user_headers):
        resp = client.get("/projects/99999/members", headers=user_headers)
        assert resp.status_code == 404


# ─── Task tests ───


class TestTaskCRUD:
    def test_create_task(self, client, user_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "New Task", "description": "Do something", "priority": "low"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task"]["title"] == "New Task"
        assert data["task"]["priority"] == "low"
        assert data["task"]["status"] == "todo"

    def test_create_task_no_title(self, client, user_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"description": "No title"},
        )
        assert resp.status_code == 400

    def test_create_task_invalid_status(self, client, user_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "T", "status": "invalid_status"},
        )
        assert resp.status_code == 400

    def test_create_task_invalid_priority(self, client, user_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "T", "priority": "critical"},
        )
        assert resp.status_code == 400

    def test_create_task_with_assignee(self, client, user_headers, project_id, user2_headers):
        resp = client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Assigned", "assigned_to": 2},
        )
        assert resp.status_code == 201
        assert resp.get_json()["task"]["assigned_to"] == 2

    def test_create_task_nonexistent_assignee(self, client, user_headers, project_id):
        resp = client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Bad assignee", "assigned_to": 99999},
        )
        assert resp.status_code == 404

    def test_create_task_viewer_cannot(self, client, user2_headers, user_headers, project_id):
        client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        resp = client.post(
            f"/projects/{project_id}/tasks",
            headers={"Authorization": f"Bearer {_get_token(client, 3)}"},
            json={"title": "Should fail"},
        )
        assert resp.status_code == 403

    def test_get_task(self, client, user_headers, task_id):
        resp = client.get(f"/tasks/{task_id}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Test Task"

    def test_get_nonexistent_task(self, client, user_headers):
        resp = client.get("/tasks/99999", headers=user_headers)
        assert resp.status_code == 404

    def test_get_task_by_viewer(self, client, user_headers, project_id, task_id):
        client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        resp = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {_get_token(client, 3)}"},
        )
        assert resp.status_code == 200

    def test_update_task(self, client, user_headers, task_id):
        resp = client.put(
            f"/tasks/{task_id}",
            headers=user_headers,
            json={"title": "Updated Task", "status": "in_progress", "priority": "low"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["task"]["title"] == "Updated Task"
        assert data["task"]["status"] == "in_progress"
        assert data["task"]["priority"] == "low"

    def test_update_task_empty_title(self, client, user_headers, task_id):
        resp = client.put(
            f"/tasks/{task_id}",
            headers=user_headers,
            json={"title": ""},
        )
        assert resp.status_code == 400

    def test_update_task_viewer_cannot(self, client, user_headers, project_id, task_id):
        client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        resp = client.put(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {_get_token(client, 3)}"},
            json={"title": "Hijack"},
        )
        assert resp.status_code == 403

    def test_delete_task_admin(self, client, user_headers, task_id):
        resp = client.delete(f"/tasks/{task_id}", headers=user_headers)
        assert resp.status_code == 200
        resp = client.get(f"/tasks/{task_id}", headers=user_headers)
        assert resp.status_code == 404

    def test_delete_task_member_cannot(self, client, user2_headers, task_id):
        resp = client.delete(f"/tasks/{task_id}", headers=user2_headers)
        assert resp.status_code == 403


class TestTaskList:
    def test_list_tasks(self, client, user_headers, project_id):
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Task 1", "status": "todo", "priority": "medium"},
        )
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Task 2", "status": "done", "priority": "high"},
        )
        resp = client.get(f"/projects/{project_id}/tasks", headers=user_headers)
        data = resp.get_json()
        assert data["total"] >= 2

    def test_list_tasks_pagination(self, client, user_headers, project_id):
        for i in range(5):
            client.post(
                f"/projects/{project_id}/tasks",
                headers=user_headers,
                json={"title": f"Task {i}"},
            )
        resp = client.get(f"/projects/{project_id}/tasks?page=1&per_page=2", headers=user_headers)
        data = resp.get_json()
        assert len(data["items"]) == 2
        assert data["per_page"] == 2

    def test_filter_tasks_by_status(self, client, user_headers, project_id):
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Todo task", "status": "todo"},
        )
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Done task", "status": "done"},
        )
        resp = client.get(
            f"/projects/{project_id}/tasks?status=done", headers=user_headers
        )
        data = resp.get_json()
        for item in data["items"]:
            assert item["status"] == "done"

    def test_filter_tasks_by_priority(self, client, user_headers, project_id):
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "High prio", "priority": "high"},
        )
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Low prio", "priority": "low"},
        )
        resp = client.get(
            f"/projects/{project_id}/tasks?priority=low", headers=user_headers
        )
        data = resp.get_json()
        for item in data["items"]:
            assert item["priority"] == "low"

    def test_filter_tasks_by_assignee(self, client, user_headers, project_id):
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Assigned to 2", "assigned_to": 2},
        )
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Unassigned"},
        )
        resp = client.get(
            f"/projects/{project_id}/tasks?assigned_to=2", headers=user_headers
        )
        data = resp.get_json()
        for item in data["items"]:
            assert item["assigned_to"] == 2

    def test_filter_tasks_invalid_assigned_to(self, client, user_headers, project_id):
        resp = client.get(
            f"/projects/{project_id}/tasks?assigned_to=abc", headers=user_headers
        )
        assert resp.status_code == 400

    def test_search_tasks(self, client, user_headers, project_id):
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Fix bug in auth", "description": "Something about login"},
        )
        client.post(
            f"/projects/{project_id}/tasks",
            headers=user_headers,
            json={"title": "Add feature", "description": "New stuff"},
        )
        resp = client.get(
            f"/projects/{project_id}/tasks?search=bug", headers=user_headers
        )
        data = resp.get_json()
        assert data["total"] == 1


# ─── Comment tests ───


class TestCommentCRUD:
    def test_create_comment(self, client, user_headers, task_id):
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "This is a comment"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["comment"]["content"] == "This is a comment"
        assert resp.get_json()["comment"]["user_id"] == 1

    def test_create_comment_empty(self, client, user_headers, task_id):
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "  "},
        )
        assert resp.status_code == 400

    def test_create_comment_viewer_cannot(self, client, user_headers, project_id, task_id):
        client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers={"Authorization": f"Bearer {_get_token(client, 3)}"},
            json={"content": "nope"},
        )
        assert resp.status_code == 403

    def test_list_comments(self, client, user_headers, task_id):
        client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "C1"},
        )
        client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "C2"},
        )
        resp = client.get(f"/tasks/{task_id}/comments", headers=user_headers)
        data = resp.get_json()
        assert len(data["comments"]) == 2
        assert data["comments"][0]["content"] == "C1"

    def test_list_comments_viewer(self, client, user_headers, project_id, task_id):
        client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "A comment"},
        )
        resp = client.get(
            f"/tasks/{task_id}/comments",
            headers={"Authorization": f"Bearer {_get_token(client, 3)}"},
        )
        assert resp.status_code == 200

    def test_update_own_comment(self, client, user_headers, task_id):
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "Original"},
        )
        cid = resp.get_json()["comment"]["id"]

        resp = client.put(
            f"/comments/{cid}",
            headers=user_headers,
            json={"content": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["comment"]["content"] == "Updated"

    def test_update_others_comment(self, client, user_headers, user2_headers, task_id):
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "Mine"},
        )
        cid = resp.get_json()["comment"]["id"]

        resp = client.put(
            f"/comments/{cid}",
            headers=user2_headers,
            json={"content": "Hijack"},
        )
        assert resp.status_code == 403

    def test_delete_own_comment(self, client, user_headers, task_id):
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "To delete"},
        )
        cid = resp.get_json()["comment"]["id"]
        resp = client.delete(f"/comments/{cid}", headers=user_headers)
        assert resp.status_code == 200

    def test_delete_comment_by_admin(self, client, user_headers, user2_headers, project_id, task_id):
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=user2_headers,
            json={"content": "Member's comment"},
        )
        cid = resp.get_json()["comment"]["id"]
        resp = client.delete(f"/comments/{cid}", headers=user_headers)
        assert resp.status_code == 200

    def test_delete_comment_unauthorized(self, client, user_headers, user2_headers, task_id):
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "Admin's comment"},
        )
        cid = resp.get_json()["comment"]["id"]
        resp = client.delete(f"/comments/{cid}", headers=user2_headers)
        assert resp.status_code == 403

    def test_update_comment_empty(self, client, user_headers, task_id):
        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=user_headers,
            json={"content": "Original"},
        )
        cid = resp.get_json()["comment"]["id"]
        resp = client.put(
            f"/comments/{cid}",
            headers=user_headers,
            json={"content": ""},
        )
        assert resp.status_code == 400


# ─── Attachment tests ───


class TestAttachments:
    def test_create_attachment_on_task(self, client, user_headers, task_id):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={
                "task_id": task_id,
                "filename": "report.pdf",
                "file_path": "/uploads/report.pdf",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["attachment"]["filename"] == "report.pdf"
        assert data["attachment"]["file_path"] == "/uploads/report.pdf"

    def test_create_attachment_on_comment(self, client, user_headers, comment_id):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={
                "comment_id": comment_id,
                "filename": "screenshot.png",
                "file_path": "/uploads/screenshot.png",
            },
        )
        assert resp.status_code == 201

    def test_create_attachment_missing_filename(self, client, user_headers, task_id):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={"task_id": task_id, "file_path": "/path/to/file"},
        )
        assert resp.status_code == 400

    def test_create_attachment_missing_file_path(self, client, user_headers, task_id):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={"task_id": task_id, "filename": "file.txt"},
        )
        assert resp.status_code == 400

    def test_create_attachment_no_target(self, client, user_headers):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={"filename": "f.txt", "file_path": "/path/f.txt"},
        )
        assert resp.status_code == 400

    def test_create_attachment_nonexistent_task(self, client, user_headers):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={"task_id": 99999, "filename": "f.txt", "file_path": "/path/f.txt"},
        )
        assert resp.status_code == 404

    def test_create_attachment_nonexistent_comment(self, client, user_headers):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={"comment_id": 99999, "filename": "f.txt", "file_path": "/path/f.txt"},
        )
        assert resp.status_code == 404

    def test_create_attachment_viewer_cannot(self, client, user_headers, project_id, task_id):
        client.post(
            f"/projects/{project_id}/members",
            headers=user_headers,
            json={"user_id": 3, "role": "viewer"},
        )
        resp = client.post(
            "/attachments",
            headers={"Authorization": f"Bearer {_get_token(client, 3)}"},
            json={"task_id": task_id, "filename": "f.txt", "file_path": "/path/f.txt"},
        )
        assert resp.status_code == 403

    def test_get_attachment(self, client, user_headers, task_id):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={"task_id": task_id, "filename": "doc.txt", "file_path": "/path/doc.txt"},
        )
        aid = resp.get_json()["attachment"]["id"]

        resp = client.get(f"/attachments/{aid}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.get_json()["filename"] == "doc.txt"

    def test_get_nonexistent_attachment(self, client, user_headers):
        resp = client.get("/attachments/99999", headers=user_headers)
        assert resp.status_code == 404

    def test_delete_own_attachment(self, client, user_headers, task_id):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={"task_id": task_id, "filename": "tmp.txt", "file_path": "/tmp/tmp.txt"},
        )
        aid = resp.get_json()["attachment"]["id"]
        resp = client.delete(f"/attachments/{aid}", headers=user_headers)
        assert resp.status_code == 200

    def test_delete_attachment_by_admin(self, client, user_headers, user2_headers, task_id):
        resp = client.post(
            "/attachments",
            headers=user2_headers,
            json={"task_id": task_id, "filename": "member_file.txt", "file_path": "/path/file.txt"},
        )
        aid = resp.get_json()["attachment"]["id"]
        resp = client.delete(f"/attachments/{aid}", headers=user_headers)
        assert resp.status_code == 200

    def test_delete_attachment_unauthorized(self, client, user_headers, user2_headers, task_id):
        resp = client.post(
            "/attachments",
            headers=user_headers,
            json={"task_id": task_id, "filename": "admin_file.txt", "file_path": "/path/file.txt"},
        )
        aid = resp.get_json()["attachment"]["id"]
        resp = client.delete(f"/attachments/{aid}", headers=user2_headers)
        assert resp.status_code == 403


# ─── Edge case tests ───


class TestNonmemberAccess:
    def test_nonmember_cannot_access_project(self, client):
        u1 = client.post(
            "/auth/register",
            json={"username": "owner", "email": "owner@test.com", "password": "secret123"},
        )
        token1 = u1.get_json()["token"]
        h1 = {"Authorization": f"Bearer {token1}"}

        u2 = client.post(
            "/auth/register",
            json={"username": "outsider", "email": "outsider@test.com", "password": "secret123"},
        )
        token2 = u2.get_json()["token"]
        h2 = {"Authorization": f"Bearer {token2}"}

        resp = client.post("/projects", headers=h1, json={"name": "Private Project"})
        pid = resp.get_json()["project"]["id"]

        resp = client.get(f"/projects/{pid}/tasks", headers=h2)
        assert resp.status_code == 403

    def test_nonmember_cannot_comment(self, client, user_headers, task_id, project_id):
        outsider = client.post(
            "/auth/register",
            json={"username": "outsider2", "email": "outsider2@test.com", "password": "secret123"},
        )
        h = {"Authorization": f"Bearer {outsider.get_json()['token']}"}

        resp = client.post(
            f"/tasks/{task_id}/comments",
            headers=h,
            json={"content": "Should not work"},
        )
        assert resp.status_code == 403


def _get_token(client, user_id):
    email_map = {1: "test@example.com", 2: "test2@example.com", 3: "test3@example.com"}
    resp = client.post("/auth/login", json={"email": email_map[user_id], "password": "secret123"})
    return resp.get_json()["token"]
