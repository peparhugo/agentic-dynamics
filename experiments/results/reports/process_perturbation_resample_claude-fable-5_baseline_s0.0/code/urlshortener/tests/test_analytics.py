import json


def shorten(client, url="https://example.com/page"):
    resp = client.post(
        "/api/shorten",
        data=json.dumps({"url": url}),
        content_type="application/json",
    )
    return resp.get_json()


def test_analytics_not_found(client):
    resp = client.get("/api/urls/missing/analytics")
    assert resp.status_code == 404


def test_analytics_empty(client):
    created = shorten(client)
    resp = client.get(f"/api/urls/{created['short_code']}/analytics")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_clicks"] == 0
    assert body["clicks_by_day"] == {}
    assert body["top_referrers"] == []


def test_analytics_tracks_clicks_and_referrers(client):
    created = shorten(client)
    code = created["short_code"]

    client.get(f"/{code}", headers={"Referer": "https://google.com"})
    client.get(f"/{code}", headers={"Referer": "https://google.com"})
    client.get(f"/{code}")  # direct, no referrer

    resp = client.get(f"/api/urls/{code}/analytics")
    body = resp.get_json()

    assert body["total_clicks"] == 3
    assert sum(body["clicks_by_day"].values()) == 3

    referrer_map = dict(body["top_referrers"])
    assert referrer_map["https://google.com"] == 2
    assert referrer_map["direct"] == 1
    assert len(body["recent_clicks"]) == 3


def test_analytics_records_user_agent(client):
    created = shorten(client)
    code = created["short_code"]
    client.get(f"/{code}", headers={"User-Agent": "pytest-agent/1.0"})

    resp = client.get(f"/api/urls/{code}/analytics")
    recent = resp.get_json()["recent_clicks"]
    assert recent[0]["user_agent"] == "pytest-agent/1.0"
