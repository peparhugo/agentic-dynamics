def register(client, username, password):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="secret"):
    register(client, username, password)
    resp = login(client, username, password)
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


def create_task(client, title, username="alice", password="secret"):
    return client.post(
        "/tasks", json={"title": title}, headers=auth_headers(client, username, password)
    )


def test_create_task(client):
    resp = create_task(client, "Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["created_at"]
    assert data["owner_id"]


def test_create_task_missing_title(client):
    resp = client.post(
        "/tasks", json={}, headers=auth_headers(client)
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client):
    resp = client.post(
        "/tasks", json={"title": "   "}, headers=auth_headers(client)
    )
    assert resp.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client):
    create_task(client, "first")
    create_task(client, "second")
    create_task(client, "third")
    resp = client.get("/tasks", headers=auth_headers(client))
    assert resp.status_code == 200
    body = resp.get_json()
    tasks = body["data"]
    assert len(tasks) == 3
    assert body["total"] == 3
    assert body["next_cursor"] is None
    assert [t["title"] for t in tasks] == ["third", "second", "first"]
    assert [t["created_at"] for t in tasks] == sorted(
        [t["created_at"] for t in tasks], reverse=True
    )


def test_get_task(client):
    created = create_task(client, "Walk dog").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers(client))
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Walk dog"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999", headers=auth_headers(client))
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client):
    created = create_task(client, "Read book").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Read a book", "status": "done"},
        headers=auth_headers(client),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Read a book"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


def test_update_task_partial(client):
    created = create_task(client, "Code").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers=auth_headers(client),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Code"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put(
        "/tasks/999", json={"title": "x"}, headers=auth_headers(client)
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── Auth ──────────────────────────────────────────────────────

def test_register_creates_user(client):
    resp = register(client, "bob", "hunter2")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "bob"
    assert data["id"]
    assert "password_hash" not in data


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    assert register(client, "bob", "hunter2").status_code == 201
    resp = register(client, "bob", "otherpass")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_login_returns_token(client):
    register(client, "bob", "hunter2")
    resp = login(client, "bob", "hunter2")
    assert resp.status_code == 200
    assert resp.get_json()["token"]


def test_login_invalid_credentials(client):
    register(client, "bob", "hunter2")
    resp = login(client, "bob", "wrong")
    assert resp.status_code == 401
    resp = login(client, "nobody", "hunter2")
    assert resp.status_code == 401


def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_invalid_token(client):
    headers = {"Authorization": "Bearer not.a.token"}
    assert client.get("/tasks", headers=headers).status_code == 401
    assert client.post("/tasks", json={"title": "x"}, headers=headers).status_code == 401


def test_users_see_only_their_own_tasks(client):
    alice = auth_headers(client, "alice", "secret")
    bob = auth_headers(client, "bob", "hunter2")

    a1 = client.post("/tasks", json={"title": "alice task"}, headers=alice).get_json()
    b1 = client.post("/tasks", json={"title": "bob task"}, headers=bob).get_json()

    alice_tasks = client.get("/tasks", headers=alice).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=bob).get_json()["data"]
    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]

    assert client.get(f"/tasks/{b1['id']}", headers=alice).status_code == 404
    assert client.get(f"/tasks/{a1['id']}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{b1['id']}", json={"title": "hacked"}, headers=alice).status_code == 404
