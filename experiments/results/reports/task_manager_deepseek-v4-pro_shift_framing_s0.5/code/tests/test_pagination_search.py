import pytest


@pytest.fixture
def seeded(client, register_and_auth):
    """Create two users, a category, and a batch of tasks; return headers."""
    alice = register_and_auth(client, "alice")
    bob = register_and_auth(client, "bob")

    cat = client.post(
        "/categories", json={"name": "Dev"}, headers=alice
    ).get_json()["category"]
    cat_id = cat["id"]
    bob_id = client.get("/auth/me", headers=bob).get_json()["user"]["id"]

    tasks = [
        {"title": "Write API", "status": "in_progress", "priority": "high",
         "category_id": cat_id, "assignee_id": bob_id, "due_date": "2026-01-01"},
        {"title": "Write tests", "status": "todo", "priority": "medium",
         "category_id": cat_id, "due_date": "2026-02-01"},
        {"title": "Deploy app", "status": "completed", "priority": "low",
         "due_date": "2026-03-01"},
        {"title": "Fix bugs", "status": "todo", "priority": "urgent",
         "category_id": cat_id, "assignee_id": bob_id},
        {"title": "Write docs", "status": "completed", "priority": "medium"},
    ]
    for t in tasks:
        client.post("/tasks", json=t, headers=alice)

    return {"alice": alice, "bob": bob, "category_id": cat_id, "bob_id": bob_id}


def test_pagination_metadata(client, seeded):
    resp = client.get("/tasks?page=1&per_page=2", headers=seeded["alice"])
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 2
    pag = data["pagination"]
    assert pag["total"] == 5
    assert pag["pages"] == 3
    assert pag["page"] == 1
    assert pag["per_page"] == 2
    assert pag["has_next"] is True
    assert pag["has_prev"] is False


def test_pagination_second_page(client, seeded):
    resp = client.get("/tasks?page=3&per_page=2", headers=seeded["alice"])
    data = resp.get_json()
    assert len(data["items"]) == 1
    assert data["pagination"]["has_next"] is False


def test_filter_by_status(client, seeded):
    resp = client.get("/tasks?status=completed", headers=seeded["alice"])
    data = resp.get_json()
    assert data["pagination"]["total"] == 2
    assert all(t["status"] == "completed" for t in data["items"])


def test_filter_by_priority(client, seeded):
    resp = client.get("/tasks?priority=urgent", headers=seeded["alice"])
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["title"] == "Fix bugs"


def test_filter_by_category_id(client, seeded):
    resp = client.get(
        f"/tasks?category_id={seeded['category_id']}", headers=seeded["alice"]
    )
    data = resp.get_json()
    assert data["pagination"]["total"] == 3


def test_filter_by_category_name(client, seeded):
    resp = client.get("/tasks?category=Dev", headers=seeded["alice"])
    data = resp.get_json()
    assert data["pagination"]["total"] == 3
    assert all(t["category"] == "Dev" for t in data["items"])


def test_filter_by_assignee(client, seeded):
    resp = client.get(
        f"/tasks?assignee_id={seeded['bob_id']}", headers=seeded["alice"]
    )
    data = resp.get_json()
    assert data["pagination"]["total"] == 2
    assert all(t["assignee"] == "bob" for t in data["items"])


def test_search_q(client, seeded):
    resp = client.get("/tasks?q=Write", headers=seeded["alice"])
    data = resp.get_json()
    assert data["pagination"]["total"] == 3
    titles = {t["title"] for t in data["items"]}
    assert titles == {"Write API", "Write tests", "Write docs"}


def test_invalid_status_filter(client, seeded):
    resp = client.get("/tasks?status=bogus", headers=seeded["alice"])
    assert resp.status_code == 400


def test_invalid_priority_filter(client, seeded):
    resp = client.get("/tasks?priority=bogus", headers=seeded["alice"])
    assert resp.status_code == 400


def test_sort_by_due_date_asc(client, seeded):
    resp = client.get("/tasks?sort_by=due_date&order=asc", headers=seeded["alice"])
    data = resp.get_json()
    dates = [t["due_date"] for t in data["items"] if t["due_date"]]
    assert dates == sorted(dates)
    # null due_dates come first in ascending order (SQLite) so just check sorted subset
    assert data["items"][0]["due_date"] is None
