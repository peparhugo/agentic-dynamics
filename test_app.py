def create_task(client, title):
    return client.post("/tasks", json={"title": title})


def test_create_task(client):
    resp = create_task(client, "Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["created_at"]


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client):
    create_task(client, "first")
    create_task(client, "second")
    create_task(client, "third")
    resp = client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert len(tasks) == 3
    assert [t["title"] for t in tasks] == ["third", "second", "first"]
    assert [t["created_at"] for t in tasks] == sorted(
        [t["created_at"] for t in tasks], reverse=True
    )


def test_get_task(client):
    created = create_task(client, "Walk dog").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Walk dog"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client):
    created = create_task(client, "Read book").get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Read a book", "status": "done"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Read a book"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


def test_update_task_partial(client):
    created = create_task(client, "Code").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Code"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()
