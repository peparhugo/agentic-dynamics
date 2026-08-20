import pytest

import fakeredis

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db))
    app_module.app.config["RATELIMIT_STORAGE_OPTIONS"] = {
        "connection_pool": fakeredis.FakeRedis().connection_pool
    }
    app_module.limiter.init_app(app_module.app)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture()
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_headers(client):
    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "secret"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth ──────────────────────────────────────────────────────

def test_register(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["id"] == 1
    assert "password_hash" not in data


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/register", json={"username": "alice", "password": "other"})
    assert resp.status_code == 409


def test_register_missing_fields(client):
    assert client.post("/auth/register", json={"username": "alice"}).status_code == 400
    assert client.post("/auth/register", json={"password": "secret"}).status_code == 400
    assert client.post("/auth/register", json={}).status_code == 400


def test_login_returns_token(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "secret"})
    assert resp.status_code == 401


# ── Tasks (protected) ─────────────────────────────────────────

def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/tasks", headers=headers).status_code == 401
    assert client.post("/tasks", json={"title": "x"}, headers=headers).status_code == 401


def test_create_task(client, auth_headers):
    resp = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Write tests"
    assert data["status"] == "pending"
    assert "created_at" in data
    assert data["owner_id"] == 1


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client, auth_headers):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
    assert resp.status_code == 400


def test_list_tasks(client, auth_headers):
    client.post("/tasks", json={"title": "first"}, headers=auth_headers)
    client.post("/tasks", json={"title": "second"}, headers=auth_headers)
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["total"] == 2
    assert payload["next_cursor"] is None
    tasks = payload["data"]
    assert len(tasks) == 2
    assert tasks[0]["title"] == "second"
    assert tasks[1]["title"] == "first"


