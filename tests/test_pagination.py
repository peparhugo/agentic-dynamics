"""
Tests for cursor-based pagination on GET /tasks.

Response shape: ``{"data": [...], "next_cursor": str | None, "total": int}``.
The cursor is the ``id`` of the last item of the current page; the next
page contains only tasks with a smaller id (results are newest-first).
"""

import json

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    flask_app = create_app(
        database=str(tmp_path / "test_tasks.db"),
        jwt_secret="test-secret",
        rate_limit="1000 per minute",
    )
    flask_app.config.update(TESTING=True)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def login(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client):
    register(client, "alice", "s3cret-pw")
    return login(client, "alice", "s3cret-pw").get_json()["token"]


def create_task(client, token, title):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
        headers=auth_headers(token),
    )


def list_tasks(client, token, cursor=None, limit=None):
    params = {}
    if cursor is not None:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit
    return client.get("/tasks", query_string=params, headers=auth_headers(token))


def create_many(client, token, count):
    """Create ``count`` tasks titled Task-0 (oldest) .. Task-{count-1} (newest)."""
    created = []
    for i in range(count):
        created.append(create_task(client, token, f"Task-{i}").get_json())
    return created


# ── Basic shape / defaults ──────────────────────────────────

def test_empty_list_shape(client, token):
    resp = list_tasks(client, token)
    assert resp.status_code == 200
    assert resp.get_json() == {"data": [], "next_cursor": None, "total": 0}


def test_default_limit_is_20(client, token):
    create_many(client, token, 25)
    resp = list_tasks(client, token)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_first_page_without_cursor_returns_newest_first(client, token):
    create_many(client, token, 5)
    resp = list_tasks(client, token, limit=3)
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["Task-4", "Task-3", "Task-2"]
    assert body["total"] == 5
    assert body["next_cursor"] == str(body["data"][-1]["id"])


def test_cursor_advances_to_next_page(client, token):
    create_many(client, token, 5)
    first = list_tasks(client, token, limit=3).get_json()
    second = list_tasks(client, token, cursor=first["next_cursor"], limit=3).get_json()

    titles = [t["title"] for t in second["data"]]
    assert titles == ["Task-1", "Task-0"]
    assert second["next_cursor"] is None
    assert second["total"] == 5


def test_paging_through_all_items_yields_no_duplicates_or_gaps(client, token):
    created = create_many(client, token, 47)
    all_titles = []
    cursor = None
    pages = 0
    while True:
        body = list_tasks(client, token, cursor=cursor, limit=10).get_json()
        all_titles.extend(t["title"] for t in body["data"])
        cursor = body["next_cursor"]
        pages += 1
        if cursor is None:
            break
        assert pages < 20  # sanity guard against infinite loop

    expected = [f"Task-{i}" for i in range(46, -1, -1)]
    assert all_titles == expected
    assert pages == 5  # 47 items / 10 per page -> 5 pages (last partial)


def test_next_cursor_is_null_on_exact_multiple_of_limit(client, token):
    create_many(client, token, 10)
    resp = list_tasks(client, token, limit=10).get_json()
    assert len(resp["data"]) == 10
    assert resp["next_cursor"] is None


def test_limit_greater_than_max_does_not_error(client, token):
    create_many(client, token, 150)
    resp = list_tasks(client, token, limit=500).get_json()
    assert len(resp["data"]) == 100  # clamped to MAX_PAGE_SIZE
    assert resp["total"] == 150


def test_invalid_cursor_returns_400(client, token):
    resp = list_tasks(client, token, cursor="not-an-int")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_invalid_limit_returns_400(client, token):
    resp = list_tasks(client, token, limit="not-an-int")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_zero_or_negative_limit_returns_400(client, token):
    resp = list_tasks(client, token, limit=0)
    assert resp.status_code == 400
    assert "error" in resp.get_json()

    resp2 = list_tasks(client, token, limit=-5)
    assert resp2.status_code == 400
    assert "error" in resp2.get_json()


def test_cursor_of_zero_returns_first_page_worth_of_older_items(client, token):
    # cursor=<smallest existing id> should return an empty page, not an error.
    created = create_many(client, token, 3)
    smallest_id = min(t["id"] for t in created)
    resp = list_tasks(client, token, cursor=smallest_id).get_json()
    assert resp["data"] == []
    assert resp["next_cursor"] is None
    assert resp["total"] == 3


# ── Per-user isolation still holds under pagination ─────────

def test_pagination_is_scoped_per_user(client, token):
    register(client, "bob", "pw-bob-1")
    token_bob = login(client, "bob", "pw-bob-1").get_json()["token"]

    create_many(client, token, 5)
    create_task(client, token_bob, "Bob-only task")

    alice_page = list_tasks(client, token, limit=2).get_json()
    bob_page = list_tasks(client, token_bob, limit=2).get_json()

    assert alice_page["total"] == 5
    assert bob_page["total"] == 1
    assert [t["title"] for t in bob_page["data"]] == ["Bob-only task"]


def test_pagination_requires_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
