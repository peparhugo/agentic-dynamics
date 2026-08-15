from repositories import TaskRepository
from test_app import (  # noqa: F401
    auth_client,
    auth_headers,
    client,
    create,
    login,
    register,
    token,
)


def create_n(c, headers, n, prefix="task"):
    return [create(c, headers, f"{prefix} {i}").get_json() for i in range(n)]


def test_pagination_default_page_size(auth_client):
    c, headers = auth_client
    create_n(c, headers, 25)

    resp = c.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] == body["data"][-1]["id"]


def test_pagination_custom_limit(auth_client):
    c, headers = auth_client
    create_n(c, headers, 10)

    resp = c.get("/tasks?limit=5", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 5
    assert body["total"] == 10
    assert body["next_cursor"] == body["data"][-1]["id"]


def test_pagination_limit_is_clamped_to_max(auth_client):
    # Seed 150 tasks directly through the repository, bypassing HTTP, so
    # this test isn't also incidentally exercising (and tripping) the
    # 100-requests-per-minute rate limit — that's covered separately in
    # test_rate_limiting.py.
    c, headers = auth_client
    owner_id = create(c, headers, "task 0").get_json()["owner_id"]
    repo = TaskRepository()
    for i in range(1, 150):
        repo.create(f"task {i}", owner_id)

    resp = c.get("/tasks?limit=1000", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 100
    assert body["total"] == 150


def test_pagination_follow_cursor_through_all_pages(auth_client):
    c, headers = auth_client
    created = create_n(c, headers, 45)
    expected_titles = [t["title"] for t in created][::-1]  # newest first

    collected = []
    cursor = None
    for _ in range(10):
        url = "/tasks?limit=20"
        if cursor is not None:
            url += f"&cursor={cursor}"
        resp = c.get(url, headers=headers)
        body = resp.get_json()
        collected.extend(t["title"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert collected == expected_titles
    assert cursor is None


def test_pagination_last_page_has_null_next_cursor(auth_client):
    c, headers = auth_client
    create_n(c, headers, 20)

    resp = c.get("/tasks?limit=20", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["next_cursor"] is None


def test_pagination_exact_page_boundary_has_next_cursor(auth_client):
    c, headers = auth_client
    create_n(c, headers, 21)

    resp = c.get("/tasks?limit=20", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["next_cursor"] is not None

    resp2 = c.get(f"/tasks?limit=20&cursor={body['next_cursor']}", headers=headers)
    body2 = resp2.get_json()
    assert len(body2["data"]) == 1
    assert body2["next_cursor"] is None


def test_pagination_without_cursor_returns_first_page(auth_client):
    c, headers = auth_client
    create_n(c, headers, 5)

    resp = c.get("/tasks", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 5
    assert body["next_cursor"] is None


def test_pagination_invalid_cursor_returns_400(auth_client):
    c, headers = auth_client
    resp = c.get("/tasks?cursor=notanumber", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_pagination_invalid_limit_returns_400(auth_client):
    c, headers = auth_client
    resp = c.get("/tasks?limit=notanumber", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_pagination_zero_limit_returns_400(auth_client):
    c, headers = auth_client
    resp = c.get("/tasks?limit=0", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_pagination_negative_limit_returns_400(auth_client):
    c, headers = auth_client
    resp = c.get("/tasks?limit=-5", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_pagination_unknown_cursor_returns_empty_page(auth_client):
    c, headers = auth_client
    create_n(c, headers, 5)

    resp = c.get("/tasks?cursor=999999", headers=headers)
    body = resp.get_json()
    assert body["data"] == []
    assert body["next_cursor"] is None
    assert body["total"] == 5


def test_pagination_isolated_per_user(client):
    register(client, "alice", "password1")
    register(client, "bob", "password2")
    alice_headers = auth_headers(login(client, "alice", "password1").get_json()["token"])
    bob_headers = auth_headers(login(client, "bob", "password2").get_json()["token"])

    create_n(client, alice_headers, 3, prefix="alice")
    create_n(client, bob_headers, 2, prefix="bob")

    alice_body = client.get("/tasks", headers=alice_headers).get_json()
    bob_body = client.get("/tasks", headers=bob_headers).get_json()

    assert alice_body["total"] == 3
    assert bob_body["total"] == 2
