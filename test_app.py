import json


class TestCreateTask:
    def test_create_task_success(self, client):
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        response = client.post(
            "/tasks",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        response = client.post(
            "/tasks",
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"


class TestListTasks:
    def test_list_tasks_empty(self, client):
        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
        )
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 2"}),
            content_type="application/json",
        )
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 3"}),
            content_type="application/json",
        )

        response = client.get("/tasks")
        assert response.status_code == 200
        tasks = response.get_json()
        assert len(tasks) == 3
        assert tasks[0]["title"] == "Task 3"
        assert tasks[1]["title"] == "Task 2"
        assert tasks[2]["title"] == "Task 1"


class TestGetTask:
    def test_get_task_success(self, client):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )
        task_id = created.get_json()["id"]

        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        response = client.get("/tasks/9999")
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"


class TestUpdateTask:
    def test_update_task_title(self, client):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
        )
        task_id = created.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Some task"}),
            content_type="application/json",
        )
        task_id = created.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Some task"
        assert data["status"] == "completed"

    def test_update_task_both_fields(self, client):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
        )
        task_id = created.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Updated", "status": "in_progress"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client):
        response = client.put(
            "/tasks/9999",
            data=json.dumps({"title": "Nope"}),
            content_type="application/json",
        )
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_update_task_no_fields_keeps_values(self, client):
        created = client.post(
            "/tasks",
            data=json.dumps({"title": "Keep me"}),
            content_type="application/json",
        )
        task_id = created.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Keep me"
        assert data["status"] == "pending"
