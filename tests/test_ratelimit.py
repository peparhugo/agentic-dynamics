"""Tests for per-client rate limiting."""

import asyncio

import fakeredis
import fakeredis.aioredis
import pytest
import websockets
from websockets.asyncio.server import serve

from app import NotificationServer, decode_message, encode_message
from broker import LocalBroker
from ratelimit import LocalRateLimiter, RedisRateLimiter, make_rate_limiter
from store import MessageStore


async def start_server(ns):
    await ns.start()
    srv = await serve(ns.handle, "127.0.0.1", 0, process_request=ns.process_request)
    port = srv.sockets[0].getsockname()[1]
    return srv, port


async def connect_client(port):
    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
    hello = decode_message(await ws.recv())
    return ws, hello


async def test_local_rate_limiter_enforces_limit():
    rl = LocalRateLimiter(limit=2)
    assert await rl.check(1) is True
    assert await rl.check(1) is True
    assert await rl.check(1) is False
    assert await rl.check(2) is True


async def test_redis_rate_limiter_uses_per_client_counters(redis_server):
    client = fakeredis.aioredis.FakeRedis(server=redis_server)
    rl = RedisRateLimiter(client, limit=3)
    for _ in range(3):
        assert await rl.check(1) is True
    assert await rl.check(1) is False
    assert await rl.check(2) is True


def test_make_rate_limiter_reads_rate_limit_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "5")
    rl = make_rate_limiter()
    assert isinstance(rl, LocalRateLimiter)
    assert rl._limit == 5


def test_make_rate_limiter_default_limit(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT", raising=False)
    rl = make_rate_limiter()
    assert rl._limit == 100


def test_make_rate_limiter_prefers_injected_redis_client(redis_server):
    client = fakeredis.aioredis.FakeRedis(server=redis_server)
    rl = make_rate_limiter(client=client, limit=2)
    assert isinstance(rl, RedisRateLimiter)
    assert rl._limit == 2


async def test_rate_limited_client_receives_error_without_drop():
    ns = NotificationServer(
        broker=LocalBroker(),
        store=MessageStore(),
        rate_limiter=LocalRateLimiter(limit=2),
    )
    srv, port = await start_server(ns)
    try:
        ws, _ = await connect_client(port)
        await ws.send(encode_message({"type": "broadcast", "payload": {"n": 1}}))
        await ws.send(encode_message({"type": "broadcast", "payload": {"n": 2}}))
        await ws.send(encode_message({"type": "broadcast", "payload": {"n": 3}}))

        r1 = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
        r2 = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
        r3 = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))

        assert r1["type"] == "broadcast"
        assert r1["payload"]["n"] == 1
        assert r2["type"] == "broadcast"
        assert r2["payload"]["n"] == 2
        assert r3["type"] == "error"
        assert r3["payload"]["code"] == "rate_limited"

        # Connection is still alive (not dropped): another message also errors.
        await ws.send(encode_message({"type": "broadcast", "payload": {"n": 4}}))
        r4 = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
        assert r4["type"] == "error"
        assert r4["payload"]["code"] == "rate_limited"

        await ws.close()
    finally:
        srv.close()
        await srv.wait_closed()
        await ns.close()


async def test_rate_limit_is_per_client_id():
    ns = NotificationServer(
        broker=LocalBroker(),
        store=MessageStore(),
        rate_limiter=LocalRateLimiter(limit=1),
    )
    srv, port = await start_server(ns)
    try:
        ws1, _ = await connect_client(port)
        ws2, _ = await connect_client(port)

        await ws1.send(encode_message({"type": "broadcast", "payload": {"n": 1}}))
        r1a = decode_message(await asyncio.wait_for(ws1.recv(), timeout=5))
        r1b = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
        assert r1a["payload"]["n"] == 1
        assert r1b["payload"]["n"] == 1

        # ws1 is now over its own limit.
        await ws1.send(encode_message({"type": "broadcast", "payload": {"n": 2}}))
        err = decode_message(await asyncio.wait_for(ws1.recv(), timeout=5))
        assert err["type"] == "error"
        assert err["payload"]["code"] == "rate_limited"

        # ws2 has an independent counter and is still allowed.
        await ws2.send(encode_message({"type": "broadcast", "payload": {"n": 3}}))
        r2a = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
        r2b = decode_message(await asyncio.wait_for(ws1.recv(), timeout=5))
        assert r2a["payload"]["n"] == 3
        assert r2b["payload"]["n"] == 3

        await ws1.close()
        await ws2.close()
    finally:
        srv.close()
        await srv.wait_closed()
        await ns.close()


@pytest.fixture
def redis_server():
    return fakeredis.FakeServer()
