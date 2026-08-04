def test_rate_limit_login(client):
    client.post(
        "/v1/auth/register",
        json={"username": "ratetest", "email": "rate@example.com", "password": "secure123"},
    )

    for i in range(5):
        resp = client.post(
            "/v1/auth/login",
            json={"username": "ratetest", "password": "wrong"},
        )
        assert resp.status_code == 401

    resp = client.post(
        "/v1/auth/login",
        json={"username": "ratetest", "password": "wrong"},
    )
    assert resp.status_code == 429
    data = resp.get_json()
    assert "Too many requests" in data["error"]


def test_rate_limit_allows_valid_login(client):
    client.post(
        "/v1/auth/register",
        json={"username": "rateok", "email": "rateok@example.com", "password": "secure123"},
    )

    for _ in range(5):
        resp = client.post(
            "/v1/auth/login",
            json={"username": "rateok", "password": "secure123"},
        )
        assert resp.status_code == 200
