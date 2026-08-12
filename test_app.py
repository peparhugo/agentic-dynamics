import os
import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE", str(db_path))
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    app_module.reset_rate_limits()
    with app_module.app.test_client() as c:
        yield c


def _register(client, username, password):
    return client.post("/auth/register", json={"username": username, "password": password})


def _login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def _token(client, username, password):
    return _login(client, username, password).get_json()["token"]


def _auth(client, username, password):
    return {"Authorization": f"Bearer {_token(client, username, password)}"}


@pytest.fixture()
def auth_headers(client):
    _register(client, "alice", "secret")
    return _auth(client, "alice", "secret")


@pytest.fixture()
def bob_headers(client):
    _register(client, "bob", "hunter2")
    return _auth(client, "bob", "hunter2")


def _create(client, title, headers):
    return client.post("/tasks", json={"title": title}, headers=headers)


# ── Auth tests ────────────────────────────────────────────────


def test_register_creates_user(client):
    resp = _register(client, "carol", "p@ssword")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "carol"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_username(client):
    assert _register(client, "carol", "one").status_code == 201
    resp = _register(client, "carol", "two")
    assert resp.status_code == 409


def test_register_missing_fields(client):
    assert _register(client, "", "pw").status_code == 400
    assert _register(client, "carol", "").status_code == 400
    assert client.post("/auth/register", json={}).status_code == 400


def test_login_returns_token(client):
    _register(client, "carol", "p@ssword")
    resp = _login(client, "carol", "p@ssword")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert data["user"]["username"] == "carol"


def test_login_wrong_password(client):
    _register(client, "carol", "right")
    assert _login(client, "carol", "wrong").status_code == 401


def test_login_unknown_user(client):
    assert _login(client, "nobody", "x").status_code == 401


def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not.a.token"}
    assert client.get("/tasks", headers=headers).status_code == 401


def test_tasks_reject_malformed_auth_header(client):
    assert client.get("/tasks", headers={"Authorization": "Basic abc"}).status_code == 401


def test_users_only_see_their_own_tasks(client, auth_headers, bob_headers):
    first = _create(client, "alice task", auth_headers).get_json()
    second = _create(client, "bob task", bob_headers).get_json()
    alice_tasks = client.get("/tasks", headers=auth_headers).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()["data"]
    assert [t["id"] for t in alice_tasks] == [first["id"]]
    assert [t["id"] for t in bob_tasks] == [second["id"]]


def test_cannot_access_other_users_task(client, auth_headers, bob_headers):
    alice_task = _create(client, "alice private", auth_headers).get_json()
    resp = client.get(f"/tasks/{alice_task['id']}", headers=bob_headers)
    assert resp.status_code == 404
    resp = client.put(f"/tasks/{alice_task['id']}", json={"title": "hacked"}, headers=bob_headers)
    assert resp.status_code == 404


# ── Task tests ────────────────────────────────────────────────


def test_create_task(client, auth_headers):
    resp = _create(client, "Buy milk", auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data
    assert data["owner_id"] == resp.get_json()["owner_id"]


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(client, auth_headers):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
    assert resp.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client, auth_headers):
    first = _create(client, "first", auth_headers).get_json()
    second = _create(client, "second", auth_headers).get_json()
    tasks = client.get("/tasks", headers=auth_headers).get_json()["data"]
    assert len(tasks) == 2
    assert tasks[0]["id"] == second["id"]
    assert tasks[1]["id"] == first["id"]


