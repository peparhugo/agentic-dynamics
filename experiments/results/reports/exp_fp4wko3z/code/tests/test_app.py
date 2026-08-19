import re
import sqlite3

import pytest

import url_shortener


@pytest.fixture
def clock():
    return [1_700_000_000]


@pytest.fixture
def app(tmp_path, clock):
    return url_shortener.create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite3"),
            "BASE_URL": "https://sho.rt",
            "TIME_PROVIDER": lambda: clock[0],
            "CREATE_RATE_LIMIT": 3,
            "READ_RATE_LIMIT": 5,
            "REDIRECT_RATE_LIMIT": 4,
            "RATE_LIMIT_WINDOW": 60,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def create_url(client, destination="https://example.com/a?x=1"):
    response = client.post("/api/urls", json={"url": destination})
    assert response.status_code == 201
    return response


def test_create_returns_collision_resistant_code(client):
    response = create_url(client)
    body = response.get_json()

    assert re.fullmatch(r"[A-Za-z0-9_-]{12}", body["code"])
    assert body == {
        "code": body["code"],
        "url": "https://example.com/a?x=1",
        "short_url": f"https://sho.rt/{body['code']}",
        "created_at": 1_700_000_000,
        "click_count": 0,
        "last_clicked_at": None,
    }
    assert response.headers["Location"] == body["short_url"]
    assert response.headers["X-RateLimit-Remaining"] == "2"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"url": 42},
        {"url": ""},
        {"url": "example.com"},
        {"url": "ftp://example.com/file"},
        {"url": "http://"},
        {"url": "http://example.com:99999"},
    ],
)
def test_create_rejects_invalid_input(client, payload):
    response = client.post("/api/urls", json=payload)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_create_rejects_overlong_url(client, app):
    app.config["MAX_URL_LENGTH"] = 25
    response = client.post("/api/urls", json={"url": "https://example.com/too-long"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "URL is too long"


def test_redirect_and_analytics(client, clock):
    code = create_url(client, "https://example.org/target").get_json()["code"]
    clock[0] += 7
    response = client.get(
        f"/{code}",
        headers={"Referer": "https://source.test/page", "User-Agent": "Test Browser"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "https://example.org/target"

    analytics = client.get(f"/api/urls/{code}").get_json()
    assert analytics["click_count"] == 1
    assert analytics["last_clicked_at"] == clock[0]
    assert analytics["recent_clicks"] == [
        {
            "clicked_at": clock[0],
            "referrer": "https://source.test/page",
            "user_agent": "Test Browser",
        }
    ]


def test_recent_clicks_are_newest_first_and_limited(client, clock):
    code = create_url(client).get_json()["code"]
    for index in range(22):
        clock[0] += 60
        client.get(f"/{code}", environ_base={"REMOTE_ADDR": f"192.0.2.{index}"})

    body = client.get(f"/api/urls/{code}").get_json()
    assert body["click_count"] == 22
    assert len(body["recent_clicks"]) == 20
    assert body["recent_clicks"][0]["clicked_at"] == clock[0]


def test_unknown_codes_return_json_404(client):
    for path in ("/does-not-exist", "/api/urls/does-not-exist"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.get_json() == {"error": "Short URL not found"}


def test_create_rate_limit_is_persistent_and_resets(app, client, clock):
    for index in range(3):
        assert client.post("/api/urls", json={"url": f"https://example.com/{index}"}).status_code == 201

    limited = client.post("/api/urls", json={"url": "https://example.com/blocked"})
    assert limited.status_code == 429
    assert limited.get_json() == {"error": "Rate limit exceeded"}
    assert limited.headers["Retry-After"] == "40"
    assert limited.headers["X-RateLimit-Remaining"] == "0"

    second_client = app.test_client()
    assert second_client.post("/api/urls", json={"url": "https://example.com/still-blocked"}).status_code == 429
    clock[0] += 40
    assert second_client.post("/api/urls", json={"url": "https://example.com/allowed"}).status_code == 201


def test_rate_limits_are_separate_by_scope_and_address(client):
    code = create_url(client).get_json()["code"]
    for _ in range(4):
        assert client.get(f"/{code}").status_code == 302
    assert client.get(f"/{code}").status_code == 429
    assert client.get(f"/api/urls/{code}").status_code == 200
    assert client.get(f"/{code}", environ_base={"REMOTE_ADDR": "192.0.2.8"}).status_code == 302


def test_code_collision_is_retried(client, monkeypatch):
    codes = iter(["duplicate", "duplicate", "replacement"])
    monkeypatch.setattr(url_shortener, "generate_code", lambda: next(codes))

    assert create_url(client).get_json()["code"] == "duplicate"
    assert create_url(client).get_json()["code"] == "replacement"


def test_collision_exhaustion_returns_503(client, app, monkeypatch):
    app.config["CODE_GENERATION_ATTEMPTS"] = 2
    monkeypatch.setattr(url_shortener, "generate_code", lambda: "same-code")
    create_url(client)

    response = client.post("/api/urls", json={"url": "https://example.org"})
    assert response.status_code == 503
    assert response.get_json() == {"error": "Could not allocate a unique short code"}


def test_data_survives_application_restart(tmp_path, clock):
    database = str(tmp_path / "persistent.sqlite3")
    config = {
        "TESTING": True,
        "DATABASE": database,
        "TIME_PROVIDER": lambda: clock[0],
    }
    first_client = url_shortener.create_app(config).test_client()
    code = create_url(first_client).get_json()["code"]

    second_client = url_shortener.create_app(config).test_client()
    assert second_client.get(f"/{code}").status_code == 302
    assert second_client.get(f"/api/urls/{code}").get_json()["click_count"] == 1


def test_health_check(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_schema_enforces_unique_codes(app):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute(
            "INSERT INTO urls (code, destination, created_at) VALUES ('x', 'https://a.test', 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO urls (code, destination, created_at) VALUES ('x', 'https://b.test', 2)"
            )
