"""Tests for pagination, search, filtering and sorting of the task list."""
import pytest


@pytest.fixture()
def seeded(client, auth):
    """Create two categories and a mix of tasks for alice."""
    work = client.post("/api/categories", headers=auth,
                       json={"name": "Work"}).get_json()["category"]
    home = client.post("/api/categories", headers=auth,
                       json={"name": "Home"}).get_json()["category"]

    tasks = [
        {"title": "Write report", "status": "todo", "priority": "high",
         "category_id": work["id"], "due_date": "2026-09-01T09:00:00"},
        {"title": "Fix bug in parser", "status": "in_progress",
         "priority": "urgent", "category_id": work["id"],
         "due_date": "2026-08-15T12:00:00"},
        {"title": "Buy groceries", "status": "todo", "priority": "low",
         "category_id": home["id"], "due_date": "2026-08-05T18:00:00"},
        {"title": "Clean garage", "status": "done", "priority": "medium",
         "category_id": home["id"]},
        {"title": "Review report draft", "status": "done", "priority": "high",
         "category_id": work["id"], "due_date": "2026-10-01T09:00:00"},
    ]
    for t in tasks:
        res = client.post("/api/tasks", headers=auth, json=t)
        assert res.status_code == 201
    return {"work": work, "home": home}


class TestFilters:
    def test_filter_by_status(self, client, auth, seeded):
        res = client.get("/api/tasks?status=done", headers=auth)
        body = res.get_json()
        assert body["pagination"]["total"] == 2
        assert all(t["status"] == "done" for t in body["tasks"])

    def test_filter_by_priority(self, client, auth, seeded):
        res = client.get("/api/tasks?priority=high", headers=auth)
        body = res.get_json()
        assert body["pagination"]["total"] == 2
        assert all(t["priority"] == "high" for t in body["tasks"])

    def test_filter_by_category(self, client, auth, seeded):
        work_id = seeded["work"]["id"]
        res = client.get(f"/api/tasks?category_id={work_id}", headers=auth)
        body = res.get_json()
        assert body["pagination"]["total"] == 3
        assert all(t["category_id"] == work_id for t in body["tasks"])

    def test_combined_filters(self, client, auth, seeded):
        work_id = seeded["work"]["id"]
        res = client.get(
            f"/api/tasks?status=done&priority=high&category_id={work_id}",
            headers=auth)
        body = res.get_json()
        assert body["pagination"]["total"] == 1
        assert body["tasks"][0]["title"] == "Review report draft"

    def test_invalid_status_filter(self, client, auth, seeded):
        assert client.get("/api/tasks?status=bogus",
                          headers=auth).status_code == 400

    def test_invalid_priority_filter(self, client, auth, seeded):
        assert client.get("/api/tasks?priority=bogus",
                          headers=auth).status_code == 400

    def test_filter_due_before(self, client, auth, seeded):
        res = client.get("/api/tasks?due_before=2026-08-31T23:59:59",
                         headers=auth)
        titles = {t["title"] for t in res.get_json()["tasks"]}
        assert titles == {"Fix bug in parser", "Buy groceries"}

    def test_filter_due_after(self, client, auth, seeded):
        res = client.get("/api/tasks?due_after=2026-09-01T00:00:00",
                         headers=auth)
        titles = {t["title"] for t in res.get_json()["tasks"]}
        assert titles == {"Write report", "Review report draft"}


