from datetime import datetime, timezone

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite3"),
            "RATE_LIMIT": 20,
            "NOW": lambda: datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def create_url(client, url="https://example.com/a?b=1"):
    return client.post("/api/urls", json={"url": url})


def test_create_url_returns_short_code(client):
    response = create_url(client)

    assert response.status_code == 201
    assert len(response.json["code"]) == 8
    assert response.json["short_url"].endswith("/" + response.json["code"])
    assert response.json["original_url"] == "https://example.com/a?b=1"
    assert response.json["created_at"] == "2026-01-02T03:04:05Z"


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"url": ""}, {"url": "ftp://example.com"}, {"url": "not a url"}, {"url": "https://user@example.com"}],
)
def test_create_rejects_invalid_urls(client, payload):
    response = client.post("/api/urls", json=payload)
    assert response.status_code == 400
    assert "url" in response.json["error"]


def test_redirect_records_click(client):
    code = create_url(client).json["code"]

    response = client.get(
        f"/{code}",
        headers={"Referer": "https://news.example/", "User-Agent": "Test Browser"},
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )

    assert response.status_code == 302
    assert response.location == "https://example.com/a?b=1"
    analytics = client.get(f"/api/urls/{code}/analytics").json
    assert analytics["total_clicks"] == 1
    assert analytics["unique_visitors"] == 1
    assert analytics["clicks"][0]["referrer"] == "https://news.example/"
    assert analytics["clicks"][0]["user_agent"] == "Test Browser"


def test_analytics_counts_unique_visitors(client):
    code = create_url(client).json["code"]
    for address in ["192.0.2.1", "192.0.2.1", "192.0.2.2"]:
        client.get(f"/{code}", environ_base={"REMOTE_ADDR": address})

    analytics = client.get(f"/api/urls/{code}/analytics").json
    assert analytics["total_clicks"] == 3
    assert analytics["unique_visitors"] == 2


def test_metadata_reports_click_count(client):
    created = create_url(client).json
    client.get(f"/{created['code']}")

    response = client.get(f"/api/urls/{created['code']}")

    assert response.status_code == 200
    assert response.json["clicks"] == 1
    assert response.json["original_url"] == created["original_url"]


def test_unknown_code_returns_404(client):
    assert client.get("/missing").status_code == 404
    assert client.get("/api/urls/missing").status_code == 404
    assert client.get("/api/urls/missing/analytics").status_code == 404
    assert client.delete("/api/urls/missing").status_code == 404


def test_delete_removes_url_and_clicks(client):
    code = create_url(client).json["code"]
    client.get(f"/{code}")

    assert client.delete(f"/api/urls/{code}").status_code == 204
    assert client.get(f"/{code}").status_code == 404


def test_collision_is_retried(tmp_path):
    codes = iter(["duplicate", "duplicate", "different"])
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "collision.sqlite3"),
            "CODE_GENERATOR": lambda: next(codes),
        }
    )
    client = app.test_client()

    assert create_url(client).json["code"] == "duplicate"
    response = create_url(client, "https://example.org")

    assert response.status_code == 201
    assert response.json["code"] == "different"


def test_collision_exhaustion_returns_503(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "exhaustion.sqlite3"),
            "CODE_GENERATOR": lambda: "same",
            "CODE_ATTEMPTS": 2,
        }
    )
    client = app.test_client()
    create_url(client)

    response = create_url(client, "https://example.org")

    assert response.status_code == 503


def test_rate_limit_is_enforced(tmp_path):
    now = [100.0]
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "rate.sqlite3"),
            "RATE_LIMIT": 2,
            "RATE_WINDOW_SECONDS": 60,
            "RATE_CLOCK": lambda: now[0],
        }
    )
    client = app.test_client()

    assert create_url(client).status_code == 201
    assert create_url(client).status_code == 201
    blocked = create_url(client)
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "20"

    now[0] = 120.0
    assert create_url(client).status_code == 201


def test_rate_limits_clients_independently(tmp_path):
    app = create_app(
        {"TESTING": True, "DATABASE": str(tmp_path / "clients.sqlite3"), "RATE_LIMIT": 1}
    )
    client = app.test_client()

    assert create_url(client).status_code == 201
    assert create_url(client).status_code == 429
    response = client.post(
        "/api/urls", json={"url": "https://example.org"}, environ_base={"REMOTE_ADDR": "192.0.2.50"}
    )
    assert response.status_code == 201
