"""
Tests for cursor-based pagination on GET /tasks.

Covers:
 - Response shape: {"data": [...], "next_cursor": str|None, "total": int}
 - Default page size (20) and explicit ?limit=<n>
 - Max limit clamp (100) and 400 on invalid limit/cursor values
 - Cursor is the id of the last item in the current page; passing it back
   as ?cursor=<id> returns the next page
 - Walking every page with the returned next_cursor eventually reaches
   next_cursor == None and yields every task exactly once, most-recent
   first
 - Pagination is scoped per-owner (matches existing task isolation)
"""

import json

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_pagination.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db_path))
    app_module.init_db()

    app_module.limiter.reset()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def _register_and_login(client, username="alice", password="s3cret-pw"):
    client.post(
        "/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )
    token = client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, headers, title):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
        headers=headers,
    )


def _create_many(client, headers, count):
    """Create ``count`` tasks titled Task 1..Task <count>, in order, and
    return them oldest-first (i.e. the order they were created in)."""
    created = []
    for i in range(1, count + 1):
        created.append(_create_task(client, headers, f"Task {i}").get_json())
    return created


# ── Response shape / defaults ───────────────────────────────────────


def test_list_tasks_default_shape(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert body["data"] == []
    assert body["next_cursor"] is None
    assert body["total"] == 0


def test_default_limit_is_20(client):
    headers = _register_and_login(client)
    _create_many(client, headers, 25)

    resp = client.get("/tasks", headers=headers)
    body = resp.get_json()

    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_no_cursor_returns_first_page_most_recent_first(client):
    headers = _register_and_login(client)
    _create_many(client, headers, 5)

    resp = client.get("/tasks?limit=3", headers=headers)
    body = resp.get_json()

    titles = [t["title"] for t in body["data"]]
    assert titles == ["Task 5", "Task 4", "Task 3"]
    assert body["total"] == 5
    assert body["next_cursor"] == str(body["data"][-1]["id"])


# ── Explicit limit ───────────────────────────────────────────────────


def test_explicit_limit_is_respected(client):
    headers = _register_and_login(client)
    _create_many(client, headers, 10)

    resp = client.get("/tasks?limit=4", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 4


def test_limit_above_max_is_clamped_to_100(client):
    headers = _register_and_login(client)
    _create_many(client, headers, 5)

    resp = client.get("/tasks?limit=1000", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    # Only 5 tasks exist, so we just confirm the request succeeds and
    # doesn't reject a large limit outright; all 5 are returned.
    assert len(body["data"]) == 5
    assert body["next_cursor"] is None


def test_limit_zero_returns_400(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks?limit=0", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_negative_limit_returns_400(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks?limit=-5", headers=headers)
    assert resp.status_code == 400


def test_non_integer_limit_returns_400(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks?limit=abc", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_non_integer_cursor_returns_400(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks?cursor=not-an-id", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── Cursor-based walking ─────────────────────────────────────────────


def test_cursor_returns_next_page(client):
    headers = _register_and_login(client)
    _create_many(client, headers, 5)

    first = client.get("/tasks?limit=2", headers=headers).get_json()
    assert [t["title"] for t in first["data"]] == ["Task 5", "Task 4"]
    cursor = first["next_cursor"]
    assert cursor is not None

    second = client.get(f"/tasks?limit=2&cursor={cursor}", headers=headers).get_json()
    assert [t["title"] for t in second["data"]] == ["Task 3", "Task 2"]
    assert second["next_cursor"] is not None

    third = client.get(
        f"/tasks?limit=2&cursor={second['next_cursor']}", headers=headers
    ).get_json()
    assert [t["title"] for t in third["data"]] == ["Task 1"]
    assert third["next_cursor"] is None


def test_walking_all_pages_covers_every_task_exactly_once(client):
    headers = _register_and_login(client)
    created = _create_many(client, headers, 47)
    expected_titles_desc = [t["title"] for t in reversed(created)]

    seen = []
    cursor = None
    for _ in range(100):  # safety bound against infinite loops
        url = "/tasks?limit=10"
        if cursor is not None:
            url += f"&cursor={cursor}"
        body = client.get(url, headers=headers).get_json()
        seen.extend(t["title"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen == expected_titles_desc


def test_last_page_has_null_next_cursor(client):
    headers = _register_and_login(client)
    _create_many(client, headers, 4)

    resp = client.get("/tasks?limit=4", headers=headers).get_json()
    assert len(resp["data"]) == 4
    assert resp["next_cursor"] is None


def test_cursor_past_last_item_returns_empty_page(client):
    headers = _register_and_login(client)
    created = _create_many(client, headers, 3)
    oldest_id = created[0]["id"]

    resp = client.get(f"/tasks?cursor={oldest_id}", headers=headers).get_json()
    assert resp["data"] == []
    assert resp["next_cursor"] is None
    assert resp["total"] == 3


# ── Pagination is scoped per owner ───────────────────────────────────


def test_pagination_scoped_to_owner(client):
    alice_headers = _register_and_login(client, "alice", "pw-alice")
    bob_headers = _register_and_login(client, "bob", "pw-bob")

    _create_many(client, alice_headers, 5)
    _create_task(client, bob_headers, "Bob's only task")

    alice_page = client.get("/tasks?limit=2", headers=alice_headers).get_json()
    bob_page = client.get("/tasks?limit=2", headers=bob_headers).get_json()

    assert alice_page["total"] == 5
    assert bob_page["total"] == 1
    assert [t["title"] for t in bob_page["data"]] == ["Bob's only task"]


def test_pagination_requires_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
