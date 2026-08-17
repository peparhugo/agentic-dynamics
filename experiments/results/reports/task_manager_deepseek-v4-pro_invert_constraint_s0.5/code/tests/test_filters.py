def _seed(client, make_user, auth_headers):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")
    carol = make_user("carol", "carol@example.com")
    h = auth_headers(alice)

    tasks = [
        {"title": "Design homepage", "status": "todo", "priority": "high", "category": "design"},
        {"title": "Write API docs", "status": "in_progress", "priority": "medium", "category": "docs"},
        {"title": "Fix login bug", "status": "done", "priority": "urgent", "category": "backend"},
        {"title": "Plan sprint", "status": "todo", "priority": "low", "category": "backend"},
        {"title": "Review pull requests", "status": "in_progress", "priority": "high", "category": "backend"},
        {"title": "Deploy release", "status": "done", "priority": "medium", "category": "ops"},
    ]
    created = []
    for i, t in enumerate(tasks):
        assigned = bob if i % 2 == 0 else None
        created.append(client.post("/api/tasks", json={**t, "assigned_to": assigned}, headers=h).get_json()["id"])

    return alice, bob, carol, h, created


def test_list_tasks_pagination(client, make_user, auth_headers):
    _, _, _, h, _ = _seed(client, make_user, auth_headers)
    resp = client.get("/api/tasks?per_page=2&page=1", headers=h)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 6
    assert data["pages"] == 3
    assert data["page"] == 1
    assert data["per_page"] == 2
    assert len(data["items"]) == 2

    page2 = client.get("/api/tasks?per_page=2&page=2", headers=h).get_json()
    assert len(page2["items"]) == 2


def test_filter_by_status(client, make_user, auth_headers):
    _, _, _, h, _ = _seed(client, make_user, auth_headers)
    resp = client.get("/api/tasks?status=done", headers=h)
    data = resp.get_json()
    assert data["total"] == 2
    assert all(t["status"] == "done" for t in data["items"])


def test_filter_by_multiple_statuses(client, make_user, auth_headers):
    _, _, _, h, _ = _seed(client, make_user, auth_headers)
    resp = client.get("/api/tasks?status=todo,done", headers=h)
    data = resp.get_json()
    assert data["total"] == 4


def test_filter_by_priority(client, make_user, auth_headers):
    _, _, _, h, _ = _seed(client, make_user, auth_headers)
    resp = client.get("/api/tasks?priority=high", headers=h)
    data = resp.get_json()
    assert data["total"] == 2
    assert all(t["priority"] == "high" for t in data["items"])


def test_filter_by_category(client, make_user, auth_headers):
    _, _, _, h, _ = _seed(client, make_user, auth_headers)
    resp = client.get("/api/tasks?category=backend", headers=h)
    data = resp.get_json()
    assert data["total"] == 3


def test_filter_by_assigned_to(client, make_user, auth_headers):
    _, bob, _, h, _ = _seed(client, make_user, auth_headers)
    resp = client.get(f"/api/tasks?assigned_to={bob}", headers=h)
    data = resp.get_json()
    assert data["total"] == 3
    assert all(t["assigned_to"] == bob for t in data["items"])


def test_search(client, make_user, auth_headers):
    _, _, _, h, _ = _seed(client, make_user, auth_headers)
    resp = client.get("/api/tasks?q=login", headers=h)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Fix login bug"


def test_sorting(client, make_user, auth_headers):
    _, _, _, h, _ = _seed(client, make_user, auth_headers)
    resp = client.get("/api/tasks?sort=title&order=asc", headers=h)
    data = resp.get_json()
    titles = [t["title"] for t in data["items"]]
    assert titles == sorted(titles)


def test_list_tasks_requires_auth(client):
    assert client.get("/api/tasks").status_code == 401


def test_meta_endpoint(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "todo" in data["statuses"]
    assert "urgent" in data["priorities"]
