import os
import importlib.util
import json

# Ensure in-memory DB before loading app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
here = os.path.dirname(__file__)
app_path = os.path.join(here, "..", "app.py")
spec = importlib.util.spec_from_file_location("app", os.path.abspath(app_path))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
app.rate_limiter.clear()
# increase rate limits for tests to avoid flakiness
app.RATE_LIMIT_POINTS = 1000


def test_register_and_login():
    client = app.app.test_client()
    # register
    r = client.post("/api/v1/auth/register", json={"username": "alice", "password": "secret"})
    assert r.status_code == 201
    data = r.get_json()
    assert data["username"] == "alice"

    # duplicate register
    r = client.post("/api/v1/auth/register", json={"username": "alice", "password": "secret"})
    assert r.status_code == 400

    # login
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret"})
    assert r.status_code == 200
    data = r.get_json()
    assert "access_token" in data


def _get_token(client, username="alice", password="secret"):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return r.get_json()["access_token"]


def test_items_crud_and_pagination():
    client = app.app.test_client()
    token = _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # create several items
    for i in range(15):
        r = client.post("/api/v1/items", json={"name": f"item{i}", "description": "x"}, headers=headers)
        assert r.status_code == 201

    # list page 1 (default per_page 10)
    r = client.get("/api/v1/items", headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data["page"] == 1
    assert data["per_page"] == 10
    assert data["total"] == 15
    assert len(data["items"]) == 10

    # page 2
    r = client.get("/api/v1/items?page=2", headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data["page"] == 2
    assert len(data["items"]) == 5

    # get single
    item_id = data["items"][0]["id"]
    r = client.get(f"/api/v1/items/{item_id}", headers=headers)
    assert r.status_code == 200

    # update
    r = client.put(f"/api/v1/items/{item_id}", json={"name": "updated"}, headers=headers)
    assert r.status_code == 200
    assert r.get_json()["name"] == "updated"

    # delete
    r = client.delete(f"/api/v1/items/{item_id}", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["deleted"] is True


def test_input_validation_and_auth_errors():
    client = app.app.test_client()
    # missing token
    r = client.get("/api/v1/items")
    assert r.status_code == 401

    # login with wrong creds
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401

    # create item with blank name
    token = _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/v1/items", json={"name": "   "}, headers=headers)
    assert r.status_code == 400


def test_rate_limiting():
    client = app.app.test_client()
    # reset limiter and set a small limit for the test
    app.rate_limiter.clear()
    app.RATE_LIMIT_POINTS = 3
    token = _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    # allow RATE_LIMIT_POINTS requests then one more should be 429
    points = app.RATE_LIMIT_POINTS
    for i in range(points):
        r = client.get("/api/v1/items", headers=headers)
        assert r.status_code in (200, 400)
    r = client.get("/api/v1/items", headers=headers)
    assert r.status_code == 429
