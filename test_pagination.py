import app as app_module


def _create_tasks(client, auth, n):
    for i in range(n):
        resp = client.post("/tasks", json={"title": f"task-{i}"}, headers=auth)
        assert resp.status_code == 201


def test_pagination_response_shape(client, auth):
    _create_tasks(client, auth, 3)
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert isinstance(body["data"], list)
    assert body["total"] == 3


def test_pagination_default_limit(client, auth):
    _create_tasks(client, auth, 25)
    body = client.get("/tasks", headers=auth).get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_pagination_first_page_without_cursor(client, auth):
    _create_tasks(client, auth, 5)
    body = client.get("/tasks", headers=auth).get_json()
    assert len(body["data"]) == 5
    assert body["next_cursor"] is None
    assert body["total"] == 5


def test_pagination_cursor_walks_all_pages(client, auth):
    _create_tasks(client, auth, 45)
    seen = []
    cursor = None
    total = None
    for _ in range(10):
        url = "/tasks" if cursor is None else f"/tasks?cursor={cursor}"
        body = client.get(url, headers=auth).get_json()
        seen.extend(t["id"] for t in body["data"])
        total = body["total"]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 45
    assert total == 45
    assert len(set(seen)) == 45


def test_pagination_no_overlap_between_pages(client, auth):
    _create_tasks(client, auth, 25)
    page1 = client.get("/tasks?limit=10", headers=auth).get_json()
    page2 = client.get(
        f"/tasks?limit=10&cursor={page1['next_cursor']}", headers=auth
    ).get_json()
    page3 = client.get(
        f"/tasks?limit=10&cursor={page2['next_cursor']}", headers=auth
    ).get_json()

    ids1 = {t["id"] for t in page1["data"]}
    ids2 = {t["id"] for t in page2["data"]}
    ids3 = {t["id"] for t in page3["data"]}

    assert len(page1["data"]) == 10
    assert len(page2["data"]) == 10
    assert len(page3["data"]) == 5
    assert page3["next_cursor"] is None
    assert ids1.isdisjoint(ids2)
    assert ids2.isdisjoint(ids3)
    assert ids1.isdisjoint(ids3)


def test_pagination_limit_param(client, auth):
    _create_tasks(client, auth, 7)
    body = client.get("/tasks?limit=3", headers=auth).get_json()
    assert len(body["data"]) == 3
    assert body["total"] == 7
    assert body["next_cursor"] is not None


def test_pagination_limit_capped_at_100(client, auth):
    for i in range(150):
        app_module.task_repo.create_task(f"bulk-{i}", 1)
    body = client.get("/tasks?limit=1000", headers=auth).get_json()
    assert len(body["data"]) == 100
    assert body["total"] == 150
    assert body["next_cursor"] is not None


def test_pagination_invalid_cursor(client, auth):
    resp = client.get("/tasks?cursor=abc", headers=auth)
    assert resp.status_code == 400


def test_pagination_unknown_cursor_returns_empty_page(client, auth):
    _create_tasks(client, auth, 3)
    body = client.get("/tasks?cursor=99999", headers=auth).get_json()
    assert body["data"] == []
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_pagination_invalid_limit_falls_back_to_default(client, auth):
    _create_tasks(client, auth, 5)
    body = client.get("/tasks?limit=abc", headers=auth).get_json()
    assert len(body["data"]) == 5


def test_pagination_scoped_to_owner(client, auth, bob_auth):
    _create_tasks(client, auth, 5)
    _create_tasks(client, bob_auth, 3)
    alice = client.get("/tasks", headers=auth).get_json()
    bob = client.get("/tasks", headers=bob_auth).get_json()
    assert alice["total"] == 5
    assert bob["total"] == 3
