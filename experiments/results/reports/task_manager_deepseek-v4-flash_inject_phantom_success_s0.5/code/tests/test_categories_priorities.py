import pytest

from conftest import auth_headers, create_task


def test_list_priorities(client, users, priority_ids):
    resp = client.get("/priorities", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert [p["name"] for p in items] == ["low", "medium", "high", "urgent"]
    assert [p["level"] for p in items] == [1, 2, 3, 4]


def test_list_priorities_requires_auth(client):
    assert client.get("/priorities").status_code == 401


def test_list_categories(client, users):
    resp = client.get("/categories", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 200
    names = [c["name"] for c in resp.get_json()["items"]]
    assert "Work" in names and "Personal" in names


def test_create_category(client, users):
    resp = client.post(
        "/categories", json={"name": "Health"}, headers=auth_headers(users["alice"]["token"])
    )
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "Health"
    assert resp.get_json()["task_count"] == 0


def test_create_category_duplicate(client, users):
    client.post("/categories", json={"name": "Health"}, headers=auth_headers(users["alice"]["token"]))
    resp = client.post(
        "/categories", json={"name": "Health"}, headers=auth_headers(users["bob"]["token"])
    )
    assert resp.status_code == 409


def test_create_category_missing_name(client, users):
    resp = client.post("/categories", json={}, headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 400


def test_category_task_counts(client, users, category_ids):
    created = create_task(
        client,
        users["alice"]["token"],
        title="Work item",
        category_id=category_ids["Work"],
    )
    assert created.status_code == 201
    create_task(
        client,
        users["alice"]["token"],
        title="Work item 2",
        category_id=category_ids["Work"],
    )
    resp = client.get("/categories", headers=auth_headers(users["alice"]["token"]))
    counts = {c["name"]: c["task_count"] for c in resp.get_json()["items"]}
    assert counts["Work"] == 2


def test_priority_task_counts(client, users, priority_ids):
    create_task(client, users["alice"]["token"], title="Urgent task", priority_id=priority_ids["urgent"])
    resp = client.get("/priorities", headers=auth_headers(users["alice"]["token"]))
    counts = {p["name"]: p["task_count"] for p in resp.get_json()["items"]}
    assert counts["urgent"] == 1


def test_categories_requires_auth(client):
    assert client.get("/categories").status_code == 401


@pytest.mark.parametrize("url", ["/priorities", "/categories"])
def test_meta_endpoints_require_auth(client, url):
    assert client.get(url).status_code == 401
