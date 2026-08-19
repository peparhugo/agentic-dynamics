def test_list_categories_empty(client, auth_headers):
    resp = client.get("/api/categories", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["categories"] == []


def test_create_category(client, auth_headers):
    resp = client.post("/api/categories", json={"name": "Work", "color": "#ff0000"},
                       headers=auth_headers)
    assert resp.status_code == 201
    cat = resp.get_json()["category"]
    assert cat["name"] == "Work"
    assert cat["color"] == "#ff0000"


def test_create_category_duplicate(client, auth_headers, category):
    resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_headers)
    assert resp.status_code == 409


def test_create_category_no_name(client, auth_headers):
    resp = client.post("/api/categories", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_get_category(client, auth_headers, category):
    resp = client.get(f"/api/categories/{category['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["category"]["name"] == "Work"


def test_get_category_not_found(client, auth_headers):
    resp = client.get("/api/categories/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_category(client, auth_headers, category):
    resp = client.put(f"/api/categories/{category['id']}",
                      json={"name": "Personal", "color": "#00ff00"},
                      headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["category"]["name"] == "Personal"
    assert resp.get_json()["category"]["color"] == "#00ff00"


def test_update_category_conflict(client, auth_headers):
    client.post("/api/categories", json={"name": "A"}, headers=auth_headers)
    r = client.post("/api/categories", json={"name": "B"}, headers=auth_headers)
    b_id = r.get_json()["category"]["id"]
    resp = client.put(f"/api/categories/{b_id}", json={"name": "A"}, headers=auth_headers)
    assert resp.status_code == 409


def test_delete_category(client, auth_headers):
    r = client.post("/api/categories", json={"name": "Temp"}, headers=auth_headers)
    cat_id = r.get_json()["category"]["id"]
    resp = client.delete(f"/api/categories/{cat_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert client.get(f"/api/categories/{cat_id}", headers=auth_headers).status_code == 404


def test_delete_category_with_tasks(client, auth_headers, category):
    client.post("/api/tasks", json={"title": "Do thing", "category_id": category["id"]},
                headers=auth_headers)
    resp = client.delete(f"/api/categories/{category['id']}", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.get_json()["task_count"] == 1


def test_categories_require_auth(client):
    assert client.get("/api/categories").status_code == 401
    assert client.post("/api/categories", json={"name": "X"}).status_code == 401
