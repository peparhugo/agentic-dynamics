def _seed_tasks(auth_client, count):
    for i in range(count):
        auth_client.post("/api/tasks", json={"title": f"Task {i:03d}"})


def test_default_pagination(auth_client):
    _seed_tasks(auth_client, 25)
    response = auth_client.get("/api/tasks")
    body = response.get_json()
    assert len(body["items"]) == 20
    assert body["pagination"] == {"page": 1, "per_page": 20, "total": 25, "pages": 2}


def test_explicit_page(auth_client):
    _seed_tasks(auth_client, 25)
    body = auth_client.get("/api/tasks?page=2&per_page=10").get_json()
    assert len(body["items"]) == 10
    assert body["pagination"]["page"] == 2
    assert body["pagination"]["pages"] == 3


def test_page_out_of_range_returns_empty(auth_client):
    _seed_tasks(auth_client, 5)
    body = auth_client.get("/api/tasks?page=10").get_json()
    assert body["items"] == []
    assert body["pagination"]["total"] == 5
    assert body["pagination"]["page"] == 10


def test_per_page_cap_rejected(auth_client):
    response = auth_client.get("/api/tasks?per_page=101")
    assert response.status_code == 400


def test_page_zero_rejected(auth_client):
    response = auth_client.get("/api/tasks?page=0")
    assert response.status_code == 400


def test_invalid_per_page_rejected(auth_client):
    response = auth_client.get("/api/tasks?per_page=abc")
    assert response.status_code == 400


def test_no_duplicates_across_pages(auth_client):
    _seed_tasks(auth_client, 35)
    page1 = auth_client.get("/api/tasks?page=1&per_page=20").get_json()["items"]
    page2 = auth_client.get("/api/tasks?page=2&per_page=20").get_json()["items"]
    ids = [t["id"] for t in page1 + page2]
    assert len(ids) == len(set(ids))


def test_pagination_with_filters(auth_client):
    _seed_tasks(auth_client, 5)
    auth_client.patch("/api/tasks/1", json={"status": "done"})
    body = auth_client.get("/api/tasks?status=done").get_json()
    assert body["pagination"]["total"] == 1
