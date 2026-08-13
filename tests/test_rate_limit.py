"""Tests for per-client message rate limiting."""

import asyncio
import json

import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect

from server import NotificationServer


async def http_get(host: str, port: int, path: str) -> str:
    """Issue a minimal HTTP/1.1 GET and return the raw response text."""
    reader, writer = await asyncio.open_connection(host, port)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    writer.write(request.encode("ascii"))
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    return raw.decode("utf-8", "replace")


def parse_json(raw: str) -> dict:
    status_line, _, body = raw.partition("\r\n\r\n")
    assert status_line.split(" ")[1] == "200", status_line
    return json.loads(body)


async def recv_json(ws):
    return json.loads(await ws.recv())


async def uri(srv):
    return f"ws://{srv.host}:{srv.bound_port}"


async def subscribe(ws, channel):
    await ws.send(
        json.dumps({"type": "subscribe", "payload": {"channel": channel}})
    )
    return await recv_json(ws)


def make_server(shared_redis, **kwargs):
    client = fakeredis.aioredis.FakeRedis(server=shared_redis)
    return NotificationServer(port=0, redis_client=client, **kwargs)


@pytest.fixture
def shared_redis():
    """A fake Redis server shared by every broker in a test."""
    return fakeredis.FakeServer()


# ── configuration ─────────────────────────────────────────────


def test_rate_limit_default_is_100():
    srv = NotificationServer(port=0)
    try:
        assert srv.rate_limit == 100
    finally:
        asyncio.run(srv.stop())


def test_rate_limit_reads_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "5")
    srv = NotificationServer(port=0)
    try:
        assert srv.rate_limit == 5
    finally:
        asyncio.run(srv.stop())


def test_rate_limit_clamps_minimum(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "0")
    srv = NotificationServer(port=0)
    try:
        assert srv.rate_limit >= 1
    finally:
        asyncio.run(srv.stop())


# ── enforcement (in-process fallback) ─────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_error_local(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "2")
    srv = NotificationServer(port=0)
    await srv.start()
    try:
        async with connect(await uri(srv)) as a:
            await recv_json(a)
            for i in range(2):
                await a.send(
                    json.dumps({"type": "broadcast", "payload": {"i": i}})
                )
                echo = await asyncio.wait_for(recv_json(a), timeout=2)
                assert echo["type"] == "broadcast"
            await a.send(json.dumps({"type": "broadcast", "payload": {"i": 2}}))
            error = await asyncio.wait_for(recv_json(a), timeout=2)
            assert error["type"] == "system"
            assert "rate limit" in error["payload"]["error"].lower()
    finally:
        await srv.stop()


# ── enforcement (Redis counters) ──────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_error_redis(shared_redis, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "3")
    srv = make_server(shared_redis)
    await srv.start()
    try:
        async with connect(await uri(srv)) as a:
            await recv_json(a)
            for i in range(3):
                await a.send(
                    json.dumps({"type": "broadcast", "payload": {"i": i}})
                )
                echo = await asyncio.wait_for(recv_json(a), timeout=2)
                assert echo["type"] == "broadcast"
            await a.send(json.dumps({"type": "broadcast", "payload": {"i": 3}}))
            error = await asyncio.wait_for(recv_json(a), timeout=2)
            assert error["type"] == "system"
            assert "rate limit" in error["payload"]["error"].lower()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_rate_limit_uses_redis_counters(shared_redis, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "100")
    srv = make_server(shared_redis)
    await srv.start()
    try:
        async with connect(await uri(srv)) as a:
            msg = await recv_json(a)
            client_id = msg["payload"]["client_id"]
            for i in range(3):
                await a.send(
                    json.dumps({"type": "broadcast", "payload": {"i": i}})
                )
                await asyncio.wait_for(recv_json(a), timeout=2)
            observer = fakeredis.aioredis.FakeRedis(server=shared_redis)
            count = await observer.get(f"notify:rate:{client_id}")
            assert int(count) == 3
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_rate_limit_is_per_client(shared_redis, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "3")
    srv = make_server(shared_redis)
    await srv.start()
    try:
        async with connect(await uri(srv)) as a, connect(await uri(srv)) as b:
            await recv_json(a)
            await recv_json(b)
            await subscribe(a, "room-a")
            await subscribe(b, "room-b")

            for i in range(2):
                await a.send(
                    json.dumps(
                        {
                            "type": "broadcast",
                            "channel": "room-a",
                            "payload": {"i": i},
                        }
                    )
                )
                echo = await asyncio.wait_for(recv_json(a), timeout=2)
                assert echo["type"] == "broadcast"
                assert echo["payload"]["i"] == i

            await a.send(
                json.dumps(
                    {"type": "broadcast", "channel": "room-a", "payload": {"i": 9}}
                )
            )
            error = await asyncio.wait_for(recv_json(a), timeout=2)
            assert error["type"] == "system"
            assert "rate limit" in error["payload"]["error"].lower()

            await b.send(
                json.dumps(
                    {"type": "broadcast", "channel": "room-b", "payload": {"i": 99}}
                )
            )
            echo_b = await asyncio.wait_for(recv_json(b), timeout=2)
            assert echo_b["type"] == "broadcast"
            assert echo_b["payload"]["i"] == 99
    finally:
        await srv.stop()
