import json


class TestAuth:
    def test_register_success(self, client):
        resp = client.post(
            "/auth/register",
            data=json.dumps({"username": "alice", "password": "secret123"}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "alice"
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_duplicate_username(self, client):
        client.post(
            "/auth/register",
            data=json.dumps({"username": "bob", "password": "pass"}),
            content_type="application/json",
        )
        resp = client.post(
            "/auth/register",
            data=json.dumps({"username": "bob", "password": "pass2"}),
            content_type="application/json",
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "username already exists"

    def test_register_missing_fields(self, client):
        resp = client.post(
            "/auth/register",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_register_missing_username(self, client):
        resp = client.post(
            "/auth/register",
            data=json.dumps({"password": "pass"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_register_missing_password(self, client):
        resp = client.post(
            "/auth/register",
            data=json.dumps({"username": "user"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_login_success(self, client):
        client.post(
            "/auth/register",
            data=json.dumps({"username": "carol", "password": "pass"}),
            content_type="application/json",
        )
        resp = client.post(
            "/auth/login",
            data=json.dumps({"username": "carol", "password": "pass"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data

    def test_login_wrong_password(self, client):
        client.post(
            "/auth/register",
            data=json.dumps({"username": "dave", "password": "pass"}),
            content_type="application/json",
        )
        resp = client.post(
            "/auth/login",
            data=json.dumps({"username": "dave", "password": "wrong"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/auth/login",
            data=json.dumps({"username": "nobody", "password": "pass"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post(
            "/auth/login",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_login_missing_username(self, client):
        resp = client.post(
            "/auth/login",
            data=json.dumps({"password": "pass"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_login_missing_password(self, client):
        resp = client.post(
            "/auth/login",
            data=json.dumps({"username": "user"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestCreateTask:
    def test_create_task_success(self, client, auth_headers):
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client, auth_headers):
        response = client.post(
            "/tasks",
            data=json.dumps({}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_empty_title(self, client, auth_headers):
        response = client.post(
            "/tasks",
            data=json.dumps({"title": ""}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_whitespace_title(self, client, auth_headers):
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_unauthorized(self, client):
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_create_task_invalid_token(self, client):
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert response.status_code == 401


class TestListTasks:
    def test_list_tasks_empty(self, client, auth_headers):
        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_tasks_ordered_by_created_at_desc(self, client, auth_headers):
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
            headers=auth_headers,
        )
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 2"}),
            content_type="application/json",
            headers=auth_headers,
        )
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 3"}),
            content_type="application/json",
            headers=auth_headers,
        )

        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200
        tasks = response.get_json()
        assert len(tasks) == 3
        assert tasks[0]["title"] == "Task 3"
        assert tasks[1]["title"] == "Task 2"
        assert tasks[2]["title"] == "Task 1"

    def test_list_tasks_unauthorized(self, client):
        response = client.get("/tasks")
        assert response.status_code == 401

    def test_list_tasks_user_isolation(self, client):
        client.post(
            "/auth/register",
            data=json.dumps({"username": "user1", "password": "pass1"}),
            content_type="application/json",
        )
        r1 = client.post(
            "/auth/login",
            data=json.dumps({"username": "user1", "password": "pass1"}),
            content_type="application/json",
        )
        token1 = r1.get_json()["token"]
        h1 = {"Authorization": "Bearer " + token1}
        client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=h1,
        )

        client.post(
            "/auth/register",
            data=json.dumps({"username": "user2", "password": "pass2"}),
            content_type="application/json",
        )
        r2 = client.post(
            "/auth/login",
            data=json.dumps({"username": "user2", "password": "pass2"}),
            content_type="application/json",
        )
        token2 = r2.get_json()["token"]
        h2 = {"Authorization": "Bearer " + token2}
        client.post(
            "/tasks",
            data=json.dumps({"title": "User 2 Task"}),
            content_type="application/json",
            headers=h2,
        )

        resp1 = client.get("/tasks", headers=h1)
        tasks1 = resp1.get_json()
        assert len(tasks1) == 1
        assert tasks1[0]["title"] == "User 1 Task"

        resp2 = client.get("/tasks", headers=h2)
        tasks2 = resp2.get_json()
        assert len(tasks2) == 1
        assert tasks2[0]["title"] == "User 2 Task"


class TestGetTask:
    def test_get_task_success(self, client, auth_headers):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_headers,
        )
        task_id = created.get_json()["id"]

        response = client.get(f"/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client, auth_headers):
        response = client.get("/tasks/9999", headers=auth_headers)
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_get_task_unauthorized(self, client):
        response = client.get("/tasks/1")
        assert response.status_code == 401

    def test_get_task_wrong_user(self, client):
        client.post(
            "/auth/register",
            data=json.dumps({"username": "user1", "password": "pass1"}),
            content_type="application/json",
        )
        r1 = client.post(
            "/auth/login",
            data=json.dumps({"username": "user1", "password": "pass1"}),
            content_type="application/json",
        )
        token1 = r1.get_json()["token"]
        h1 = {"Authorization": "Bearer " + token1}
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=h1,
        )
        task_id = created.get_json()["id"]

        client.post(
            "/auth/register",
            data=json.dumps({"username": "user2", "password": "pass2"}),
            content_type="application/json",
        )
        r2 = client.post(
            "/auth/login",
            data=json.dumps({"username": "user2", "password": "pass2"}),
            content_type="application/json",
        )
        token2 = r2.get_json()["token"]
        h2 = {"Authorization": "Bearer " + token2}

        resp = client.get(f"/tasks/{task_id}", headers=h2)
        assert resp.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client, auth_headers):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
            headers=auth_headers,
        )
        task_id = created.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, auth_headers):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Some task"}),
            content_type="application/json",
            headers=auth_headers,
        )
        task_id = created.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Some task"
        assert data["status"] == "completed"

    def test_update_task_both_fields(self, client, auth_headers):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
            headers=auth_headers,
        )
        task_id = created.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Updated", "status": "in_progress"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client, auth_headers):
        response = client.put(
            "/tasks/9999",
            data=json.dumps({"title": "Nope"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_update_task_no_fields_keeps_values(self, client, auth_headers):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Keep me"}),
            content_type="application/json",
            headers=auth_headers,
        )
        task_id = created.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Keep me"
        assert data["status"] == "pending"

    def test_update_task_unauthorized(self, client):
        response = client.put(
            "/tasks/1",
            data=json.dumps({"title": "Nope"}),
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_update_task_wrong_user(self, client):
        client.post(
            "/auth/register",
            data=json.dumps({"username": "user1", "password": "pass1"}),
            content_type="application/json",
        )
        r1 = client.post(
            "/auth/login",
            data=json.dumps({"username": "user1", "password": "pass1"}),
            content_type="application/json",
        )
        token1 = r1.get_json()["token"]
        h1 = {"Authorization": "Bearer " + token1}
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=h1,
        )
        task_id = created.get_json()["id"]

        client.post(
            "/auth/register",
            data=json.dumps({"username": "user2", "password": "pass2"}),
            content_type="application/json",
        )
        r2 = client.post(
            "/auth/login",
            data=json.dumps({"username": "user2", "password": "pass2"}),
            content_type="application/json",
        )
        token2 = r2.get_json()["token"]
        h2 = {"Authorization": "Bearer " + token2}

        resp = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Hacked"}),
            content_type="application/json",
            headers=h2,
        )
        assert resp.status_code == 404


class TestNotificationTrigger:
    def test_notification_sent_when_status_changes_to_completed(self, client, auth_headers, monkeypatch):
        import tasks

        calls = []
        def fake_delay(email, title):
            calls.append((email, title))

        monkeypatch.setattr(tasks.send_notification_email, "delay", fake_delay)

        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Finish report"}),
            content_type="application/json",
            headers=auth_headers,
        )
        task_id = created.get_json()["id"]

        resp = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(calls) == 1
        assert calls[0][0] == "testuser@example.com"
        assert calls[0][1] == "Finish report"

    def test_notification_not_sent_when_other_status(self, client, auth_headers, monkeypatch):
        import tasks

        calls = []
        def fake_delay(email, title):
            calls.append((email, title))

        monkeypatch.setattr(tasks.send_notification_email, "delay", fake_delay)

        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Task"}),
            content_type="application/json",
            headers=auth_headers,
        )
        task_id = created.get_json()["id"]

        resp = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(calls) == 0

    def test_notification_not_sent_when_already_completed(self, client, auth_headers, monkeypatch):
        import tasks

        calls = []
        def fake_delay(email, title):
            calls.append((email, title))

        monkeypatch.setattr(tasks.send_notification_email, "delay", fake_delay)

        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Task"}),
            content_type="application/json",
            headers=auth_headers,
        )
        task_id = created.get_json()["id"]

        client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=auth_headers,
        )
        calls.clear()

        resp = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(calls) == 0

    def test_notification_not_sent_for_nonexistent_task(self, client, auth_headers, monkeypatch):
        import tasks

        calls = []
        def fake_delay(email, title):
            calls.append((email, title))

        monkeypatch.setattr(tasks.send_notification_email, "delay", fake_delay)

        resp = client.put(
            "/tasks/9999",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert len(calls) == 0
