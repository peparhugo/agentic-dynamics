import sqlite3

import pytest

import url_shortener
from url_shortener import ALPHABET, create_app


def test_create_short_url(client):
    response = client.post("/api/shorten", json={"url": "https://example.com/a?b=c"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["url"] == "https://example.com/a?b=c"
    assert body["created_at"] == "2023-11-14T22:13:20Z"
    assert len(body["code"]) == 8
    assert set(body["code"]) <= set(ALPHABET)
    assert body["short_url"].endswith("/" + body["code"])


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"url": ""},
        {"url": 42},
        {"url": "example.com"},
        {"url": "ftp://example.com/file"},
        {"url": "http:///missing-host"},
        {"url": "https://example.com/\nInjected"},
        {"url": "https://" + "a" * 2048},
    ],
)
def test_rejects_invalid_requests(client, payload):
    kwargs = {"json": payload} if payload is not None else {"data": "not json"}
    response = client.post("/api/shorten", **kwargs)

    assert response.status_code in {400, 422}
    assert response.is_json
    assert response.get_json()["error"]["status"] == response.status_code


def test_allows_http_and_https(client):
    for target in ("http://example.com", "https://example.org/path"):
        assert client.post("/api/shorten", json={"url": target}).status_code == 201


def test_redirect_records_click_analytics(client, shortened, clock):
    clock["now"] += 2
    response = client.get(
        "/" + shortened["code"],
        headers={"Referer": "https://referrer.test/", "User-Agent": "Test Browser"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == shortened["url"]

    stats = client.get(f"/api/urls/{shortened['code']}/stats")
    assert stats.status_code == 200
    body = stats.get_json()
    assert body["click_count"] == 1
    assert body["url"] == shortened["url"]
    assert body["recent_clicks"] == [
        {
            "clicked_at": "2023-11-14T22:13:22Z",
            "referrer": "https://referrer.test/",
            "user_agent": "Test Browser",
        }
    ]


def test_recent_clicks_are_newest_first_and_limited(client, shortened, clock):
    for offset in range(25):
        clock["now"] += 1
        client.get("/" + shortened["code"], headers={"User-Agent": f"agent-{offset}"})

    body = client.get(f"/api/urls/{shortened['code']}/stats").get_json()
    assert body["click_count"] == 25
    assert len(body["recent_clicks"]) == 20
    assert body["recent_clicks"][0]["user_agent"] == "agent-24"
    assert body["recent_clicks"][-1]["user_agent"] == "agent-5"


def test_unknown_code_and_route_return_json(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"]["message"] == "Short URL not found"

    response = client.get("/api/urls/does-not-exist/stats")
    assert response.status_code == 404
    assert response.is_json


def test_method_not_allowed_returns_json(client):
    response = client.get("/api/shorten")
    assert response.status_code == 405
    assert response.is_json


def test_collision_is_retried(client, monkeypatch):
    candidates = iter(["duplicate", "duplicate", "different"])
    monkeypatch.setattr(url_shortener, "generate_code", lambda _length: next(candidates))

    first = client.post("/api/shorten", json={"url": "https://one.test"})
    second = client.post("/api/shorten", json={"url": "https://two.test"})

    assert first.get_json()["code"] == "duplicate"
    assert second.status_code == 201
    assert second.get_json()["code"] == "different"


def test_collision_exhaustion_returns_service_unavailable(app, client, monkeypatch):
    app.config["CODE_ATTEMPTS"] = 2
    monkeypatch.setattr(url_shortener, "generate_code", lambda _length: "same")
    assert client.post("/api/shorten", json={"url": "https://one.test"}).status_code == 201

    response = client.post("/api/shorten", json={"url": "https://two.test"})
    assert response.status_code == 503
    assert response.get_json()["error"]["status"] == 503


def test_data_persists_across_app_instances(tmp_path, clock):
    database = str(tmp_path / "persistent.sqlite")
    config = {
        "TESTING": True,
        "DATABASE": database,
        "RATE_LIMIT": 100,
        "TIME_PROVIDER": clock["time"],
    }
    first_client = create_app(config).test_client()
    created = first_client.post("/api/shorten", json={"url": "https://persist.test"}).get_json()
    first_client.get("/" + created["code"])

    second_client = create_app(config).test_client()
    stats = second_client.get(f"/api/urls/{created['code']}/stats").get_json()
    assert stats["url"] == "https://persist.test"
    assert stats["click_count"] == 1


def test_schema_enforces_unique_codes(app):
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.execute(
        "INSERT INTO urls (code, target_url, created_at) VALUES ('fixed', 'https://a.test', 'now')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO urls (code, target_url, created_at) VALUES ('fixed', 'https://b.test', 'now')"
        )
    connection.close()
