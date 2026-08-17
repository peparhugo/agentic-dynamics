from tests.conftest import auth_header, get_token


def _seed(client, token):
    tasks = [
        {"title": "Write report", "status": "pending", "priority": "high", "description": "Quarterly summary"},
        {"title": "Call client", "status": "in_progress", "priority": "urgent", "description": "Follow up on deal"},
        {"title": "Review code", "status": "pending", "priority": "medium", "description": "Pull request review"},
        {"title": "File taxes", "status": "completed", "priority": "low", "description": "2025 return"},
        {"title": "Book travel", "status": "completed", "priority": "medium", "description": "Conference trip"},
        {"title": "Plan sprint", "status": "pending", "priority": "high", "description": "Sprint 42 planning"},
        {"title": "Fix bug", "status": "in_progress", "priority": "urgent", "description": "Login crash"},
        {"title": "Draft email", "status": "pending", "priority": "low", "description": "Team announcement"},
        {"title": "Update docs", "status": "completed", "priority": "low", "description": "API reference"},
        {"title": "Run tests", "status": "pending", "priority": "medium", "description": "CI pipeline"},
        {"title": "Deploy release", "status": "in_progress", "priority": "high", "description": "v2.0 rollout"},
        {"title": "Interview candidate", "status": "pending", "priority": "medium", "description": "Backend role"},
    ]
    for t in tasks:
        client.post("/api/tasks", json=t, headers=auth_header(token))


def test_list_tasks_requires_auth(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_list_tasks_pagination(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get("/api/tasks?page=1&per_page=5", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["tasks"]) == 5
    meta = data["meta"]
    assert meta["page"] == 1
    assert meta["per_page"] == 5
    assert meta["total"] == 12
    assert meta["total_pages"] == 3
    assert meta["has_next"] is True
    assert meta["has_prev"] is False


def test_list_tasks_second_page(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get("/api/tasks?page=2&per_page=5", headers=auth_header(token))
    data = resp.get_json()
    assert data["meta"]["page"] == 2
    assert len(data["tasks"]) == 5
    assert data["meta"]["has_prev"] is True


def test_list_tasks_last_page(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get("/api/tasks?page=3&per_page=5", headers=auth_header(token))
    data = resp.get_json()
    assert len(data["tasks"]) == 2
    assert data["meta"]["has_next"] is False


def test_filter_by_status(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get("/api/tasks?status=completed", headers=auth_header(token))
    data = resp.get_json()
    assert data["meta"]["total"] == 3
    assert all(t["status"] == "completed" for t in data["tasks"])


def test_filter_by_priority(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get("/api/tasks?priority=urgent", headers=auth_header(token))
    data = resp.get_json()
    assert data["meta"]["total"] == 2
    assert all(t["priority"] == "urgent" for t in data["tasks"])


def test_filter_invalid_status(client):
    token = get_token(client)
    resp = client.get("/api/tasks?status=bogus", headers=auth_header(token))
    assert resp.status_code == 400


def test_filter_invalid_priority(client):
    token = get_token(client)
    resp = client.get("/api/tasks?priority=bogus", headers=auth_header(token))
    assert resp.status_code == 400


def test_search_by_title(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get("/api/tasks?q=report", headers=auth_header(token))
    data = resp.get_json()
    assert data["meta"]["total"] == 1
    assert data["tasks"][0]["title"] == "Write report"


def test_search_by_description(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get("/api/tasks?q=pull%20request", headers=auth_header(token))
    data = resp.get_json()
    assert data["meta"]["total"] == 1
    assert data["tasks"][0]["title"] == "Review code"


def test_search_case_insensitive(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get("/api/tasks?q=REPORT", headers=auth_header(token))
    data = resp.get_json()
    assert data["meta"]["total"] == 1


def test_combined_filters(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get(
        "/api/tasks?status=pending&priority=high", headers=auth_header(token)
    )
    data = resp.get_json()
    assert data["meta"]["total"] == 2
    assert all(
        t["status"] == "pending" and t["priority"] == "high" for t in data["tasks"]
    )


def test_sort_by_priority_desc(client):
    token = get_token(client)
    _seed(client, token)
    resp = client.get(
        "/api/tasks?sort_by=priority&order=desc&per_page=100",
        headers=auth_header(token),
    )
    tasks = resp.get_json()["tasks"]
    priorities = [t["priority"] for t in tasks]
    order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    assert priorities == sorted(priorities, key=lambda p: order[p])


def test_invalid_sort_by(client):
    token = get_token(client)
    resp = client.get("/api/tasks?sort_by=bogus", headers=auth_header(token))
    assert resp.status_code == 400
