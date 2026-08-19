import re

import pytest

from shortener import create_app


def test_create_and_follow_short_url(client):
    response = client.post("/api/urls", json={"url": "https://example.com/a?q=1"})

    assert response.status_code == 201
    body = response.get_json()
    assert re.fullmatch(r"[0-9A-Za-z]{7}", body["code"])
    assert body["url"] == "https://example.com/a?q=1"
    assert body["short_url"].endswith("/" + body["code"])
    assert response.headers["Location"] == body["short_url"]

    followed = client.get("/" + body["code"], follow_redirects=False)
    assert followed.status_code == 302
    assert followed.headers["Location"] == "https://example.com/a?q=1"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"url": ""},
        {"url": "ftp://example.com/file"},
        {"url": "not a URL"},
        {"url": "https://"},
        {"url": 42},
    ],
)
def test_rejects_invalid_urls(client, payload):
    response = client.post("/api/urls", json=payload)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_codes_are_unique(client):
    codes = {
        client.post("/api/urls", json={"url": f"https://example.com/{number}"}).get_json()["code"]
        for number in range(50)
    }
    assert len(codes) == 50


def test_click_analytics(client):
    created = client.post("/api/urls", json={"url": "https://example.org"}).get_json()
    headers = {"Referer": "https://referrer.example", "User-Agent": "analytics-test"}

    client.get("/" + created["code"], headers=headers)
    client.get("/" + created["code"], headers=headers)
    response = client.get("/api/urls/" + created["code"])

    assert response.status_code == 200
    analytics = response.get_json()
    assert analytics["click_count"] == 2
    assert analytics["unique_visitors"] == 1
    assert analytics["last_clicked_at"] is not None
    assert len(analytics["recent_clicks"]) == 2
    assert analytics["recent_clicks"][0]["referrer"] == "https://referrer.example"
    assert analytics["recent_clicks"][0]["user_agent"] == "analytics-test"


def test_data_survives_new_app_instance(tmp_path):
    database = str(tmp_path / "persistent.sqlite3")
    first = create_app({"TESTING": True, "DATABASE": database, "RATE_LIMIT": 100})
    created = first.test_client().post(
        "/api/urls", json={"url": "https://persistent.example"}
    ).get_json()

    second = create_app({"TESTING": True, "DATABASE": database, "RATE_LIMIT": 100})
    response = second.test_client().get("/" + created["code"])
    assert response.status_code == 302
    assert response.headers["Location"] == "https://persistent.example"


def test_missing_code_returns_json_404(client):
    response = client.get("/api/urls/0000000")
    assert response.status_code == 404
    assert response.get_json() == {"error": "short URL not found"}


def test_persistent_rate_limit(tmp_path):
    config = {
        "TESTING": True,
        "DATABASE": str(tmp_path / "limited.sqlite3"),
        "RATE_LIMIT": 2,
        "RATE_LIMIT_WINDOW": 60,
    }
    first_client = create_app(config).test_client()
    assert first_client.get("/api/urls/0000000").status_code == 404
    assert first_client.get("/api/urls/0000000").status_code == 404

    second_client = create_app(config).test_client()
    blocked = second_client.get("/api/urls/0000000")
    assert blocked.status_code == 429
    assert blocked.get_json() == {"error": "rate limit exceeded"}
    assert int(blocked.headers["Retry-After"]) > 0
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


def test_health_is_not_rate_limited(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "health.sqlite3"),
            "RATE_LIMIT": 1,
        }
    )
    client = app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
