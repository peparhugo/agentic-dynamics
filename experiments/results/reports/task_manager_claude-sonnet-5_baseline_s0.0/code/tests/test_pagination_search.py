import pytest

from tests.conftest import auth_header


def create_task(client, token, **overrides):
    payload = {"title": "Task", "description": "", "priority": "medium", "status": "pending"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=auth_header(token))


@pytest.fixture
def seeded_tasks(client, user_token):
    cat_work = client.post(
        "/api/categories", json={"name": "Work"}, headers=auth_header(user_token)
    ).get_json()["category"]
    cat_home = client.post(
        "/api/categories", json={"name": "Home"}, headers=auth_header(user_token)
    ).get_json()["category"]

    tasks = [
        {"title": "Buy groceries", "description": "milk and eggs", "status": "pending",
         "priority": "low", "category_id": cat_home["id"]},
        {"title": "Finish report", "description": "quarterly numbers", "status": "in_progress",
         "priority": "high", "category_id": cat_work["id"]},
        {"title": "Review PR", "description": "check the auth module", "status": "completed",
         "priority": "medium", "category_id": cat_work["id"]},
        {"title": "Clean garage", "description": "organize tools", "status": "pending",
         "priority": "low", "category_id": cat_home["id"]},
        {"title": "Plan sprint", "description": "backlog grooming", "status": "pending",
         "priority": "high", "category_id": cat_work["id"]},
    ]
    for t in tasks:
        create_task(client, user_token, **t)

    return {"work": cat_work, "home": cat_home}


def test_pagination_default(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks", headers=auth_header(user_token))
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["pagination"]["total"] == 5
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 10
    assert len(data["tasks"]) == 5


def test_pagination_custom_page_size(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?per_page=2&page=1", headers=auth_header(user_token))
    data = resp.get_json()
    assert len(data["tasks"]) == 2
    assert data["pagination"]["pages"] == 3

    resp2 = client.get("/api/tasks?per_page=2&page=2", headers=auth_header(user_token))
    data2 = resp2.get_json()
    assert len(data2["tasks"]) == 2

    ids_page1 = {t["id"] for t in data["tasks"]}
    ids_page2 = {t["id"] for t in data2["tasks"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_pagination_last_page_partial(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?per_page=2&page=3", headers=auth_header(user_token))
    data = resp.get_json()
    assert len(data["tasks"]) == 1


def test_pagination_beyond_range(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?per_page=10&page=99", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["tasks"] == []
    assert data["pagination"]["total"] == 5


def test_filter_by_status(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?status=pending", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total"] == 3
    assert all(t["status"] == "pending" for t in data["tasks"])


def test_filter_by_priority(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?priority=high", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total"] == 2
    assert all(t["priority"] == "high" for t in data["tasks"])


def test_filter_by_category(client, user_token, seeded_tasks):
    work_id = seeded_tasks["work"]["id"]
    resp = client.get(f"/api/tasks?category_id={work_id}", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total"] == 3
    assert all(t["category_id"] == work_id for t in data["tasks"])


def test_filter_invalid_status(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?status=bogus", headers=auth_header(user_token))
    assert resp.status_code == 400


def test_search_by_title(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?q=report", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["tasks"][0]["title"] == "Finish report"


def test_search_by_description(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?q=auth", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["tasks"][0]["title"] == "Review PR"


def test_search_no_match(client, user_token, seeded_tasks):
    resp = client.get("/api/tasks?q=nonexistentterm", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total"] == 0


def test_combined_filters(client, user_token, seeded_tasks):
    work_id = seeded_tasks["work"]["id"]
    resp = client.get(
        f"/api/tasks?status=pending&priority=high&category_id={work_id}",
        headers=auth_header(user_token),
    )
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["tasks"][0]["title"] == "Plan sprint"


def test_tasks_scoped_to_user(client, user_token, other_user_token, seeded_tasks):
    resp = client.get("/api/tasks", headers=auth_header(other_user_token))
    data = resp.get_json()
    assert data["pagination"]["total"] == 0


def test_filter_by_assignee(client, user_token, other_user_token, other_user_id, seeded_tasks):
    task = create_task(client, user_token, title="Assigned task", assignee_id=other_user_id).get_json()["task"]
    resp = client.get(f"/api/tasks?assignee_id={other_user_id}", headers=auth_header(user_token))
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["tasks"][0]["id"] == task["id"]
