import pytest


def test_rate_limit_login(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "ratelimituser",
            "email": "rate@example.com",
            "password": "password123",
        },
    )

    for i in range(5):
        resp = client.post(
            "/v1/auth/login",
            json={"email": "rate@example.com", "password": "password123"},
        )
        assert resp.status_code == 200, f"Request {i + 1} should succeed"

    resp = client.post(
        "/v1/auth/login",
        json={"email": "rate@example.com", "password": "password123"},
    )
    assert resp.status_code == 429


def test_rate_limit_respects_ip_scope(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "ratelimit2",
            "email": "rate2@example.com",
            "password": "password123",
        },
    )

    for _ in range(6):
        resp = client.post(
            "/v1/auth/login",
            json={"email": "rate2@example.com", "password": "password123"},
        )

    assert resp.status_code == 429
