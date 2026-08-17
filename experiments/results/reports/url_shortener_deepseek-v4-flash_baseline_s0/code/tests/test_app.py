import re
import time

import pytest

from shortener import create_app
from shortener.codes import ALPHABET, CodeGenerator
from shortener.models import Storage
from shortener.rate_limit import RateLimiter

VALID_URL = "https://example.com/some/long/path?q=1&r=2"


@pytest.fixture
def app():
    app = create_app({"TESTING": True})
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_shorten_returns_short_code(client):
    resp = client.post("/api/shorten", json={"url": VALID_URL})
    assert resp.status_code == 201
    data = resp.get_json()
    assert re.fullmatch(r"[A-Za-z0-9]{6}", data["short_code"])
    assert data["original_url"] == VALID_URL
    assert data["short_url"].endswith("/" + data["short_code"])


def test_shorten_generates_distinct_codes():
    app = create_app({"TESTING": True, "SHORTEN_RATE_LIMIT": 1000})
    client = app.test_client()
    codes = set()
    for _ in range(20):
        resp = client.post("/api/shorten", json={"url": VALID_URL})
        assert resp.status_code == 201
        codes.add(resp.get_json()["short_code"])
    assert len(codes) == 20


def test_shorten_rejects_missing_url(client):
    resp = client.post("/api/shorten", json={})
    assert resp.status_code == 400
    assert "url" in resp.get_json()["error"]


def test_shorten_rejects_relative_url(client):
    resp = client.post("/api/shorten", json={"url": "/just/a/path"})
    assert resp.status_code == 400


def test_shorten_rejects_bad_scheme(client):
    resp = client.post("/api/shorten", json={"url": "ftp://example.com/x"})
    assert resp.status_code == 400


