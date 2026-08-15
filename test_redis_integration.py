"""Integration tests for the Redis pub/sub backbone and message persistence.

These tests use an in-process Redis server (``fakeredis``) that faithfully
implements the pub/sub semantics of a real Redis server, including sharing
state across multiple client connections. This lets us exercise the exact
code path a real multi-instance deployment would use:

    client -> server publishes to Redis -> worker subscribes -> deliver.
"""

import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from conftest import http_get, parse_http, recv_message, send_message


@pytest_asyncio.fixture
async def two_servers(redis_server_factory, tmp_path):
    """Start two Redis-backed servers sharing the same backbone."""
    app1, port1 = await redis_server_factory(str(tmp_path / "a.db"))
    app2, port2 = await redis_server_factory(str(tmp_path / "b.db"))
    return (app1, port1), (app2, port2)


async def _connect_client(port):
    ws = await connect(f"ws://127.0.0.1:{port}")
    return ws


# ── Redis pub/sub backbone ────────────────────────────────────


async def test_redis_backbone_broadcast_across_instances(two_servers):
    (app1, port1), (app2, port2) = two_servers
    assert app1.redis_connected and app2.redis_connected

    ws1 = await _connect_client(port1)
    ws2 = await _connect_client(port2)

    assert (await recv_message(ws1))["type"] == "system"
    assert (await recv_message(ws2))["type"] == "system"

    await send_message(ws1, {"type": "broadcast", "payload": {"text": "hello"}})

    # Both clients should receive the broadcast, including the sender.
    for ws in (ws1, ws2):
        msg = await recv_message(ws)
        assert msg["type"] == "broadcast"
        assert msg["payload"]["text"] == "hello"

    await ws1.close()
    await ws2.close()


async def test_redis_backbone_direct_across_instances(two_servers):
    (_, port1), (_, port2) = two_servers

    ws1 = await _connect_client(port1)
    ws2 = await _connect_client(port2)

    id1 = (await recv_message(ws1))["payload"]["client_id"]
    id2 = (await recv_message(ws2))["payload"]["client_id"]

    await send_message(
        ws1, {"type": "direct", "payload": {"to": id2, "message": "secret"}}
    )

    msg = await recv_message(ws2)
    assert msg["type"] == "direct"
    assert msg["payload"]["from"] == id1
    assert msg["payload"]["message"] == "secret"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(recv_message(ws1), timeout=0.3)

    await ws1.close()
    await ws2.close()


async def test_redis_backbone_channel_broadcast_across_instances(two_servers):
    (app1, port1), (_, port2) = two_servers

    ws1 = await _connect_client(port1)
    ws2 = await _connect_client(port2)
    await recv_message(ws1)
    await recv_message(ws2)

    await send_message(ws1, {"type": "subscribe", "payload": {"channel": "alerts"}})
    for _ in range(100):
        if app1.channels.counts().get("alerts", 0) == 1:
            break
        await asyncio.sleep(0.01)

    await send_message(
        ws2, {"type": "broadcast", "channel": "alerts", "payload": {"text": "alert!"}}
    )

    msg = await recv_message(ws1)
    assert msg["type"] == "broadcast"
    assert msg["channel"] == "alerts"
    assert msg["payload"]["text"] == "alert!"

    await ws1.close()
    await ws2.close()


async def test_client_connection_state_stored_in_redis(two_servers, redis_backbone):
    import fakeredis.aioredis as fakeredis_aioredis

    (_, port1), (_, _) = two_servers

    ws1 = await _connect_client(port1)
    client_id = (await recv_message(ws1))["payload"]["client_id"]

    client = fakeredis_aioredis.FakeRedis(server=redis_backbone, decode_responses=True)
    try:
        key = "notifications:client:" + client_id
        assert await client.exists(key)
        assert await client.get(key)  # instance id is stored as the value
    finally:
        await client.aclose()

    await ws1.close()
    await ws1.wait_closed()

    client = fakeredis_aioredis.FakeRedis(server=redis_backbone, decode_responses=True)
    try:
        key = "notifications:client:" + client_id
        for _ in range(100):
            if not await client.exists(key):
                break
            await asyncio.sleep(0.01)
        assert not await client.exists(key)
    finally:
        await client.aclose()


# ── Message persistence ───────────────────────────────────────


async def test_messages_are_persisted_to_sqlite(server, client_factory):
    app, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()
    id1 = (await recv_message(ws1))["payload"]["client_id"]
    await recv_message(ws2)

    await send_message(ws1, {"type": "subscribe", "payload": {"channel": "room"}})
    for _ in range(100):
        if app.channels.counts().get("room", 0) == 1:
            break
        await asyncio.sleep(0.01)

    await send_message(
        ws2, {"type": "broadcast", "channel": "room", "payload": {"text": "hi"}}
    )
    await recv_message(ws1)

    await send_message(ws2, {"type": "direct", "payload": {"to": id1, "message": "pm"}})
    await recv_message(ws1)

    messages = app.store.list()
    assert len(messages) == 2

    by_type = {m["type"]: m for m in messages}
    assert "broadcast" in by_type
    assert by_type["broadcast"]["channel"] == "room"
    assert by_type["broadcast"]["payload"] == {"text": "hi"}
    assert by_type["broadcast"]["timestamp"]

    assert "direct" in by_type
    assert by_type["direct"]["channel"] == ""
    assert by_type["direct"]["payload"]["message"] == "pm"


async def test_messages_endpoint_returns_history(server, client_factory):
    _, port = server
    ws = await client_factory()
    await recv_message(ws)

    for i in range(3):
        await send_message(ws, {"type": "broadcast", "payload": {"n": i}})
        await recv_message(ws)

    status, body = parse_http(await http_get(port, "/messages?limit=50&offset=0"))
    assert status == 200
    data = json.loads(body)
    assert len(data) == 3

    # Ordered newest-first (by id descending).
    assert [m["payload"]["n"] for m in data] == [2, 1, 0]

    # Each message exposes the required columns.
    for m in data:
        assert set(m.keys()) >= {"id", "channel", "type", "payload", "timestamp"}


async def test_messages_endpoint_limit_and_offset(server, client_factory):
    _, port = server
    ws = await client_factory()
    await recv_message(ws)

    for i in range(5):
        await send_message(ws, {"type": "broadcast", "payload": {"n": i}})
        await recv_message(ws)

    status, body = parse_http(await http_get(port, "/messages?limit=2&offset=1"))
    assert status == 200
    data = json.loads(body)
    assert [m["payload"]["n"] for m in data] == [3, 2]


async def test_messages_endpoint_defaults(server, client_factory):
    _, port = server
    ws = await client_factory()
    await recv_message(ws)

    await send_message(ws, {"type": "broadcast", "payload": {"n": 0}})
    await recv_message(ws)

    status, body = parse_http(await http_get(port, "/messages"))
    assert status == 200
    data = json.loads(body)
    assert len(data) == 1
