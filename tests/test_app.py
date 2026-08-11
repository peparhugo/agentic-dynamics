import os
import tempfile
from unittest import mock

import pytest

db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE"] = db_file.name
os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"

import app


def _register_and_login(client, username="testuser", password="testpass"):
    client.post("/auth/register", json={"username": username, "password": password})
    resp = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


@pytest.fixture
def client():
    app.limiter.reset()
    app.init_db()
    with app.app.test_client() as client:
        yield client
    conn = app.get_db()
    conn.execute("DROP TABLE IF EXISTS tasks")
    conn.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    conn.close()


# ── Auth Tests ──────────────────────────────────────────────────

def test_register(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["username"] == "alice"


def test_register_duplicate(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 409
    assert "already exists" in resp.get_json()["error"]


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={"password": "secret"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400


def test_login(client):
    client.post("/auth/register", json={"username": "bob", "password": "pass"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "pass"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert isinstance(data["token"], str)


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "bob", "password": "pass"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401
    assert "invalid credentials" in resp.get_json()["error"]


def test_login_nonexistent_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "pass"})
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "bob"})
    assert resp.status_code == 400
    resp = client.post("/auth/login", json={"password": "pass"})
    assert resp.status_code == 400


# ── Task Auth Protection ───────────────────────────────────────

def test_tasks_require_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    resp = client.post("/tasks", json={"title": "test"})
    assert resp.status_code == 401
    resp = client.get("/tasks/1")
    assert resp.status_code == 401
    resp = client.put("/tasks/1", json={"title": "test"})
    assert resp.status_code == 401


def test_invalid_token(client):
    headers = {"Authorization": "Bearer invalid.token.here"}
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401


def test_expired_token(client):
    expired = app.jwt.encode(
        {"user_id": 1, "exp": app.datetime.utcnow() - app.timedelta(seconds=1)},
        app.app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {expired}"}
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401


def test_user_isolation(client):
    headers1 = _register_and_login(client, "user1", "pass1")
    client.post("/tasks", json={"title": "Task of user1"}, headers=headers1)

    headers2 = _register_and_login(client, "user2", "pass2")
    client.post("/tasks", json={"title": "Task of user2"}, headers=headers2)

    resp = client.get("/tasks", headers=headers1)
    data = resp.get_json()
    assert len(data["data"]) == 1
    assert data["data"][0]["title"] == "Task of user1"

    resp = client.get("/tasks", headers=headers2)
    data = resp.get_json()
    assert len(data["data"]) == 1
    assert data["data"][0]["title"] == "Task of user2"


def test_cannot_access_other_users_task(client):
    headers1 = _register_and_login(client, "user1", "pass1")
    resp = client.post("/tasks", json={"title": "Secret"}, headers=headers1)
    task_id = resp.get_json()["id"]

    headers2 = _register_and_login(client, "user2", "pass2")
    resp = client.get(f"/tasks/{task_id}", headers=headers2)
    assert resp.status_code == 404


# ── Existing Task Tests (Updated with Auth) ─────────────────────

def test_create_task(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_list_tasks_empty(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"] == []
    assert data["next_cursor"] is None
    assert data["total"] == 0


def test_list_tasks_ordered(client):
    headers = _register_and_login(client)
    client.post("/tasks", json={"title": "Task 1"}, headers=headers)
    client.post("/tasks", json={"title": "Task 2"}, headers=headers)
    client.post("/tasks", json={"title": "Task 3"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 3
    assert data["data"][0]["title"] == "Task 3"
    assert data["data"][1]["title"] == "Task 2"
    assert data["data"][2]["title"] == "Task 1"
    assert data["total"] == 3
    assert data["next_cursor"] is None


def test_get_single_task(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Read book"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.get(f"/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == task_id
    assert data["title"] == "Read book"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_title(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Old title"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"title": "New title"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Do laundry"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"


def test_update_task_both(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Walk dog"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"title": "Walk cat", "status": "in_progress"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Walk cat"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    headers = _register_and_login(client)
    resp = client.put("/tasks/999", json={"title": "Nope"}, headers=headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_no_fields(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Test"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Test"
    assert data["status"] == "pending"


def test_post_missing_json(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", data="", content_type="application/json", headers=headers)
    assert resp.status_code == 400


def test_multiple_tasks_increment_ids(client):
    headers = _register_and_login(client)
    r1 = client.post("/tasks", json={"title": "A"}, headers=headers)
    r2 = client.post("/tasks", json={"title": "B"}, headers=headers)
    r3 = client.post("/tasks", json={"title": "C"}, headers=headers)
    assert r1.get_json()["id"] == 1
    assert r2.get_json()["id"] == 2
    assert r3.get_json()["id"] == 3


# ── Notification Tests ─────────────────────────────────────────

def test_notification_triggered_on_completed(client):
    headers = _register_and_login(client, "notifyuser", "pass")
    client.post("/tasks", json={"title": "Send email"}, headers=headers)
    with mock.patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put("/tasks/1", json={"status": "completed"}, headers=headers)
        assert resp.status_code == 200
        mock_delay.assert_called_once_with("notifyuser@example.com", "Send email")


def test_notification_not_triggered_on_other_status(client):
    headers = _register_and_login(client, "notifyuser2", "pass")
    client.post("/tasks", json={"title": "In progress task"}, headers=headers)
    with mock.patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put("/tasks/1", json={"status": "in_progress"}, headers=headers)
        assert resp.status_code == 200
        mock_delay.assert_not_called()


def test_notification_not_triggered_on_title_only(client):
    headers = _register_and_login(client, "notifyuser3", "pass")
    client.post("/tasks", json={"title": "Old title"}, headers=headers)
    with mock.patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put("/tasks/1", json={"title": "New title"}, headers=headers)
        assert resp.status_code == 200
        mock_delay.assert_not_called()


def test_notification_not_triggered_task_not_found(client):
    headers = _register_and_login(client, "notifyuser4", "pass")
    with mock.patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put("/tasks/999", json={"status": "completed"}, headers=headers)
        assert resp.status_code == 404
        mock_delay.assert_not_called()


def test_notification_with_custom_email(client):
    headers = _register_and_login(client, "custemail", "pass")
    client.post("/auth/register", json={"username": "custemail2", "password": "pass", "email": "custom@test.com"})
    login_resp = client.post("/auth/login", json={"username": "custemail2", "password": "pass"})
    headers2 = {"Authorization": f"Bearer {login_resp.get_json()['token']}"}
    client.post("/tasks", json={"title": "Custom email task"}, headers=headers2)
    with mock.patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put("/tasks/1", json={"status": "completed"}, headers=headers2)
        assert resp.status_code == 200
        mock_delay.assert_called_once_with("custom@test.com", "Custom email task")


# ── Pagination Tests ─────────────────────────────────────────────

def test_pagination_default_limit(client):
    headers = _register_and_login(client, "paginateuser", "pass")
    for i in range(25):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 20
    assert data["total"] == 25
    assert data["next_cursor"] is not None


def test_pagination_custom_limit(client):
    headers = _register_and_login(client, "paginateuser2", "pass")
    for i in range(10):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
    resp = client.get("/tasks?limit=5", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["total"] == 10
    assert data["next_cursor"] is not None


def test_pagination_max_limit(client):
    headers = _register_and_login(client, "paginateuser3", "pass")
    for i in range(150):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
    resp = client.get("/tasks?limit=200", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 100
    assert data["total"] == 150


def test_pagination_cursor(client):
    headers = _register_and_login(client, "paginateuser4", "pass")
    for i in range(25):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    page1 = client.get("/tasks?limit=10", headers=headers).get_json()
    assert len(page1["data"]) == 10
    assert page1["next_cursor"] is not None

    page2 = client.get(f"/tasks?limit=10&cursor={page1['next_cursor']}", headers=headers).get_json()
    assert len(page2["data"]) == 10
    assert page2["next_cursor"] is not None

    page3 = client.get(f"/tasks?limit=10&cursor={page2['next_cursor']}", headers=headers).get_json()
    assert len(page3["data"]) == 5
    assert page3["next_cursor"] is None

    all_tasks = page1["data"] + page2["data"] + page3["data"]
    titles = [t["title"] for t in all_tasks]
    assert titles == [f"Task {i}" for i in range(24, -1, -1)]


def test_pagination_no_duplicates(client):
    headers = _register_and_login(client, "paginateuser5", "pass")
    for i in range(30):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    seen_ids = set()
    cursor = None
    while True:
        url = "/tasks?limit=7"
        if cursor:
            url += f"&cursor={cursor}"
        page = client.get(url, headers=headers).get_json()
        for task in page["data"]:
            assert task["id"] not in seen_ids
            seen_ids.add(task["id"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(seen_ids) == 30


def test_pagination_total_remains_constant(client):
    headers = _register_and_login(client, "paginateuser6", "pass")
    for i in range(15):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    page1 = client.get("/tasks?limit=5", headers=headers).get_json()
    assert page1["total"] == 15

    page2 = client.get(f"/tasks?limit=5&cursor={page1['next_cursor']}", headers=headers).get_json()
    assert page2["total"] == 15

    page3 = client.get(f"/tasks?limit=5&cursor={page2['next_cursor']}", headers=headers).get_json()
    assert page3["total"] == 15


# ── Rate Limiting Tests ───────────────────────────────────────────

def test_rate_limit_on_register(client):
    for i in range(101):
        resp = client.post("/auth/register", json={"username": f"rluser{i}", "password": "pass"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_on_login(client):
    client.post("/auth/register", json={"username": "rllogin", "password": "pass"})
    for i in range(100):
        resp = client.post("/auth/login", json={"username": "rllogin", "password": "pass"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_on_authenticated_endpoint(client):
    headers = _register_and_login(client, "rlauth", "pass")
    for i in range(100):
        resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_returns_retry_after_header(client):
    for i in range(101):
        resp = client.post("/auth/register", json={"username": f"rlheader{i}", "password": "pass"})
    assert resp.status_code == 429
    retry_after = resp.headers.get("Retry-After")
    assert retry_after is not None
    assert int(retry_after) >= 1


def test_rate_limit_per_user_isolation(client):
    for i in range(101):
        resp = client.post("/auth/register", json={"username": f"rlu{i}", "password": "pass"})
    assert resp.status_code == 429

    headers = _register_and_login(client, "rlisolated", "pass")
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
