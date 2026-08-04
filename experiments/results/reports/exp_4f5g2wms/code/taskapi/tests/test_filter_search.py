import time


class TestListTasksPagination:
    def test_list_tasks_empty(self, client, auth_header):
        resp = client.get("/tasks", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["total"] == 0
        assert data["tasks"] == []

    def test_list_tasks_pagination_defaults(self, client, auth_header, sample_task):
        resp = client.get("/tasks", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total"] >= 1

    def test_list_tasks_per_page(self, client, auth_header):
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header)

        resp = client.get("/tasks?per_page=2", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 2
        assert data["pagination"]["per_page"] == 2
        assert data["pagination"]["total_pages"] == 3

    def test_list_tasks_page_2(self, client, auth_header):
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header)

        resp = client.get("/tasks?per_page=2&page=2", headers=auth_header)
        data = resp.get_json()
        assert data["pagination"]["page"] == 2
        assert len(data["tasks"]) == 2

    def test_list_tasks_page_out_of_range(self, client, auth_header):
        for i in range(3):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header)

        resp = client.get("/tasks?page=999&per_page=10", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 0


class TestListTasksFiltering:
    def test_filter_by_status(self, client, auth_header):
        client.post("/tasks", json={"title": "Pending", "status": "pending"}, headers=auth_header)
        client.post("/tasks", json={"title": "Done", "status": "completed"}, headers=auth_header)

        resp = client.get("/tasks?status=completed", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Done"

    def test_filter_by_priority(self, client, auth_header):
        client.post("/tasks", json={"title": "Low", "priority": "low"}, headers=auth_header)
        client.post("/tasks", json={"title": "Critical", "priority": "critical"}, headers=auth_header)

        resp = client.get("/tasks?priority=critical", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Critical"

    def test_filter_by_category(self, client, auth_header, sample_category, sample_category2):
        client.post(
            "/tasks",
            json={"title": "Cat1 Task", "category_id": sample_category["id"]},
            headers=auth_header,
        )
        client.post(
            "/tasks",
            json={"title": "Cat2 Task", "category_id": sample_category2["id"]},
            headers=auth_header,
        )

        resp = client.get(
            f"/tasks?category_id={sample_category2['id']}", headers=auth_header
        )
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Cat2 Task"

    def test_filter_by_assigned_to(self, client, auth_header, auth_tokens):
        bob_id = auth_tokens["users"]["bob"]["id"]
        charlie_id = auth_tokens["users"]["charlie"]["id"]

        client.post(
            "/tasks",
            json={"title": "Bob's task", "assigned_to": bob_id},
            headers=auth_header,
        )
        client.post(
            "/tasks",
            json={"title": "Charlie's task", "assigned_to": charlie_id},
            headers=auth_header,
        )

        resp = client.get(f"/tasks?assigned_to={bob_id}", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Bob's task"

    def test_filter_combined(self, client, auth_header, sample_category):
        client.post(
            "/tasks",
            json={
                "title": "Match",
                "status": "in_progress",
                "priority": "high",
                "category_id": sample_category["id"],
            },
            headers=auth_header,
        )
        client.post(
            "/tasks",
            json={
                "title": "No match",
                "status": "pending",
                "priority": "high",
                "category_id": sample_category["id"],
            },
            headers=auth_header,
        )

        resp = client.get(
            f"/tasks?status=in_progress&priority=high&category_id={sample_category['id']}",
            headers=auth_header,
        )
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Match"


class TestListTasksSearch:
    def test_search_title(self, client, auth_header):
        client.post("/tasks", json={"title": "Buy groceries"}, headers=auth_header)
        client.post("/tasks", json={"title": "Fix bug"}, headers=auth_header)

        resp = client.get("/tasks?q=groceries", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["title"] == "Buy groceries"

    def test_search_description(self, client, auth_header):
        client.post(
            "/tasks",
            json={"title": "Task A", "description": "Contains keyword alpha"},
            headers=auth_header,
        )
        client.post(
            "/tasks",
            json={"title": "Task B", "description": "Nothing relevant"},
            headers=auth_header,
        )

        resp = client.get("/tasks?q=alpha", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 1

    def test_search_partial_match(self, client, auth_header):
        client.post("/tasks", json={"title": "Deploy microservice"}, headers=auth_header)

        resp = client.get("/tasks?q=micro", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 1

    def test_search_no_results(self, client, auth_header):
        client.post("/tasks", json={"title": "Something"}, headers=auth_header)

        resp = client.get("/tasks?q=zzznotfoundzzz", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) == 0


class TestListTasksSorting:
    def test_sort_by_created_at_desc(self, client, auth_header):
        client.post("/tasks", json={"title": "First"}, headers=auth_header)

        resp = client.get("/tasks?sort_by=created_at&sort_order=desc", headers=auth_header)
        data = resp.get_json()
        assert len(data["tasks"]) >= 1

    def test_sort_by_title_asc(self, client, auth_header):
        client.post("/tasks", json={"title": "B Task"}, headers=auth_header)
        client.post("/tasks", json={"title": "A Task"}, headers=auth_header)

        resp = client.get("/tasks?sort_by=title&sort_order=asc", headers=auth_header)
        data = resp.get_json()
        titles = [t["title"] for t in data["tasks"]]
        assert titles[0] == "A Task"

    def test_sort_by_priority(self, client, auth_header):
        client.post(
            "/tasks", json={"title": "Critical task", "priority": "critical"}, headers=auth_header
        )
        client.post(
            "/tasks", json={"title": "Low task", "priority": "low"}, headers=auth_header
        )

        resp = client.get("/tasks?sort_by=priority&sort_order=asc", headers=auth_header)
        data = resp.get_json()
        priorities = [t["priority"] for t in data["tasks"]]
        assert priorities[0] == "critical"

    def test_sort_invalid_field(self, client, auth_header):
        client.post("/tasks", json={"title": "Test"}, headers=auth_header)
        resp = client.get("/tasks?sort_by=not_a_field&sort_order=asc", headers=auth_header)
        assert resp.status_code == 200


class TestListTasksIsolation:
    def test_user_isolation(self, client, auth_header, bob_header):
        client.post("/tasks", json={"title": "Alice task"}, headers=auth_header)
        client.post("/tasks", json={"title": "Bob task"}, headers=bob_header)

        resp = client.get("/tasks", headers=auth_header)
        data = resp.get_json()
        titles = {t["title"] for t in data["tasks"]}
        assert "Alice task" in titles
        assert "Bob task" not in titles

    def test_unauthenticated(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


class TestTaskCreationEdgeCases:
    def test_create_task_trims_whitespace(self, client, auth_header):
        resp = client.post(
            "/tasks",
            json={"title": "  Padded title  ", "description": "  Padded desc  "},
            headers=auth_header,
        )
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Padded title"
        assert task["description"] == "Padded desc"

    def test_task_has_timestamps(self, client, auth_header):
        resp = client.post("/tasks", json={"title": "Timestamp test"}, headers=auth_header)
        task = resp.get_json()["task"]
        assert task["created_at"] is not None
        assert task["updated_at"] is not None

    def test_update_task_changes_updated_at(self, client, auth_header, sample_task):
        old_updated = sample_task["updated_at"]
        time.sleep(0.1)

        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"title": "Updated timestamp test"},
            headers=auth_header,
        )
        new_updated = resp.get_json()["task"]["updated_at"]
        assert new_updated != old_updated


class TestCategoriesEdgeCases:
    def test_categories_isolated_per_user(self, client, auth_header, bob_header):
        client.post(
            "/categories", json={"name": "Alice Cat"}, headers=auth_header
        )
        client.post(
            "/categories", json={"name": "Bob Cat"}, headers=bob_header
        )

        resp = client.get("/categories", headers=auth_header)
        cat_names = {c["name"] for c in resp.get_json()["categories"]}
        assert "Alice Cat" in cat_names
        assert "Bob Cat" not in cat_names
