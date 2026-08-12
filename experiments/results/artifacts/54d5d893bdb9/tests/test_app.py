import app as task_app


def clear_tasks():
    with task_app.get_db() as connection:
        connection.execute("DELETE FROM tasks")
        connection.execute("DELETE FROM users")
        connection.commit()


def client():
    clear_tasks()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def authenticated_client(api, username="alice", password="secret"):
    response = api.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201
    response = api.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    api.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {response.get_json()['token']}"
    return api


def auth_header(api, username, password="secret"):
    response = api.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_create_task_uses_pending_status():
    response = authenticated_client(client()).post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] > 0
    assert body["title"] == "Write tests"
    assert body["status"] == "pending"
    assert body["created_at"]


def test_create_task_requires_nonblank_title():
    api = authenticated_client(client())

    assert api.post("/tasks", json={}).status_code == 400
    response = api.post("/tasks", json={"title": "  "})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_ordered_newest_first():
    api = authenticated_client(client())
    first = api.post("/tasks", json={"title": "First"}).get_json()
    second = api.post("/tasks", json={"title": "Second"}).get_json()

    response = api.get("/tasks")
    assert response.status_code == 200
    body = response.get_json()
    assert [task["id"] for task in body["data"]] == [second["id"], first["id"]]
    assert body["next_cursor"] is None
    assert body["total"] == 2


def test_list_tasks_supports_cursor_pagination():
    api = authenticated_client(client())
    created = [
        api.post("/tasks", json={"title": title}).get_json()
        for title in ("First", "Second", "Third")
    ]

    response = api.get("/tasks?limit=2")
    first_page = response.get_json()
    assert [task["id"] for task in first_page["data"]] == [created[2]["id"], created[1]["id"]]
    assert first_page["next_cursor"] == str(created[1]["id"])
    assert first_page["total"] == 3

    response = api.get(f"/tasks?cursor={first_page['next_cursor']}&limit=2")
    second_page = response.get_json()
    assert [task["id"] for task in second_page["data"]] == [created[0]["id"]]
    assert second_page["next_cursor"] is None
    assert second_page["total"] == 3


def test_list_tasks_rejects_invalid_pagination_parameters():
    api = authenticated_client(client())

    assert api.get("/tasks?limit=0").status_code == 400
    assert api.get("/tasks?limit=101").status_code == 400
    assert api.get("/tasks?cursor=not-an-id").status_code == 400


def test_rate_limit_returns_retry_after_header():
    api = authenticated_client(client())
    for _ in range(99):
        response = api.get("/tasks")
        assert response.status_code == 200

    response = api.get("/tasks")
    assert response.status_code == 200
    response = api.get("/tasks")
    assert response.status_code == 429
    assert response.headers.get("Retry-After")


def test_get_and_update_task():
    api = authenticated_client(client())
    created = api.post("/tasks", json={"title": "Old title"}).get_json()

    response = api.get(f"/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.get_json()["title"] == "Old title"

    response = api.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "complete"},
    )
    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "complete"


def test_completing_task_enqueues_owner_email(monkeypatch):
    api = authenticated_client(client())
    created = api.post("/tasks", json={"title": "Ship feature"}).get_json()
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: calls.append(args),
    )

    response = api.put(f"/tasks/{created['id']}", json={"status": "completed"})

    assert response.status_code == 200
    assert calls == [("alice", "Ship feature")]


def test_updating_completed_task_does_not_enqueue_another_email(monkeypatch):
    api = authenticated_client(client())
    created = api.post("/tasks", json={"title": "Ship feature"}).get_json()
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: calls.append(args),
    )

    api.put(f"/tasks/{created['id']}", json={"status": "completed"})
    response = api.put(f"/tasks/{created['id']}", json={"title": "Shipped"})

    assert response.status_code == 200
    assert calls == [("alice", "Ship feature")]


def test_missing_task_returns_json_404():
    api = authenticated_client(client())

    for method in (api.get, api.put):
        response = method("/tasks/999999", json={} if method == api.put else None)
        assert response.status_code == 404
        assert response.get_json() == {"error": "task not found"}


def test_tasks_require_a_valid_bearer_token():
    api = client()
    assert api.get("/tasks").status_code == 401
    assert api.get("/tasks", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert api.get("/tasks", headers={"Authorization": "Basic credentials"}).status_code == 401


def test_register_login_and_duplicate_user():
    api = client()
    response = api.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert response.status_code == 201
    assert response.get_json()["username"] == "alice"
    assert api.post("/auth/register", json={"username": "alice", "password": "secret"}).status_code == 409
    assert api.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    response = api.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert response.status_code == 200
    assert response.get_json().get("token")


def test_users_only_see_and_modify_their_own_tasks():
    api = authenticated_client(client(), "alice")
    task = api.post("/tasks", json={"title": "Alice task"}).get_json()

    api.post("/auth/register", json={"username": "bob", "password": "secret"})
    bob_headers = auth_header(api, "bob")

    assert api.get("/tasks", headers=bob_headers).get_json() == {
        "data": [], "next_cursor": None, "total": 0
    }
    assert api.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert api.put(f"/tasks/{task['id']}", json={"title": "hacked"}, headers=bob_headers).status_code == 404
    assert api.get(f"/tasks/{task['id']}").get_json()["title"] == "Alice task"
