import pytest
from app import app, storage, rate_limiter


@pytest.fixture
def client():
    app.config["TESTING"] = True
    storage._urls.clear()
    rate_limiter._clients.clear()
    with app.test_client() as c:
        yield c
    storage._urls.clear()
    rate_limiter._clients.clear()


@pytest.fixture
def limiter():
    lim = rate_limiter
    lim._clients.clear()
    return lim


class TestShorten:
    def test_shorten_valid_url(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "short_code" in data
        assert "short_url" in data
        assert len(data["short_code"]) == 6
        assert data["short_url"] == f"/{data['short_code']}"

    def test_shorten_missing_url(self, client):
        resp = client.post("/shorten", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "missing 'url' in request body"

    def test_shorten_no_json(self, client):
        resp = client.post("/shorten", data="not json")
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "missing 'url' in request body"

    def test_shorten_invalid_url(self, client):
        resp = client.post("/shorten", json={"url": "not-a-url"})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid URL format"

    def test_shorten_generates_unique_codes(self, client):
        codes = set()
        for _ in range(50):
            resp = client.post("/shorten", json={"url": "https://unique.com"})
            assert resp.status_code == 201
            codes.add(resp.get_json()["short_code"])
        assert len(codes) == 50


class TestResolve:
    def test_resolve_redirects(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        redir = client.get(f"/{code}")
        assert redir.status_code == 302
        assert redir.location == "https://example.com"

    def test_resolve_not_found(self, client):
        resp = client.get("/nonex1stent")
        assert resp.status_code == 404

    def test_resolve_increments_clicks(self, client):
        resp = client.post("/shorten", json={"url": "https://click.com"})
        code = resp.get_json()["short_code"]

        for _ in range(3):
            client.get(f"/{code}")

        stats = client.get(f"/{code}/stats")
        assert stats.get_json()["clicks"] == 3


class TestStats:
    def test_stats_returns_data(self, client):
        resp = client.post("/shorten", json={"url": "https://stats.com"})
        code = resp.get_json()["short_code"]

        s = client.get(f"/{code}/stats")
        data = s.get_json()
        assert data["short_code"] == code
        assert data["url"] == "https://stats.com"
        assert data["clicks"] == 0
        assert "created_at" in data

    def test_stats_not_found(self, client):
        resp = client.get("/noexist/stats")
        assert resp.status_code == 404


class TestRateLimiting:
    def test_allows_under_limit(self, limiter):
        for _ in range(10):
            assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False

    def test_independent_clients(self, limiter):
        for _ in range(10):
            limiter.is_allowed("client1")
        assert limiter.is_allowed("client2") is True

    def test_rate_limit_endpoint(self, client):
        for _ in range(10):
            resp = client.post("/shorten", json={"url": "https://ratelimit.com"})
            assert resp.status_code == 201

        resp = client.post("/shorten", json={"url": "https://ratelimit.com"})
        assert resp.status_code == 429
        assert resp.get_json()["error"] == "rate limit exceeded"


class TestStorage:
    def test_save_and_get(self):
        store = storage
        store._urls.clear()
        store.save("abc123", "https://test.com")
        assert store.get("abc123") == "https://test.com"

    def test_get_nonexistent(self):
        store = storage
        store._urls.clear()
        assert store.get("noexist") is None

    def test_stats(self):
        store = storage
        store._urls.clear()
        store.save("xyz789", "https://stats-test.com")
        store.get("xyz789")
        store.get("xyz789")
        s = store.stats("xyz789")
        assert s["url"] == "https://stats-test.com"
        assert s["clicks"] == 2
        assert "created_at" in s
