import sqlite3

import url_shortener.app as app_module
from url_shortener import create_app


def test_create_returns_collision_resistant_code(client):
    response = client.post("/api/urls", json={"url": "https://example.com/a"})

    assert response.status_code == 201
    body = response.get_json()
    assert len(body["code"]) == 8
    assert body["short_url"].endswith("/" + body["code"])
    assert body["url"] == "https://example.com/a"
    assert body["clicks"] == 0


def test_create_rejects_invalid_urls(client):
    for payload in ({}, {"url": "javascript:alert(1)"}, {"url": "not a url"}):
        response = client.post("/api/urls", json=payload)
        assert response.status_code == 400


def test_create_retries_code_collision(app, client, monkeypatch):
    codes = iter(["duplicate", "duplicate", "new_code"])
    monkeypatch.setattr(app_module, "generate_code", lambda _length: next(codes))

    first = client.post("/api/urls", json={"url": "https://example.com/one"})
    second = client.post("/api/urls", json={"url": "https://example.com/two"})

    assert first.get_json()["code"] == "duplicate"
    assert second.status_code == 201
    assert second.get_json()["code"] == "new_code"


def test_redirect_and_click_analytics(client, shortened):
    response = client.get(
        "/" + shortened["code"],
        headers={"Referer": "https://search.example/", "User-Agent": "Test Browser"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == shortened["url"]

    metadata = client.get("/api/urls/" + shortened["code"]).get_json()
    analytics = client.get("/api/urls/" + shortened["code"] + "/analytics").get_json()
    assert metadata["clicks"] == 1
    assert analytics["total_clicks"] == 1
    assert analytics["recent_clicks"][0]["referrer"] == "https://search.example/"
    assert analytics["recent_clicks"][0]["user_agent"] == "Test Browser"
    assert analytics["recent_clicks"][0]["ip_address"] == "127.0.0.1"


def test_analytics_limit_validation(client, shortened):
    response = client.get(f"/api/urls/{shortened['code']}/analytics?limit=nope")
    assert response.status_code == 400


def test_missing_code_returns_404(client):
    assert client.get("/missing").status_code == 404
    assert client.get("/api/urls/missing").status_code == 404
    assert client.get("/api/urls/missing/analytics").status_code == 404
    assert client.delete("/api/urls/missing").status_code == 404


def test_delete_removes_url_and_analytics(client, app, shortened):
    client.get("/" + shortened["code"])
    response = client.delete("/api/urls/" + shortened["code"])

    assert response.status_code == 204
    assert client.get("/" + shortened["code"]).status_code == 404
    connection = sqlite3.connect(app.config["DATABASE"])
    try:
        assert connection.execute("SELECT COUNT(*) FROM clicks").fetchone()[0] == 0
    finally:
        connection.close()


def test_rate_limit_is_enforced(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "limited.sqlite3"),
            "RATE_LIMIT": 2,
            "RATE_LIMIT_WINDOW": 60,
        }
    )
    client = app.test_client()

    assert client.post("/api/urls", json={"url": "https://example.com/1"}).status_code == 201
    assert client.post("/api/urls", json={"url": "https://example.com/2"}).status_code == 201
    response = client.post("/api/urls", json={"url": "https://example.com/3"})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert response.get_json()["error"] == "rate limit exceeded"
