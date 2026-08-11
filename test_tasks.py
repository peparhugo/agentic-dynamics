import pytest
from app import app, init_db, get_db


def register_and_login(client, username="testuser", password="password123"):
    client.post("/auth/register", json={"username": username, "password": password})
    res = client.post("/auth/login", json={"username": username, "password": password})
    return res.get_json()["token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    with app.app_context():
        init_db()
        with get_db() as conn:
            conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM users")
            conn.commit()
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth(client):
    return register_and_login(client)


# ── Auth Tests ────────────────────────────────────────────────

def test_register_success(client):
    res = client.post("/auth/register", json={"username": "newuser", "password": "password123"})
    assert res.status_code == 201
    data = res.get_json()
    assert data["message"] == "user registered"
    assert data["username"] == "newuser"


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "dup", "password": "password123"})
    res = client.post("/auth/register", json={"username": "dup", "password": "password123"})
    assert res.status_code == 409
    assert "error" in res.get_json()


def test_register_missing_fields(client):
    res = client.post("/auth/register", json={})
    assert res.status_code == 400


def test_register_short_password(client):
    res = client.post("/auth/register", json={"username": "user", "password": "short"})
    assert res.status_code == 400


def test_login_success(client, auth):
    assert auth is not None
    assert len(auth) > 0


def test_login_invalid_credentials(client):
    res = client.post("/auth/login", json={"username": "ghost", "password": "wrongpass"})
    assert res.status_code == 401


def test_tasks_requires_auth_no_token(client):
    res = client.post("/tasks", json={"title": "test"})
    assert res.status_code == 401


def test_tasks_requires_auth_invalid_token(client):
    headers = auth_headers("invalid.token.here")
    res = client.get("/tasks", headers=headers)
    assert res.status_code == 401


def test_tasks_requires_auth_expired_token(client):
    expired = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsInVzZXJuYW1lIjoidGVzdCIsInJvbGUiOiJ1c2VyIiwiZXhwIjoxMDAwMDAwMDAwLCJpYXQiOjEwMDAwMDAwMDB9.fake"
    res = client.get("/tasks", headers=auth_headers(expired))
    assert res.status_code == 401


# ── Task CRUD Tests (authenticated) ───────────────────────────

def test_create_task_success(client, auth):
    headers = auth_headers(auth)
    res = client.post("/tasks", json={"title": "Buy groceries"}, headers=headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert data["id"] is not None
    assert "created_at" in data


def test_create_task_missing_title_returns_400(client, auth):
    headers = auth_headers(auth)
    res = client.post("/tasks", json={}, headers=headers)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_create_task_empty_title_returns_400(client, auth):
    headers = auth_headers(auth)
    res = client.post("/tasks", json={"title": ""}, headers=headers)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_create_task_whitespace_title_returns_400(client, auth):
    headers = auth_headers(auth)
    res = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_list_tasks_empty(client, auth):
    headers = auth_headers(auth)
    res = client.get("/tasks", headers=headers)
    assert res.status_code == 200
    assert res.get_json() == []


def test_list_tasks_ordered_by_created_at_desc(client, auth):
    headers = auth_headers(auth)
    client.post("/tasks", json={"title": "First"}, headers=headers)
    client.post("/tasks", json={"title": "Second"}, headers=headers)
    res = client.get("/tasks", headers=headers)
    data = res.get_json()
    assert len(data) == 2
    assert data[0]["title"] == "Second"
    assert data[1]["title"] == "First"


def test_get_task_success(client, auth):
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Test task"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.get(f"/tasks/{task_id}", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["title"] == "Test task"


def test_get_task_not_found(client, auth):
    headers = auth_headers(auth)
    res = client.get("/tasks/9999", headers=headers)
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_update_task_title(client, auth):
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Original"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "Updated"}, headers=headers)
    assert res.status_code == 200
    assert res.get_json()["title"] == "Updated"
    assert res.get_json()["status"] == "pending"


def test_update_task_status(client, auth):
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Task"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    assert res.status_code == 200
    assert res.get_json()["status"] == "completed"
    assert res.get_json()["title"] == "Task"


def test_update_task_both_fields(client, auth):
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Old"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "New", "status": "done"}, headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"


def test_update_task_empty_title_returns_400(client, auth):
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Task"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": ""}, headers=headers)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_update_task_whitespace_title_returns_400(client, auth):
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Task"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "   "}, headers=headers)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_update_task_not_found(client, auth):
    headers = auth_headers(auth)
    res = client.put("/tasks/9999", json={"title": "Ghost"}, headers=headers)
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_update_task_with_no_fields_does_not_crash(client, auth):
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Keep"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={}, headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["title"] == "Keep"
    assert data["status"] == "pending"


