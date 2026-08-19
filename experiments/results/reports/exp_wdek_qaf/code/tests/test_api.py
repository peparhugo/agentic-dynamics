"""Tests for the REST API."""

import json

from shortener.db import Database


def test_shorten_success(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com/path"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["original_url"] == "https://example.com/path"
    assert data["short_code"]
    assert data["short_url"].endswith("/" + data["short_code"])


def test_shorten_missing_url(client):
    resp = client.post("/api/shorten", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_shorten_non_json_body(client):
    resp = client.post("/api/shorten", data="not json",
                       content_type="text/plain")
    assert resp.status_code == 400


def test_shorten_invalid_url(client):
    for bad in ("ftp://example.com", "not-a-url", "example.com", ""):
        resp = client.post("/api/shorten", json={"url": bad})
        assert resp.status_code == 400, bad


def test_shorten_rejects_javascript_scheme(client):
    resp = client.post("/api/shorten", json={"url": "javascript:alert(1)"})
    assert resp.status_code == 400


def test_redirect(client, app):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["short_code"]

    redir = client.get(f"/{code}")
    assert redir.status_code == 302
    assert redir.headers["Location"] == "https://example.com"


def test_redirect_unknown(client):
    resp = client.get("/doesnotexist")
    assert resp.status_code == 404


def test_resolve(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com/x"})
    code = resp.get_json()["short_code"]

    got = client.get(f"/api/{code}")
    assert got.status_code == 200
    data = got.get_json()
    assert data["original_url"] == "https://example.com/x"
    assert data["short_code"] == code
    assert data["created_at"]


def test_resolve_unknown(client):
    assert client.get("/api/nope").status_code == 404


def test_short_codes_do_not_collide(tmp_path):
    from shortener import create_app
    from shortener.config import TestConfig

    cfg = type("_Cfg", (TestConfig,),
               {"DATABASE": str(tmp_path / "c.db"), "RATE_LIMIT_MAX": 10000})
    client = create_app(cfg).test_client()

    seen = set()
    for _ in range(50):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
        code = resp.get_json()["short_code"]
        assert code not in seen
        seen.add(code)
    assert len(seen) == 50


def test_persistence_across_apps(tmp_path):
    from shortener import create_app
    from shortener.config import TestConfig

    cfg = type("_Cfg", (TestConfig,), {"DATABASE": str(tmp_path / "p.db")})

    app1 = create_app(cfg)
    c1 = app1.test_client()
    resp = c1.post("/api/shorten", json={"url": "https://persist.example"})
    code = resp.get_json()["short_code"]

    # New app instance sharing the same database file.
    app2 = create_app(cfg)
    c2 = app2.test_client()
    got = c2.get(f"/api/{code}")
    assert got.status_code == 200
    assert got.get_json()["original_url"] == "https://persist.example"


def test_same_url_gets_distinct_codes(client):
    a = client.post("/api/shorten", json={"url": "https://example.com"})
    b = client.post("/api/shorten", json={"url": "https://example.com"})
    assert a.get_json()["short_code"] != b.get_json()["short_code"]
