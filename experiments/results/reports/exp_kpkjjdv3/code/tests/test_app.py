import sqlite3
from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite"),
            "RATE_LIMIT": 3,
            "RATE_WINDOW_SECONDS": 60,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def create_url(client, url="https://example.com/path?q=1"):
    return client.post("/api/urls", json={"url": url})


def test_create_returns_short_url(client):
    response = create_url(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["target_url"] == "https://example.com/path?q=1"
    assert body["short_url"].endswith("/" + body["code"])
    assert body["click_count"] == 0
    assert len(body["code"]) == 8


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"url": ""}, {"url": "example.com"}, {"url": "ftp://example.com"}, {"url": 4}],
)
def test_create_rejects_invalid_urls(client, payload):
    response = client.post("/api/urls", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_url"


def test_get_metadata(client):
    created = create_url(client).get_json()
    response = client.get(f"/api/urls/{created['code']}")
    assert response.status_code == 200
    assert response.get_json()["target_url"] == created["target_url"]


def test_redirect_records_analytics(client):
    created = create_url(client).get_json()
    response = client.get(
        f"/{created['code']}",
        headers={"Referer": "https://referrer.test/", "User-Agent": "test-browser"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == created["target_url"]

    analytics = client.get(f"/api/urls/{created['code']}/analytics").get_json()
    assert analytics["click_count"] == 1
    assert analytics["clicks"][0]["referrer"] == "https://referrer.test/"
    assert analytics["clicks"][0]["user_agent"] == "test-browser"
    assert analytics["clicks"][0]["clicked_at"]


def test_multiple_clicks_are_counted(client):
    code = create_url(client).get_json()["code"]
    client.get(f"/{code}")
    client.get(f"/{code}")
    assert client.get(f"/api/urls/{code}").get_json()["click_count"] == 2


def test_delete_removes_url_and_clicks(client, app):
    code = create_url(client).get_json()["code"]
    client.get(f"/{code}")
    assert client.delete(f"/api/urls/{code}").status_code == 204
    assert client.get(f"/{code}").status_code == 404
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT count(*) FROM clicks WHERE code = ?", (code,)).fetchone()[0] == 0


def test_missing_resources_return_json_404(client):
    for path in ("/missing", "/api/urls/missing", "/api/urls/missing/analytics"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.get_json()["error"] == "not_found"


def test_creation_is_rate_limited(client):
    for number in range(3):
        assert create_url(client, f"https://example.com/{number}").status_code == 201
    response = create_url(client, "https://example.com/blocked")
    assert response.status_code == 429
    assert response.get_json()["error"] == "rate_limit_exceeded"
    assert int(response.headers["Retry-After"]) > 0


def test_rate_limit_is_per_ip(client):
    for number in range(3):
        assert client.post(
            "/api/urls",
            json={"url": f"https://example.com/{number}"},
            environ_base={"REMOTE_ADDR": "192.0.2.1"},
        ).status_code == 201
    assert client.post(
        "/api/urls",
        json={"url": "https://example.com/other"},
        environ_base={"REMOTE_ADDR": "192.0.2.2"},
    ).status_code == 201


def test_code_collision_is_retried(client):
    with patch("app.secrets.token_urlsafe", side_effect=["duplicate", "duplicate", "unique"]):
        first = create_url(client)
        second = create_url(client, "https://other.example")
    assert first.get_json()["code"] == "duplicate"
    assert second.status_code == 201
    assert second.get_json()["code"] == "unique"


def test_code_generation_exhaustion_returns_503(client, app):
    app.config["CODE_RETRIES"] = 2
    with patch("app.secrets.token_urlsafe", return_value="same"):
        assert create_url(client).status_code == 201
        response = create_url(client, "https://other.example")
    assert response.status_code == 503
    assert response.get_json()["error"] == "code_generation_failed"
