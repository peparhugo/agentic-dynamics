"""Tests for task CRUD, validation, assignment and access control."""


def create_task(client, headers, **overrides):
    payload = {"title": "Write report"}
    payload.update(overrides)
    return client.post("/api/tasks", headers=headers, json=payload)


class TestTaskCreate:
    def test_create_minimal(self, client, auth):
        res = create_task(client, auth)
        assert res.status_code == 201
        task = res.get_json()["task"]
        assert task["title"] == "Write report"
        assert task["status"] == "todo"
        assert task["priority"] == "medium"
        assert task["due_date"] is None
        assert task["category_id"] is None
        assert task["assignee_id"] is None

    def test_create_full(self, client, auth):
        cat = client.post("/api/categories", headers=auth,
                          json={"name": "Work"}).get_json()["category"]
        res = create_task(
            client, auth,
            description="Quarterly numbers",
            status="in_progress",
            priority="high",
            due_date="2026-12-31T17:00:00",
            category_id=cat["id"],
        )
        assert res.status_code == 201
        task = res.get_json()["task"]
        assert task["description"] == "Quarterly numbers"
        assert task["status"] == "in_progress"
        assert task["priority"] == "high"
        assert task["due_date"].startswith("2026-12-31T17:00:00")
        assert task["category"]["name"] == "Work"

    def test_create_requires_title(self, client, auth):
        res = client.post("/api/tasks", headers=auth, json={})
        assert res.status_code == 400

    def test_create_invalid_status(self, client, auth):
        res = create_task(client, auth, status="bogus")
        assert res.status_code == 400

    def test_create_invalid_priority(self, client, auth):
        res = create_task(client, auth, priority="bogus")
        assert res.status_code == 400

    def test_create_invalid_due_date(self, client, auth):
        res = create_task(client, auth, due_date="not-a-date")
        assert res.status_code == 400

    def test_create_with_missing_category(self, client, auth):
        res = create_task(client, auth, category_id=999)
        assert res.status_code == 404

    def test_create_with_other_users_category(self, client, auth, auth2):
        cat = client.post("/api/categories", headers=auth2,
                          json={"name": "Secret"}).get_json()["category"]
        res = create_task(client, auth, category_id=cat["id"])
        assert res.status_code == 404

    def test_create_with_missing_assignee(self, client, auth):
        res = create_task(client, auth, assignee_id=999)
        assert res.status_code == 404

    def test_title_too_long(self, client, auth):
        res = create_task(client, auth, title="x" * 201)
        assert res.status_code == 400


class TestTaskRead:
    def test_get_task(self, client, auth):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.get(f"/api/tasks/{task_id}", headers=auth)
        assert res.status_code == 200
        assert res.get_json()["task"]["id"] == task_id

    def test_get_missing_task(self, client, auth):
        assert client.get("/api/tasks/999", headers=auth).status_code == 404

    def test_cannot_read_others_task(self, client, auth, auth2):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        assert client.get(f"/api/tasks/{task_id}",
                          headers=auth2).status_code == 404


class TestTaskUpdate:
    def test_update_fields(self, client, auth):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.put(f"/api/tasks/{task_id}", headers=auth, json={
            "title": "Updated",
            "description": "New desc",
            "status": "done",
            "priority": "urgent",
            "due_date": "2027-01-15T09:00:00",
        })
        assert res.status_code == 200
        task = res.get_json()["task"]
        assert task["title"] == "Updated"
        assert task["description"] == "New desc"
        assert task["status"] == "done"
        assert task["priority"] == "urgent"
        assert task["due_date"].startswith("2027-01-15T09:00:00")

    def test_patch_partial_update(self, client, auth):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.patch(f"/api/tasks/{task_id}", headers=auth,
                           json={"status": "in_progress"})
        assert res.status_code == 200
        task = res.get_json()["task"]
        assert task["status"] == "in_progress"
        assert task["title"] == "Write report"  # unchanged

    def test_clear_due_date(self, client, auth):
        task_id = create_task(
            client, auth,
            due_date="2026-06-01T00:00:00").get_json()["task"]["id"]
        res = client.patch(f"/api/tasks/{task_id}", headers=auth,
                           json={"due_date": None})
        assert res.status_code == 200
        assert res.get_json()["task"]["due_date"] is None

    def test_update_invalid_status(self, client, auth):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.put(f"/api/tasks/{task_id}", headers=auth,
                         json={"status": "bogus"})
        assert res.status_code == 400

    def test_update_empty_title_rejected(self, client, auth):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.put(f"/api/tasks/{task_id}", headers=auth,
                         json={"title": "  "})
        assert res.status_code == 400

    def test_cannot_update_others_task(self, client, auth, auth2):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.put(f"/api/tasks/{task_id}", headers=auth2,
                         json={"title": "Hacked"})
        assert res.status_code == 404


