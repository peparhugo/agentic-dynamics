import json


class TestCreateTask:
    def test_create_minimal(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "Simple task"},
            headers=headers,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Simple task"
        assert task["status"] == "pending"
        assert task["priority"] == "medium"
        assert task["description"] == ""

    def test_create_full(self, auth_client, headers, category_id):
        resp = auth_client.post(
            "/tasks",
            json={
                "title": "Full task",
                "description": "Description here",
                "status": "in_progress",
                "priority": "urgent",
                "category_id": category_id,
                "due_date": "2026-06-15T09:00:00",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Full task"
        assert task["description"] == "Description here"
        assert task["status"] == "in_progress"
        assert task["priority"] == "urgent"
        assert task["category"] is not None
        assert task["category"]["id"] == category_id
        assert task["due_date"] == "2026-06-15T09:00:00"

    def test_create_with_assignment(self, auth_client, headers, second_user_headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "Assigned task", "assigned_to": 2},
            headers=headers,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["assigned_to"]["id"] == 2
        assert task["assigned_to"]["username"] == "user2"

    def test_create_no_title(self, auth_client, headers):
        resp = auth_client.post("/tasks", json={}, headers=headers)
        assert resp.status_code == 400

    def test_create_empty_title(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks", json={"title": "   "}, headers=headers
        )
        assert resp.status_code == 400

    def test_create_invalid_status(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "Bad status", "status": "nonexistent"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_create_invalid_priority(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "Bad priority", "priority": "extreme"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_create_invalid_due_date(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "Bad date", "due_date": "not-a-date"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_create_nonexistent_category(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "Bad cat", "category_id": 99999},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_create_nonexistent_assignee(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "Bad assignee", "assigned_to": 99999},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_create_no_auth(self, client):
        resp = client.post("/tasks", json={"title": "No auth"})
        assert resp.status_code == 401

    def test_create_created_by_is_current_user(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks", json={"title": "My task"}, headers=headers
        )
        task = resp.get_json()["task"]
        assert task["created_by"]["id"] == 1
        assert task["created_by"]["username"] == "testuser"


class TestGetTask:
    def test_get_existing(self, auth_client, headers, sample_task):
        resp = auth_client.get(f"/tasks/{sample_task['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["id"] == sample_task["id"]

    def test_get_nonexistent(self, auth_client, headers):
        resp = auth_client.get("/tasks/99999", headers=headers)
        assert resp.status_code == 404

    def test_get_no_auth(self, client, sample_task):
        resp = client.get(f"/tasks/{sample_task['id']}")
        assert resp.status_code == 401


class TestUpdateTask:
    def test_update_title(self, auth_client, headers, sample_task):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"title": "Updated title"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["title"] == "Updated title"

    def test_update_status(self, auth_client, headers, sample_task):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"status": "completed"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["status"] == "completed"

    def test_update_priority(self, auth_client, headers, sample_task):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"priority": "low"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["priority"] == "low"

    def test_update_due_date(self, auth_client, headers, sample_task):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"due_date": "2027-01-15T12:00:00"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["due_date"] == "2027-01-15T12:00:00"

    def test_update_assignment(self, auth_client, headers, sample_task, second_user_headers):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"assigned_to": 2},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["assigned_to"]["id"] == 2

    def test_update_category(self, auth_client, headers, sample_task, category_id):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"category_id": category_id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["category"]["id"] == category_id

    def test_update_nonexistent(self, auth_client, headers):
        resp = auth_client.put(
            "/tasks/99999",
            json={"title": "Nope"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_update_no_fields(self, auth_client, headers, sample_task):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_update_invalid_status(self, auth_client, headers, sample_task):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"status": "invalid"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_update_empty_title(self, auth_client, headers, sample_task):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"title": ""},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_update_clearing_due_date(self, auth_client, headers, sample_task):
        resp = auth_client.put(
            f"/tasks/{sample_task['id']}",
            json={"due_date": None},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["due_date"] is None

    def test_update_no_auth(self, client, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"title": "Hack"},
        )
        assert resp.status_code == 401


class TestDeleteTask:
    def test_delete_existing(self, auth_client, headers, sample_task):
        resp = auth_client.delete(f"/tasks/{sample_task['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Task deleted"

    def test_delete_nonexistent(self, auth_client, headers):
        resp = auth_client.delete("/tasks/99999", headers=headers)
        assert resp.status_code == 404

    def test_delete_already_deleted(self, auth_client, headers, sample_task):
        auth_client.delete(f"/tasks/{sample_task['id']}", headers=headers)
        resp = auth_client.delete(f"/tasks/{sample_task['id']}", headers=headers)
        assert resp.status_code == 404

    def test_delete_no_auth(self, client, sample_task):
        resp = client.delete(f"/tasks/{sample_task['id']}")
        assert resp.status_code == 401


class TestListTasks:
    def _create_tasks(self, auth_client, headers, count):
        for i in range(count):
            auth_client.post(
                "/tasks",
                json={
                    "title": f"Task {i}",
                    "status": "pending" if i % 2 == 0 else "completed",
                    "priority": "high" if i % 3 == 0 else "medium",
                    "due_date": f"2026-{12 - (i % 12):02d}-{(i % 28) + 1:02d}T00:00:00" if i % 4 != 0 else None,
                },
                headers=headers,
            )

    def test_list_empty(self, auth_client, headers):
        resp = auth_client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["tasks"] == []
        assert data["pagination"]["total"] == 0

    def test_list_with_tasks(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 5)
        resp = auth_client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tasks"]) == 5
        assert data["pagination"]["total"] == 5

    def test_pagination_first_page(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 25)
        resp = auth_client.get("/tasks?page=1&per_page=10", headers=headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 10
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total_pages"] == 3
        assert data["pagination"]["total"] == 25

    def test_pagination_second_page(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 25)
        resp = auth_client.get("/tasks?page=2&per_page=10", headers=headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 10
        assert data["pagination"]["page"] == 2

    def test_pagination_last_page(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 25)
        resp = auth_client.get("/tasks?page=3&per_page=10", headers=headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 5

    def test_pagination_beyond_last(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 5)
        resp = auth_client.get("/tasks?page=10&per_page=10", headers=headers)
        data = resp.get_json()
        assert data["tasks"] == []

    def test_filter_by_status(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 10)
        resp = auth_client.get("/tasks?status=completed", headers=headers)
        data = resp.get_json()
        assert all(t["status"] == "completed" for t in data["tasks"])

    def test_filter_by_priority(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 10)
        resp = auth_client.get("/tasks?priority=high", headers=headers)
        data = resp.get_json()
        assert all(t["priority"] == "high" for t in data["tasks"])

    def test_filter_by_category(self, auth_client, headers, category_id):
        auth_client.post(
            "/tasks",
            json={"title": "Cat task", "category_id": category_id},
            headers=headers,
        )
        resp = auth_client.get(f"/tasks?category_id={category_id}", headers=headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["category"]["id"] == category_id

    def test_filter_by_assigned_to(self, auth_client, headers):
        auth_client.post(
            "/tasks",
            json={"title": "Mine", "assigned_to": 2},
            headers=headers,
        )
        resp = auth_client.get("/tasks?assigned_to=2", headers=headers)
        data = resp.get_json()
        assert all(t["assigned_to"]["id"] == 2 for t in data["tasks"])

    def test_filter_by_created_by(self, auth_client, headers, second_user_headers):
        auth_client.post(
            "/tasks",
            json={"title": "Created by 2"},
            headers=second_user_headers,
        )
        resp = auth_client.get("/tasks?created_by=2", headers=headers)
        data = resp.get_json()
        assert all(t["created_by"]["id"] == 2 for t in data["tasks"])

    def test_search_title(self, auth_client, headers):
        auth_client.post("/tasks", json={"title": "buy groceries"}, headers=headers)
        auth_client.post("/tasks", json={"title": "buy milk"}, headers=headers)
        auth_client.post("/tasks", json={"title": "walk dog"}, headers=headers)
        resp = auth_client.get("/tasks?search=buy", headers=headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 2

    def test_search_description(self, auth_client, headers):
        auth_client.post(
            "/tasks",
            json={"title": "Task A", "description": "important meeting notes"},
            headers=headers,
        )
        auth_client.post(
            "/tasks",
            json={"title": "Task B", "description": "random stuff"},
            headers=headers,
        )
        resp = auth_client.get("/tasks?search=meeting", headers=headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 1

    def test_search_no_match(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 5)
        resp = auth_client.get("/tasks?search=xyznonexistent", headers=headers)
        data = resp.get_json()
        assert data["tasks"] == []

    def test_sort_by_title_asc(self, auth_client, headers):
        auth_client.post("/tasks", json={"title": "Zebra"}, headers=headers)
        auth_client.post("/tasks", json={"title": "Alpha"}, headers=headers)
        resp = auth_client.get("/tasks?sort_by=title&sort_order=asc", headers=headers)
        data = resp.get_json()
        titles = [t["title"] for t in data["tasks"]]
        assert titles == sorted(titles)

    def test_sort_by_status_desc(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 5)
        resp = auth_client.get("/tasks?sort_by=status&sort_order=desc", headers=headers)
        assert resp.status_code == 200

    def test_invalid_sort_field(self, auth_client, headers):
        resp = auth_client.get("/tasks?sort_by=nonexistent", headers=headers)
        assert resp.status_code == 400

    def test_due_before_filter(self, auth_client, headers):
        auth_client.post("/tasks", json={"title": "Old", "due_date": "2025-01-01T00:00:00"}, headers=headers)
        auth_client.post("/tasks", json={"title": "New", "due_date": "2027-01-01T00:00:00"}, headers=headers)
        resp = auth_client.get("/tasks?due_before=2026-01-01T00:00:00", headers=headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Old"

    def test_due_after_filter(self, auth_client, headers):
        auth_client.post("/tasks", json={"title": "Old", "due_date": "2025-01-01T00:00:00"}, headers=headers)
        auth_client.post("/tasks", json={"title": "New", "due_date": "2027-01-01T00:00:00"}, headers=headers)
        resp = auth_client.get("/tasks?due_after=2026-01-01T00:00:00", headers=headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "New"

    def test_combined_filters(self, auth_client, headers, category_id):
        auth_client.post(
            "/tasks",
            json={"title": "Match", "status": "pending", "priority": "high", "category_id": category_id},
            headers=headers,
        )
        auth_client.post(
            "/tasks",
            json={"title": "No match wrong status", "status": "completed", "priority": "high", "category_id": category_id},
            headers=headers,
        )
        resp = auth_client.get(
            f"/tasks?status=pending&priority=high&category_id={category_id}",
            headers=headers,
        )
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Match"

    def test_per_page_capped(self, auth_client, headers):
        self._create_tasks(auth_client, headers, 15)
        resp = auth_client.get("/tasks?per_page=200", headers=headers)
        assert resp.get_json()["pagination"]["per_page"] == 100

    def test_list_no_auth(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401


class TestCategories:
    def test_list_categories(self, auth_client, headers):
        resp = auth_client.get("/categories", headers=headers)
        assert resp.status_code == 200
        cats = resp.get_json()["categories"]
        assert len(cats) >= 7
        names = [c["name"] for c in cats]
        assert "Work" in names
        assert "Personal" in names

    def test_create_category(self, auth_client, headers):
        resp = auth_client.post(
            "/categories",
            json={"name": "Gardening"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.get_json()["category"]["name"] == "Gardening"

    def test_create_duplicate_category(self, auth_client, headers):
        resp = auth_client.post(
            "/categories",
            json={"name": "Work"},
            headers=headers,
        )
        assert resp.status_code == 409

    def test_create_category_no_name(self, auth_client, headers):
        resp = auth_client.post("/categories", json={}, headers=headers)
        assert resp.status_code == 400

    def test_list_categories_no_auth(self, client):
        resp = client.get("/categories")
        assert resp.status_code == 401

    def test_create_category_no_auth(self, client):
        resp = client.post("/categories", json={"name": "Hacking"})
        assert resp.status_code == 401


class TestEdgeCases:
    def test_task_includes_timestamps(self, auth_client, headers, sample_task):
        assert "created_at" in sample_task
        assert "updated_at" in sample_task

    def test_unicode_titles(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "日本語のタスク 🎉 café résumé"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.get_json()["task"]["title"] == "日本語のタスク 🎉 café résumé"

    def test_xss_in_title_not_stripped_by_api(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "<script>alert(1)</script>"},
            headers=headers,
        )
        assert resp.status_code == 201

    def test_due_date_with_timezone(self, auth_client, headers):
        resp = auth_client.post(
            "/tasks",
            json={"title": "TZ", "due_date": "2026-12-31T23:59:59+00:00"},
            headers=headers,
        )
        assert resp.status_code == 201
