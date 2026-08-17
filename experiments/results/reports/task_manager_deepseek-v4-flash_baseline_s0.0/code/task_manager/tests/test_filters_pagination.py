def _create(client, headers, **kwargs):
    payload = {
        "title": kwargs.get("title", "Sample task"),
        "description": kwargs.get("description", "A sample description"),
        "status": kwargs.get("status", "todo"),
        "priority": kwargs.get("priority", "medium"),
    }
    if "due_date" in kwargs:
        payload["due_date"] = kwargs["due_date"]
    if "category_id" in kwargs:
        payload["category_id"] = kwargs["category_id"]
    if "assignee_id" in kwargs:
        payload["assignee_id"] = kwargs["assignee_id"]
    response = client.post("/api/tasks", json=payload, headers=headers)
    assert response.status_code == 201
    return response.get_json()


def test_filter_by_status(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="Todo task", status="todo")
    _create(client, headers, title="In progress task", status="in_progress")
    _create(client, headers, title="Done task", status="done")

    response = client.get("/api/tasks?status=done", headers=headers)
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Done task"

    response = client.get("/api/tasks?status=in_progress", headers=headers)
    assert len(response.get_json()["items"]) == 1


def test_filter_by_status_invalid(client, user_token):
    token, headers = user_token()
    response = client.get("/api/tasks?status=blocked", headers=headers)
    assert response.status_code == 400


def test_filter_by_priority(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="Low", priority="low")
    _create(client, headers, title="High", priority="high")
    _create(client, headers, title="Med", priority="medium")

    response = client.get("/api/tasks?priority=high", headers=headers)
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "High"

    response = client.get("/api/tasks?priority=urgent", headers=headers)
    assert response.status_code == 400


def test_filter_by_category(client, user_token):
    token, headers = user_token()
    cat = client.post("/api/categories", json={"name": "Engineering"}, headers=headers).get_json()
    _create(client, headers, title="With category", category_id=cat["id"])
    _create(client, headers, title="Without category")

    response = client.get(f"/api/tasks?category={cat['id']}", headers=headers)
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "With category"

    response = client.get("/api/tasks?category=engineering", headers=headers)
    assert len(response.get_json()["items"]) == 1


def test_filter_by_assignee(client, user_token, register_user):
    token, headers = user_token()
    bob = register_user(username="bob", email="bob@example.com")
    carol = register_user(username="carol", email="carol@example.com")

    _create(client, headers, title="Bob's task", assignee_id=bob["user"]["id"])
    _create(client, headers, title="Carol's task", assignee_id=carol["user"]["id"])
    _create(client, headers, title="Unassigned")

    response = client.get(f"/api/tasks?assignee_id={bob['user']['id']}", headers=headers)
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Bob's task"

    response = client.get("/api/tasks?assignee_id=notanumber", headers=headers)
    assert response.status_code == 400


def test_filter_by_creator(client, user_token, register_user):
    token, headers = user_token()
    _create(client, headers, title="Alice task")

    bob = register_user(username="bob", email="bob@example.com")
    bob_headers = {"Authorization": f"Bearer {bob['token']}"}
    _create(client, bob_headers, title="Bob task")

    response = client.get("/api/tasks", headers=headers)
    assert response.get_json()["pagination"]["total"] == 2

    response = client.get(
        f"/api/tasks?created_by={bob['user']['id']}", headers=bob_headers
    )
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Bob task"


def test_search_by_title_and_description(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="Pay invoices", description="Accounts payable work")
    _create(client, headers, title="Book flights", description="Holiday travel")
    _create(client, headers, title="File tax returns")

    response = client.get("/api/tasks?search=invoices", headers=headers)
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Pay invoices"

    response = client.get("/api/tasks?search=holiday", headers=headers)
    assert len(response.get_json()["items"]) == 1

    response = client.get("/api/tasks?search=doesnotexist", headers=headers)
    assert response.get_json()["items"] == []


def test_filter_by_due_date(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="Early", due_date="2026-01-15")
    _create(client, headers, title="Middle", due_date="2026-06-15")
    _create(client, headers, title="Late", due_date="2026-12-31")
    _create(client, headers, title="No due date")

    response = client.get("/api/tasks?due_before=2026-03-01", headers=headers)
    assert [t["title"] for t in response.get_json()["items"]] == ["Early"]

    response = client.get("/api/tasks?due_after=2026-07-01", headers=headers)
    assert [t["title"] for t in response.get_json()["items"]] == ["Late"]

    response = client.get(
        "/api/tasks?due_after=2026-01-01&due_before=2027-01-01", headers=headers
    )
    assert len(response.get_json()["items"]) == 3

    response = client.get("/api/tasks?due_before=notadate", headers=headers)
    assert response.status_code == 400


