def _seed(auth_client):
    auth_client.post("/api/categories", json={"name": "work"})
    auth_client.post("/api/categories", json={"name": "personal"})
    auth_client.post(
        "/api/tasks",
        json={"title": "Design API", "description": "Design the REST API", "status": "in_progress", "priority": "high", "category": "work", "due_date": "2026-09-01"},
    )
    auth_client.post(
        "/api/tasks",
        json={"title": "Buy milk", "description": "pickup groceries", "status": "todo", "priority": "low", "category": "personal", "due_date": "2026-09-05"},
    )
    auth_client.post(
        "/api/tasks",
        json={"title": "Fix bug", "description": "resolve the crash", "status": "done", "priority": "urgent", "category": "work"},
    )


def test_filter_by_status(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?status=done").get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Fix bug"


def test_filter_by_priority(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?priority=high").get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Design API"


def test_filter_by_category(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?category=personal").get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Buy milk"


def test_search_matches_title(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?q=Design").get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Design API"


def test_search_matches_description(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?q=crash").get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Fix bug"


def test_search_no_match(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?q=zzzz").get_json()
    assert body["items"] == []


def test_filter_by_assignee(auth_client, make_user):
    make_user("zoe")
    auth_client.post("/api/tasks", json={"title": "Mine", "assignee": "zoe"})
    auth_client.post("/api/tasks", json={"title": "Not mine"})
    body = auth_client.get("/api/tasks?assignee=zoe").get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Mine"


def test_filter_due_before(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?due_before=2026-09-03").get_json()
    titles = {t["title"] for t in body["items"]}
    assert titles == {"Design API"}


def test_filter_due_after(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?due_after=2026-09-02").get_json()
    titles = {t["title"] for t in body["items"]}
    assert titles == {"Buy milk"}


def test_archived_excluded_by_default(auth_client):
    auth_client.post("/api/tasks", json={"title": "Visible"})
    auth_client.post("/api/tasks", json={"title": "Hidden", "archived": True})
    body = auth_client.get("/api/tasks").get_json()
    titles = {t["title"] for t in body["items"]}
    assert "Hidden" not in titles
    assert "Visible" in titles


def test_archived_filter_includes_archived(auth_client):
    auth_client.post("/api/tasks", json={"title": "Visible"})
    auth_client.post("/api/tasks", json={"title": "Hidden", "archived": True})
    body = auth_client.get("/api/tasks?archived=true").get_json()
    titles = {t["title"] for t in body["items"]}
    assert titles == {"Hidden"}


def test_combined_filters(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?category=work&priority=urgent&status=done").get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Fix bug"


def test_sort_by_due_date_ascending(auth_client):
    _seed(auth_client)
    body = auth_client.get("/api/tasks?sort=due_date&order=asc").get_json()
    due_dates = [t["due_date"] for t in body["items"] if t["due_date"]]
    assert due_dates == sorted(due_dates)


def test_invalid_status_filter(auth_client):
    response = auth_client.get("/api/tasks?status=bogus")
    assert response.status_code == 400


def test_invalid_sort_filter(auth_client):
    response = auth_client.get("/api/tasks?sort=banana")
    assert response.status_code == 400


def test_invalid_due_date_filter(auth_client):
    response = auth_client.get("/api/tasks?due_before=not-a-date")
    assert response.status_code == 400
