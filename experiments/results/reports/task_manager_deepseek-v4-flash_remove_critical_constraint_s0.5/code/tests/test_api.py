import sqlite3

from task_api import create_app


def create_task(client, **overrides):
    payload = {"title": "Write report"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_list_empty(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"items": [], "total": 0, "page": 1, "per_page": 20}


def test_create_task_minimal(client):
    resp = create_task(client)
    assert resp.status_code == 201
    task = resp.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write report"
    assert task["description"] is None
    assert task["status"] == "pending"
    assert task["priority"] == 3
    assert task["due_date"] is None
    assert task["created_at"] == task["updated_at"]
    assert "T" in task["created_at"]


def test_create_task_all_fields(client):
    resp = create_task(
        client,
        title="  Deploy v2  ",
        description="  Ship to production  ",
        status="in_progress",
        priority=5,
        due_date="2026-09-01",
    )
    assert resp.status_code == 201
    task = resp.get_json()
    assert task["title"] == "Deploy v2"
    assert task["description"] == "Ship to production"
    assert task["status"] == "in_progress"
    assert task["priority"] == 5
    assert task["due_date"] == "2026-09-01"


def test_create_task_title_required(client):
    resp = client.post("/api/tasks", json={})
    assert resp.status_code == 400
    assert "title" in resp.get_json()["error"]


def test_create_task_empty_title(client):
    resp = create_task(client, title="   ")
    assert resp.status_code == 400
    assert "title" in resp.get_json()["error"]


def test_create_task_invalid_status(client):
    resp = create_task(client, status="done")
    assert resp.status_code == 400
    assert "status" in resp.get_json()["error"]


def test_create_task_invalid_priority(client):
    for bad in (0, 6, "high", True, None, 3.5):
        resp = create_task(client, priority=bad)
        assert resp.status_code == 400, bad
        assert "priority" in resp.get_json()["error"]


def test_create_task_invalid_due_date(client):
    for bad in ("not-a-date", "2026-13-01", "2026/09/01", 20260901, "2026-09-01T00:00"):
        resp = create_task(client, due_date=bad)
        assert resp.status_code == 400, bad
        assert "due_date" in resp.get_json()["error"]


def test_create_task_non_object_body(client):
    resp = client.post("/api/tasks", json=["a", "b"])
    assert resp.status_code == 400


def test_create_task_invalid_json(client):
    resp = client.post(
        "/api/tasks", data="{not json", content_type="application/json"
    )
    assert resp.status_code == 400


def test_get_task(client):
    created = create_task(client, title="Read a book").get_json()
    resp = client.get(f"/api/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Read a book"


def test_get_missing_task(client):
    resp = client.get("/api/tasks/999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_put_full_update(client):
    created = create_task(client).get_json()
    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={"title": "Rewritten", "status": "completed", "priority": 1},
    )
    assert resp.status_code == 200
    task = resp.get_json()
    assert task["title"] == "Rewritten"
    assert task["status"] == "completed"
    assert task["priority"] == 1
    assert task["description"] is None
    assert task["due_date"] is None


def test_put_requires_title(client):
    created = create_task(client).get_json()
    resp = client.put(f"/api/tasks/{created['id']}", json={"status": "completed"})
    assert resp.status_code == 400
    assert "title" in resp.get_json()["error"]


def test_patch_partial_update(client):
    created = create_task(client, description="first draft").get_json()
    resp = client.patch(
        f"/api/tasks/{created['id']}", json={"status": "completed"}
    )
    assert resp.status_code == 200
    task = resp.get_json()
    assert task["status"] == "completed"
    assert task["description"] == "first draft"
    assert task["title"] == "Write report"


def test_patch_empty_body_keeps_fields(client):
    created = create_task(client).get_json()
    resp = client.patch(f"/api/tasks/{created['id']}", json={})
    assert resp.status_code == 200
    task = resp.get_json()
    assert task["title"] == "Write report"
    assert task["status"] == "pending"


def test_patch_clear_description(client):
    created = create_task(client, description="notes").get_json()
    resp = client.patch(f"/api/tasks/{created['id']}", json={"description": None})
    assert resp.status_code == 200
    assert resp.get_json()["description"] is None


def test_patch_invalid_status(client):
    created = create_task(client).get_json()
    resp = client.patch(f"/api/tasks/{created['id']}", json={"status": "urgent"})
    assert resp.status_code == 400


def test_update_missing_task(client):
    assert client.put("/api/tasks/999", json={"title": "x"}).status_code == 404
    assert client.patch("/api/tasks/999", json={"status": "completed"}).status_code == 404


def test_delete_task(client):
    created = create_task(client).get_json()
    resp = client.delete(f"/api/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == created["id"]
    assert client.get(f"/api/tasks/{created['id']}").status_code == 404


def test_delete_missing_task(client):
    resp = client.delete("/api/tasks/999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_list_status_filter(client):
    create_task(client, title="One", status="completed")
    create_task(client, title="Two")
    resp = client.get("/api/tasks?status=completed")
    body = resp.get_json()
    assert body["total"] == 1
    assert [t["title"] for t in body["items"]] == ["One"]


def test_list_status_filter_invalid(client):
    resp = client.get("/api/tasks?status=bogus")
    assert resp.status_code == 400


def test_list_search(client):
    create_task(client, title="Buy milk")
    create_task(client, title="Write code", description="uses milk crates")
    create_task(client, title="Walk dog")
    resp = client.get("/api/tasks?q=milk")
    body = resp.get_json()
    assert body["total"] == 2
    titles = {t["title"] for t in body["items"]}
    assert titles == {"Buy milk", "Write code"}


def test_list_pagination(client):
    for i in range(5):
        create_task(client, title=f"Task {i}")
    resp = client.get("/api/tasks?page=2&per_page=2")
    body = resp.get_json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["per_page"] == 2
    assert len(body["items"]) == 2


def test_list_per_page_capped(client):
    for i in range(5):
        create_task(client, title=f"Task {i}")
    resp = client.get("/api/tasks?per_page=1000")
    assert resp.get_json()["per_page"] == 100


def test_list_sort(client):
    create_task(client, title="banana")
    create_task(client, title="apple")
    resp = client.get("/api/tasks?sort=title&order=asc")
    titles = [t["title"] for t in resp.get_json()["items"]]
    assert titles == ["apple", "banana"]
    resp = client.get("/api/tasks?sort=title&order=desc")
    titles = [t["title"] for t in resp.get_json()["items"]]
    assert titles == ["banana", "apple"]


def test_list_invalid_sort(client):
    assert client.get("/api/tasks?sort=nope").status_code == 400


def test_list_invalid_page(client):
    assert client.get("/api/tasks?page=0").status_code == 400
    assert client.get("/api/tasks?page=abc").status_code == 400


def test_updated_at_changes_on_update(client):
    created = create_task(client).get_json()
    resp = client.patch(f"/api/tasks/{created['id']}", json={"title": "Changed"})
    updated = resp.get_json()
    assert updated["updated_at"] != created["updated_at"]
    assert updated["created_at"] == created["created_at"]


def test_unknown_route_returns_json_404(client):
    resp = client.get("/api/nope")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}


def test_method_not_allowed_returns_json_405(client):
    resp = client.delete("/api/tasks")
    assert resp.status_code == 405
    assert resp.get_json() == {"error": "method not allowed"}


def test_migrations_applied(app, db_path):
    conn = sqlite3.connect(db_path)
    try:
        versions = {
            r[0]
            for r in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        assert versions == {
            "001_create_tasks.sql",
            "002_add_priority.sql",
            "003_add_due_date.sql",
        }
        columns = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "priority" in columns
        assert "due_date" in columns
    finally:
        conn.close()


def test_migrations_are_idempotent(app, db_path):
    second = create_app({"TESTING": True, "DATABASE": db_path})
    with second.test_client() as client:
        create_task(client, title="Still works")
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        assert count == 3
    finally:
        conn.close()


def test_data_persists_across_app_instances(client, db_path):
    created = create_task(client, title="Persistent task").get_json()
    other = create_app({"TESTING": True, "DATABASE": db_path})
    other_client = other.test_client()
    resp = other_client.get(f"/api/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Persistent task"
