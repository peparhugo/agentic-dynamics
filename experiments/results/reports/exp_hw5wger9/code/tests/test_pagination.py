def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_tasks(client, token, n):
    ids = []
    for i in range(n):
        resp = client.post(
            "/api/tasks",
            json={"title": f"Task {i:02d}"},
            headers=_headers(token),
        )
        ids.append(resp.get_json()["task"]["id"])
    return ids


def test_default_pagination(client, make_user):
    user = make_user()
    _seed_tasks(client, user["token"], 25)
    resp = client.get("/api/tasks", headers=_headers(user["token"]))
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data["tasks"]) == 20
    assert data["meta"]["total"] == 25
    assert data["meta"]["page"] == 1
    assert data["meta"]["per_page"] == 20
    assert data["meta"]["pages"] == 2
    assert data["meta"]["has_next"] is True
    assert data["meta"]["has_prev"] is False


def test_page_two(client, make_user):
    user = make_user()
    _seed_tasks(client, user["token"], 25)
    resp = client.get("/api/tasks?page=2", headers=_headers(user["token"]))
    data = resp.get_json()
    assert len(data["tasks"]) == 5
    assert data["meta"]["page"] == 2
    assert data["meta"]["has_next"] is False
    assert data["meta"]["has_prev"] is True


def test_per_page_param(client, make_user):
    user = make_user()
    _seed_tasks(client, user["token"], 10)
    resp = client.get("/api/tasks?per_page=3", headers=_headers(user["token"]))
    data = resp.get_json()
    assert len(data["tasks"]) == 3
    assert data["meta"]["pages"] == 4


def test_per_page_capped(client, make_user):
    user = make_user()
    resp = client.get("/api/tasks?per_page=500", headers=_headers(user["token"]))
    assert resp.status_code == 400


def test_invalid_page(client, make_user):
    user = make_user()
    resp = client.get("/api/tasks?page=0", headers=_headers(user["token"]))
    assert resp.status_code == 400
    resp = client.get("/api/tasks?page=abc", headers=_headers(user["token"]))
    assert resp.status_code == 400


def test_page_beyond_range_returns_empty(client, make_user):
    user = make_user()
    _seed_tasks(client, user["token"], 3)
    resp = client.get("/api/tasks?page=99", headers=_headers(user["token"]))
    data = resp.get_json()
    assert data["tasks"] == []
    assert data["meta"]["total"] == 3


def test_empty_list(client, make_user):
    user = make_user()
    resp = client.get("/api/tasks", headers=_headers(user["token"]))
    data = resp.get_json()
    assert data["tasks"] == []
    assert data["meta"]["total"] == 0
    assert data["meta"]["pages"] == 0
