import os

import pytest

os.environ["DATABASE"] = "test_tasks.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FAKE_REDIS"] = "1"
import app as task_app

task_app.init_db()


@pytest.fixture()
def client():
    task_app.app.config["TESTING"] = True
    with task_app.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    yield
    task_app.app.config["RATE_LIMIT_PER_MINUTE"] = 100
    task_app.limiter.reset()
    with task_app.get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM users")
        conn.commit()


@pytest.fixture()
def low_rate_limit():
    task_app.app.config["RATE_LIMIT_PER_MINUTE"] = 5
    yield
    task_app.app.config["RATE_LIMIT_PER_MINUTE"] = 100


@pytest.fixture()
def high_rate_limit():
    task_app.app.config["RATE_LIMIT_PER_MINUTE"] = 10000
    yield
    task_app.app.config["RATE_LIMIT_PER_MINUTE"] = 100


def register_and_login(client, username="alice", password="password123"):
    resp = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert resp.status_code == 201
    resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_tasks(client, token, count):
    ids = []
    for i in range(count):
        resp = client.post(
            "/tasks", json={"title": f"task {i}"}, headers=auth(token)
        )
        assert resp.status_code == 201
        ids.append(resp.get_json()["id"])
    return ids


# ── Rate limiting ─────────────────────────────────────────────


def test_rate_limit_exceeded_returns_429_with_retry_after(
    client, low_rate_limit
):
    token = register_and_login(client)
    headers = auth(token)
    for _ in range(5):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429
    assert "error" in resp.get_json()
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 0


def test_rate_limit_applies_to_auth_endpoints(client, low_rate_limit):
    for i in range(5):
        resp = client.post(
            "/auth/register",
            json={"username": f"user{i}", "password": "password123"},
        )
        assert resp.status_code == 201

    resp = client.post(
        "/auth/register",
        json={"username": "overflow", "password": "password123"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_is_per_user(client, low_rate_limit):
    token_a = register_and_login(client, username="alice")
    token_b = register_and_login(client, username="bob")
    for _ in range(5):
        resp = client.get("/tasks", headers=auth(token_a))
        assert resp.status_code == 200

    resp = client.get("/tasks", headers=auth(token_b))
    assert resp.status_code == 200
    assert resp.get_json()["data"] == []

    resp = client.get("/tasks", headers=auth(token_a))
    assert resp.status_code == 429


def test_rate_limit_allows_requests_after_reset(client, low_rate_limit):
    token = register_and_login(client)
    headers = auth(token)
    for _ in range(5):
        assert client.get("/tasks", headers=headers).status_code == 200
    assert client.get("/tasks", headers=headers).status_code == 429

    task_app.limiter.reset()
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200


# ── Pagination ────────────────────────────────────────────────


def test_pagination_first_page_and_next_cursor(client):
    token = register_and_login(client)
    create_tasks(client, token, 5)

    resp = client.get("/tasks?limit=2", headers=auth(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 2
    assert data["total"] == 5
    assert data["next_cursor"] is not None

    page1_ids = [t["id"] for t in data["data"]]
    cursor = data["next_cursor"]

    resp = client.get(
        f"/tasks?limit=2&cursor={cursor}", headers=auth(token)
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 2
    assert data["total"] == 5
    page2_ids = [t["id"] for t in data["data"]]
    assert not set(page1_ids) & set(page2_ids)
    assert data["next_cursor"] is not None

    resp = client.get(
        f"/tasks?limit=2&cursor={data['next_cursor']}", headers=auth(token)
    )
    data = resp.get_json()
    assert len(data["data"]) == 1
    assert data["total"] == 5
    assert data["next_cursor"] is None


def test_pagination_no_next_cursor_when_exhausted(client):
    token = register_and_login(client)
    create_tasks(client, token, 3)

    resp = client.get("/tasks?limit=5", headers=auth(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 3
    assert data["total"] == 3
    assert data["next_cursor"] is None


def test_pagination_default_limit(client):
    token = register_and_login(client)
    create_tasks(client, token, 25)

    resp = client.get("/tasks", headers=auth(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 20
    assert data["total"] == 25
    assert data["next_cursor"] is not None


def test_pagination_max_limit_is_clamped(client, high_rate_limit):
    token = register_and_login(client)
    create_tasks(client, token, 105)

    resp = client.get("/tasks?limit=1000", headers=auth(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 100
    assert data["total"] == 105
    assert data["next_cursor"] is not None


def test_pagination_page_is_ordered_desc_without_duplicates(client):
    token = register_and_login(client)
    create_tasks(client, token, 10)

    seen = []
    cursor = None
    total = None
    while True:
        params = "?limit=4" + (f"&cursor={cursor}" if cursor else "")
        resp = client.get(f"/tasks{params}", headers=auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        total = data["total"]
        ids = [t["id"] for t in data["data"]]
        assert not set(seen) & set(ids)
        seen.extend(ids)
        assert ids == sorted(ids, reverse=True)
        cursor = data["next_cursor"]
        if cursor is None:
            break
    assert total == 10
    assert len(seen) == 10


def test_pagination_invalid_cursor(client):
    token = register_and_login(client)
    resp = client.get("/tasks?cursor=abc", headers=auth(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_pagination_invalid_limit(client):
    token = register_and_login(client)
    resp = client.get("/tasks?limit=abc", headers=auth(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()
