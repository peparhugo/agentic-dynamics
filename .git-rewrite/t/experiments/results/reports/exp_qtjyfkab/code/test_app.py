import os
import sqlite3
import tempfile

import pytest

import app as urlshortener


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    urlshortener.app.config["TESTING"] = True
    urlshortener.app.config["DATABASE"] = db_path
    urlshortener.app.config["RATE_LIMIT_REQUESTS"] = 100
    urlshortener.app.config["RATE_LIMIT_WINDOW"] = 60
    urlshortener.init_db()

    with urlshortener.app.test_client() as c:
        yield c

    os.unlink(db_path)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_shorten_success(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert "short_url" in data
    assert "code" in data
    assert len(data["code"]) == urlshortener.app.config["CODE_LENGTH"]
    assert data["short_url"].startswith("http")
    assert data["code"] in data["short_url"]


def test_shorten_adds_https(client):
    resp = client.post("/shorten", json={"url": "example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert "code" in data

    redirect_resp = client.get(f"/{data['code']}", follow_redirects=False)
    assert redirect_resp.status_code == 302
    assert redirect_resp.headers["Location"] == "https://example.com"


def test_shorten_missing_url(client):
    resp = client.post("/shorten", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_shorten_empty_url(client):
    resp = client.post("/shorten", json={"url": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_shorten_no_json(client):
    resp = client.post("/shorten", data="not json", content_type="text/plain")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_shorten_produces_unique_codes(client):
    codes = set()
    for i in range(20):
        resp = client.post("/shorten", json={"url": f"https://unique-{i}.example.com"})
        assert resp.status_code == 201
        code = resp.get_json()["code"]
        assert code not in codes
        codes.add(code)


def test_redirect_valid_code(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]

    redirect_resp = client.get(f"/{code}", follow_redirects=False)
    assert redirect_resp.status_code == 302
    assert redirect_resp.headers["Location"] == "https://example.com"


def test_redirect_not_found(client):
    resp = client.get("/zzzzzzz")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_redirect_records_click(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]

    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)

    stats = client.get(f"/{code}/stats")
    assert stats.status_code == 200
    data = stats.get_json()
    assert data["total_clicks"] == 2


def test_click_records_ip(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]

    client.get(f"/{code}", follow_redirects=False, environ_base={"REMOTE_ADDR": "1.2.3.4"})
    client.get(f"/{code}", follow_redirects=False, environ_base={"REMOTE_ADDR": "5.6.7.8"})

    stats = client.get(f"/{code}/stats")
    data = stats.get_json()
    assert data["total_clicks"] == 2
    assert data["unique_ips"] == 2


def test_stats_not_found(client):
    resp = client.get("/zzzzzzz/stats")
    assert resp.status_code == 404


def test_stats_returns_created_at(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]

    stats = client.get(f"/{code}/stats")
    data = stats.get_json()
    assert "created_at" in data
    assert data["is_active"] is True
    assert data["total_clicks"] == 0
    assert data["last_clicked_at"] is None
    assert data["daily_clicks"] == []


def test_stats_daily_clicks(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]

    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False)

    stats = client.get(f"/{code}/stats")
    data = stats.get_json()
    assert data["total_clicks"] == 3
    assert len(data["daily_clicks"]) == 1
    assert data["daily_clicks"][0]["count"] == 3


def test_code_collision_handled(client):
    def generate_number():
        import time as t
        digest = __import__("hashlib").sha256(
            f"fixed-prefix{t.time_ns()}{os.urandom(16).hex()}".encode()
        ).digest()
        num = int.from_bytes(digest, "big")
        return num

    original = urlshortener.generate_code  # noqa: F811
    call_count = [0]

    def colliding_generator(url):
        call_count[0] += 1
        num = generate_number()
        if call_count[0] == 1:
            return "collide"
        return urlshortener.encode_base62(num)[: urlshortener.app.config["CODE_LENGTH"]]

    urlshortener.generate_code = colliding_generator
    urlshortener.create_code.cache_clear() if hasattr(
        urlshortener.create_code, "cache_clear"
    ) else None

    resp1 = client.post("/shorten", json={"url": "https://first.example.com"})
    assert resp1.status_code == 201
    assert resp1.get_json()["code"] == "collide"

    resp2 = client.post("/shorten", json={"url": "https://second.example.com"})
    assert resp2.status_code == 201
    assert resp2.get_json()["code"] != "collide"

    urlshortener.generate_code = original


def test_click_records_user_agent(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]

    client.get(
        f"/{code}",
        follow_redirects=False,
        headers={"User-Agent": "TestBrowser/1.0"},
    )

    db = sqlite3.connect(urlshortener.app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    click = db.execute(
        "SELECT * FROM clicks WHERE url_code = ?", (code,)
    ).fetchone()
    db.close()
    assert click["user_agent"] == "TestBrowser/1.0"


def test_click_records_referer(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]

    client.get(
        f"/{code}",
        follow_redirects=False,
        headers={"Referer": "https://referrer.example.com"},
    )

    stats = client.get(f"/{code}/stats")
    data = stats.get_json()
    assert len(data["top_referers"]) == 1
    assert data["top_referers"][0]["referer"] == "https://referrer.example.com"


def test_rate_limit_exceeded(client):
    urlshortener.app.config["RATE_LIMIT_REQUESTS"] = 3
    urlshortener.app.config["RATE_LIMIT_WINDOW"] = 3600
    urlshortener._rate_limit_store.clear()

    for _ in range(3):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201

    resp = client.post("/shorten", json={"url": "https://blocked.example.com"})
    assert resp.status_code == 429
    assert "Rate limit" in resp.get_json()["error"]

    urlshortener._rate_limit_store.clear()


def test_deactivated_url(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["code"]

    db = sqlite3.connect(urlshortener.app.config["DATABASE"])
    db.execute("UPDATE urls SET is_active = 0 WHERE code = ?", (code,))
    db.commit()
    db.close()

    redirect_resp = client.get(f"/{code}", follow_redirects=False)
    assert redirect_resp.status_code == 410
    assert "deactivated" in redirect_resp.get_json()["error"].lower()


def test_encode_base62():
    assert urlshortener.encode_base62(0) == "0"
    assert urlshortener.encode_base62(1) == "1"
    assert urlshortener.encode_base62(10) == "A"
    assert urlshortener.encode_base62(61) == "z"

    decoded = urlshortener.ALPHABET.index("Z")
    assert urlshortener.encode_base62(decoded) == "Z"


def test_generate_code_length(client):
    code = urlshortener.generate_code("https://example.com")
    assert len(code) == urlshortener.app.config["CODE_LENGTH"]
    assert all(c in urlshortener.ALPHABET for c in code)
