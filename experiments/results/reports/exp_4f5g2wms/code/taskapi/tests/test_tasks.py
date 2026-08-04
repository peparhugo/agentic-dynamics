class TestCreateTask:
    def test_create_task_minimal(self, client, auth_header):
        resp = client.post(
            "/tasks",
            json={"title": "A simple task"},
            headers=auth_header,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "A simple task"
        assert task["status"] == "pending"
        assert task["priority"] == "medium"
        assert task["description"] == ""

    def test_create_task_full(self, client, auth_header, sample_category, auth_tokens):
        resp = client.post(
            "/tasks",
            json={
                "title": "Full task",
                "description": "With everything",
                "status": "in_progress",
                "priority": "critical",
                "due_date": "2026-12-31",
                "category_id": sample_category["id"],
                "assigned_to": auth_tokens["users"]["bob"]["id"],
            },
            headers=auth_header,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Full task"
        assert task["status"] == "in_progress"
        assert task["priority"] == "critical"
        assert task["due_date"] == "2026-12-31"
        assert task["category_id"] == sample_category["id"]
        assert task["assigned_to"] == auth_tokens["users"]["bob"]["id"]

    def test_create_task_missing_title(self, client, auth_header):
        resp = client.post("/tasks", json={}, headers=auth_header)
        assert resp.status_code == 400
        assert "Missing required fields" in resp.get_json()["error"]

    def test_create_task_empty_title(self, client, auth_header):
        resp = client.post(
            "/tasks", json={"title": "   "}, headers=auth_header
        )
        assert resp.status_code == 400

    def test_create_task_invalid_status(self, client, auth_header):
        resp = client.post(
            "/tasks",
            json={"title": "Test", "status": "bogus"},
            headers=auth_header,
        )
        assert resp.status_code == 400

    def test_create_task_invalid_priority(self, client, auth_header):
        resp = client.post(
            "/tasks",
            json={"title": "Test", "priority": "super"},
            headers=auth_header,
        )
        assert resp.status_code == 400

    def test_create_task_bad_category(self, client, auth_header):
        resp = client.post(
            "/tasks",
            json={"title": "Test", "category_id": 9999},
            headers=auth_header,
        )
        assert resp.status_code == 404

    def test_create_task_bad_assigned_to(self, client, auth_header):
        resp = client.post(
            "/tasks",
            json={"title": "Test", "assigned_to": 9999},
            headers=auth_header,
        )
        assert resp.status_code == 404

    def test_create_task_unauthorized(self, client):
        resp = client.post("/tasks", json={"title": "Test"})
        assert resp.status_code == 401


class TestGetTask:
    def test_get_task(self, client, auth_header, sample_task):
        resp = client.get(f"/tasks/{sample_task['id']}", headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["id"] == sample_task["id"]

    def test_get_task_not_found(self, client, auth_header):
        resp = client.get("/tasks/9999", headers=auth_header)
        assert resp.status_code == 404

    def test_get_task_wrong_user(self, client, bob_header, sample_task):
        resp = client.get(f"/tasks/{sample_task['id']}", headers=bob_header)
        assert resp.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client, auth_header, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"title": "Updated title"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Updated title"

    def test_update_task_status(self, client, auth_header, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"status": "completed"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["status"] == "completed"

    def test_update_task_priority(self, client, auth_header, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"priority": "critical"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["priority"] == "critical"

    def test_update_task_multiple_fields(self, client, auth_header, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={
                "title": "New title",
                "status": "in_progress",
                "priority": "low",
                "description": "New description",
            },
            headers=auth_header,
        )
        assert resp.status_code == 200
        task = resp.get_json()["task"]
        assert task["title"] == "New title"
        assert task["status"] == "in_progress"
        assert task["priority"] == "low"
        assert task["description"] == "New description"

    def test_update_task_not_found(self, client, auth_header):
        resp = client.put(
            "/tasks/9999", json={"title": "Nope"}, headers=auth_header
        )
        assert resp.status_code == 404

    def test_update_task_no_fields(self, client, auth_header, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}", json={}, headers=auth_header
        )
        assert resp.status_code == 400

    def test_update_task_bad_status(self, client, auth_header, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"status": "whoops"},
            headers=auth_header,
        )
        assert resp.status_code == 400

    def test_update_task_unset_fields(self, client, auth_header, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"due_date": None, "category_id": None, "assigned_to": None},
            headers=auth_header,
        )
        assert resp.status_code == 200
        task = resp.get_json()["task"]
        assert task["due_date"] is None
        assert task["category_id"] is None
        assert task["assigned_to"] is None


class TestDeleteTask:
    def test_delete_task(self, client, auth_header, sample_task):
        resp = client.delete(
            f"/tasks/{sample_task['id']}", headers=auth_header
        )
        assert resp.status_code == 200

        resp = client.get(f"/tasks/{sample_task['id']}", headers=auth_header)
        assert resp.status_code == 404

    def test_delete_task_not_found(self, client, auth_header):
        resp = client.delete("/tasks/9999", headers=auth_header)
        assert resp.status_code == 404

    def test_delete_task_wrong_user(self, client, bob_header, sample_task):
        resp = client.delete(f"/tasks/{sample_task['id']}", headers=bob_header)
        assert resp.status_code == 404


class TestAssignTask:
    def test_assign_task(self, client, auth_header, sample_task, auth_tokens):
        bob_id = auth_tokens["users"]["bob"]["id"]
        resp = client.post(
            f"/tasks/{sample_task['id']}/assign",
            json={"user_id": bob_id},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["assigned_to"] == bob_id

    def test_assign_task_not_found(self, client, auth_header):
        resp = client.post(
            "/tasks/9999/assign",
            json={"user_id": 1},
            headers=auth_header,
        )
        assert resp.status_code == 404

    def test_assign_task_bad_user(self, client, auth_header, sample_task):
        resp = client.post(
            f"/tasks/{sample_task['id']}/assign",
            json={"user_id": 9999},
            headers=auth_header,
        )
        assert resp.status_code == 404

    def test_assign_task_missing_user_id(self, client, auth_header, sample_task):
        resp = client.post(
            f"/tasks/{sample_task['id']}/assign",
            json={},
            headers=auth_header,
        )
        assert resp.status_code == 400
