import json


def shorten(client, url="https://example.com/some/page", **kwargs):
    payload = {"url": url, **kwargs}
    return client.post("/api/shorten", data=json.dumps(payload), content_type="application/json")


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_shorten_creates_code(client):
    resp = shorten(client)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["long_url"] == "https://example.com/some/page"
    assert len(body["short_code"]) == 6
    assert body["short_url"].endswith(body["short_code"])
    assert body["click_count"] == 0


def test_shorten_rejects_invalid_url(client):
    resp = shorten(client, url="not-a-url")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_shorten_rejects_missing_url(client):
    resp = client.post("/api/shorten", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 400


def test_shorten_with_custom_code(client):
    resp = shorten(client, custom_code="mycode")
    assert resp.status_code == 201
    assert resp.get_json()["short_code"] == "mycode"


def test_shorten_custom_code_conflict(client):
    shorten(client, custom_code="dupe")
    resp = shorten(client, custom_code="dupe")
    assert resp.status_code == 409


def test_shorten_rejects_invalid_custom_code(client):
    resp = shorten(client, custom_code="bad code!")
    assert resp.status_code == 400


def test_shorten_with_expiry(client):
    resp = shorten(client, expires_in_days=1)
    assert resp.status_code == 201
    assert resp.get_json()["expires_at"] is not None


def test_shorten_rejects_invalid_expiry(client):
    resp = shorten(client, expires_in_days=-1)
    assert resp.status_code == 400
    resp2 = shorten(client, expires_in_days="soon")
    assert resp2.status_code == 400


def test_get_url_info(client):
    created = shorten(client).get_json()
    resp = client.get(f"/api/urls/{created['short_code']}")
    assert resp.status_code == 200
    assert resp.get_json()["long_url"] == created["long_url"]


def test_get_url_info_not_found(client):
    resp = client.get("/api/urls/missing")
    assert resp.status_code == 404


def test_redirect_follows_to_long_url(client):
    created = shorten(client, url="https://example.org/target").get_json()
    resp = client.get(f"/{created['short_code']}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.org/target"


def test_redirect_not_found(client):
    resp = client.get("/doesnotexist")
    assert resp.status_code == 404


def test_redirect_increments_click_count(client):
    created = shorten(client).get_json()
    code = created["short_code"]
    client.get(f"/{code}")
    client.get(f"/{code}")
    info = client.get(f"/api/urls/{code}").get_json()
    assert info["click_count"] == 2


def test_redirect_expired_url(client):
    created = shorten(client, expires_in_days=0.0000001).get_json()
    import time

    time.sleep(0.05)
    resp = client.get(f"/{created['short_code']}")
    assert resp.status_code == 410


def test_delete_url(client):
    created = shorten(client).get_json()
    code = created["short_code"]
    resp = client.delete(f"/api/urls/{code}")
    assert resp.status_code == 204
    assert client.get(f"/api/urls/{code}").status_code == 404


def test_delete_url_not_found(client):
    resp = client.delete("/api/urls/missing")
    assert resp.status_code == 404