def test_shorten_rejects_malformed_json(client):
    resp = client.post(
        "/api/shorten",
        data="not json",
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_custom_code(client):
    resp = client.post(
        "/api/shorten", json={"url": VALID_URL, "custom_code": "my-code"}
    )
    assert resp.status_code == 201
    assert resp.get_json()["short_code"] == "my-code"


def test_duplicate_custom_code_conflict(client):
    payload = {"url": VALID_URL, "custom_code": "dup"}
    assert client.post("/api/shorten", json=payload).status_code == 201
    resp = client.post("/api/shorten", json=payload)
    assert resp.status_code == 409
    assert "already in use" in resp.get_json()["error"]


@pytest.mark.parametrize("code", ["ab", "a" * 33, "bad code!", "Ümlaut"])
def test_invalid_custom_code_rejected(client, code):
    resp = client.post(
        "/api/shorten", json={"url": VALID_URL, "custom_code": code}
    )
    assert resp.status_code == 400


def test_redirect_and_click_recorded(client):
    created = client.post("/api/shorten", json={"url": VALID_URL}).get_json()
    code = created["short_code"]
    resp = client.get(
        f"/r/{code}",
        headers={
            "User-Agent": "test-agent",
            "Referer": "https://ref.example.com",
            "X-Forwarded-For": "1.2.3.4",
        },
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == VALID_URL

    stats = client.get(f"/api/stats/{code}").get_json()
    assert stats["total"] == 1
    assert stats["unique_ips"] == 1
    assert stats["recent_clicks"][0]["user_agent"] == "test-agent"
    assert stats["recent_clicks"][0]["referer"] == "https://ref.example.com"
    assert stats["recent_clicks"][0]["ip"] == "1.2.3.4"
    assert stats["clicks_per_day"] != {}


def test_redirect_unknown_code_404(client):
    assert client.get("/r/nope").status_code == 404
    assert client.get("/api/stats/nope").status_code == 404


def test_unique_ip_counting(client):
    code = client.post("/api/shorten", json={"url": VALID_URL}).get_json()[
        "short_code"
    ]
    client.get(f"/r/{code}", headers={"X-Forwarded-For": "10.0.0.1"})
    client.get(f"/r/{code}", headers={"X-Forwarded-For": "10.0.0.1"})
    client.get(f"/r/{code}", headers={"X-Forwarded-For": "10.0.0.2"})
    stats = client.get(f"/api/stats/{code}").get_json()
    assert stats["total"] == 3
    assert stats["unique_ips"] == 2


def test_delete_code(client):
    code = client.post("/api/shorten", json={"url": VALID_URL}).get_json()[
        "short_code"
    ]
    resp = client.delete(f"/api/codes/{code}")
    assert resp.status_code == 200
    assert resp.get_json()["deleted"] == code
    assert client.get(f"/r/{code}").status_code == 404


def test_delete_unknown_code_404(client):
    assert client.delete("/api/codes/nope").status_code == 404


def test_rate_limiting():
    app = create_app(
        {"TESTING": True, "SHORTEN_RATE_LIMIT": 3, "SHORTEN_RATE_WINDOW": 60}
    )
    client = app.test_client()
    for _ in range(3):
        assert client.post("/api/shorten", json={"url": VALID_URL}).status_code == 201
    resp = client.post("/api/shorten", json={"url": VALID_URL})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert "rate limit" in resp.get_json()["error"]


def test_rate_limit_per_ip():
    app = create_app(
        {"TESTING": True, "SHORTEN_RATE_LIMIT": 2, "SHORTEN_RATE_WINDOW": 60}
    )
    client = app.test_client()
    h1 = {"X-Forwarded-For": "10.0.0.1"}
    h2 = {"X-Forwarded-For": "10.0.0.2"}
    assert client.post("/api/shorten", json={"url": VALID_URL}, headers=h1).status_code == 201
    assert client.post("/api/shorten", json={"url": VALID_URL}, headers=h1).status_code == 201
    assert client.post("/api/shorten", json={"url": VALID_URL}, headers=h2).status_code == 201
    assert client.post("/api/shorten", json={"url": VALID_URL}, headers=h1).status_code == 429
    assert client.post("/api/shorten", json={"url": VALID_URL}, headers=h2).status_code == 201
    assert client.post("/api/shorten", json={"url": VALID_URL}, headers=h2).status_code == 429


def test_persistence_across_app_instances(tmp_path):
    db = tmp_path / "test.db"
    app1 = create_app({"TESTING": True, "DATABASE": str(db)})
    code = app1.test_client().post(
        "/api/shorten", json={"url": VALID_URL, "custom_code": "persist"}
    ).get_json()["short_code"]

    app2 = create_app({"TESTING": True, "DATABASE": str(db)})
    c2 = app2.test_client()
    resp = c2.get(f"/r/{code}")
    assert resp.status_code == 302
    assert resp.headers["Location"] == VALID_URL
    stats = c2.get(f"/api/stats/{code}").get_json()
    assert stats["total"] == 1


def test_code_generator_avoids_collisions():
    taken = {"abc", "xyz"}
    gen = CodeGenerator(lambda c: c in taken)
    for _ in range(20):
        code = gen.generate()
        assert code not in taken
        assert set(code).issubset(set(ALPHABET))


def test_code_generator_extends_length_on_exhaustion():
    used = set()
    taken = set()

    def exists(c):
        used.add(len(c))
        return c in taken

    gen = CodeGenerator(exists, length=2)
    alphabet_size = len(ALPHABET)
    for i in range(alphabet_size * alphabet_size + 5):
        code = gen.generate()
        assert code not in taken
        taken.add(code)
    assert max(used) > 2


def test_code_generator_raises_when_everything_taken():
    gen = CodeGenerator(lambda c: True)
    with pytest.raises(RuntimeError):
        gen.generate()


def test_storage_delete_url_removes_clicks():
    db = Storage(":memory:")
    db.create_url("a", VALID_URL)
    db.record_click("a", "1.1.1.1", "ua", "ref")
    db.delete_url("a")
    assert db.get_url("a") is None
    assert db.click_stats("a")["total"] == 0


def test_rate_limiter_window_resets():
    limiter = RateLimiter(limit=1, window_seconds=60)
    assert limiter.allow("k")[0] is True
    assert limiter.allow("k")[0] is False
    limiter.window = 0.001
    time.sleep(0.01)
    assert limiter.allow("k")[0] is True
