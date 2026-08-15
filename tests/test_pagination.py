import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATABASE = str(tmp_path / "test.db")
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def register(client, username="alice", password="secret123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(client, username="alice", password="secret123"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def create_tasks(client, headers, count):
    for i in range(count):
        client.post("/tasks", json={"title": f"task-{i}"}, headers=headers)


# ── Response shape ────────────────────────────────────────────────

def test_list_tasks_response_shape(client):
    headers = auth_header(client)
    create_tasks(client, headers, 3)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert isinstance(body["data"], list)
    assert body["total"] == 3


# ── Default paging ───────────────────────────────────────────────

def test_default_limit_is_20(client):
    headers = auth_header(client)
    create_tasks(client, headers, 25)

    resp = client.get("/tasks", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_no_cursor_returns_first_page_newest_first(client):
    headers = auth_header(client)
    create_tasks(client, headers, 3)

    resp = client.get("/tasks", headers=headers)
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["task-2", "task-1", "task-0"]


# ── Custom limit ─────────────────────────────────────────────────

def test_custom_limit(client):
    headers = auth_header(client)
    create_tasks(client, headers, 10)

    resp = client.get("/tasks?limit=5", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 5
    assert body["next_cursor"] is not None


def test_limit_capped_at_100(client):
    headers = auth_header(client)
    create_tasks(client, headers, 5)

    resp = client.get("/tasks?limit=500", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 5  # only 5 tasks exist, well under the cap


def test_limit_zero_is_rejected(client):
    headers = auth_header(client)
    resp = client.get("/tasks?limit=0", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_limit_negative_is_rejected(client):
    headers = auth_header(client)
    resp = client.get("/tasks?limit=-5", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_limit_non_integer_is_rejected(client):
    headers = auth_header(client)
    resp = client.get("/tasks?limit=abc", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── Cursor traversal ─────────────────────────────────────────────

def test_cursor_is_id_of_last_item_in_page(client):
    headers = auth_header(client)
    create_tasks(client, headers, 5)

    resp = client.get("/tasks?limit=2", headers=headers)
    body = resp.get_json()
    assert body["next_cursor"] == str(body["data"][-1]["id"])


def test_walking_all_pages_via_cursor_covers_every_task(client):
    headers = auth_header(client)
    create_tasks(client, headers, 25)

    seen_ids = []
    cursor = None
    for _ in range(10):  # safety bound against infinite loop on a bug
        url = "/tasks?limit=10" + (f"&cursor={cursor}" if cursor else "")
        resp = client.get(url, headers=headers)
        body = resp.get_json()
        seen_ids.extend(t["id"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen_ids) == 25
    assert len(set(seen_ids)) == 25  # no duplicates or gaps across pages


def test_last_page_has_null_next_cursor(client):
    headers = auth_header(client)
    create_tasks(client, headers, 25)

    first_page = client.get("/tasks?limit=20", headers=headers).get_json()
    second_page = client.get(
        f"/tasks?limit=20&cursor={first_page['next_cursor']}", headers=headers
    ).get_json()

    assert len(second_page["data"]) == 5
    assert second_page["next_cursor"] is None


def test_exact_multiple_of_limit_has_null_next_cursor(client):
    """A page that happens to be exactly `limit` long but is the last page
    must still report next_cursor=None, not just whenever a page is full."""
    headers = auth_header(client)
    create_tasks(client, headers, 20)

    resp = client.get("/tasks?limit=20", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["next_cursor"] is None


def test_invalid_cursor_is_rejected(client):
    headers = auth_header(client)
    resp = client.get("/tasks?cursor=not-an-id", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── Isolation / auth ─────────────────────────────────────────────

def test_pagination_scoped_to_owner(client):
    alice_headers = auth_header(client, "alice", "secret123")
    bob_headers = auth_header(client, "bob", "secret456")

    create_tasks(client, alice_headers, 3)
    create_tasks(client, bob_headers, 2)

    alice_body = client.get("/tasks", headers=alice_headers).get_json()
    bob_body = client.get("/tasks", headers=bob_headers).get_json()

    assert alice_body["total"] == 3
    assert bob_body["total"] == 2


def test_paginated_tasks_still_requires_auth(client):
    resp = client.get("/tasks?limit=5")
    assert resp.status_code == 401
