def test_create_project(client):
    resp = client.post(
        "/api/projects", json={"name": "Website Revamp", "description": "Q3 project"}
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["name"] == "Website Revamp"
    assert body["description"] == "Q3 project"
    assert "created_at" in body and "updated_at" in body


def test_create_project_requires_name(client):
    resp = client.post("/api/projects", json={"description": "no name"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_project_rejects_unknown_field(client):
    resp = client.post("/api/projects", json={"name": "X", "foo": "bar"})
    assert resp.status_code == 400


def test_create_project_defaults_description(client):
    resp = client.post("/api/projects", json={"name": "No description"})
    assert resp.status_code == 201
    assert resp.get_json()["description"] == ""


def test_list_projects(client, make_project):
    make_project(name="A")
    make_project(name="B")
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 2
    assert {p["name"] for p in body} == {"A", "B"}


def test_get_project(client, make_project):
    project = make_project()
    resp = client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == project["id"]


def test_get_project_404(client):
    resp = client.get("/api/projects/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_project(client, make_project):
    project = make_project(name="Old name")
    resp = client.put(
        f"/api/projects/{project['id']}", json={"name": "New name"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "New name"
    assert body["updated_at"] >= project["updated_at"]


def test_update_project_404(client):
    resp = client.put("/api/projects/999", json={"name": "X"})
    assert resp.status_code == 404


def test_delete_project(client, make_project):
    project = make_project()
    resp = client.delete(f"/api/projects/{project['id']}")
    assert resp.status_code == 204
    resp = client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 404


def test_delete_project_404(client):
    resp = client.delete("/api/projects/999")
    assert resp.status_code == 404


def test_delete_project_nulls_task_project_id(client, make_project, make_task):
    project = make_project()
    task = make_task(title="Linked task", project_id=project["id"])
    client.delete(f"/api/projects/{project['id']}")
    resp = client.get(f"/api/tasks/{task['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["project_id"] is None
