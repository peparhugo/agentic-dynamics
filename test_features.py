"""Tests for rate limiting, message history, and message expiry."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest
import redis
import websockets

from server import NotificationServer

REDIS_DB = 15
REDIS_URL = f"redis://127.0.0.1:6379/{REDIS_DB}"


@pytest.fixture
def redis_url():
    url = REDIS_URL
    client = None
    try:
        client = redis.Redis.from_url(url)
        client.ping()
        client.flushdb()
    except Exception:
        pytest.skip("Redis is not available on 127.0.0.1:6379")
    yield url
    if client is not None:
        try:
            client.flushdb()
            client.close()
        except Exception:
            pass


def make_server(redis_url=None, database_url=":memory:", **kwargs):
    return NotificationServer(
        host="127.0.0.1",
        port=0,
        health_port=0,
        redis_url=redis_url,
        database_url=database_url,
        **kwargs,
    )


async def connect_client(server):
    websocket = await websockets.connect(f"ws://{server.host}:{server.port}")
    first = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
    return websocket, first["payload"]["client_id"]


async def http_get_json(host, port, path="/history", params=None):
    query = f"?{urlencode(params)}" if params else ""
    reader, writer = await asyncio.open_connection(host, port)
    request = (
        f"GET {path}{query} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\nConnection: close\r\n\r\n"
    )
    writer.write(request.encode("latin-1"))
    await writer.drain()
    response = await asyncio.wait_for(reader.read(), timeout=2)
    writer.close()
    await writer.wait_closed()
    header, _, body = response.partition(b"\r\n\r\n")
    status_line = header.split(b"\r\n", 1)[0].decode("latin-1")
    return status_line, json.loads(body.decode("utf-8"))


async def wait_until(predicate, timeout=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


def iso_ago(hours=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def advance_iso(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (dt + timedelta(microseconds=1)).isoformat()


async def test_history_returns_chronological_order():
    server = make_server()
    await server.start()
    try:
        await server.publish_to_channel("news", "broadcast", {"n": 1})
        await server.publish_to_channel("news", "broadcast", {"n": 2})
        await server.publish_to_channel("news", "broadcast", {"n": 3})

        status, body = await http_get_json(
            server.host, server.health_port, "/history", {"channel": "news"}
        )
        assert "200 OK" in status
        messages = body["messages"]
        assert [m["payload"]["n"] for m in messages] == [1, 2, 3]
        assert body["has_more"] is False
    finally:
        await server.stop()


async def test_history_filters_by_channel():
    server = make_server()
    await server.start()
    try:
        await server.publish_to_channel("alpha", "broadcast", {"c": "a"})
        await server.publish_to_channel("beta", "broadcast", {"c": "b"})

        status, body = await http_get_json(
            server.host, server.health_port, "/history", {"channel": "alpha"}
        )
        assert "200 OK" in status
        assert len(body["messages"]) == 1
        assert body["messages"][0]["payload"] == {"c": "a"}
        assert body["messages"][0]["channel"] == "alpha"
    finally:
        await server.stop()


async def test_history_filters_by_since():
    server = make_server()
    await server.start()
    try:
        for hours in (5, 4, 3, 2, 1):
            server.store.add("news", "broadcast", {"age": hours}, iso_ago(hours))

        since = iso_ago(hours=3.5)
        status, body = await http_get_json(
            server.host, server.health_port, "/history",
            {"channel": "news", "since": since},
        )
        assert "200 OK" in status
        ages = [m["payload"]["age"] for m in body["messages"]]
        assert ages == [3, 2, 1]
    finally:
        await server.stop()


async def test_history_pagination_has_more():
    server = make_server()
    await server.start()
    try:
        for n in range(5):
            server.store.add("news", "broadcast", {"n": n}, iso_ago(hours=5 - n))

        status, body = await http_get_json(
            server.host, server.health_port, "/history",
            {"channel": "news", "limit": 2},
        )
        assert "200 OK" in status
        assert len(body["messages"]) == 2
        assert body["has_more"] is True
        assert [m["payload"]["n"] for m in body["messages"]] == [0, 1]

        since = advance_iso(body["messages"][-1]["timestamp"])
        status, body = await http_get_json(
            server.host, server.health_port, "/history",
            {"channel": "news", "limit": 2, "since": since},
        )
        assert "200 OK" in status
        assert len(body["messages"]) == 2
        assert [m["payload"]["n"] for m in body["messages"]] == [2, 3]
        assert body["has_more"] is True

        since = advance_iso(body["messages"][-1]["timestamp"])
        status, body = await http_get_json(
            server.host, server.health_port, "/history",
            {"channel": "news", "limit": 2, "since": since},
        )
        assert "200 OK" in status
        assert len(body["messages"]) == 1
        assert [m["payload"]["n"] for m in body["messages"]] == [4]
        assert body["has_more"] is False
    finally:
        await server.stop()


async def test_rate_limit_in_memory_fallback():
    server = make_server(rate_limit=3)
    await server.start()
    try:
        ws, client_id = await connect_client(server)
        for n in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"n": n}

        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 4}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert msg["type"] == "error"
        assert msg["payload"]["code"] == "rate_limited"
        assert "rate limit" in msg["payload"]["message"]

        await ws.close()
    finally:
        await server.stop()


async def test_rate_limit_via_redis(redis_url):
    server = make_server(redis_url=redis_url, rate_limit=3)
    await server.start()
    try:
        ws, client_id = await connect_client(server)
        for n in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert msg["type"] == "broadcast"

        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 4}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert msg["type"] == "error"
        assert msg["payload"]["code"] == "rate_limited"

        client = redis.Redis.from_url(redis_url, decode_responses=True)
        assert int(client.get(f"notif:rate:{client_id}")) >= 4
        assert client.ttl(f"notif:rate:{client_id}") > 0
        client.close()

        await ws.close()
    finally:
        await server.stop()


async def test_rate_limit_env_var(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "42")
    server = make_server()
    assert server.rate_limit == 42
    assert server.rate_limiter.limit == 42
    server.store.close()


async def test_message_expiry_cleanup_on_startup(tmp_path):
    db_path = tmp_path / "messages.db"
    server = make_server(
        database_url=f"sqlite:///{db_path}", message_ttl_days=7
    )
    server.store.add(
        "news", "broadcast", {"old": True},
        (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
    )
    server.store.add("news", "broadcast", {"recent": True}, datetime.now(timezone.utc).isoformat())
    await server.start()
    try:
        assert await wait_until(lambda: server.store.count() == 1)
        messages, has_more = server.store.history(channel="news", limit=50)
        assert len(messages) == 1
        assert messages[0]["payload"] == {"recent": True}
    finally:
        await server.stop()


async def test_message_ttl_days_env_var(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    server = make_server()
    assert server.message_ttl_days == 3
    server.store.close()
