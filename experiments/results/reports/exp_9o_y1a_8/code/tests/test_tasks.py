class TestTaskCreate:
    def test_create_task_success(self, client, auth_headers, category):
        resp = client.post(
            "/api/tasks",
            json={
                "title": "Implement login",
                "description": "Add JWT login endpoint",
                "priority": "high",
                "status": "in_progress",
                "due_date": "2026-08-15T00:00:00Z",
                "category_id": category["id"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Implement login"
        assert data["priority"] == "high"
        assert data["status"] == "in_progress"
        assert data["due_date"] is not None
        assert data["category"]["name"] == "Work"
        assert data["created_by"]["username"] == "testuser"
        assert "id" in data

    def test_create_task_minimal(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Minimal task"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "pending"
        assert data["priority"] == "medium"

    def test_create_task_with_assignment(self, client, auth_headers, second_user_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Assigned task", "assigned_to_id": None},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    def test_create_task_invalid_category(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Bad cat", "category_id": "nonexistent"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_create_task_invalid_status(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Bad status", "status": "fantasy"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_task_invalid_priority(self, client, auth_headers):
        resp = client.post(
            "/api/tasks",
            json={"title": "Bad priority", "priority": "extreme"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_task_unauthenticated(self, client):
        resp = client.post("/api/tasks", json={"title": "No auth"})
        assert resp.status_code == 401


class TestTaskRead:
    def test_get_task(self, client, auth_headers, task):
        resp = client.get(f"/api/tasks/{task['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["id"] == task["id"]
        assert resp.get_json()["title"] == task["title"]

    def test_get_nonexistent_task(self, client, auth_headers):
        resp = client.get("/api/tasks/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_list_tasks(self, client, auth_headers, task):
        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) >= 1
        assert data["pagination"]["total"] >= 1
        assert data["pagination"]["page"] == 1

    def test_list_tasks_pagination(self, client, auth_headers):
        for i in range(5):
            client.post(
                "/api/tasks",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )
        resp = client.get("/api/tasks?page=1&per_page=3", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 3
        assert data["pagination"]["per_page"] == 3
        assert data["pagination"]["total"] >= 5

    def test_list_tasks_filter_status(self, client, auth_headers):
        client.post(
            "/api/tasks",
            json={"title": "Done task", "status": "completed"},
            headers=auth_headers,
        )
        resp = client.get("/api/tasks?status=completed", headers=auth_headers)
        assert resp.status_code == 200
        for item in resp.get_json()["data"]:
            assert item["status"] == "completed"

    def test_list_tasks_filter_priority(self, client, auth_headers):
        client.post(
            "/api/tasks",
            json={"title": "Urgent", "priority": "urgent"},
            headers=auth_headers,
        )
        resp = client.get("/api/tasks?priority=urgent", headers=auth_headers)
        assert resp.status_code == 200
        for item in resp.get_json()["data"]:
            assert item["priority"] == "urgent"

    def test_list_tasks_filter_category(self, client, auth_headers, category):
        resp = client.get(
            f"/api/tasks?category_id={category['id']}", headers=auth_headers
        )
        assert resp.status_code == 200
        for item in resp.get_json()["data"]:
            assert item["category_id"] == category["id"]

    def test_list_tasks_search(self, client, auth_headers):
        client.post(
            "/api/tasks",
            json={"title": "Deploy to AWS lambda"},
            headers=auth_headers,
        )
        client.post(
            "/api/tasks",
            json={"title": "Fix CSS bug"},
            headers=auth_headers,
        )
        resp = client.get("/api/tasks?search=AWS", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert any("AWS" in t["title"] or "aws" in t["title"] for t in data["data"])

    def test_list_tasks_sort(self, client, auth_headers):
        for i in range(3):
            client.post(
                "/api/tasks",
                json={"title": f"Sort {i}"},
                headers=auth_headers,
            )
        resp = client.get(
            "/api/tasks?sort_by=title&sort_order=asc", headers=auth_headers
        )
        assert resp.status_code == 200
        titles = [t["title"] for t in resp.get_json()["data"]]
        assert titles == sorted(titles)


class TestTaskUpdate:
    def test_update_title(self, client, auth_headers, task):
        resp = client.put(
            f"/api/tasks/{task['id']}",
            json={"title": "Updated Title"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Updated Title"

    def test_update_status(self, client, auth_headers, task):
        resp = client.put(
            f"/api/tasks/{task['id']}",
            json={"status": "completed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "completed"

    def test_update_priority(self, client, auth_headers, task):
        resp = client.put(
            f"/api/tasks/{task['id']}",
            json={"priority": "urgent"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["priority"] == "urgent"

    def test_update_due_date(self, client, auth_headers, task):
        resp = client.put(
            f"/api/tasks/{task['id']}",
            json={"due_date": "2026-12-31T00:00:00Z"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["due_date"] is not None

    def test_update_category(self, client, auth_headers, task):
        cat_resp = client.post(
            "/api/categories",
            json={"name": "Personal"},
            headers=auth_headers,
        )
        new_cat = cat_resp.get_json()
        resp = client.put(
            f"/api/tasks/{task['id']}",
            json={"category_id": new_cat["id"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["category"]["name"] == "Personal"

    def test_update_nonexistent_task(self, client, auth_headers):
        resp = client.put("/api/tasks/nope", json={"title": "x"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_update_invalid_status(self, client, auth_headers, task):
        resp = client.put(
            f"/api/tasks/{task['id']}",
            json={"status": "invalid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestTaskDelete:
    def test_delete_task(self, client, auth_headers, task):
        resp = client.delete(f"/api/tasks/{task['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Task deleted."
        resp2 = client.get(f"/api/tasks/{task['id']}", headers=auth_headers)
        assert resp2.status_code == 404

    def test_delete_nonexistent_task(self, client, auth_headers):
        resp = client.delete("/api/tasks/nope", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_unauthenticated(self, client, task):
        resp = client.delete(f"/api/tasks/{task['id']}")
        assert resp.status_code == 401
