def _seed(client, headers):
    tasks = [
        {"title": "Alpha task", "status": "pending", "priority": "low", "category": "work"},
        {"title": "Beta task", "status": "in_progress", "priority": "high", "category": "home"},
        {"title": "Gamma task", "status": "completed", "priority": "urgent", "category": "work"},
        {"title": "Delta task", "status": "pending", "priority": "medium", "category": "personal"},
    ]
    for t in tasks:
        client.post("/tasks", json=t, headers=headers)


def test_pagination(client, auth_headers):
    headers, _ = auth_headers
    _seed(client, headers)
    resp = client.get("/tasks?page=1&per_page=2", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 2
    assert data["total"] == 4
    assert data["pages"] == 2
    assert data["per_page"] == 2


def test_filter_by_status(client, auth_headers):
    headers, _ = auth_headers
    _seed(client, headers)
    resp = client.get("/tasks?status=pending", headers=headers)
    data = resp.get_json()
    assert data["total"] == 2
    assert all(t["status"] == "pending" for t in data["items"])


def test_filter_by_priority(client, auth_headers):
    headers, _ = auth_headers
    _seed(client, headers)
    resp = client.get("/tasks?priority=urgent", headers=headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Gamma task"


def test_filter_by_category(client, auth_headers):
    headers, _ = auth_headers
    _seed(client, headers)
    resp = client.get("/tasks?category=work", headers=headers)
    data = resp.get_json()
    assert data["total"] == 2
    assert all(t["category"] == "work" for t in data["items"])


def test_search(client, auth_headers):
    headers, _ = auth_headers
    _seed(client, headers)
    resp = client.get("/tasks?q=beta", headers=headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Beta task"


def test_search_description(client, auth_headers):
    headers, _ = auth_headers
    client.post(
        "/tasks",
        json={"title": "Unique", "description": "contains needle in haystack"},
        headers=headers,
    )
    resp = client.get("/tasks?q=needle", headers=headers)
    data = resp.get_json()
    assert data["total"] == 1


def test_filter_by_assignee(client, auth_headers, second_user):
    headers, _ = auth_headers
    client.post("/tasks", json={"title": "Assigned", "assignee_id": second_user["id"]}, headers=headers)
    client.post("/tasks", json={"title": "Unassigned"}, headers=headers)
    resp = client.get(f"/tasks?assignee_id={second_user['id']}", headers=headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Assigned"


def test_combined_filters(client, auth_headers):
    headers, _ = auth_headers
    _seed(client, headers)
    resp = client.get("/tasks?status=pending&category=work", headers=headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Alpha task"
