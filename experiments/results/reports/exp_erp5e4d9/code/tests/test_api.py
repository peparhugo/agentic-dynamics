import pytest
import sys
import os

# ensure project root is on sys.path for pytest import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app, generate_code, rate_limiter
from app.db import SessionLocal
from app import models


client = TestClient(app)


def db_session():
    return SessionLocal()


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    # ensure each test has a fresh rate limiter state
    rate_limiter.storage.clear()
    # also clear DB tables to ensure tests are isolated
    db = SessionLocal()
    try:
        db.query(models.Click).delete()
        db.query(models.URL).delete()
        db.commit()
    finally:
        db.close()
    yield


def test_shorten_and_redirect():
    # shorten
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data
    code = data["code"]

    # redirect
    r = client.get(f"/r/{code}", follow_redirects=False)
    assert r.status_code in (307, 302, 301)
    assert "example.com" in r.headers["location"]

    # analytics shows one click
    a = client.get(f"/analytics/{code}")
    assert a.status_code == 200
    ad = a.json()
    assert ad["total_clicks"] >= 1


def test_custom_code_collision():
    # create with custom code
    resp = client.post("/shorten", json={"url": "https://a.com", "custom_code": "mycode"})
    assert resp.status_code == 200

    # attempt same custom code
    resp2 = client.post("/shorten", json={"url": "https://b.com", "custom_code": "mycode"})
    assert resp2.status_code == 400


def test_generated_code_collision(monkeypatch):
    # force generate_code to collide first, then produce a new one
    calls = ["COLLIDE1", "UNIQUE1"]

    def fake_gen(length=7):
        return calls.pop(0)

    # pre-insert COLLIDE1 to cause collision
    db = db_session()
    try:
        db.add(models.URL(code="COLLIDE1", target="https://x.com"))
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr('app.main.generate_code', fake_gen)
    resp = client.post("/shorten", json={"url": "https://y.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "UNIQUE1"


def test_rate_limit():
    # Rate limiter allows 5 per minute; sixth should 429
    for i in range(5):
        r = client.post("/shorten", json={"url": f"https://rl{i}.com"})
        assert r.status_code == 200
    r6 = client.post("/shorten", json={"url": "https://rl6.com"})
    assert r6.status_code == 429
