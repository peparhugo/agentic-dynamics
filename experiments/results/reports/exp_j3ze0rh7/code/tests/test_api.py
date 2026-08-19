from datetime import datetime, timedelta, timezone

import urlshortener
from urlshortener import create_app, get_db


UTC = timezone.utc


def test_create_generated_short_url(client):
    response = client.post("/api/v1/urls", json={"url": "https://example.com/path?q=yes"})

    assert response.status_code == 201
    body = response.get_json()
    assert len(body["code"]) == 8
    assert body["url"] == "https://example.com/path?q=yes"
    assert body["active"] is True
    assert body["short_url"].endswith("/" + body["code"])
    assert response.headers["Location"].endswith("/api/v1/urls/" + body["code"])


def test_create_custom_code_and_reject_duplicate(client):
    first = client.post("/api/v1/urls", json={"url": "https://one.example", "custom_code": "mine"})
    second = client.post("/api/v1/urls", json={"url": "https://two.example", "custom_code": "mine"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "code_conflict"


def test_generated_code_retries_after_collision(client, monkeypatch):
    values = iter(["duplicate", "duplicate", "new-code"])
    monkeypatch.setattr(urlshortener.secrets, "token_urlsafe", lambda _length: next(values))

    one = client.post("/api/v1/urls", json={"url": "https://one.example"})
    two = client.post("/api/v1/urls", json={"url": "https://two.example"})

    assert one.get_json()["code"] == "duplicat"
    assert two.status_code == 201
    assert two.get_json()["code"] == "new-code"


def test_create_validates_json_url_code_and_expiry(client):
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    cases = [
        (None, "invalid_json"),
        ({"url": "javascript:alert(1)"}, "invalid_url"),
        ({"url": "https://example.com", "custom_code": "x"}, "invalid_code"),
        ({"url": "https://example.com", "custom_code": "api"}, "invalid_code"),
        ({"url": "https://example.com", "expires_at": past}, "invalid_expiry"),
        ({"url": "https://example.com", "expires_at": "2027-01-01"}, "invalid_expiry"),
    ]

    for payload, error_code in cases:
        response = client.post("/api/v1/urls", json=payload) if payload else client.post("/api/v1/urls")
        assert response.status_code in {400, 422}
        assert response.get_json()["error"]["code"] == error_code


def test_get_and_list_with_pagination(client):
    for code in ("first", "second", "third"):
        client.post("/api/v1/urls", json={"url": f"https://{code}.example", "custom_code": code})

    detail = client.get("/api/v1/urls/second")
    page = client.get("/api/v1/urls?limit=1&offset=1")

    assert detail.get_json()["url"] == "https://second.example"
    assert page.get_json()["total"] == 3
    assert page.get_json()["items"][0]["code"] == "second"


def test_list_rejects_invalid_pagination(client):
    response = client.get("/api/v1/urls?limit=nope")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_pagination"


def test_patch_updates_target_expiry_and_active(client, short_link):
    expiry = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    response = client.patch(
        "/api/v1/urls/story",
        json={"url": "https://updated.example", "expires_at": expiry, "active": False},
    )

    assert response.status_code == 200
    assert response.get_json()["url"] == "https://updated.example"
    assert response.get_json()["expires_at"].endswith("+00:00")
    assert response.get_json()["active"] is False
    assert client.get("/story").status_code == 410


def test_patch_validates_payload(client, short_link):
    assert client.patch("/api/v1/urls/story", json={}).status_code == 400
    assert client.patch("/api/v1/urls/story", json={"code": "other"}).status_code == 422
    assert client.patch("/api/v1/urls/story", json={"active": 1}).status_code == 422
    assert client.patch("/api/v1/urls/story", json={"url": "file:///etc/passwd"}).status_code == 422


def test_redirect_records_analytics(client, short_link):
    direct = client.get("/story", headers={"User-Agent": "pytest-browser"})
    referred = client.get("/story", headers={"Referer": "https://news.example/page"})
    analytics = client.get("/api/v1/urls/story/analytics").get_json()

    assert direct.status_code == 302
    assert direct.headers["Location"] == "https://example.com/articles?id=7"
    assert referred.status_code == 302
    assert analytics["total_clicks"] == 2
    assert analytics["first_click"] is not None
    assert analytics["last_click"] is not None
    assert analytics["clicks_by_day"][0]["clicks"] == 2
    assert {item["referrer"] for item in analytics["top_referrers"]} == {
        "direct",
        "https://news.example/page",
    }


def test_analytics_stores_hashed_not_raw_ip(app, client, short_link):
    client.get("/story", environ_base={"REMOTE_ADDR": "203.0.113.19"})

    with app.app_context():
        click = get_db().execute("SELECT ip_hash, user_agent FROM clicks").fetchone()
        assert click["ip_hash"] != "203.0.113.19"
        assert len(click["ip_hash"]) == 64


def test_expired_link_returns_gone_without_click(app, client, short_link):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE urls SET expires_at = ? WHERE code = 'story'", ("2000-01-01T00:00:00+00:00",))
        db.commit()

    assert client.get("/story").status_code == 410
    assert client.get("/api/v1/urls/story/analytics").get_json()["total_clicks"] == 0


def test_delete_cascades_analytics(client, short_link):
    client.get("/story")
    deleted = client.delete("/api/v1/urls/story")

    assert deleted.status_code == 204
    assert client.get("/api/v1/urls/story").status_code == 404
    assert client.delete("/api/v1/urls/story").status_code == 404


def test_database_persists_across_app_instances(tmp_path):
    path = str(tmp_path / "persistent.sqlite3")
    first_app = create_app({"TESTING": True, "DATABASE": path, "RATE_LIMIT": 100})
    first_app.test_client().post(
        "/api/v1/urls", json={"url": "https://persistent.example", "custom_code": "saved"}
    )

    second_app = create_app({"TESTING": True, "DATABASE": path, "RATE_LIMIT": 100})
    response = second_app.test_client().get("/api/v1/urls/saved")
    assert response.status_code == 200
    assert response.get_json()["url"] == "https://persistent.example"


def test_rate_limit_has_headers_and_is_per_client(tmp_path):
    app = create_app(
        {"TESTING": True, "DATABASE": str(tmp_path / "rate.sqlite3"), "RATE_LIMIT": 2, "RATE_WINDOW_SECONDS": 60}
    )
    client = app.test_client()

    first = client.get("/health", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    second = client.get("/health", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    blocked = client.get("/health", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    other = client.get("/health", environ_base={"REMOTE_ADDR": "10.0.0.2"})

    assert first.headers["X-RateLimit-Limit"] == "2"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.get_json()["error"]["code"] == "rate_limit_exceeded"
    assert other.status_code == 200


def test_health_and_json_route_errors(client):
    assert client.get("/health").get_json() == {"status": "ok"}
    assert client.get("/does-not-exist").get_json()["error"]["code"] == "not_found"
    assert client.post("/health").get_json()["error"]["code"] == "method_not_allowed"
