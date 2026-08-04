class TestCategories:
    def test_list_categories_defaults(self, client, auth_headers):
        resp = client.get("/api/categories", headers=auth_headers)
        assert resp.status_code == 200
        categories = resp.get_json()["categories"]
        assert len(categories) == 5
        names = {c["name"] for c in categories}
        assert names == {"bug", "feature", "improvement", "documentation", "testing"}

    def test_create_category(self, client, auth_headers):
        resp = client.post("/api/categories", json={
            "name": "security",
            "description": "Security tasks",
        }, headers=auth_headers)
        assert resp.status_code == 201
        cat = resp.get_json()["category"]
        assert cat["name"] == "security"
        assert cat["description"] == "Security tasks"

    def test_create_duplicate_category(self, client, auth_headers):
        client.post("/api/categories", json={"name": "security"}, headers=auth_headers)
        resp = client.post("/api/categories", json={"name": "security"}, headers=auth_headers)
        assert resp.status_code == 409

    def test_create_category_no_name(self, client, auth_headers):
        resp = client.post("/api/categories", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_delete_category(self, client, auth_headers):
        cat_resp = client.post("/api/categories", json={"name": "tempcat"}, headers=auth_headers)
        cat_id = cat_resp.get_json()["category"]["id"]
        resp = client.delete(f"/api/categories/{cat_id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_delete_nonexistent_category(self, client, auth_headers):
        resp = client.delete("/api/categories/9999", headers=auth_headers)
        assert resp.status_code == 404


class TestTaskCRUD:
    def test_create_task_minimal(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Minimal Task",
        }, headers=auth_headers)
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Minimal Task"
        assert task["status"] == "pending"
        assert task["priority"] == "medium"

    def test_create_task_full(self, client, auth_headers, sample_category):
        resp = client.post("/api/tasks", json={
            "title": "Full Task",
            "description": "All fields set",
            "status": "in_progress",
            "priority": "urgent",
            "category_id": sample_category["id"],
            "due_date": "2026-12-25T00:00:00",
        }, headers=auth_headers)
        assert resp.status_code == 201
        task = resp.get_json()["task"]
        assert task["title"] == "Full Task"
        assert task["status"] == "in_progress"
        assert task["priority"] == "urgent"
        assert task["category_id"] == sample_category["id"]

    def test_create_task_no_title(self, client, auth_headers):
        resp = client.post("/api/tasks", json={"description": "no title"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_task_invalid_status(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad Task",
            "status": "invalid_status",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_task_invalid_priority(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad Task",
            "priority": "critical",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_task_invalid_category(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad Task",
            "category_id": 9999,
        }, headers=auth_headers)
        assert resp.status_code == 404

    def test_create_task_invalid_assigned_user(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "Bad Task",
            "assigned_to": 9999,
        }, headers=auth_headers)
        assert resp.status_code == 404

    def test_get_task(self, client, auth_headers, sample_task):
        resp = client.get(f"/api/tasks/{sample_task['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["task"]["id"] == sample_task["id"]

    def test_get_nonexistent_task(self, client, auth_headers):
        resp = client.get("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_task_partial(self, client, auth_headers, sample_task):
        resp = client.put(f"/api/tasks/{sample_task['id']}", json={
            "status": "completed",
            "priority": "low",
        }, headers=auth_headers)
        assert resp.status_code == 200
        task = resp.get_json()["task"]
        assert task["status"] == "completed"
        assert task["priority"] == "low"
        assert task["title"] == sample_task["title"]

    def test_update_task_all_fields(self, client, auth_headers, sample_task, sample_category, auth_headers2):
        resp = client.put(f"/api/tasks/{sample_task['id']}", json={
            "title": "Updated Title",
            "description": "Updated description",
            "status": "in_progress",
            "priority": "urgent",
            "category_id": sample_category["id"],
            "due_date": "2027-01-01T00:00:00",
        }, headers=auth_headers)
        assert resp.status_code == 200
        task = resp.get_json()["task"]
        assert task["title"] == "Updated Title"
        assert task["description"] == "Updated description"

    def test_update_nonexistent_task(self, client, auth_headers):
        resp = client.put("/api/tasks/99999", json={"title": "nope"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_update_task_empty_title(self, client, auth_headers, sample_task):
        resp = client.put(f"/api/tasks/{sample_task['id']}", json={
            "title": "   ",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_update_task_no_fields(self, client, auth_headers, sample_task):
        resp = client.put(f"/api/tasks/{sample_task['id']}", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_delete_task(self, client, auth_headers, sample_task):
        resp = client.delete(f"/api/tasks/{sample_task['id']}", headers=auth_headers)
        assert resp.status_code == 200
        resp2 = client.get(f"/api/tasks/{sample_task['id']}", headers=auth_headers)
        assert resp2.status_code == 404

    def test_delete_nonexistent_task(self, client, auth_headers):
        resp = client.delete("/api/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestTaskAssignment:
    def test_assign_task(self, client, auth_headers, auth_headers2):
        resp = client.post("/api/tasks", json={
            "title": "Assignable Task",
            "assigned_to": None,
        }, headers=auth_headers)
        task = resp.get_json()["task"]
        assert task["assigned_to"] is None

        resp2 = client.put(f"/api/tasks/{task['id']}", json={
            "assigned_to": None,
        }, headers=auth_headers)
        assert resp2.status_code == 200

    def test_assign_to_self(self, client, auth_headers):
        resp = client.post("/api/tasks", json={
            "title": "My Task",
        }, headers=auth_headers)
        task = resp.get_json()["task"]
        assert task["created_by"] is not None


class TestPagination:
    def test_pagination_defaults(self, client, auth_headers):
        for i in range(25):
            client.post("/api/tasks", json={"title": f"Task {i}"}, headers=auth_headers)

        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tasks"]) == 20
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total"] == 25
        assert data["pagination"]["pages"] == 2

    def test_pagination_page_2(self, client, auth_headers):
        for i in range(25):
            client.post("/api/tasks", json={"title": f"Task {i}"}, headers=auth_headers)

        resp = client.get("/api/tasks?page=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tasks"]) == 5
        assert data["pagination"]["page"] == 2

    def test_pagination_page_size(self, client, auth_headers):
        for i in range(15):
            client.post("/api/tasks", json={"title": f"Task {i}"}, headers=auth_headers)

        resp = client.get("/api/tasks?page_size=5", headers=auth_headers)
        data = resp.get_json()
        assert len(data["tasks"]) == 5
        assert data["pagination"]["pages"] == 3

    def test_pagination_max_page_size(self, client, auth_headers):
        for i in range(150):
            client.post("/api/tasks", json={"title": f"Task {i}"}, headers=auth_headers)

        resp = client.get("/api/tasks?page_size=200", headers=auth_headers)
        data = resp.get_json()
        assert len(data["tasks"]) <= 100

    def test_pagination_invalid_page(self, client, auth_headers):
        resp = client.get("/api/tasks?page=abc&page_size=xyz", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 20


class TestTaskAuth:
    def test_unauthenticated_list(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 401

    def test_unauthenticated_create(self, client):
        resp = client.post("/api/tasks", json={"title": "nope"})
        assert resp.status_code == 401
