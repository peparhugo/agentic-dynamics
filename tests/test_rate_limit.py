import asyncio
import json

import aiohttp
import fakeredis.aioredis
import pytest
import websockets

import app
from conftest import recv_message


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = app.RateLimiter(redis, limit=3)
    for _ in range(3):
        assert await limiter.check("client-1") is True
    assert await limiter.check("client-1") is False
    assert await limiter.count("client-1") == 4


@pytest.mark.asyncio
async def test_rate_limiter_per_client_isolation():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = app.RateLimiter(redis, limit=2)
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-b") is True
    assert await limiter.check("client-a") is False
    assert await limiter.check("client-b") is True


@pytest.mark.asyncio
async def test_rate_limiter_reset_clears_counter():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = app.RateLimiter(redis, limit=1)
    assert await limiter.check("client-1") is True
    assert await limiter.check("client-1") is False
    await limiter.reset("client-1")
    assert await limiter.count("client-1") == 0
    assert await limiter.check("client-1") is True


@pytest.mark.asyncio
async def test_rate_limiter_disabled_with_zero_limit():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = app.RateLimiter(redis, limit=0)
    for _ in range(10):
        assert await limiter.check("client-1") is True


@pytest.mark.asyncio
async def test_server_rejects_over_limit_client_with_error_message():
    server = app.NotificationServer(rate_limit=2, database_url=":memory:")
    await server.start(ws_host="127.0.0.1", ws_port=0,
                       http_host="127.0.0.1", http_port=0)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{server.ws_port}") as ws:
            await recv_message(ws)

            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
            message = await recv_message(ws)
            assert message["type"] == "broadcast"

            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
            message = await recv_message(ws)
            assert message["type"] == "broadcast"

            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
            message = await recv_message(ws)
            assert message["type"] == "error"
            assert message["payload"]["error"] == "rate limit exceeded"
            assert message["payload"]["limit"] == 2
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_rate_limit_env_var(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    server = app.NotificationServer(database_url=":memory:")
    assert server.rate_limit == 1


@pytest.mark.asyncio
async def test_default_rate_limit_is_100():
    server = app.NotificationServer(database_url=":memory:")
    assert server.rate_limit == 100


@pytest.mark.asyncio
async def test_rate_limit_error_does_not_disconnect_client():
    server = app.NotificationServer(rate_limit=1, database_url=":memory:")
    await server.start(ws_host="127.0.0.1", ws_port=0,
                       http_host="127.0.0.1", http_port=0)
    try:
        async with websockets.connect(f"ws://127.0.0.1:{server.ws_port}") as ws:
            await recv_message(ws)

            await ws.send(json.dumps({"type": "broadcast", "payload": {"a": 1}}))
            await recv_message(ws)

            await ws.send(json.dumps({"type": "broadcast", "payload": {"a": 2}}))
            message = await recv_message(ws)
            assert message["type"] == "error"

            assert server.registry.count() == 1
            assert ws.close_code is None
    finally:
        await server.stop()
