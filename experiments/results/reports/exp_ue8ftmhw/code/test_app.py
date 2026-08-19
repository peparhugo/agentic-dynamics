import time

import pytest

from app import RateLimiter, make_app


@pytest.fixture()
def client(tmp_path):
    app = make_app(
        db_path=str(tmp_path / "test.db"),
        rate_limit=200,
        rate_window=60,
        base_url="http://short.test",
    )
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    app.config["LIMITER"].reset()


def test_shorten_returns_short_url(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com/long/path?q=1"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["code"]
    assert data["short_url"] == f"http://short.test/{data['code']}"
    assert data["url"] == "https://example.com/long/path?q=1"


def test_shorten_requires_url(client):
    assert client.post("/api/shorten", json={}).status_code == 400
    assert client.post("/api/shorten", json={"url": "   "}).status_code == 400
    assert client.post("/api/shorten", json={"url": "a" * 3000}).status_code == 400
    assert client.post("/api/shorten", data={}).status_code == 400


def test_shorten_form_urlencoded(client):
    resp = client.post("/api/shorten", data={"url": "https://example.com"})
    assert resp.status_code == 201
    assert resp.get_json()["code"]


def test_redirect_counts_click(client):
    created = client.post("/api/shorten", json={"url": "https://example.com"})
    code = created.get_json()["code"]
    resp = client.get(f"/{code}")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.com"


def test_redirect_unknown_code_404(client):
    assert client.get("/no-such-code").status_code == 404


def test_redirect_stores_click_metadata(client):
    created = client.post("/api/shorten", json={"url": "https://example.com"})
    code = created.get_json()["code"]
    client.get(f"/{code}", headers={"User-Agent": "test-bot", "Referer": "https://ref.test"})
    stats = client.get(f"/api/stats/{code}").get_json()
    assert stats["total_clicks"] == 1
    assert stats["top_user_agents"][0]["user_agent"] == "test-bot"
    assert stats["top_referrers"][0]["referrer"] == "https://ref.test"
    assert stats["clicks_by_day"][0]["count"] == 1


def test_stats_unknown_code_404(client):
    assert client.get("/api/stats/nope").status_code == 404


def test_multiple_clicks_aggregate(client):
    created = client.post("/api/shorten", json={"url": "https://example.com"})
    code = created.get_json()["code"]
    for _ in range(5):
        client.get(f"/{code}")
    stats = client.get(f"/api/stats/{code}").get_json()
    assert stats["total_clicks"] == 5
    assert stats["clicks_by_day"][0]["count"] == 5


def test_unique_codes(client):
    codes = set()
    for _ in range(50):
        resp = client.post("/api/shorten", json={"url": f"https://example.com/{_}"})
        assert resp.status_code == 201
        codes.add(resp.get_json()["code"])
    assert len(codes) == 50


def test_rate_limiting(client, tmp_path):
    app = client.application
    app.config["LIMITER"] = RateLimiter(limit=3, window=60)
    for _ in range(3):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 429
    assert resp.get_json()["error"] == "rate limit exceeded"


def test_rate_limit_resets_with_new_window(client, tmp_path):
    app = client.application
    app.config["LIMITER"] = RateLimiter(limit=2, window=1)
    assert client.post("/api/shorten", json={"url": "https://a.com"}).status_code == 201
    assert client.post("/api/shorten", json={"url": "https://a.com"}).status_code == 201
    assert client.post("/api/shorten", json={"url": "https://a.com"}).status_code == 429
    time.sleep(1.1)
    assert client.post("/api/shorten", json={"url": "https://a.com"}).status_code == 201


def test_rate_limiter_unit():
    limiter = RateLimiter(limit=2, window=60)
    assert limiter.allow("ip1") == (True, 1)
    assert limiter.allow("ip1") == (True, 0)
    assert limiter.allow("ip1") == (False, 0)
    assert limiter.allow("ip2") == (True, 1)


def test_persistent_storage_across_apps(tmp_path):
    db_path = str(tmp_path / "persist.db")
    app1 = make_app(db_path=db_path, base_url="http://short.test")
    app1.config["TESTING"] = True
    with app1.test_client() as c:
        code = c.post("/api/shorten", json={"url": "https://example.com"}).get_json()["code"]
    app2 = make_app(db_path=db_path, base_url="http://short.test")
    app2.config["TESTING"] = True
    with app2.test_client() as c:
        assert c.get(f"/{code}").status_code == 302
        stats = c.get(f"/api/stats/{code}").get_json()
        assert stats["total_clicks"] == 1


def test_collision_retry(tmp_path, monkeypatch):
    import app as appmod

    calls = {"n": 0}

    def flaky(db_path, code):
        calls["n"] += 1
        return calls["n"] <= 2

    monkeypatch.setattr(appmod, "code_exists", flaky)
    app = make_app(db_path=str(tmp_path / "c.db"), base_url="http://short.test")
    app.config["TESTING"] = True
    with app.test_client() as c:
        resp = c.post("/api/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    assert calls["n"] >= 3
