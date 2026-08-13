def test_create_task_success(client, auth_headers):
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_blank_title(client, auth_headers):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_no_body(client, auth_headers):
    resp = client.post("/tasks", headers=auth_headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_list_tasks_empty(client, auth_headers):
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_order_desc(client, auth_headers):
    client.post("/tasks", json={"title": "first"}, headers=auth_headers)
    client.post("/tasks", json={"title": "second"}, headers=auth_headers)
    client.post("/tasks", json={"title": "third"}, headers=auth_headers)

    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["third", "second", "first"]
    assert body["total"] == 3
    assert body["next_cursor"] is None


def test_get_task_success(client, auth_headers):
    created = client.post("/tasks", json={"title": "Read book"}, headers=auth_headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "Read book"
    assert data["status"] == "pending"


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/tasks/9999", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_title(client, auth_headers):
    created = client.post("/tasks", json={"title": "Old title"}, headers=auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client, auth_headers):
    created = client.post("/tasks", json={"title": "Task"}, headers=auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Task"


def test_update_task_title_and_status(client, auth_headers):
    created = client.post("/tasks", json={"title": "Task"}, headers=auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "done"}, headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "done"


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/tasks/9999", json={"title": "nope"}, headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_create_then_persisted_in_db(client, auth_headers):
    created = client.post("/tasks", json={"title": "Persisted"}, headers=auth_headers).get_json()
    listed = client.get("/tasks", headers=auth_headers).get_json()
    assert any(t["id"] == created["id"] and t["status"] == "pending" for t in listed["data"])
