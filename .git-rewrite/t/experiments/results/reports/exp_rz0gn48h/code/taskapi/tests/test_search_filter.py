class TestFilterByStatus:
    def test_filter_pending(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Pending", "status": "pending"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Done", "status": "completed"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "In Progress", "status": "in_progress"}, headers=auth_headers)

        resp = client.get("/api/tasks?status=pending", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Pending"

    def test_filter_completed(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Pending", "status": "pending"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Done 1", "status": "completed"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Done 2", "status": "completed"}, headers=auth_headers)

        resp = client.get("/api/tasks?status=completed", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 2


class TestFilterByPriority:
    def test_filter_high(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Low", "priority": "low"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "High 1", "priority": "high"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "High 2", "priority": "high"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Urgent", "priority": "urgent"}, headers=auth_headers)

        resp = client.get("/api/tasks?priority=high", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 2
        assert all(t["priority"] == "high" for t in tasks)


class TestFilterByCategory:
    def test_filter_by_category(self, client, auth_headers):
        cat_resp1 = client.post("/api/categories", json={"name": "frontend"}, headers=auth_headers)
        cat_resp2 = client.post("/api/categories", json={"name": "backend"}, headers=auth_headers)
        cid1 = cat_resp1.get_json()["category"]["id"]
        cid2 = cat_resp2.get_json()["category"]["id"]

        client.post("/api/tasks", json={"title": "FE Task", "category_id": cid1}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "BE Task 1", "category_id": cid2}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "BE Task 2", "category_id": cid2}, headers=auth_headers)

        resp = client.get(f"/api/tasks?category_id={cid2}", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 2
        assert all(t["category_id"] == cid2 for t in tasks)


class TestFilterByAssignment:
    def test_filter_assigned_to_me(self, client, auth_headers, auth_headers2):
        me_resp = client.get("/api/auth/me", headers=auth_headers)
        me_id = me_resp.get_json()["user"]["id"]

        client.post("/api/tasks", json={"title": "My Task", "assigned_to": me_id}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Unassigned"}, headers=auth_headers)

        resp = client.get("/api/tasks?assigned_to=me", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "My Task"

    def test_filter_unassigned(self, client, auth_headers):
        me_resp = client.get("/api/auth/me", headers=auth_headers)
        me_id = me_resp.get_json()["user"]["id"]

        client.post("/api/tasks", json={"title": "My Task", "assigned_to": me_id}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Unassigned 1"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Unassigned 2"}, headers=auth_headers)

        resp = client.get("/api/tasks?assigned_to=unassigned", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 2


class TestFilterByCreator:
    def test_filter_created_by_me(self, client, auth_headers, auth_headers2):
        client.post("/api/tasks", json={"title": "My Creation 1"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "My Creation 2"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Other Creation"}, headers=auth_headers2)

        resp = client.get("/api/tasks?created_by=me", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 2
        for t in tasks:
            assert t["title"] in ("My Creation 1", "My Creation 2")


class TestSearch:
    def test_search_title(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Fix login bug"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Update README"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Bug in dashboard"}, headers=auth_headers)

        resp = client.get("/api/tasks?search=bug", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 2

    def test_search_description(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Task A",
            "description": "Fix database migration issue",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Task B",
            "description": "Write unit tests",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?search=migration", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Task A"

    def test_search_no_results(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Write docs"}, headers=auth_headers)
        resp = client.get("/api/tasks?search=xyzzy_nonexistent", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 0


class TestFilterByDate:
    def test_filter_due_before(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Old Task", "due_date": "2025-01-01T00:00:00",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Future Task", "due_date": "2027-06-01T00:00:00",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?due_before=2026-01-01T00:00:00", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Old Task"

    def test_filter_due_after(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Old Task", "due_date": "2025-01-01T00:00:00",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Future Task", "due_date": "2027-06-01T00:00:00",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?due_after=2027-01-01T00:00:00", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Future Task"


class TestCombinedFilters:
    def test_status_and_priority(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "High Pending", "status": "pending", "priority": "high",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "High Done", "status": "completed", "priority": "high",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Low Pending", "status": "pending", "priority": "low",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?status=pending&priority=high", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["title"] == "High Pending"


class TestSorting:
    def test_sort_by_priority(self, client, auth_headers):
        client.post("/api/tasks", json={"title": "Low", "priority": "low"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "High", "priority": "high"}, headers=auth_headers)
        client.post("/api/tasks", json={"title": "Medium", "priority": "medium"}, headers=auth_headers)

        resp = client.get("/api/tasks?sort_by=priority&sort_dir=asc", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        priorities = [t["priority"] for t in tasks]
        assert priorities == sorted(priorities)

    def test_sort_by_due_date_desc(self, client, auth_headers):
        client.post("/api/tasks", json={
            "title": "Early", "due_date": "2025-01-01T00:00:00",
        }, headers=auth_headers)
        client.post("/api/tasks", json={
            "title": "Late", "due_date": "2027-01-01T00:00:00",
        }, headers=auth_headers)

        resp = client.get("/api/tasks?sort_by=due_date&sort_dir=desc", headers=auth_headers)
        tasks = resp.get_json()["tasks"]
        assert tasks[0]["title"] == "Late"

    def test_invalid_sort_column_falls_back(self, client, auth_headers):
        resp = client.get("/api/tasks?sort_by=nonexistent&sort_dir=invalid", headers=auth_headers)
        assert resp.status_code == 200


class TestEdgeCases:
    def test_create_task_empty_json(self, client, auth_headers):
        resp = client.post("/api/tasks", data="", headers=auth_headers,
                           content_type="application/json")
        assert resp.status_code == 400

    def test_get_tasks_empty_list(self, client, auth_headers):
        resp = client.get("/api/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["tasks"] == []
        assert resp.get_json()["pagination"]["total"] == 0

    def test_404_routes(self, client):
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404

    def test_method_not_allowed(self, client, auth_headers):
        resp = client.patch("/api/auth/login")
        assert resp.status_code == 405
