import pytest


@pytest.fixture
def seeded_tasks(client, auth_headers):
    work = client.post("/api/categories", json={"name": "Work"}, headers=auth_headers).get_json()
    home = client.post("/api/categories", json={"name": "Home"}, headers=auth_headers).get_json()

    tasks = [
        {"title": "Write quarterly report", "status": "pending", "priority": "high", "category_id": work["id"]},
        {"title": "Fix login bug", "status": "in_progress", "priority": "urgent", "category_id": work["id"]},
        {"title": "Clean the garage", "status": "pending", "priority": "low", "category_id": home["id"]},
        {"title": "Plan vacation", "status": "completed", "priority": "medium", "category_id": home["id"]},
        {"title": "Review pull requests", "status": "pending", "priority": "high", "category_id": work["id"]},
        {"title": "Water the plants", "status": "cancelled", "priority": "low", "category_id": home["id"]},
    ]
    created = []
    for t in tasks:
        resp = client.post("/api/tasks", json=t, headers=auth_headers)
        assert resp.status_code == 201
        created.append(resp.get_json())

    return {"work": work, "home": home, "tasks": created}


def test_pagination_default(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 6
    assert body["page"] == 1
    assert body["per_page"] == 10
    assert body["total_pages"] == 1
    assert len(body["items"]) == 6


def test_pagination_per_page(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?page=1&per_page=2", headers=auth_headers)
    body = resp.get_json()
    assert len(body["items"]) == 2
    assert body["total"] == 6
    assert body["total_pages"] == 3
    assert body["has_next"] is True
    assert body["has_prev"] is False

    resp2 = client.get("/api/tasks?page=3&per_page=2", headers=auth_headers)
    body2 = resp2.get_json()
    assert len(body2["items"]) == 2
    assert body2["has_next"] is False
    assert body2["has_prev"] is True


def test_pagination_invalid_page(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?page=0", headers=auth_headers)
    assert resp.status_code == 400


def test_pagination_per_page_too_large(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?per_page=1000", headers=auth_headers)
    assert resp.status_code == 400


def test_filter_by_status(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?status=pending", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 3
    assert all(item["status"] == "pending" for item in body["items"])


def test_filter_by_invalid_status(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?status=bogus", headers=auth_headers)
    assert resp.status_code == 400


def test_filter_by_priority(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?priority=high", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 2
    assert all(item["priority"] == "high" for item in body["items"])


def test_filter_by_category(client, auth_headers, seeded_tasks):
    home_id = seeded_tasks["home"]["id"]
    resp = client.get(f"/api/tasks?category_id={home_id}", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 3
    assert all(item["category_id"] == home_id for item in body["items"])


def test_filter_combined(client, auth_headers, seeded_tasks):
    work_id = seeded_tasks["work"]["id"]
    resp = client.get(
        f"/api/tasks?category_id={work_id}&status=pending", headers=auth_headers
    )
    body = resp.get_json()
    assert body["total"] == 2
    titles = {item["title"] for item in body["items"]}
    assert titles == {"Write quarterly report", "Review pull requests"}


def test_search_by_title(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?q=report", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Write quarterly report"


def test_search_case_insensitive(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?q=GARAGE", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Clean the garage"


def test_search_no_match(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?q=nonexistentterm", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 0
    assert body["items"] == []


def test_sort_by_title_ascending(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?sort_by=title&order=asc&per_page=10", headers=auth_headers)
    titles = [item["title"] for item in resp.get_json()["items"]]
    assert titles == sorted(titles)


def test_invalid_sort_field(client, auth_headers, seeded_tasks):
    resp = client.get("/api/tasks?sort_by=bogus", headers=auth_headers)
    assert resp.status_code == 400


def test_list_scoped_to_owner_and_assignee(client, auth_headers, second_auth_headers, seeded_tasks):
    resp = client.get("/api/tasks", headers=second_auth_headers)
    body = resp.get_json()
    assert body["total"] == 0
