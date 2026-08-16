"""Tests for per-client rate limiting."""

import asyncio
import json
import time

import fakeredis.aioredis as fa
import pytest
import websockets

from notifications import (
    TYPE_BROADCAST,
    TYPE_SYSTEM,
    NotificationServer,
)
from rate_limiter import KEY_PREFIX, RateLimiter


@pytest.fixture
def fake_server():
    return fa.FakeServer()


@pytest.fixture
def redis_client(fake_server):
    return fa.FakeRedis(server=fake_server)


@pytest.fixture
async def server():
    srv = NotificationServer(
        host="127.0.0.1",
        ws_port=0,
        rest_port=0,
        database_url="sqlite:///:memory:",
        rate_limit=5,
    )
    await srv.start()
    yield srv
    await srv.stop()


async def open_client(ws_port, timeout=5):
    return await asyncio.wait_for(
        websockets.connect(f"ws://127.0.0.1:{ws_port}"),
        timeout=timeout,
    )


async def recv_json(ws):
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    return json.loads(raw)


async def send_broadcast(ws, text):
    await ws.send(json.dumps({
        "type": TYPE_BROADCAST,
        "payload": {"text": text},
    }))


# ── RateLimiter unit behaviour ──────────────────────────────


async def test_memory_limiter_enforces_limit():
    limiter = RateLimiter(limit=2)
    assert await limiter.allow("client-1")
    assert await limiter.allow("client-1")
    assert not await limiter.allow("client-1")


async def test_memory_limiter_is_per_client():
    limiter = RateLimiter(limit=1)
    assert await limiter.allow("client-1")
    assert not await limiter.allow("client-1")
    assert await limiter.allow("client-2")


async def test_memory_limiter_window_resets():
    limiter = RateLimiter(limit=2, window_seconds=1)
    assert await limiter.allow("client-1")
    assert await limiter.allow("client-1")
    assert not await limiter.allow("client-1")
    await asyncio.sleep(1.1)
    assert await limiter.allow("client-1")


async def test_zero_limit_disables_limiting():
    limiter = RateLimiter(limit=0)
    for _ in range(10):
        assert await limiter.allow("client-1")


async def test_redis_limiter_uses_counters(fake_server):
    client = fa.FakeRedis(server=fake_server)
    limiter = RateLimiter(limit=2, redis_client=client)
    assert await limiter.allow("client-1")
    assert await limiter.allow("client-1")
    assert not await limiter.allow("client-1")
    bucket = int(time.time()) // 60
    key = f"{KEY_PREFIX}client-1:{bucket}"
    assert int(await client.get(key)) == 3


# ── Rate limiting over WebSocket (in-memory backend) ────────


async def test_rate_limit_exceeded_returns_error(server):
    async with await open_client(server.ws_bound_port) as ws:
        welcome = await recv_json(ws)
        client_id = welcome["payload"]["client_id"]
        for _ in range(server.rate_limiter.limit):
            await send_broadcast(ws, "ok")
            got = await recv_json(ws)
            assert got["type"] == TYPE_BROADCAST

        await send_broadcast(ws, "too many")
        got = await recv_json(ws)
        assert got["type"] == TYPE_SYSTEM
        assert "rate limit" in got["payload"]["error"]
        assert got["payload"]["client_id"] == client_id

        await send_broadcast(ws, "still limited")
        got = await recv_json(ws)
        assert got["type"] == TYPE_SYSTEM
        assert "rate limit" in got["payload"]["error"]


async def test_rate_limit_within_limit_is_normal(server):
    async with await open_client(server.ws_bound_port) as ws:
        await recv_json(ws)
        for i in range(server.rate_limiter.limit):
            await send_broadcast(ws, f"msg-{i}")
            got = await recv_json(ws)
            assert got["type"] == TYPE_BROADCAST


# ── Rate limiting over WebSocket (Redis counters) ───────────


async def test_rate_limit_uses_redis_counters(fake_server, redis_client):
    srv = NotificationServer(
        host="127.0.0.1",
        ws_port=0,
        rest_port=0,
        redis_client=redis_client,
        database_url="sqlite:///:memory:",
        rate_limit=3,
    )
    await srv.start()
    try:
        async with await open_client(srv.ws_bound_port) as ws:
            welcome = await recv_json(ws)
            client_id = welcome["payload"]["client_id"]
            for _ in range(3):
                await send_broadcast(ws, "ok")
                await recv_json(ws)

            await send_broadcast(ws, "blocked")
            got = await recv_json(ws)
            assert got["type"] == TYPE_SYSTEM
            assert "rate limit" in got["payload"]["error"]

            bucket = int(time.time()) // 60
            key = f"{KEY_PREFIX}{client_id}:{bucket}"
            assert int(await redis_client.get(key)) > 3
    finally:
        await srv.stop()


async def test_rate_limit_env_var(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "3")
    srv = NotificationServer(
        host="127.0.0.1",
        ws_port=0,
        rest_port=0,
        database_url="sqlite:///:memory:",
    )
    assert srv.rate_limiter.limit == 3
    await srv.start()
    try:
        async with await open_client(srv.ws_bound_port) as ws:
            await recv_json(ws)
            for _ in range(3):
                await send_broadcast(ws, "ok")
                await recv_json(ws)
            await send_broadcast(ws, "blocked")
            got = await recv_json(ws)
            assert got["type"] == TYPE_SYSTEM
            assert "rate limit" in got["payload"]["error"]
    finally:
        await srv.stop()