class TestSearch:
    def test_search_title(self, client, auth, seeded):
        res = client.get("/api/tasks?search=report", headers=auth)
        titles = {t["title"] for t in res.get_json()["tasks"]}
        assert titles == {"Write report", "Review report draft"}

    def test_search_case_insensitive(self, client, auth, seeded):
        res = client.get("/api/tasks?search=REPORT", headers=auth)
        assert res.get_json()["pagination"]["total"] == 2

    def test_search_description(self, client, auth, seeded):
        client.post("/api/tasks", headers=auth, json={
            "title": "Misc", "description": "contains xyzzy keyword"})
        res = client.get("/api/tasks?search=xyzzy", headers=auth)
        body = res.get_json()
        assert body["pagination"]["total"] == 1
        assert body["tasks"][0]["title"] == "Misc"

    def test_search_no_results(self, client, auth, seeded):
        res = client.get("/api/tasks?search=nonexistentzzz", headers=auth)
        body = res.get_json()
        assert body["tasks"] == []
        assert body["pagination"]["total"] == 0

    def test_search_combined_with_filter(self, client, auth, seeded):
        res = client.get("/api/tasks?search=report&status=todo", headers=auth)
        body = res.get_json()
        assert body["pagination"]["total"] == 1
        assert body["tasks"][0]["title"] == "Write report"


class TestPagination:
    def test_default_pagination(self, client, auth, seeded):
        res = client.get("/api/tasks", headers=auth)
        body = res.get_json()
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["per_page"] == 10
        assert body["pagination"]["total"] == 5
        assert len(body["tasks"]) == 5

    def test_page_size_and_navigation(self, client, auth, seeded):
        res = client.get("/api/tasks?per_page=2&page=1", headers=auth)
        body = res.get_json()
        assert len(body["tasks"]) == 2
        assert body["pagination"]["pages"] == 3
        assert body["pagination"]["has_next"] is True
        assert body["pagination"]["has_prev"] is False

        res = client.get("/api/tasks?per_page=2&page=3", headers=auth)
        body = res.get_json()
        assert len(body["tasks"]) == 1
        assert body["pagination"]["has_next"] is False
        assert body["pagination"]["has_prev"] is True

    def test_pages_do_not_overlap(self, client, auth, seeded):
        ids1 = [t["id"] for t in client.get(
            "/api/tasks?per_page=2&page=1", headers=auth).get_json()["tasks"]]
        ids2 = [t["id"] for t in client.get(
            "/api/tasks?per_page=2&page=2", headers=auth).get_json()["tasks"]]
        assert not set(ids1) & set(ids2)

    def test_out_of_range_page_returns_empty(self, client, auth, seeded):
        res = client.get("/api/tasks?page=99", headers=auth)
        assert res.status_code == 200
        assert res.get_json()["tasks"] == []

    def test_invalid_pagination_params(self, client, auth, seeded):
        assert client.get("/api/tasks?page=0", headers=auth).status_code == 400
        assert client.get("/api/tasks?per_page=0",
                          headers=auth).status_code == 400
        assert client.get("/api/tasks?per_page=101",
                          headers=auth).status_code == 400


class TestSorting:
    def test_sort_by_title_asc(self, client, auth, seeded):
        res = client.get("/api/tasks?sort_by=title&order=asc", headers=auth)
        titles = [t["title"] for t in res.get_json()["tasks"]]
        assert titles == sorted(titles)

    def test_sort_by_due_date_desc(self, client, auth, seeded):
        res = client.get("/api/tasks?sort_by=due_date&order=desc", headers=auth)
        dates = [t["due_date"] for t in res.get_json()["tasks"]
                 if t["due_date"]]
        assert dates == sorted(dates, reverse=True)

    def test_invalid_sort_params(self, client, auth, seeded):
        assert client.get("/api/tasks?sort_by=bogus",
                          headers=auth).status_code == 400
        assert client.get("/api/tasks?order=sideways",
                          headers=auth).status_code == 400


class TestIsolation:
    def test_list_excludes_other_users_tasks(self, client, auth, auth2, seeded):
        client.post("/api/tasks", headers=auth2, json={"title": "Bob task"})
        res = client.get("/api/tasks", headers=auth)
        titles = {t["title"] for t in res.get_json()["tasks"]}
        assert "Bob task" not in titles
        assert res.get_json()["pagination"]["total"] == 5
