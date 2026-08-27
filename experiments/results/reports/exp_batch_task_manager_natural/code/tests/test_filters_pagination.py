import pytest


@pytest.fixture
def seeded(client, auth_headers):
    c1 = client.post(
        "/api/categories", json={"name": "Work"}, headers=auth_headers
    ).get_json()
    c2 = client.post(
        "/api/categories", json={"name": "Home"}, headers=auth_headers
    ).get_json()

    tasks = [
        {"title": "Fix login bug", "status": "todo", "priority": "high", "category_id": c1["id"]},
        {"title": "Write report", "status": "in_progress", "priority": "medium", "category_id": c1["id"]},
        {"title": "Buy groceries", "status": "done", "priority": "low", "category_id": c2["id"]},
        {"title": "Plan vacation", "status": "todo", "priority": "low", "category_id": c2["id"]},
        {"title": "Deploy release", "status": "done", "priority": "urgent", "category_id": c1["id"]},
    ]
    for t in tasks:
        client.post("/api/tasks", json=t, headers=auth_headers)
    return {"work": c1, "home": c2}


def test_filter_by_status(client, auth_headers, seeded):
    resp = client.get("/api/tasks?status=todo", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 2
    assert all(t["status"] == "todo" for t in body["tasks"])


def test_filter_by_invalid_status(client, auth_headers, seeded):
    resp = client.get("/api/tasks?status=bogus", headers=auth_headers)
    assert resp.status_code == 400


def test_filter_by_priority(client, auth_headers, seeded):
    resp = client.get("/api/tasks?priority=high", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["tasks"][0]["title"] == "Fix login bug"


def test_filter_by_category_id(client, auth_headers, seeded):
    resp = client.get(
        f"/api/tasks?category_id={seeded['work']['id']}", headers=auth_headers
    )
    body = resp.get_json()
    assert body["total"] == 3


def test_filter_by_category_name(client, auth_headers, seeded):
    resp = client.get("/api/tasks?category=Home", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 2
    assert all(t["category"]["name"] == "Home" for t in body["tasks"])


def test_filter_by_assignee(client, auth_headers, seeded):
    client.post(
        "/api/tasks",
        json={"title": "Assigned task", "assignee_id": 1},
        headers=auth_headers,
    )
    resp = client.get("/api/tasks?assignee_id=1", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["tasks"][0]["title"] == "Assigned task"


def test_search(client, auth_headers, seeded):
    resp = client.get("/api/tasks?search=report", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["tasks"][0]["title"] == "Write report"


def test_combined_filters(client, auth_headers, seeded):
    resp = client.get("/api/tasks?status=done&priority=urgent", headers=auth_headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["tasks"][0]["title"] == "Deploy release"


def test_pagination(client, auth_headers, seeded):
    resp = client.get("/api/tasks?page=1&per_page=2", headers=auth_headers)
    body = resp.get_json()
    assert body["page"] == 1
    assert body["per_page"] == 2
    assert body["total"] == 5
    assert body["pages"] == 3
    assert body["has_next"] is True
    assert body["has_prev"] is False
    assert len(body["tasks"]) == 2


def test_pagination_second_page(client, auth_headers, seeded):
    resp = client.get("/api/tasks?page=2&per_page=2", headers=auth_headers)
    body = resp.get_json()
    assert body["page"] == 2
    assert body["has_next"] is True
    assert body["has_prev"] is True
    assert len(body["tasks"]) == 2


def test_pagination_last_page(client, auth_headers, seeded):
    resp = client.get("/api/tasks?page=3&per_page=2", headers=auth_headers)
    body = resp.get_json()
    assert body["page"] == 3
    assert body["has_next"] is False
    assert len(body["tasks"]) == 1


def test_pagination_out_of_range(client, auth_headers, seeded):
    resp = client.get("/api/tasks?page=99&per_page=2", headers=auth_headers)
    body = resp.get_json()
    assert body["tasks"] == []
    assert body["total"] == 5


def test_pagination_invalid_params(client, auth_headers, seeded):
    resp = client.get("/api/tasks?page=abc&per_page=xyz", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["page"] == 1


def test_task_assignment_roundtrip(client, auth_headers):
    client.post(
        "/api/auth/register",
        json={"username": "mallory", "email": "mallory@example.com", "password": "secret123"},
    )
    created = client.post(
        "/api/tasks",
        json={"title": "Assign me", "assignee_id": 2},
        headers=auth_headers,
    ).get_json()
    assert created["assignee"]["username"] == "mallory"
    assert created["assignee"]["email"] == "mallory@example.com"

    resp = client.get("/api/tasks?assignee=mallory", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 1


def test_filter_by_due_date(client, auth_headers):
    client.post(
        "/api/tasks",
        json={"title": "Early task", "due_date": "2026-01-01T00:00:00+00:00"},
        headers=auth_headers,
    )
    client.post(
        "/api/tasks",
        json={"title": "Late task", "due_date": "2026-12-01T00:00:00+00:00"},
        headers=auth_headers,
    )
    resp = client.get(
        "/api/tasks?due_before=2026-06-01T00:00:00Z", headers=auth_headers
    )
    body = resp.get_json()
    assert body["total"] == 1
    assert body["tasks"][0]["title"] == "Early task"

    resp = client.get(
        "/api/tasks?due_after=2026-06-01T00:00:00Z", headers=auth_headers
    )
    body = resp.get_json()
    assert body["total"] == 1
    assert body["tasks"][0]["title"] == "Late task"