def test_get_single_task(client, auth_headers):
    created = _create(client, "single", auth_headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/tasks/9999", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_update_title_and_status(client, auth_headers):
    created = _create(client, "old", auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new", "status": "done"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


def test_update_status_only(client, auth_headers):
    created = _create(client, "keep", auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth_headers)
    data = resp.get_json()
    assert data["title"] == "keep"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/tasks/9999", json={"title": "x"}, headers=auth_headers)
    assert resp.status_code == 404


def test_default_status_is_pending(client, auth_headers):
    _create(client, "a", auth_headers)
    data = client.get("/tasks", headers=auth_headers).get_json()["data"]
    assert data[0]["status"] == "pending"


# ── Rate limiting tests ───────────────────────────────────────


def test_rate_limit_returns_429_with_retry_after(client, auth_headers):
    for _ in range(100):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 429
    assert resp.get_json() == {"error": "rate limit exceeded"}
    retry_after = resp.headers.get("Retry-After")
    assert retry_after is not None
    assert int(retry_after) > 0


def test_rate_limit_allows_requests_under_limit(client, auth_headers):
    for _ in range(50):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
    assert "Retry-After" in client.get("/tasks", headers=auth_headers).headers


def test_rate_limit_applies_to_auth_endpoints(client):
    for _ in range(100):
        resp = client.post(
            "/auth/login", json={"username": "nobody", "password": "x"}
        )
        assert resp.status_code == 401
    resp = client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") is not None


def test_rate_limit_is_per_user(client, auth_headers, bob_headers):
    for _ in range(5):
        client.get("/tasks", headers=auth_headers)
    remaining_alice = client.get("/tasks", headers=auth_headers).headers[
        "X-RateLimit-Remaining"
    ]
    for _ in range(5):
        client.get("/tasks", headers=bob_headers)
    remaining_bob = client.get("/tasks", headers=bob_headers).headers[
        "X-RateLimit-Remaining"
    ]
    assert remaining_alice == "94"
    assert remaining_bob == "94"


def test_rate_limit_resets_between_tests(client, auth_headers):
    for _ in range(60):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
    remaining = client.get("/tasks", headers=auth_headers).headers[
        "X-RateLimit-Remaining"
    ]
    assert remaining == "39"


# ── Pagination tests ──────────────────────────────────────────


def _create_many(client, headers, n):
    return [_create(client, f"task {i}", headers).get_json()["id"] for i in range(n)]


def test_list_tasks_returns_paginated_shape(client, auth_headers):
    _create_many(client, auth_headers, 3)
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert isinstance(body["data"], list)
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_pagination_default_limit(client, auth_headers):
    _create_many(client, auth_headers, 25)
    body = client.get("/tasks", headers=auth_headers).get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_pagination_limit_param(client, auth_headers):
    _create_many(client, auth_headers, 25)
    body = client.get("/tasks?limit=5", headers=auth_headers).get_json()
    assert len(body["data"]) == 5
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_pagination_max_limit_capped_at_100(client, auth_headers):
    for i in range(120):
        app_module.task_repository.create_task(1, f"bulk {i}")
    body = client.get("/tasks?limit=1000", headers=auth_headers).get_json()
    assert len(body["data"]) == 100
    assert body["total"] == 120


def test_pagination_cursor_walks_all_pages(client, auth_headers):
    ids = _create_many(client, auth_headers, 7)
    ids.reverse()
    seen = []
    cursor = None
    total = None
    for _ in range(10):
        params = "?limit=3"
        if cursor is not None:
            params += f"&cursor={cursor}"
        body = client.get(f"/tasks{params}", headers=auth_headers).get_json()
        assert body["total"] == 7
        total = body["total"]
        seen.extend(t["id"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert total == 7
    assert seen == ids


def test_pagination_does_not_include_cursor_task(client, auth_headers):
    ids = _create_many(client, auth_headers, 5)
    body = client.get("/tasks?limit=2", headers=auth_headers).get_json()
    assert [t["id"] for t in body["data"]] == ids[-1:-3:-1]
    cursor = body["next_cursor"]
    body2 = client.get(f"/tasks?limit=2&cursor={cursor}", headers=auth_headers).get_json()
    assert cursor not in [t["id"] for t in body2["data"]]


def test_pagination_empty_list(client, auth_headers):
    body = client.get("/tasks", headers=auth_headers).get_json()
    assert body == {"data": [], "next_cursor": None, "total": 0}


def test_pagination_invalid_cursor(client, auth_headers):
    _create_many(client, auth_headers, 2)
    resp = client.get("/tasks?cursor=abc", headers=auth_headers)
    assert resp.status_code == 400
