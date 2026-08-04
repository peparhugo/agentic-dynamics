def test_public_rate_limit(client):
    # Endpoint limited to 2 per minute; third should be 429
    assert client.get("/api/v1/limited").status_code == 200
    assert client.get("/api/v1/limited").status_code == 200
    res = client.get("/api/v1/limited")
    assert res.status_code == 429
    body = res.get_json()
    assert body["error"] == "rate_limited"
