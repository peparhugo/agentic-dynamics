def test_shorten_creates_link(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com/hello"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["url"] == "https://example.com/hello"
    assert data["short_url"] == f"http://short.test/{data['code']}"
    assert len(data["code"]) == 7


def test_shorten_is_idempotent(client):
    first = client.post("/api/shorten", json={"url": "https://example.com/same"}).get_json()
    second = client.post("/api/shorten", json={"url": "https://example.com/same"}).get_json()
    assert first["code"] == second["code"]


def test_shorten_rejects_invalid_url(client):
    resp = client.post("/api/shorten", json={"url": "not-a-url"})
    assert resp.status_code == 400

    resp2 = client.post("/api/shorten", json={})
    assert resp2.status_code == 400


def test_redirect_follows_and_records_click(client):
    created = client.post("/api/shorten", json={"url": "https://example.com/target"}).get_json()
    code = created["code"]

    resp = client.get(f"/{code}", headers={"Referer": "https://ref.example"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.com/target"

    stats = client.get(f"/api/links/{code}").get_json()
    assert stats["clicks"] == 1


def test_redirect_unknown_code_404(client):
    resp = client.get("/doesnotexist")
    assert resp.status_code == 404


def test_get_link_unknown_code_404(client):
    resp = client.get("/api/links/nope000")
    assert resp.status_code == 404


def test_analytics_endpoint_aggregates_by_day(client):
    created = client.post("/api/shorten", json={"url": "https://example.com/analytics"}).get_json()
    code = created["code"]

    client.get(f"/{code}")
    client.get(f"/{code}")

    analytics = client.get(f"/api/links/{code}/analytics").get_json()
    assert analytics["total_clicks"] == 2
    assert analytics["last_click_at"] is not None
    assert sum(analytics["clicks_by_day"].values()) == 2


def test_delete_link(client):
    created = client.post("/api/shorten", json={"url": "https://example.com/delete-me"}).get_json()
    code = created["code"]

    resp = client.delete(f"/api/links/{code}")
    assert resp.status_code == 204

    resp2 = client.delete(f"/api/links/{code}")
    assert resp2.status_code == 404

    resp3 = client.get(f"/api/links/{code}")
    assert resp3.status_code == 404


def test_rate_limit_blocks_after_threshold(client):
    # fixture configures RATE_LIMIT_MAX_REQUESTS=5 per scope
    for _ in range(5):
        resp = client.post("/api/shorten", json={"url": "https://example.com/rl"})
        assert resp.status_code in (200, 201)

    resp = client.post("/api/shorten", json={"url": "https://example.com/rl-over"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_scopes_are_independent(client):
    for _ in range(5):
        client.post("/api/shorten", json={"url": "https://example.com/scope-fill"})

    # shorten scope is exhausted, but the read scope is a separate bucket
    created = client.post("/api/shorten", json={"url": "https://example.com/scope-fill"})
    assert created.status_code == 429

    resp = client.get("/api/links/anything")
    assert resp.status_code == 404  # not 429 -- separate bucket, request went through