def test_task_default_status_is_pending(client, auth):
    headers = auth_headers(auth)
    res = client.post("/tasks", json={"title": "Default test"}, headers=headers)
    assert res.get_json()["status"] == "pending"


# ── User Isolation Tests ─────────────────────────────────────

def test_user_cannot_see_other_users_tasks(client):
    token_a = register_and_login(client, "userA", "password123")
    token_b = register_and_login(client, "userB", "password456")

    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    client.post("/tasks", json={"title": "Task A"}, headers=headers_a)
    client.post("/tasks", json={"title": "Task B"}, headers=headers_b)

    res = client.get("/tasks", headers=headers_a)
    data = res.get_json()
    titles = [t["title"] for t in data]
    assert "Task A" in titles
    assert "Task B" not in titles

    res = client.get("/tasks", headers=headers_b)
    data = res.get_json()
    titles = [t["title"] for t in data]
    assert "Task B" in titles
    assert "Task A" not in titles


def test_user_cannot_get_other_users_task(client):
    token_a = register_and_login(client, "userC", "password123")
    token_b = register_and_login(client, "userD", "password123")

    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    create_res = client.post("/tasks", json={"title": "C's task"}, headers=headers_a)
    task_id = create_res.get_json()["id"]

    res = client.get(f"/tasks/{task_id}", headers=headers_b)
    assert res.status_code == 404


def test_user_cannot_update_other_users_task(client):
    token_a = register_and_login(client, "userE", "password123")
    token_b = register_and_login(client, "userF", "password123")

    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    create_res = client.post("/tasks", json={"title": "E's task"}, headers=headers_a)
    task_id = create_res.get_json()["id"]

    res = client.put(f"/tasks/{task_id}", json={"title": "Hacked"}, headers=headers_b)
    assert res.status_code == 404


# ── Notification Trigger Tests ────────────────────────────────

def test_update_task_to_completed_triggers_notification(client, auth, mocker):
    mock_delay = mocker.patch("app.send_notification_email.delay")
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Notify Me"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    assert res.status_code == 200
    mock_delay.assert_called_once_with("testuser", "Notify Me")


def test_update_task_to_other_status_does_not_trigger_notification(client, auth, mocker):
    mock_delay = mocker.patch("app.send_notification_email.delay")
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "No Notify"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"status": "in_progress"}, headers=headers)
    assert res.status_code == 200
    mock_delay.assert_not_called()


def test_update_task_title_only_does_not_trigger_notification(client, auth, mocker):
    mock_delay = mocker.patch("app.send_notification_email.delay")
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Title Only"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "New Title"}, headers=headers)
    assert res.status_code == 200
    mock_delay.assert_not_called()


def test_update_task_both_title_and_completed_triggers_notification(client, auth, mocker):
    mock_delay = mocker.patch("app.send_notification_email.delay")
    headers = auth_headers(auth)
    create_res = client.post("/tasks", json={"title": "Both"}, headers=headers)
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "Both Updated", "status": "completed"}, headers=headers)
    assert res.status_code == 200
    mock_delay.assert_called_once_with("testuser", "Both Updated")


def test_notification_not_triggered_on_task_not_found(client, auth, mocker):
    mock_delay = mocker.patch("app.send_notification_email.delay")
    headers = auth_headers(auth)
    res = client.put("/tasks/9999", json={"status": "completed"}, headers=headers)
    assert res.status_code == 404
    mock_delay.assert_not_called()
