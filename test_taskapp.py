import pytest

from taskapp import create_app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "tasks.db"
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def create(client, title="Buy milk"):
    return client.post("/tasks", json={"title": title})


class TestCreateTask:
    def test_create_task_success(self, client):
        resp = create(client, "Write report")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Write report"
        assert data["status"] == "pending"
        assert isinstance(data["id"], int)
        assert "created_at" in data and data["created_at"]

    def test_create_task_missing_title(self, client):
        resp = client.post("/tasks", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_empty_title(self, client):
        resp = client.post("/tasks", json={"title": "   "})
        assert resp.status_code == 400

    def test_create_task_non_string_title(self, client):
        resp = client.post("/tasks", json={"title": 123})
        assert resp.status_code == 400

    def test_create_task_no_body(self, client):
        resp = client.post("/tasks")
        assert resp.status_code == 400

    def test_create_task_strips_whitespace(self, client):
        resp = create(client, "  Trim me  ")
        assert resp.status_code == 201
        assert resp.get_json()["title"] == "Trim me"


class TestListTasks:
    def test_list_empty(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_ordered_desc_by_created_at(self, client):
        create(client, "first")
        create(client, "second")
        create(client, "third")
        resp = client.get("/tasks")
        assert resp.status_code == 200
        titles = [t["title"] for t in resp.get_json()]
        assert titles == ["third", "second", "first"]


class TestGetTask:
    def test_get_existing_task(self, client):
        created = create(client, "Read book").get_json()
        resp = client.get(f"/tasks/{created['id']}")
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Read book"

    def test_get_missing_task(self, client):
        resp = client.get("/tasks/999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestUpdateTask:
    def test_update_title_only(self, client):
        created = create(client, "Old title").get_json()
        resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_status_only(self, client):
        created = create(client, "Task").get_json()
        resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "done"
        assert data["title"] == "Task"

    def test_update_title_and_status(self, client):
        created = create(client, "Task").get_json()
        resp = client.put(
            f"/tasks/{created['id']}",
            json={"title": "Updated", "status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_missing_task(self, client):
        resp = client.put("/tasks/999", json={"title": "x"})
        assert resp.status_code == 404

    def test_update_empty_title_rejected(self, client):
        created = create(client, "Task").get_json()
        resp = client.put(f"/tasks/{created['id']}", json={"title": "  "})
        assert resp.status_code == 400

    def test_update_empty_status_rejected(self, client):
        created = create(client, "Task").get_json()
        resp = client.put(f"/tasks/{created['id']}", json={"status": ""})
        assert resp.status_code == 400

    def test_update_no_fields_rejected(self, client):
        created = create(client, "Task").get_json()
        resp = client.put(f"/tasks/{created['id']}", json={})
        assert resp.status_code == 400


class TestErrorFormat:
    def test_404_is_json(self, client):
        resp = client.get("/tasks/1")
        assert resp.content_type == "application/json"
        assert "error" in resp.get_json()

    def test_400_is_json(self, client):
        resp = client.post("/tasks", json={})
        assert resp.content_type == "application/json"
        assert "error" in resp.get_json()
