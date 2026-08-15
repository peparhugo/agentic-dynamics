from tests.conftest import auth_header, get_token


def test_list_categories_empty(client):
    token = get_token(client)
    resp = client.get("/api/categories", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["categories"] == []


def test_create_category(client):
    token = get_token(client)
    resp = client.post(
        "/api/categories",
        json={"name": "Work", "color": "#ff0000"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    category = resp.get_json()["category"]
    assert category["name"] == "Work"
    assert category["color"] == "#ff0000"


def test_create_category_requires_name(client):
    token = get_token(client)
    resp = client.post("/api/categories", json={}, headers=auth_header(token))
    assert resp.status_code == 400


def test_create_category_duplicate(client):
    token = get_token(client)
    client.post(
        "/api/categories", json={"name": "Work"}, headers=auth_header(token)
    )
    resp = client.post(
        "/api/categories", json={"name": "Work"}, headers=auth_header(token)
    )
    assert resp.status_code == 409


def test_list_categories_sorted(client):
    token = get_token(client)
    client.post("/api/categories", json={"name": "Zebra"}, headers=auth_header(token))
    client.post("/api/categories", json={"name": "Alpha"}, headers=auth_header(token))
    resp = client.get("/api/categories", headers=auth_header(token))
    names = [c["name"] for c in resp.get_json()["categories"]]
    assert names == ["Alpha", "Zebra"]


def test_categories_require_auth(client):
    assert client.get("/api/categories").status_code == 401
    assert client.post("/api/categories", json={"name": "X"}).status_code == 401


def test_task_filter_by_category(client):
    token = get_token(client)
    cat_resp = client.post(
        "/api/categories", json={"name": "Work"}, headers=auth_header(token)
    )
    category_id = cat_resp.get_json()["category"]["id"]

    client.post(
        "/api/tasks",
        json={"title": "Task A", "category_id": category_id},
        headers=auth_header(token),
    )
    client.post(
        "/api/tasks", json={"title": "Task B"}, headers=auth_header(token)
    )

    resp = client.get(
        f"/api/tasks?category_id={category_id}", headers=auth_header(token)
    )
    data = resp.get_json()
    assert data["meta"]["total"] == 1
    assert data["tasks"][0]["title"] == "Task A"


def test_task_filter_by_assignee(client):
    token = get_token(client)
    get_token(client, username="bob", email="bob@example.com", password="secret456")

    client.post(
        "/api/tasks",
        json={"title": "Assigned", "assignee_id": 2},
        headers=auth_header(token),
    )
    client.post(
        "/api/tasks", json={"title": "Unassigned"}, headers=auth_header(token)
    )

    resp = client.get("/api/tasks?assignee_id=2", headers=auth_header(token))
    data = resp.get_json()
    assert data["meta"]["total"] == 1
    assert data["tasks"][0]["title"] == "Assigned"


def test_list_users(client):
    token = get_token(client)
    get_token(client, username="bob", email="bob@example.com", password="secret456")
    resp = client.get("/api/users", headers=auth_header(token))
    assert resp.status_code == 200
    users = resp.get_json()["users"]
    assert len(users) == 2
    assert {u["username"] for u in users} == {"alice", "bob"}


def test_users_require_auth(client):
    assert client.get("/api/users").status_code == 401
