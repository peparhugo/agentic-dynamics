import json
import pytest
from app import app as _app, _init_db, _conn, _insert, _lookup, _generate_code


@pytest.fixture(autouse=True)
def _clean_db():
    with _conn() as conn:
        conn.execute("DROP TABLE IF EXISTS urls")
    _init_db()


@pytest.fixture
def app():
    _app.config["TESTING"] = True
    return _app


@pytest.fixture
def client(app):
    return app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_shorten_missing_url(client):
    resp = client.post("/shorten", content_type="application/json", data="{}")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "url is required"


def test_shorten_empty_url(client):
    resp = client.post(
        "/shorten",
        content_type="application/json",
        data=json.dumps({"url": "   "}),
    )
    assert resp.status_code == 400


def test_shorten_invalid_json(client):
    resp = client.post(
        "/shorten", content_type="application/json", data="not json"
    )
    assert resp.status_code == 400


def test_shorten_success(client):
    resp = client.post(
        "/shorten",
        content_type="application/json",
        data=json.dumps({"url": "https://example.com"}),
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "short_code" in data
    assert len(data["short_code"]) == 6
    assert data["long_url"] == "https://example.com"


def test_shorten_adds_protocol(client):
    resp = client.post(
        "/shorten",
        content_type="application/json",
        data=json.dumps({"url": "example.com/path"}),
    )
    assert resp.status_code == 201
    assert resp.get_json()["long_url"] == "https://example.com/path"


def test_shorten_already_has_http(client):
    resp = client.post(
        "/shorten",
        content_type="application/json",
        data=json.dumps({"url": "http://example.com"}),
    )
    assert resp.status_code == 201
    assert resp.get_json()["long_url"] == "http://example.com"


def test_redirect_exists(client):
    code = _generate_code()
    _insert(code, "https://target.com")

    resp = client.get(f"/{code}")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://target.com"


def test_redirect_not_found(client):
    resp = client.get("/nonexist")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not found"


def test_redirect_increments_hits(client):
    code = _generate_code()
    _insert(code, "https://counter.com")

    for _ in range(3):
        client.get(f"/{code}")

    row = _lookup(code)
    assert row["hits"] == 3


def test_stats_exists(client):
    code = _generate_code()
    _insert(code, "https://stats.com")

    resp = client.get(f"/{code}/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["short_code"] == code
    assert data["long_url"] == "https://stats.com"
    assert data["hits"] == 0
    assert "created_at" in data


def test_stats_not_found(client):
    resp = client.get("/nope/stats")
    assert resp.status_code == 404


def test_generate_code_length():
    code = _generate_code()
    assert len(code) == 6
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in code)


def test_generate_code_unique():
    codes = {_generate_code() for _ in range(200)}
    assert len(codes) == 200


def test_insert_duplicate():
    code = _generate_code()
    assert _insert(code, "https://first.com") is True
    assert _insert(code, "https://second.com") is False


def test_rate_limit_shorten(client):
    for _ in range(10):
        client.post(
            "/shorten",
            content_type="application/json",
            data=json.dumps({"url": "https://ratelimit.com"}),
        )
    # 11th request should be rate limited
    resp = client.post(
        "/shorten",
        content_type="application/json",
        data=json.dumps({"url": "https://ratelimit.com"}),
    )
    assert resp.status_code == 429
