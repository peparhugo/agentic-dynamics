import pytest

from shortener import create_app
from shortener.models import ClickEvent, ShortURL, db
from shortener.utils import generate_short_code


def test_shorten_creates_short_code(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert len(data["short_code"]) == 6
    assert data["original_url"] == "https://example.com"
    assert data["short_url"].endswith("/" + data["short_code"])


def test_shorten_requires_url(client):
    resp = client.post("/api/shorten", json={})
    assert resp.status_code == 400


def test_shorten_rejects_invalid_url(client):
    for bad in ["not-a-url", "ftp://example.com", "", "javascript:alert(1)"]:
        resp = client.post("/api/shorten", json={"url": bad})
        assert resp.status_code == 400


def test_redirect_follows_and_counts(client):
    code = client.post("/api/shorten", json={"url": "https://example.com"}).get_json()[
        "short_code"
    ]
    resp = client.get(f"/{code}")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.com"

    resp2 = client.get(f"/{code}")
    assert resp2.status_code == 302


def test_redirect_unknown_code(client):
    assert client.get("/zzzzzz").status_code == 404


def test_stats_report_clicks(client):
    code = client.post("/api/shorten", json={"url": "https://example.com"}).get_json()[
        "short_code"
    ]
    client.get(f"/{code}")
    client.get(f"/{code}", headers={"Referer": "https://ref.example"})
    resp = client.get(f"/api/stats/{code}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["clicks"] == 2
    assert data["last_accessed_at"] is not None
    assert len(data["recent_clicks"]) == 2


def test_stats_unknown_code(client):
    assert client.get("/api/stats/zzzzzz").status_code == 404


def test_list_urls(client):
    client.post("/api/shorten", json={"url": "https://a.com"})
    client.post("/api/shorten", json={"url": "https://b.com"})
    resp = client.get("/api/urls")
    assert resp.status_code == 200
    assert len(resp.get_json()["urls"]) == 2


def test_codes_are_unique(client):
    seen = set()
    for i in range(200):
        code = client.post(
            "/api/shorten", json={"url": f"https://example.com/{i}"}
        ).get_json()["short_code"]
        assert code not in seen
        seen.add(code)
    assert len(seen) == 200


def test_generate_code_length_and_alphabet():
    code = generate_short_code(8)
    assert len(code) == 8
    assert all(c.isalnum() for c in code)


def test_persistence_across_app_instances(tmp_path):
    db_path = tmp_path / "persist.db"
    uri = f"sqlite:///{db_path}"
    app1 = create_app(
        {"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "RATELIMIT_ENABLED": False}
    )
    c1 = app1.test_client()
    code = c1.post("/api/shorten", json={"url": "https://persist.example"}).get_json()[
        "short_code"
    ]

    app2 = create_app(
        {"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "RATELIMIT_ENABLED": False}
    )
    c2 = app2.test_client()
    resp = c2.get(f"/{code}")
    assert resp.status_code == 302
    assert c2.get(f"/api/stats/{code}").get_json()["clicks"] == 1


def test_rate_limiting(rate_limited_app):
    client = rate_limited_app.test_client()
    for _ in range(2):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 429