class TestTaskDelete:
    def test_delete_task(self, client, auth):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        assert client.delete(f"/api/tasks/{task_id}",
                             headers=auth).status_code == 200
        assert client.get(f"/api/tasks/{task_id}",
                          headers=auth).status_code == 404

    def test_delete_missing_task(self, client, auth):
        assert client.delete("/api/tasks/999", headers=auth).status_code == 404

    def test_cannot_delete_others_task(self, client, auth, auth2):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        assert client.delete(f"/api/tasks/{task_id}",
                             headers=auth2).status_code == 404

    def test_assignee_cannot_delete_task(self, client, auth, auth2):
        """Only the creator may delete, even if the task is assigned to you."""
        bob = client.get("/api/auth/me", headers=auth2).get_json()["user"]
        task_id = create_task(
            client, auth, assignee_id=bob["id"]).get_json()["task"]["id"]
        assert client.delete(f"/api/tasks/{task_id}",
                             headers=auth2).status_code == 404


class TestTaskAssignment:
    def test_assign_on_create(self, client, auth, auth2):
        bob = client.get("/api/auth/me", headers=auth2).get_json()["user"]
        res = create_task(client, auth, assignee_id=bob["id"])
        assert res.status_code == 201
        task = res.get_json()["task"]
        assert task["assignee_id"] == bob["id"]
        assert task["assignee"]["username"] == "bob"

    def test_assign_endpoint(self, client, auth, auth2):
        bob = client.get("/api/auth/me", headers=auth2).get_json()["user"]
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.post(f"/api/tasks/{task_id}/assign", headers=auth,
                          json={"assignee_id": bob["id"]})
        assert res.status_code == 200
        assert res.get_json()["task"]["assignee_id"] == bob["id"]

    def test_unassign(self, client, auth, auth2):
        bob = client.get("/api/auth/me", headers=auth2).get_json()["user"]
        task_id = create_task(
            client, auth, assignee_id=bob["id"]).get_json()["task"]["id"]
        res = client.post(f"/api/tasks/{task_id}/assign", headers=auth,
                          json={"assignee_id": None})
        assert res.status_code == 200
        assert res.get_json()["task"]["assignee_id"] is None

    def test_assign_missing_user(self, client, auth):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.post(f"/api/tasks/{task_id}/assign", headers=auth,
                          json={"assignee_id": 999})
        assert res.status_code == 404

    def test_assign_requires_field(self, client, auth):
        task_id = create_task(client, auth).get_json()["task"]["id"]
        res = client.post(f"/api/tasks/{task_id}/assign", headers=auth, json={})
        assert res.status_code == 400

    def test_assignee_can_see_and_update_task(self, client, auth, auth2):
        bob = client.get("/api/auth/me", headers=auth2).get_json()["user"]
        task_id = create_task(
            client, auth, assignee_id=bob["id"]).get_json()["task"]["id"]

        assert client.get(f"/api/tasks/{task_id}",
                          headers=auth2).status_code == 200
        res = client.patch(f"/api/tasks/{task_id}", headers=auth2,
                           json={"status": "done"})
        assert res.status_code == 200
        assert res.get_json()["task"]["status"] == "done"

    def test_assigned_task_shows_in_assignee_list(self, client, auth, auth2):
        bob = client.get("/api/auth/me", headers=auth2).get_json()["user"]
        create_task(client, auth, title="For Bob", assignee_id=bob["id"])
        res = client.get("/api/tasks", headers=auth2)
        titles = [t["title"] for t in res.get_json()["tasks"]]
        assert "For Bob" in titles
