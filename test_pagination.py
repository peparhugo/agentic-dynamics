import pytest

import app as app_module
from conftest import set_default_limit


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "test.db"))
    app_module.init_db()
    app_module.migrate()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create(client, title, headers):
    return client.post("/tasks", json={"title": title}, headers=headers)


def test_list_tasks_returns_paginated_shape(client, auth_headers):
    for i in range(3):
        _create(client, f"task {i}", auth_headers)

    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {"data", "next_cursor", "total"}
    assert data["total"] == 3
    assert [t["title"] for t in data["data"]] == ["task 2", "task 1", "task 0"]
    assert data["next_cursor"] is None


def test_cursor_pagination_walks_through_pages(client, auth_headers):
    for i in range(5):
        _create(client, f"task {i}", auth_headers)

    page1 = client.get("/tasks?limit=2", headers=auth_headers).get_json()
    assert [t["id"] for t in page1["data"]] == [5, 4]
    assert page1["next_cursor"] == "4"
    assert page1["total"] == 5

    page2 = client.get("/tasks?limit=2&cursor=4", headers=auth_headers).get_json()
    assert [t["id"] for t in page2["data"]] == [3, 2]
    assert page2["next_cursor"] == "2"

    page3 = client.get("/tasks?limit=2&cursor=2", headers=auth_headers).get_json()
    assert [t["id"] for t in page3["data"]] == [1]
    assert page3["next_cursor"] is None


def test_default_limit_is_20_and_max_is_100(client, auth_headers):
    for i in range(25):
        _create(client, f"task {i}", auth_headers)

    first = client.get("/tasks", headers=auth_headers).get_json()
    assert len(first["data"]) == 20
    assert first["total"] == 25
    assert first["next_cursor"] is not None

    all_tasks = client.get("/tasks?limit=100", headers=auth_headers).get_json()
    assert len(all_tasks["data"]) == 25
    assert all_tasks["next_cursor"] is None


def test_limit_is_capped_at_100(client, auth_headers):
    set_default_limit("1000 per minute")
    for i in range(120):
        _create(client, f"task {i}", auth_headers)

    page = client.get("/tasks?limit=1000", headers=auth_headers).get_json()
    assert len(page["data"]) == 100
    assert page["total"] == 120
    assert page["next_cursor"] is not None


def test_invalid_cursor_returns_first_page(client, auth_headers):
    for i in range(3):
        _create(client, f"task {i}", auth_headers)

    page = client.get("/tasks?cursor=not-a-number", headers=auth_headers).get_json()
    assert [t["title"] for t in page["data"]] == ["task 2", "task 1", "task 0"]
