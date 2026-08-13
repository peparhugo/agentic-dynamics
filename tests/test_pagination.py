import app as app_module


def _create_tasks(client, headers, n):
    # Bulk-creating tasks over HTTP would itself run into the 100
    # requests/minute rate limit for counts above that; periodically reset
    # the limiter's counters so these pagination tests aren't coupled to
    # rate-limiting behavior (covered separately in test_rate_limiting.py).
    created = []
    for i in range(n):
        if i % 50 == 0:
            app_module.limiter.reset()
        resp = client.post("/tasks", json={"title": f"task {i}"}, headers=headers)
        created.append(resp.get_json())
    return created


def test_list_tasks_empty_page(client, auth_headers):
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_default_limit(client, auth_headers):
    _create_tasks(client, auth_headers, 25)

    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 20
    assert data["total"] == 25
    assert data["next_cursor"] is not None
    assert data["next_cursor"] == data["data"][-1]["id"]


def test_list_tasks_respects_limit_param(client, auth_headers):
    _create_tasks(client, auth_headers, 10)

    resp = client.get("/tasks?limit=5", headers=auth_headers)
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["total"] == 10
    assert data["next_cursor"] == data["data"][-1]["id"]


def test_list_tasks_limit_capped_at_max(client, auth_headers):
    _create_tasks(client, auth_headers, 150)

    resp = client.get("/tasks?limit=1000", headers=auth_headers)
    data = resp.get_json()
    assert len(data["data"]) == 100
    assert data["total"] == 150
    assert data["next_cursor"] is not None


def test_list_tasks_limit_floor_is_one(client, auth_headers):
    _create_tasks(client, auth_headers, 5)

    resp = client.get("/tasks?limit=0", headers=auth_headers)
    data = resp.get_json()
    assert len(data["data"]) == 1


def test_list_tasks_last_page_has_no_next_cursor(client, auth_headers):
    _create_tasks(client, auth_headers, 3)

    resp = client.get("/tasks?limit=20", headers=auth_headers)
    data = resp.get_json()
    assert len(data["data"]) == 3
    assert data["next_cursor"] is None
    assert data["total"] == 3


def test_list_tasks_exact_page_boundary_has_no_next_cursor(client, auth_headers):
    _create_tasks(client, auth_headers, 20)

    resp = client.get("/tasks?limit=20", headers=auth_headers)
    data = resp.get_json()
    assert len(data["data"]) == 20
    assert data["next_cursor"] is None


def test_list_tasks_cursor_walks_through_all_pages(client, auth_headers):
    created = _create_tasks(client, auth_headers, 45)
    expected_order = [t["id"] for t in reversed(created)]

    seen_ids = []
    cursor = None
    pages = 0
    while True:
        url = "/tasks?limit=20"
        if cursor is not None:
            url += f"&cursor={cursor}"
        resp = client.get(url, headers=auth_headers)
        data = resp.get_json()
        seen_ids.extend(t["id"] for t in data["data"])
        pages += 1
        cursor = data["next_cursor"]
        if cursor is None:
            break
        assert pages < 10  # guard against an infinite loop bug

    assert pages == 3
    assert seen_ids == expected_order


def test_list_tasks_invalid_cursor_returns_400(client, auth_headers):
    resp = client.get("/tasks?cursor=not-a-number", headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_invalid_limit_returns_400(client, auth_headers):
    resp = client.get("/tasks?limit=not-a-number", headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_pagination_isolated_per_user(client, auth_headers):
    _create_tasks(client, auth_headers, 5)

    client.post("/auth/register", json={"username": "carol", "password": "secret123"})
    carol_login = client.post(
        "/auth/login", json={"username": "carol", "password": "secret123"}
    ).get_json()
    carol_headers = {"Authorization": f"Bearer {carol_login['token']}"}
    client.post("/tasks", json={"title": "carol task"}, headers=carol_headers)

    resp = client.get("/tasks", headers=carol_headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert len(data["data"]) == 1

    resp = client.get("/tasks", headers=auth_headers)
    data = resp.get_json()
    assert data["total"] == 5


def test_list_tasks_requires_auth_still_enforced(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