def test_get_task(client, auth_headers):
    client.post("/tasks", json={"title": "hello"}, headers=auth_headers)
    resp = client.get("/tasks/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "hello"


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/tasks/999", headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task(client, auth_headers):
    client.post("/tasks", json={"title": "old"}, headers=auth_headers)
    resp = client.put("/tasks/1", json={"title": "new", "status": "done"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "done"


def test_update_task_partial(client, auth_headers):
    client.post("/tasks", json={"title": "old"}, headers=auth_headers)
    resp = client.put("/tasks/1", json={"status": "in progress"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "old"
    assert data["status"] == "in progress"


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/tasks/999", json={"title": "x"}, headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── Per-user isolation ────────────────────────────────────────

def test_users_see_only_their_own_tasks(client, auth_headers, other_headers):
    client.post("/tasks", json={"title": "alice task"}, headers=auth_headers)
    client.post("/tasks", json={"title": "bob task"}, headers=other_headers)

    alice_tasks = client.get("/tasks", headers=auth_headers).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=other_headers).get_json()["data"]

    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_user_cannot_access_other_users_task(client, auth_headers, other_headers):
    client.post("/tasks", json={"title": "alice task"}, headers=auth_headers)
    resp = client.get("/tasks/1", headers=other_headers)
    assert resp.status_code == 404
    resp = client.put("/tasks/1", json={"title": "stolen"}, headers=other_headers)
    assert resp.status_code == 404


# ── Notification trigger ──────────────────────────────────────

class _FakeTask:
    def __init__(self):
        self.calls = []

    def delay(self, user_email, task_title):
        self.calls.append((user_email, task_title))


@pytest.fixture()
def fake_notifier(monkeypatch):
    fake = _FakeTask()
    monkeypatch.setattr(app_module, "send_notification_email", fake)
    return fake


def test_completing_task_triggers_notification(client, auth_headers, fake_notifier):
    client.post("/tasks", json={"title": "Finish report"}, headers=auth_headers)
    resp = client.put("/tasks/1", json={"status": "completed"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert fake_notifier.calls == [("alice@example.com", "Finish report")]


def test_completing_task_uses_owner_email(client, monkeypatch):
    fake = _FakeTask()
    monkeypatch.setattr(app_module, "send_notification_email", fake)
    client.post(
        "/auth/register",
        json={"username": "carol", "password": "secret", "email": "carol@example.com"},
    )
    resp = client.post(
        "/auth/login", json={"username": "carol", "password": "secret"}
    )
    headers = {"Authorization": f"Bearer {resp.get_json()['token']}"}
    client.post("/tasks", json={"title": "Ship it"}, headers=headers)
    client.put("/tasks/1", json={"status": "completed"}, headers=headers)
    assert fake.calls == [("carol@example.com", "Ship it")]


def test_non_completed_status_does_not_trigger_notification(
    client, auth_headers, fake_notifier
):
    client.post("/tasks", json={"title": "WIP"}, headers=auth_headers)
    resp = client.put("/tasks/1", json={"status": "in progress"}, headers=auth_headers)
    assert resp.status_code == 200
    assert fake_notifier.calls == []


def test_recompleting_task_does_not_retrigger_notification(
    client, auth_headers, fake_notifier
):
    client.post("/tasks", json={"title": "Done twice"}, headers=auth_headers)
    client.put("/tasks/1", json={"status": "completed"}, headers=auth_headers)
    client.put("/tasks/1", json={"status": "completed"}, headers=auth_headers)
    assert fake_notifier.calls == [("alice@example.com", "Done twice")]


def test_title_only_update_does_not_trigger_notification(
    client, auth_headers, fake_notifier
):
    client.post("/tasks", json={"title": "rename me"}, headers=auth_headers)
    resp = client.put("/tasks/1", json={"title": "renamed"}, headers=auth_headers)
    assert resp.status_code == 200
    assert fake_notifier.calls == []


# ── Pagination ────────────────────────────────────────────────

def test_pagination_cursor_walks_all_pages(client, auth_headers):
    for i in range(25):
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth_headers)

    first = client.get("/tasks?limit=10", headers=auth_headers)
    assert first.status_code == 200
    body = first.get_json()
    assert body["total"] == 25
    assert len(body["data"]) == 10
    assert body["data"][0]["title"] == "task 24"
    assert body["data"][-1]["title"] == "task 15"
    assert body["next_cursor"] is not None

    second = client.get(
        f"/tasks?limit=10&cursor={body['next_cursor']}", headers=auth_headers
    )
    assert second.status_code == 200
    body2 = second.get_json()
    assert body2["total"] == 25
    assert len(body2["data"]) == 10
    assert body2["data"][0]["title"] == "task 14"
    assert body2["data"][-1]["title"] == "task 5"
    assert body2["next_cursor"] is not None

    third = client.get(
        f"/tasks?limit=10&cursor={body2['next_cursor']}", headers=auth_headers
    )
    assert third.status_code == 200
    body3 = third.get_json()
    assert body3["total"] == 25
    assert len(body3["data"]) == 5
    assert body3["data"][0]["title"] == "task 4"
    assert body3["data"][-1]["title"] == "task 0"
    assert body3["next_cursor"] is None


def test_pagination_default_limit(client, auth_headers):
    for i in range(25):
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth_headers)
    body = client.get("/tasks", headers=auth_headers).get_json()
    assert body["total"] == 25
    assert len(body["data"]) == 20
    assert body["next_cursor"] is not None


def test_pagination_limit_clamped_to_max(client, auth_headers):
    for i in range(150):
        app_module.task_repository.create(f"task {i}", 1)
    body = client.get("/tasks?limit=1000", headers=auth_headers).get_json()
    assert len(body["data"]) == 100
    assert body["total"] == 150


def test_pagination_invalid_cursor_returns_first_page(client, auth_headers):
    client.post("/tasks", json={"title": "a"}, headers=auth_headers)
    client.post("/tasks", json={"title": "b"}, headers=auth_headers)
    body = client.get("/tasks?cursor=notanumber", headers=auth_headers).get_json()
    assert [t["title"] for t in body["data"]] == ["b", "a"]


def test_pagination_is_isolated_per_user(client, auth_headers, other_headers):
    client.post("/tasks", json={"title": "alice 1"}, headers=auth_headers)
    client.post("/tasks", json={"title": "alice 2"}, headers=auth_headers)
    client.post("/tasks", json={"title": "bob 1"}, headers=other_headers)

    alice = client.get("/tasks?limit=1", headers=auth_headers).get_json()
    assert alice["total"] == 2
    assert [t["title"] for t in alice["data"]] == ["alice 2"]
    assert alice["next_cursor"] is not None

    alice_page2 = client.get(
        f"/tasks?limit=1&cursor={alice['next_cursor']}", headers=auth_headers
    ).get_json()
    assert [t["title"] for t in alice_page2["data"]] == ["alice 1"]
    assert alice_page2["next_cursor"] is None


# ── Rate limiting ─────────────────────────────────────────────

def test_rate_limit_user_returns_429_with_retry_after(client, auth_headers):
    for _ in range(100):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_applies_to_auth_endpoints(client):
    for i in range(100):
        resp = client.post(
            "/auth/register", json={"username": f"user{i}", "password": "secret"}
        )
        assert resp.status_code == 201
    resp = client.post(
        "/auth/register", json={"username": "overflow", "password": "secret"}
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_is_per_user(client, auth_headers, other_headers):
    for _ in range(100):
        assert client.get("/tasks", headers=auth_headers).status_code == 200
    assert client.get("/tasks", headers=auth_headers).status_code == 429
    assert client.get("/tasks", headers=other_headers).status_code == 200
