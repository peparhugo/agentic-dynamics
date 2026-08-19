from __future__ import annotations

import sqlite3

from url_shortener import create_app


def create(client, url="https://example.com/path?q=1", **extra):
    return client.post("/api/urls", json={"url": url, **extra})


def test_create_generated_url(client):
    response = create(client)

    assert response.status_code == 201
    body = response.get_json()
    assert len(body["code"]) == 8
    assert body["url"] == "https://example.com/path?q=1"
    assert body["short_url"].endswith("/" + body["code"])
    assert body["click_count"] == 0
    assert body["last_clicked_at"] is None
    assert body["created_at"].endswith("+00:00")


def test_create_custom_code_and_reject_duplicate(client):
    first = create(client, custom_code="my_link")
    duplicate = create(client, "https://other.example", custom_code="my_link")

    assert first.status_code == 201
    assert first.get_json()["code"] == "my_link"
    assert duplicate.status_code == 409
    assert duplicate.get_json() == {"error": "custom_code is already in use"}


def test_rejects_invalid_requests(client):
    cases = [
        ({}, "url must be a valid"),
        ({"url": "javascript:alert(1)"}, "url must be a valid"),
        ({"url": "https://example.com", "custom_code": "a!"}, "custom_code"),
    ]
    for payload, message in cases:
        response = client.post("/api/urls", json=payload)
        assert response.status_code == 400
        assert message in response.get_json()["error"]

    response = client.post("/api/urls", data="not json", content_type="text/plain")
    assert response.status_code == 400


def test_redirect_records_click_analytics(client):
    code = create(client, custom_code="tracked").get_json()["code"]

    response = client.get(
        f"/{code}",
        headers={"Referer": "https://source.example/", "User-Agent": "Test Browser"},
        environ_base={"REMOTE_ADDR": "192.0.2.4"},
    )

    assert response.status_code == 302
    assert response.location == "https://example.com/path?q=1"
    analytics = client.get(f"/api/urls/{code}").get_json()
    assert analytics["click_count"] == 1
    assert analytics["last_clicked_at"] is not None
    assert analytics["recent_clicks"] == [
        {
            "clicked_at": analytics["last_clicked_at"],
            "ip_address": "192.0.2.4",
            "referrer": "https://source.example/",
            "user_agent": "Test Browser",
        }
    ]


def test_analytics_returns_most_recent_100_clicks(client):
    code = create(client, custom_code="popular").get_json()["code"]
    for _ in range(105):
        assert client.get(f"/{code}").status_code == 302

    analytics = client.get(f"/api/urls/{code}").get_json()
    assert analytics["click_count"] == 105
    assert len(analytics["recent_clicks"]) == 100


def test_delete_removes_url_and_clicks(client, app):
    code = create(client, custom_code="remove-me").get_json()["code"]
    client.get(f"/{code}")

    assert client.delete(f"/api/urls/{code}").status_code == 204
    assert client.get(f"/{code}").status_code == 404
    assert client.get(f"/api/urls/{code}").status_code == 404
    connection = sqlite3.connect(app.config["DATABASE"])
    try:
        assert connection.execute("SELECT COUNT(*) FROM clicks").fetchone()[0] == 0
    finally:
        connection.close()


def test_missing_resources_and_methods_are_json(client):
    assert client.get("/missing").get_json() == {"error": "short code not found"}
    response = client.put("/api/urls")
    assert response.status_code == 405
    assert response.get_json() == {"error": "method not allowed"}


def test_generated_code_retries_after_collision(client, app, monkeypatch):
    assert create(client, custom_code="aaa").status_code == 201
    app.config.update(SHORT_CODE_LENGTH=3, SHORT_CODE_ATTEMPTS=2)
    choices = iter("aaabbb")
    monkeypatch.setattr("url_shortener.routes.secrets.choice", lambda _alphabet: next(choices))

    response = create(client, "https://collision.example")

    assert response.status_code == 201
    assert response.get_json()["code"] == "bbb"


def test_rate_limit_is_per_client_and_returns_headers(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "limited.sqlite3"),
            "RATE_LIMIT": 2,
            "RATE_LIMIT_WINDOW": 60,
        }
    )
    client = app.test_client()

    first = client.get("/unknown", environ_base={"REMOTE_ADDR": "192.0.2.1"})
    second = client.get("/unknown", environ_base={"REMOTE_ADDR": "192.0.2.1"})
    blocked = client.get("/unknown", environ_base={"REMOTE_ADDR": "192.0.2.1"})
    other_client = client.get("/unknown", environ_base={"REMOTE_ADDR": "192.0.2.2"})

    assert first.headers["X-RateLimit-Remaining"] == "1"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.status_code == 429
    assert blocked.get_json() == {"error": "rate limit exceeded"}
    assert int(blocked.headers["Retry-After"]) > 0
    assert other_client.status_code == 404


def test_database_persists_across_app_instances(tmp_path):
    database = str(tmp_path / "persistent.sqlite3")
    config = {"TESTING": True, "DATABASE": database, "RATE_LIMIT": 0}
    first_client = create_app(config).test_client()
    assert create(first_client, custom_code="durable").status_code == 201

    second_client = create_app(config).test_client()
    response = second_client.get("/durable")

    assert response.status_code == 302
    assert second_client.get("/api/urls/durable").get_json()["click_count"] == 1
