from url_shortener import create_app


def test_rate_limit_and_window_reset(tmp_path, clock):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "rate.sqlite"),
            "RATE_LIMIT": 2,
            "RATE_LIMIT_WINDOW": 60,
            "TIME_PROVIDER": clock["time"],
        }
    )
    client = app.test_client()

    for number in range(2):
        response = client.post("/api/shorten", json={"url": f"https://example.com/{number}"})
        assert response.status_code == 201

    blocked = client.post("/api/shorten", json={"url": "https://example.com/blocked"})
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "40"
    assert blocked.headers["X-RateLimit-Limit"] == "2"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.get_json()["error"]["retry_after"] == 40

    clock["now"] += 40
    allowed = client.post("/api/shorten", json={"url": "https://example.com/new-window"})
    assert allowed.status_code == 201


def test_rate_limit_is_per_client(tmp_path, clock):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "clients.sqlite"),
            "RATE_LIMIT": 1,
            "TIME_PROVIDER": clock["time"],
        }
    )
    client = app.test_client()
    payload = {"url": "https://example.com"}

    assert client.post("/api/shorten", json=payload, environ_base={"REMOTE_ADDR": "10.0.0.1"}).status_code == 201
    assert client.post("/api/shorten", json=payload, environ_base={"REMOTE_ADDR": "10.0.0.1"}).status_code == 429
    assert client.post("/api/shorten", json=payload, environ_base={"REMOTE_ADDR": "10.0.0.2"}).status_code == 201


def test_disabled_rate_limit(tmp_path, clock):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "disabled.sqlite"),
            "RATE_LIMIT": 0,
            "TIME_PROVIDER": clock["time"],
        }
    )
    client = app.test_client()
    for _ in range(3):
        assert client.post("/api/shorten", json={"url": "https://example.com"}).status_code == 201
