def test_list_tasks_empty(client, auth_a):
    res = client.get("/api/tasks", headers=auth_a)
    assert res.status_code == 200
    data = res.get_json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 0
    assert data["pagination"]["page"] == 1


def test_list_tasks_pagination(client, auth_a):
    for i in range(25):
        client.post("/api/tasks", json={"title": f"Task {i}"}, headers=auth_a)

    res = client.get("/api/tasks?page=1&per_page=10", headers=auth_a)
    data = res.get_json()
    assert len(data["items"]) == 10
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["pages"] == 3
    assert data["pagination"]["page"] == 1

    res = client.get("/api/tasks?page=3&per_page=10", headers=auth_a)
    assert len(res.get_json()["items"]) == 5

    res = client.get("/api/tasks?page=9&per_page=10", headers=auth_a)
    assert res.get_json()["items"] == []


def test_list_tasks_invalid_pagination(client, auth_a):
    assert client.get("/api/tasks?page=abc", headers=auth_a).status_code == 400
    assert client.get("/api/tasks?per_page=0", headers=auth_a).status_code == 400
    assert client.get("/api/tasks?per_page=abc", headers=auth_a).status_code == 400


def test_filter_by_status(client, auth_a):
    client.post("/api/tasks", json={"title": "pending one"}, headers=auth_a)
    client.post("/api/tasks", json={"title": "done one", "status": "completed"}, headers=auth_a)
    client.post("/api/tasks", json={"title": "doing one", "status": "in_progress"}, headers=auth_a)

    res = client.get("/api/tasks?status=completed", headers=auth_a)
    data = res.get_json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "done one"
    assert data["pagination"]["total"] == 1


def test_filter_invalid_status(client, auth_a):
    res = client.get("/api/tasks?status=bogus", headers=auth_a)
    assert res.status_code == 400


def test_filter_by_priority(client, auth_a):
    client.post("/api/tasks", json={"title": "low", "priority": "low"}, headers=auth_a)
    client.post("/api/tasks", json={"title": "high", "priority": "high"}, headers=auth_a)

    res = client.get("/api/tasks?priority=high", headers=auth_a)
    assert res.get_json()["pagination"]["total"] == 1
    assert res.get_json()["items"][0]["title"] == "high"


def test_filter_by_category(client, auth_a):
    cat = client.post("/api/categories", json={"name": "Work"}, headers=auth_a).get_json()
    client.post("/api/tasks", json={"title": "in work", "category_id": cat["id"]}, headers=auth_a)
    client.post("/api/tasks", json={"title": "no category"}, headers=auth_a)

    res = client.get(f"/api/tasks?category_id={cat['id']}", headers=auth_a)
    data = res.get_json()
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["title"] == "in work"
    assert data["items"][0]["category"] == "Work"

    res = client.get(f"/api/tasks?category={cat['name']}", headers=auth_a)
    assert res.get_json()["pagination"]["total"] == 1


def test_filter_by_assignee(client, auth_a, user_b, auth_b):
    client.post("/api/tasks", json={"title": "assigned", "assigned_to": user_b["id"]}, headers=auth_a)
    client.post("/api/tasks", json={"title": "unassigned"}, headers=auth_a)

    res = client.get(f"/api/tasks?assigned_to={user_b['id']}", headers=auth_a)
    data = res.get_json()
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["assigned_to"] == user_b["id"]
    assert data["items"][0]["assigned_username"] == "bob"


def test_search(client, auth_a):
    client.post(
        "/api/tasks",
        json={"title": "Fix login bug", "description": "auth flow"},
        headers=auth_a,
    )
    client.post(
        "/api/tasks",
        json={"title": "Add tests", "description": "test everything"},
        headers=auth_a,
    )

    res = client.get("/api/tasks?q=login", headers=auth_a)
    assert res.get_json()["pagination"]["total"] == 1

    res = client.get("/api/tasks?search=everything", headers=auth_a)
    assert res.get_json()["pagination"]["total"] == 1

    res = client.get("/api/tasks?q=nope", headers=auth_a)
    assert res.get_json()["pagination"]["total"] == 0


def test_sorting(client, auth_a):
    for i in range(5):
        client.post("/api/tasks", json={"title": f"Task {i}", "priority": "low"}, headers=auth_a)
    client.post("/api/tasks", json={"title": "Urgent", "priority": "high"}, headers=auth_a)

    res = client.get("/api/tasks?sort=priority&order=asc", headers=auth_a)
    assert res.get_json()["items"][0]["title"] == "Urgent"

    res = client.get("/api/tasks?sort=bogus", headers=auth_a)
    assert res.status_code == 400

    res = client.get("/api/tasks?order=sideways", headers=auth_a)
    assert res.status_code == 400


def test_sort_by_due_date(client, auth_a):
    client.post("/api/tasks", json={"title": "later", "due_date": "2027-06-01"}, headers=auth_a)
    client.post("/api/tasks", json={"title": "sooner", "due_date": "2026-06-01"}, headers=auth_a)
    client.post("/api/tasks", json={"title": "never", "due_date": None}, headers=auth_a)

    res = client.get("/api/tasks?sort=due_date&order=asc", headers=auth_a)
    items = res.get_json()["items"]
    due_dates = [t["due_date"] for t in items if t["due_date"] is not None]
    assert due_dates == sorted(due_dates)


def test_combined_filters(client, auth_a):
    client.post(
        "/api/tasks",
        json={"title": "target", "status": "in_progress", "priority": "high"},
        headers=auth_a,
    )
    client.post(
        "/api/tasks",
        json={"title": "other", "status": "in_progress", "priority": "low"},
        headers=auth_a,
    )

    res = client.get("/api/tasks?status=in_progress&priority=high", headers=auth_a)
    data = res.get_json()
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["title"] == "target"
