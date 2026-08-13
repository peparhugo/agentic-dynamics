"""
Tests for cursor-based pagination on GET /tasks.
"""

import pytest

from tasks_api import create_app

RATE_LIMIT_STORAGE_URI = "redis://localhost:6379/2"


@pytest.fixture
def app(tmp_path):
    storage_path = tmp_path / "tasks.json"
    users_storage_path = tmp_path / "users.json"
    app = create_app(
        storage_path=str(storage_path),
        users_storage_path=str(users_storage_path),
        rate_limit_storage_uri=RATE_LIMIT_STORAGE_URI,
        rate_limit="1000 per minute",
    )
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client):
    register(client)
    return login(client).get_json()["token"]


@pytest.fixture
def auth(token):
    return auth_headers(token)


def create_task(client, auth, title):
    return client.post("/tasks", json={"title": title}, headers=auth)


def create_tasks(client, auth, count):
    return [create_task(client, auth, f"Task {i}").get_json() for i in range(count)]


# ── Response shape ────────────────────────────────────────────────

def test_list_tasks_response_has_data_next_cursor_and_total(client, auth):
    create_tasks(client, auth, 3)
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert body["total"] == 3
    assert body["next_cursor"] is None
    assert len(body["data"]) == 3


def test_list_tasks_empty_returns_empty_page(client, auth):
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json() == {"data": [], "next_cursor": None, "total": 0}


# ── Default limit ─────────────────────────────────────────────────

def test_default_limit_is_20(client, auth):
    create_tasks(client, auth, 25)
    resp = client.get("/tasks", headers=auth)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] == body["data"][-1]["id"]


# ── Custom limit ──────────────────────────────────────────────────

def test_custom_limit_is_respected(client, auth):
    create_tasks(client, auth, 10)
    resp = client.get("/tasks?limit=5", headers=auth)
    body = resp.get_json()
    assert len(body["data"]) == 5
    assert body["next_cursor"] == body["data"][-1]["id"]


def test_limit_above_max_returns_400(client, auth):
    resp = client.get("/tasks?limit=101", headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_limit_of_100_is_allowed(client, auth):
    create_tasks(client, auth, 5)
    resp = client.get("/tasks?limit=100", headers=auth)
    assert resp.status_code == 200
    assert len(resp.get_json()["data"]) == 5


def test_limit_below_1_returns_400(client, auth):
    resp = client.get("/tasks?limit=0", headers=auth)
    assert resp.status_code == 400


def test_non_integer_limit_returns_400(client, auth):
    resp = client.get("/tasks?limit=abc", headers=auth)
    assert resp.status_code == 400


# ── Cursor traversal ──────────────────────────────────────────────

def test_cursor_returns_next_page(client, auth):
    tasks = create_tasks(client, auth, 25)  # ids 1..25, newest (25) first
    first_page = client.get("/tasks?limit=20", headers=auth).get_json()
    cursor = first_page["next_cursor"]
    assert cursor is not None

    second_page = client.get(f"/tasks?cursor={cursor}&limit=20", headers=auth).get_json()
    assert len(second_page["data"]) == 5
    assert second_page["next_cursor"] is None
    assert second_page["total"] == 25

    # No overlap between pages.
    first_ids = {t["id"] for t in first_page["data"]}
    second_ids = {t["id"] for t in second_page["data"]}
    assert first_ids.isdisjoint(second_ids)
    assert first_ids | second_ids == {t["id"] for t in tasks}


def test_full_traversal_yields_all_tasks_without_duplicates(client, auth):
    created = create_tasks(client, auth, 47)
    seen_ids = []
    cursor = None
    while True:
        url = "/tasks?limit=10" + (f"&cursor={cursor}" if cursor is not None else "")
        body = client.get(url, headers=auth).get_json()
        seen_ids.extend(t["id"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen_ids) == len(set(seen_ids)) == 47
    assert set(seen_ids) == {t["id"] for t in created}


def test_cursor_of_last_item_returns_empty_final_page(client, auth):
    tasks = create_tasks(client, auth, 3)
    oldest_id = min(t["id"] for t in tasks)
    resp = client.get(f"/tasks?cursor={oldest_id}", headers=auth)
    body = resp.get_json()
    assert body["data"] == []
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_unknown_cursor_returns_400(client, auth):
    create_tasks(client, auth, 2)
    resp = client.get("/tasks?cursor=999999", headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_non_integer_cursor_returns_400(client, auth):
    resp = client.get("/tasks?cursor=abc", headers=auth)
    assert resp.status_code == 400


# ── Ordering & isolation preserved ─────────────────────────────────

def test_pagination_preserves_newest_first_ordering(client, auth):
    create_task(client, auth, "Oldest")
    create_task(client, auth, "Middle")
    create_task(client, auth, "Newest")

    body = client.get("/tasks?limit=2", headers=auth).get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["Newest", "Middle"]


def test_pagination_respects_per_user_isolation(client, auth):
    register(client, "bob", "password123")
    bob_auth = auth_headers(login(client, "bob", "password123").get_json()["token"])

    create_tasks(client, auth, 3)
    create_tasks(client, bob_auth, 2)

    alice_body = client.get("/tasks", headers=auth).get_json()
    bob_body = client.get("/tasks", headers=bob_auth).get_json()

    assert alice_body["total"] == 3
    assert bob_body["total"] == 2
