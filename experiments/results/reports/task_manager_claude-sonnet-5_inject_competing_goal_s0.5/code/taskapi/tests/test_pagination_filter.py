import pytest

from tests.conftest import auth_headers


@pytest.fixture
def seeded_tasks(client, user_token):
    cat_work = client.post(
        "/api/categories", json={"name": "Work"}, headers=auth_headers(user_token)
    ).get_json()
    cat_home = client.post(
        "/api/categories", json={"name": "Home"}, headers=auth_headers(user_token)
    ).get_json()

    tasks = [
        {"title": "Write report", "status": "todo", "priority": "high", "category_id": cat_work["id"]},
        {"title": "Review PR", "status": "in_progress", "priority": "medium", "category_id": cat_work["id"]},
        {"title": "Clean garage", "status": "todo", "priority": "low", "category_id": cat_home["id"]},
        {"title": "Water plants", "status": "done", "priority": "low", "category_id": cat_home["id"]},
        {"title": "Fix bug urgently", "status": "todo", "priority": "urgent", "category_id": cat_work["id"]},
    ]
    for t in tasks:
        client.post("/api/tasks", json=t, headers=auth_headers(user_token))

    return {"work": cat_work, "home": cat_home}


class TestPagination:
    def test_default_pagination(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 5
        assert data["pagination"]["page"] == 1
        assert len(data["items"]) == 5

    def test_per_page(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?per_page=2", headers=auth_headers(user_token))
        data = resp.get_json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total_pages"] == 3
        assert data["pagination"]["has_next"] is True

    def test_page_two(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?per_page=2&page=2", headers=auth_headers(user_token))
        data = resp.get_json()
        assert len(data["items"]) == 2
        assert data["pagination"]["has_prev"] is True

    def test_per_page_capped_at_max(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?per_page=1000", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["per_page"] == 100

    def test_page_beyond_range_returns_empty(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?page=50", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["items"] == []


class TestFiltering:
    def test_filter_by_status(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?status=todo", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 3
        assert all(t["status"] == "todo" for t in data["items"])

    def test_filter_by_invalid_status(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?status=bogus", headers=auth_headers(user_token))
        assert resp.status_code == 400

    def test_filter_by_priority(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?priority=low", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 2

    def test_filter_by_category(self, client, user_token, seeded_tasks):
        work_id = seeded_tasks["work"]["id"]
        resp = client.get(f"/api/tasks?category_id={work_id}", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 3

    def test_combined_filters(self, client, user_token, seeded_tasks):
        work_id = seeded_tasks["work"]["id"]
        resp = client.get(
            f"/api/tasks?category_id={work_id}&status=todo", headers=auth_headers(user_token)
        )
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 2

    def test_filter_by_assignee(self, client, user_token, second_user_token, seeded_tasks):
        me = client.get("/api/auth/me", headers=auth_headers(second_user_token)).get_json()
        tasks = client.get("/api/tasks", headers=auth_headers(user_token)).get_json()["items"]
        client.post(
            f"/api/tasks/{tasks[0]['id']}/assign",
            json={"assignee_id": me["id"]},
            headers=auth_headers(user_token),
        )
        resp = client.get(f"/api/tasks?assignee_id={me['id']}", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 1


class TestSearch:
    def test_search_by_title(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?search=report", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 1
        assert data["items"][0]["title"] == "Write report"

    def test_search_case_insensitive(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?search=GARAGE", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 1

    def test_search_no_results(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?search=nonexistentterm", headers=auth_headers(user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 0


class TestSorting:
    def test_sort_by_title_asc(self, client, user_token, seeded_tasks):
        resp = client.get("/api/tasks?sort_by=title&sort_dir=asc", headers=auth_headers(user_token))
        titles = [t["title"] for t in resp.get_json()["items"]]
        assert titles == sorted(titles)


class TestVisibilityScope:
    def test_tasks_scoped_to_owner_and_assignee(self, client, user_token, second_user_token, seeded_tasks):
        resp = client.get("/api/tasks", headers=auth_headers(second_user_token))
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 0