def test_overdue_filter(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="Overdue todo", due_date="2020-01-01")
    _create(client, headers, title="Overdue done", due_date="2020-01-01", status="done")
    _create(client, headers, title="Future", due_date="2030-01-01")

    response = client.get("/api/tasks?overdue=true", headers=headers)
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Overdue todo"


def test_combined_filters(client, user_token):
    token, headers = user_token()
    cat = client.post("/api/categories", json={"name": "Ops"}, headers=headers).get_json()
    _create(client, headers, title="Match", status="in_progress", priority="high", category_id=cat["id"])
    _create(client, headers, title="Wrong status", status="todo", priority="high", category_id=cat["id"])
    _create(client, headers, title="Wrong category", status="in_progress", priority="high")

    response = client.get(
        f"/api/tasks?status=in_progress&priority=high&category={cat['id']}", headers=headers
    )
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Match"


def test_pagination(client, user_token):
    token, headers = user_token()
    for i in range(25):
        _create(client, headers, title=f"Task {i:02d}")

    response = client.get("/api/tasks?per_page=10&page=1", headers=headers)
    body = response.get_json()
    assert len(body["items"]) == 10
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["per_page"] == 10
    assert body["pagination"]["total"] == 25
    assert body["pagination"]["pages"] == 3
    assert body["pagination"]["prev"] is None
    assert body["pagination"]["next"] is not None
    assert "page=2" in body["pagination"]["next"]

    response = client.get("/api/tasks?per_page=10&page=3", headers=headers)
    body = response.get_json()
    assert len(body["items"]) == 5
    assert body["pagination"]["next"] is None
    assert body["pagination"]["prev"] is not None

    response = client.get("/api/tasks?per_page=10&page=50", headers=headers)
    body = response.get_json()
    assert body["items"] == []
    assert body["pagination"]["total"] == 25


def test_pagination_validation_and_clamping(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="One task")

    response = client.get("/api/tasks?per_page=abc", headers=headers)
    assert response.status_code == 400

    response = client.get("/api/tasks?page=0", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["pagination"]["page"] == 1

    response = client.get("/api/tasks?per_page=100000", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["pagination"]["per_page"] == 100


def test_pagination_pages_are_distinct(client, user_token):
    token, headers = user_token()
    for i in range(15):
        _create(client, headers, title=f"Task {i:02d}")

    page1_ids = {t["id"] for t in client.get("/api/tasks?page=1&per_page=5", headers=headers).get_json()["items"]}
    page2_ids = {t["id"] for t in client.get("/api/tasks?page=2&per_page=5", headers=headers).get_json()["items"]}
    page3_ids = {t["id"] for t in client.get("/api/tasks?page=3&per_page=5", headers=headers).get_json()["items"]}
    assert page1_ids.isdisjoint(page2_ids)
    assert page2_ids.isdisjoint(page3_ids)
    assert len(page1_ids | page2_ids | page3_ids) == 15


def test_sort_by_created_at_desc_default(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="First")
    _create(client, headers, title="Second")
    response = client.get("/api/tasks", headers=headers)
    titles = [t["title"] for t in response.get_json()["items"]]
    assert titles == ["Second", "First"]

    response = client.get("/api/tasks?order=asc", headers=headers)
    titles = [t["title"] for t in response.get_json()["items"]]
    assert titles == ["First", "Second"]


def test_sort_by_due_date(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="Late", due_date="2026-12-31")
    _create(client, headers, title="No date")
    _create(client, headers, title="Early", due_date="2026-01-01")

    response = client.get("/api/tasks?sort=due_date&order=asc", headers=headers)
    titles = [t["title"] for t in response.get_json()["items"]]
    assert titles[0] == "Early"
    assert titles[1] == "Late"
    assert titles[2] == "No date"


def test_sort_by_priority(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="High", priority="high")
    _create(client, headers, title="Low", priority="low")
    _create(client, headers, title="Medium", priority="medium")

    response = client.get("/api/tasks?sort=priority&order=asc", headers=headers)
    titles = [t["title"] for t in response.get_json()["items"]]
    assert titles == ["Low", "Medium", "High"]

    response = client.get("/api/tasks?sort=priority&order=desc", headers=headers)
    titles = [t["title"] for t in response.get_json()["items"]]
    assert titles == ["High", "Medium", "Low"]


def test_sort_by_title(client, user_token):
    token, headers = user_token()
    _create(client, headers, title="banana")
    _create(client, headers, title="apple")
    _create(client, headers, title="cherry")

    response = client.get("/api/tasks?sort=title&order=asc", headers=headers)
    titles = [t["title"] for t in response.get_json()["items"]]
    assert titles == ["apple", "banana", "cherry"]


def test_invalid_sort_param(client, user_token):
    token, headers = user_token()
    response = client.get("/api/tasks?sort=bogus", headers=headers)
    assert response.status_code == 400

    response = client.get("/api/tasks?order=sideways", headers=headers)
    assert response.status_code == 400
