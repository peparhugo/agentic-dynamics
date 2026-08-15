import pytest

from tests.conftest import auth_header


@pytest.fixture
def seeded_tasks(client, user_token):
    categories = {}
    for name in ("Work", "Home"):
        resp = client.post("/api/categories", json={"name": name}, headers=auth_header(user_token))
        categories[name] = resp.get_json()["category"]["id"]

    tasks = [
        {"title": "Write report", "status": "pending", "priority": "high", "category_id": categories["Work"]},
        {"title": "Clean garage", "status": "pending", "priority": "low", "category_id": categories["Home"]},
        {"title": "Review budget", "status": "in_progress", "priority": "medium", "category_id": categories["Work"]},
        {"title": "Fix sink", "status": "completed", "priority": "high", "category_id": categories["Home"]},
        {"title": "Plan meeting", "status": "in_progress", "priority": "low", "category_id": categories["Work"]},
        {"title": "Buy groceries", "status": "pending", "priority": "medium", "category_id": categories["Home"]},
    ]
    for payload in tasks:
        resp = client.post("/api/tasks", json=payload, headers=auth_header(user_token))
        assert resp.status_code == 201
    return categories


def test_pagination_default(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks", headers=auth_header(user_token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 6
    assert data["pagination"]["total_items"] == 6
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["has_next"] is False


def test_pagination_custom_page_size(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?per_page=2&page=1", headers=auth_header(user_token))
    data = resp.get_json()
    assert len(data["items"]) == 2
    assert data["pagination"]["total_pages"] == 3
    assert data["pagination"]["has_next"] is True
    assert data["pagination"]["has_prev"] is False


def test_pagination_second_page(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?per_page=2&page=2", headers=auth_header(user_token))
    data = resp.get_json()
    assert len(data["items"]) == 2
    assert data["pagination"]["has_next"] is True
    assert data["pagination"]["has_prev"] is True


def test_pagination_out_of_range_page_returns_empty(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?per_page=2&page=99", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["items"] == []


def test_pagination_per_page_capped_at_max(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?per_page=1000", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["per_page"] == 100


def test_filter_by_status(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?status=pending", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total_items"] == 3
    assert all(t["status"] == "pending" for t in data["items"])


def test_filter_by_priority(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?priority=high", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total_items"] == 2
    assert all(t["priority"] == "high" for t in data["items"])


def test_filter_by_category(client, user_token, seeded_tasks):
    work_id = seeded_tasks["Work"]
    resp = client.get(f"/api/tasks?category_id={work_id}", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total_items"] == 3
    assert all(t["category"]["id"] == work_id for t in data["items"])


def test_filter_invalid_status(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?status=bogus", headers=auth_header(user_token))
    assert resp.status_code == 400


def test_filter_invalid_priority(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?priority=urgent", headers=auth_header(user_token))
    assert resp.status_code == 400


def test_search_by_title(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?q=report", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total_items"] == 1
    assert data["items"][0]["title"] == "Write report"


def test_search_case_insensitive(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?q=REPORT", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total_items"] == 1


def test_search_no_match(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?q=nonexistentterm", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total_items"] == 0


def test_combined_filters(client, user_token, seeded_tasks):
    work_id = seeded_tasks["Work"]
    resp = client.get(
        f"/api/tasks?status=in_progress&category_id={work_id}", headers=auth_header(user_token)
    )
    data = resp.get_json()
    assert data["pagination"]["total_items"] == 2
    assert all(t["status"] == "in_progress" and t["category"]["id"] == work_id for t in data["items"])
