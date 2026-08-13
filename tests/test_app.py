def test_create_task_success(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_blank_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_no_body(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_order_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    client.post("/tasks", json={"title": "third"})

    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    titles = [t["title"] for t in data]
    assert titles == ["third", "second", "first"]


def test_get_task_success(client):
    created = client.post("/tasks", json={"title": "Read book"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "Read book"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_title(client):
    created = client.post("/tasks", json={"title": "Old title"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Task"


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "done"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "nope"})
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_create_then_persisted_in_db(client):
    created = client.post("/tasks", json={"title": "Persisted"}).get_json()
    listed = client.get("/tasks").get_json()
    assert any(t["id"] == created["id"] and t["status"] == "pending" for t in listed)
