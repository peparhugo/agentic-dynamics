import app as app_module


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(client, username="alice", password="secret"):
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def seed_tasks(n, owner_id=1):
    for i in range(n):
        app_module.task_repo.create(f"task {i}", owner_id)


def list_ids(payload):
    return [t["id"] for t in payload["data"]]


# ── Response shape ───────────────────────────────────────────

def test_list_returns_paginated_response_shape(client):
    register(client)
    headers = auth_header(client)
    seed_tasks(25)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert isinstance(body["next_cursor"], str)


def test_empty_result(client):
    register(client)
    headers = auth_header(client)

    body = client.get("/tasks", headers=headers).get_json()
    assert body == {"data": [], "next_cursor": None, "total": 0}


def test_first_page_without_cursor_returns_newest_first(client):
    register(client)
    headers = auth_header(client)
    seed_tasks(5)

    body = client.get("/tasks", headers=headers).get_json()
    assert body["total"] == 5
    assert body["next_cursor"] is None
    assert list_ids(body) == [5, 4, 3, 2, 1]
    assert [t["title"] for t in body["data"]] == [
        "task 4",
        "task 3",
        "task 2",
        "task 1",
        "task 0",
    ]


# ── limit parameter ──────────────────────────────────────────

def test_default_limit_is_20(client):
    register(client)
    headers = auth_header(client)
    seed_tasks(30)

    body = client.get("/tasks", headers=headers).get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 30
    assert body["next_cursor"] is not None


def test_limit_query_param(client):
    register(client)
    headers = auth_header(client)
    seed_tasks(30)

    body = client.get("/tasks?limit=5", headers=headers).get_json()
    assert len(body["data"]) == 5
    assert list_ids(body) == [30, 29, 28, 27, 26]


def test_limit_clamped_to_max_100(client):
    register(client)
    headers = auth_header(client)
    seed_tasks(120)

    body = client.get("/tasks?limit=500", headers=headers).get_json()
    assert len(body["data"]) == 100
    assert body["total"] == 120
    assert body["next_cursor"] is not None


def test_invalid_limit_returns_400(client):
    register(client)
    headers = auth_header(client)
    assert client.get("/tasks?limit=abc", headers=headers).status_code == 400
    assert client.get("/tasks?limit=0", headers=headers).status_code == 400
    assert client.get("/tasks?limit=-3", headers=headers).status_code == 400


# ── cursor navigation ────────────────────────────────────────

def test_cursor_returns_next_page(client):
    register(client)
    headers = auth_header(client)
    seed_tasks(10)

    first = client.get("/tasks?limit=3", headers=headers).get_json()
    assert list_ids(first) == [10, 9, 8]
    assert first["next_cursor"] == "8"

    second = client.get(
        f"/tasks?limit=3&cursor={first['next_cursor']}", headers=headers
    ).get_json()
    assert list_ids(second) == [7, 6, 5]
    assert second["next_cursor"] == "5"


def test_paginate_through_all_pages(client):
    register(client)
    headers = auth_header(client)
    seed_tasks(45)

    seen = []
    cursor = None
    pages = 0
    while True:
        url = "/tasks?limit=10"
        if cursor:
            url += f"&cursor={cursor}"
        body = client.get(url, headers=headers).get_json()
        seen.extend(list_ids(body))
        pages += 1
        if body["next_cursor"] is None:
            break
        cursor = body["next_cursor"]

    assert pages == 5
    assert len(seen) == 45
    assert len(set(seen)) == 45
    assert seen == sorted(seen, reverse=True)


# ── Isolation ────────────────────────────────────────────────

def test_pagination_respects_per_user_isolation(client):
    register(client, "alice")
    register(client, "bob")
    alice_headers = auth_header(client, "alice")
    bob_headers = auth_header(client, "bob")
    seed_tasks(25, owner_id=1)
    seed_tasks(3, owner_id=2)

    alice_body = client.get("/tasks?limit=100", headers=alice_headers).get_json()
    assert alice_body["total"] == 25
    assert len(alice_body["data"]) == 25

    bob_body = client.get("/tasks", headers=bob_headers).get_json()
    assert bob_body["total"] == 3
    assert len(bob_body["data"]) == 3
    assert bob_body["next_cursor"] is None
