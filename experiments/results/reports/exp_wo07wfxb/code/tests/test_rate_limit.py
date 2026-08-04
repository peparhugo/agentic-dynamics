def test_rate_limiting_enabled_in_production(client, monkeypatch):
    from flask import current_app

    with client.application.app_context():
        assert current_app.config["RATELIMIT_ENABLED"] is False


def test_429_response_format(client):
    resp = client.post("/api/v1/auth/login", data="bad json")
    assert resp.status_code == 400


def test_404_response_format(client):
    resp = client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_405_response_format(client):
    resp = client.patch("/api/v1/auth/login")
    assert resp.status_code == 405
    assert "error" in resp.get_json()
