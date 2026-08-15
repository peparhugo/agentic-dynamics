import os
import tempfile

import pytest

import app as app_module


@pytest.fixture()
def client():
    db_fd, db_path = tempfile.mkstemp()
    app_module.DATABASE = db_path
    app_module.app.config["TESTING"] = True
    # Rate limiting has its own dedicated tests; keep it off here so pagination
    # tests (which can issue many requests to build up fixture data) can't
    # fail from crossing the shared Redis-backed limit.
    app_module.limiter.enabled = False
    app_module.init_db()
    with app_module.app.test_client() as client:
        yield client
    os.close(db_fd)
    os.unlink(db_path)


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def create_tasks(client, token, count):
    for i in range(count):
        client.post("/tasks", json={"name": f"Task {i}"}, headers=auth_header(token))


# ── Response shape ──────────────────────────────────────────────

def test_list_tasks_response_shape(client):
    register(client)
    token = login(client).get_json()["token"]
    client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token))

    resp = client.get("/tasks", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert isinstance(body["data"], list)
    assert body["total"] == 1
    assert body["next_cursor"] is None


def test_empty_task_list(client):
    register(client)
    token = login(client).get_json()["token"]

    resp = client.get("/tasks", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"data": [], "next_cursor": None, "total": 0}


# ── Default pagination ──────────────────────────────────────────

def test_default_limit_is_20(client):
    register(client)
    token = login(client).get_json()["token"]
    create_tasks(client, token, 25)

    resp = client.get("/tasks", headers=auth_header(token))
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_no_cursor_returns_first_page_newest_first(client):
    register(client)
    token = login(client).get_json()["token"]
    create_tasks(client, token, 3)

    resp = client.get("/tasks", headers=auth_header(token))
    body = resp.get_json()
    names = [t["name"] for t in body["data"]]
    assert names == ["Task 2", "Task 1", "Task 0"]


# ── Cursor traversal ─────────────────────────────────────────────

def test_cursor_pagination_walks_all_pages_without_duplicates(client):
    register(client)
    token = login(client).get_json()["token"]
    create_tasks(client, token, 25)

    seen_ids = []
    cursor = None
    for _ in range(10):
        url = "/tasks?limit=10" + (f"&cursor={cursor}" if cursor is not None else "")
        resp = client.get(url, headers=auth_header(token))
        body = resp.get_json()
        seen_ids.extend(t["id"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen_ids) == 25
    assert len(set(seen_ids)) == 25


def test_last_page_has_null_next_cursor(client):
    register(client)
    token = login(client).get_json()["token"]
    create_tasks(client, token, 5)

    resp = client.get("/tasks?limit=5", headers=auth_header(token))
    body = resp.get_json()
    assert len(body["data"]) == 5
    assert body["next_cursor"] is None


def test_next_cursor_is_id_of_last_item_in_page(client):
    register(client)
    token = login(client).get_json()["token"]
    create_tasks(client, token, 5)

    resp = client.get("/tasks?limit=3", headers=auth_header(token))
    body = resp.get_json()
    assert body["next_cursor"] == body["data"][-1]["id"]


# ── Limit clamping / validation ─────────────────────────────────

def test_limit_is_capped_at_100(client):
    register(client)
    token = login(client).get_json()["token"]
    create_tasks(client, token, 5)

    resp = client.get("/tasks?limit=1000", headers=auth_header(token))
    body = resp.get_json()
    assert len(body["data"]) == 5


def test_limit_below_one_is_clamped_to_one(client):
    register(client)
    token = login(client).get_json()["token"]
    create_tasks(client, token, 5)

    resp = client.get("/tasks?limit=0", headers=auth_header(token))
    body = resp.get_json()
    assert len(body["data"]) == 1


def test_invalid_limit_returns_400(client):
    register(client)
    token = login(client).get_json()["token"]

    resp = client.get("/tasks?limit=notanumber", headers=auth_header(token))
    assert resp.status_code == 400


def test_invalid_cursor_returns_400(client):
    register(client)
    token = login(client).get_json()["token"]

    resp = client.get("/tasks?cursor=notanumber", headers=auth_header(token))
    assert resp.status_code == 400


# ── Ownership isolation still holds under pagination ────────────

def test_pagination_only_includes_own_tasks(client):
    register(client, username="alice")
    register(client, username="bob")
    alice_token = login(client, username="alice").get_json()["token"]
    bob_token = login(client, username="bob").get_json()["token"]

    create_tasks(client, alice_token, 3)
    create_tasks(client, bob_token, 2)

    alice_body = client.get("/tasks", headers=auth_header(alice_token)).get_json()
    bob_body = client.get("/tasks", headers=auth_header(bob_token)).get_json()

    assert alice_body["total"] == 3
    assert bob_body["total"] == 2


def test_pagination_requires_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
