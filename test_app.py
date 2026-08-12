import time


def test_post_create_task(client):
    resp = client.post("/tasks", json={"title": "write code"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "write code"
    assert data["status"] == "pending"
    assert data["created_at"]


def test_post_missing_title_returns_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"]


def test_post_empty_title_returns_400(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_get_list_ordered_by_created_at_desc(client):
    client.post("/tasks", json={"title": "first"})
    time.sleep(0.01)
    client.post("/tasks", json={"title": "second"})
    time.sleep(0.01)
    client.post("/tasks", json={"title": "third"})

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


def test_get_single_task(client):
    created = client.post("/tasks", json={"title": "single"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "single"


def test_get_task_not_found_returns_404(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_put_update_title(client):
    created = client.post("/tasks", json={"title": "old"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "pending"


def test_put_update_status(client):
    created = client.post("/tasks", json={"title": "t"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"


def test_put_update_title_and_status(client):
    created = client.post("/tasks", json={"title": "t"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "new", "status": "in_progress"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "in_progress"


def test_put_task_not_found_returns_404(client):
    resp = client.put("/tasks/999", json={"title": "nope"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()
