def register(client, username, password):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username, password):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def auth_headers(client, username="alice", password="secret"):
    register(client, username, password)
    resp = login(client, username, password)
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


def create_tasks(client, count, username="alice"):
    headers = auth_headers(client, username)
    for i in range(count):
        client.post("/tasks", json={"title": f"task {i}"}, headers=headers)
    return headers


def test_default_limit_returns_first_page(client):
    headers = create_tasks(client, 25)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] == str(body["data"][-1]["id"])
    assert body["data"][0]["title"] == "task 24"
    assert body["data"][-1]["title"] == "task 5"


def test_cursor_paginates_through_all_tasks(client):
    headers = create_tasks(client, 25)
    seen = []
    cursor = None
    while True:
        url = "/tasks?limit=10"
        if cursor is not None:
            url += f"&cursor={cursor}"
        body = client.get(url, headers=headers).get_json()
        assert len(body["data"]) <= 10
        seen.extend(t["id"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 25
    assert len(set(seen)) == 25


def test_limit_param_clamped_to_max(client):
    headers = create_tasks(client, 25)
    body = client.get("/tasks?limit=1000", headers=headers).get_json()
    assert len(body["data"]) == 25
    assert body["total"] == 25


def test_limit_below_one_clamped_to_one(client):
    headers = create_tasks(client, 5)
    body = client.get("/tasks?limit=0", headers=headers).get_json()
    assert len(body["data"]) == 1


def test_invalid_limit_returns_400(client):
    headers = auth_headers(client)
    resp = client.get("/tasks?limit=abc", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_invalid_cursor_returns_400(client):
    headers = auth_headers(client)
    resp = client.get("/tasks?cursor=notanint", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_cursor_at_end_returns_empty_page(client):
    headers = create_tasks(client, 3)
    first = client.get("/tasks", headers=headers).get_json()
    last_id = first["data"][-1]["id"]
    body = client.get(f"/tasks?cursor={last_id}", headers=headers).get_json()
    assert body["data"] == []
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_total_counts_only_owners_tasks(client):
    alice = create_tasks(client, 3, username="alice")
    create_tasks(client, 5, username="bob")
    body = client.get("/tasks", headers=alice).get_json()
    assert body["total"] == 3
    assert len(body["data"]) == 3
