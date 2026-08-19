"""Tests for click analytics."""

from shortener.db import Database


def _shorten(client):
    resp = client.post("/api/shorten", json={"url": "https://analytics.example"})
    assert resp.status_code == 201
    return resp.get_json()["short_code"]


def test_stats_initial_state(client):
    code = _shorten(client)
    resp = client.get(f"/api/{code}/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["clicks"] == 0
    assert data["recent"] == []


def test_stats_counts_clicks(client):
    code = _shorten(client)
    for _ in range(3):
        client.get(f"/{code}")

    data = client.get(f"/api/{code}/stats").get_json()
    assert data["clicks"] == 3
    assert len(data["recent"]) == 3


def test_recent_clicks_record_metadata(client):
    code = _shorten(client)
    client.get(f"/{code}", headers={"User-Agent": "pytest-agent"})

    data = client.get(f"/api/{code}/stats").get_json()
    assert len(data["recent"]) == 1
    click = data["recent"][0]
    assert click["user_agent"] == "pytest-agent"
    assert click["clicked_at"]


def test_stats_unknown_returns_404(client):
    assert client.get("/api/nope/stats").status_code == 404


def test_analytics_persist_across_apps(tmp_path):
    from shortener import create_app
    from shortener.config import TestConfig

    cfg = type("_Cfg", (TestConfig,), {"DATABASE": str(tmp_path / "a.db")})
    app1 = create_app(cfg)
    c1 = app1.test_client()
    code = _shorten(c1)
    c1.get(f"/{code}")
    c1.get(f"/{code}")

    app2 = create_app(cfg)
    data = app2.test_client().get(f"/api/{code}/stats").get_json()
    assert data["clicks"] == 2
