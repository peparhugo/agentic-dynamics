import asyncio
import json

import aiohttp
import fakeredis.aioredis
import pytest
import websockets

import app
from conftest import recv_message


@pytest.mark.asyncio
async def test_redis_pubsub_distributes_broadcast_across_instances():
    """Two server instances sharing one Redis backbone: a broadcast published
    on instance A is delivered to clients connected to instance B."""
    shared = fakeredis.FakeServer()
    server_a = app.NotificationServer(
        redis_client=fakeredis.aioredis.FakeRedis(server=shared, decode_responses=True),
        database_url=":memory:",
    )
    server_b = app.NotificationServer(
        redis_client=fakeredis.aioredis.FakeRedis(server=shared, decode_responses=True),
        database_url=":memory:",
    )
    await server_a.start(ws_host="127.0.0.1", ws_port=0,
                         http_host="127.0.0.1", http_port=0)
    await server_b.start(ws_host="127.0.0.1", ws_port=0,
                         http_host="127.0.0.1", http_port=0)
    try:
        url_a = f"ws://127.0.0.1:{server_a.ws_port}"
        url_b = f"ws://127.0.0.1:{server_b.ws_port}"
        async with websockets.connect(url_a) as ws_a, \
                   websockets.connect(url_b) as ws_b:
            await recv_message(ws_a)
            await recv_message(ws_b)

            await server_a.broadcast({"hello": "world"})

            message_a = await recv_message(ws_a)
            message_b = await recv_message(ws_b)
            assert message_a["type"] == "broadcast"
            assert message_a["payload"] == {"hello": "world"}
            assert message_b["type"] == "broadcast"
            assert message_b["payload"] == {"hello": "world"}
    finally:
        await server_a.stop()
        await server_b.stop()


@pytest.mark.asyncio
async def test_redis_pubsub_routes_channels_across_instances():
    """Channel-tagged broadcasts published on one instance only reach
    subscribers on the other instance."""
    shared = fakeredis.FakeServer()
    server_a = app.NotificationServer(
        redis_client=fakeredis.aioredis.FakeRedis(server=shared, decode_responses=True),
        database_url=":memory:",
    )
    server_b = app.NotificationServer(
        redis_client=fakeredis.aioredis.FakeRedis(server=shared, decode_responses=True),
        database_url=":memory:",
    )
    await server_a.start(ws_host="127.0.0.1", ws_port=0,
                         http_host="127.0.0.1", http_port=0)
    await server_b.start(ws_host="127.0.0.1", ws_port=0,
                         http_host="127.0.0.1", http_port=0)
    try:
        url_a = f"ws://127.0.0.1:{server_a.ws_port}"
        url_b = f"ws://127.0.0.1:{server_b.ws_port}"
        async with websockets.connect(url_a) as ws_a, \
                   websockets.connect(url_b) as ws_b:
            await recv_message(ws_a)
            await recv_message(ws_b)

            await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await ws_b.send(json.dumps({"type": "subscribe", "channel": "other"}))
            await asyncio.sleep(0.1)

            await server_a.broadcast({"alert": "down"}, channel="alerts")

            message = await recv_message(ws_a)
            assert message["payload"] == {"alert": "down"}

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws_b.recv(), 0.2)
    finally:
        await server_a.stop()
        await server_b.stop()


@pytest.mark.asyncio
async def test_client_state_is_stored_in_redis(running_server):
    async with websockets.connect(f"ws://127.0.0.1:{running_server.ws_port}") as ws:
        client_id = (await recv_message(ws))["payload"]["client_id"]
        await ws.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        await asyncio.sleep(0.1)

        state = await running_server.broker.get_client_state(client_id)
        assert state.get("connected_at")
        assert client_id in await running_server.broker.list_clients()
        assert "chat" in await running_server.broker.get_client_channels(client_id)


@pytest.mark.asyncio
async def test_client_state_survives_server_restart():
    """Client connection state is stored in Redis and can be read back by a
    fresh server instance sharing the same Redis backbone."""
    shared = fakeredis.aioredis.FakeRedis(decode_responses=True)
    server = app.NotificationServer(redis_client=shared, database_url=":memory:")
    await server.start(ws_host="127.0.0.1", ws_port=0,
                       http_host="127.0.0.1", http_port=0)
    client_id = "client-that-survives"
    await server.broker.store_client(client_id, {
        "connected_at": "2026-01-01T00:00:00+00:00",
        "address": "127.0.0.1",
    })
    await server.broker.add_client_channel(client_id, "alerts")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://127.0.0.1:{server.http_port}/clients") as response:
            assert response.status == 200
            body = await response.json()
            assert client_id in body["clients"]

    await server.stop()

    restarted = app.NotificationServer(redis_client=shared, database_url=":memory:")
    await restarted.start(ws_host="127.0.0.1", ws_port=0,
                          http_host="127.0.0.1", http_port=0)
    try:
        assert client_id in await restarted.broker.list_clients()
        state = await restarted.broker.get_client_state(client_id)
        assert state.get("connected_at") == "2026-01-01T00:00:00+00:00"
        assert "alerts" in await restarted.broker.get_client_channels(client_id)
    finally:
        await restarted.stop()


@pytest.mark.asyncio
async def test_messages_endpoint_returns_persisted_history(running_server):
    await running_server.broadcast({"seq": 1})
    await running_server.broadcast({"seq": 2}, channel="alerts")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://127.0.0.1:{running_server.http_port}/messages") as response:
            assert response.status == 200
            body = await response.json()
            assert body["total"] == 2
            assert body["limit"] == 50
            assert body["offset"] == 0
            messages = body["messages"]
            assert [m["payload"] for m in messages] == [{"seq": 2}, {"seq": 1}]
            assert messages[0]["channel"] == "alerts"
            assert messages[1]["channel"] == "global"
            for message in messages:
                assert set(message.keys()) == {"id", "channel", "type", "payload", "timestamp"}
                assert message["type"] == "broadcast"
                assert isinstance(message["timestamp"], str) and message["timestamp"]


@pytest.mark.asyncio
async def test_messages_endpoint_pagination(running_server):
    for i in range(5):
        await running_server.broadcast({"i": i})

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"http://127.0.0.1:{running_server.http_port}/messages?limit=2&offset=1"
        ) as response:
            assert response.status == 200
            body = await response.json()
            assert body["total"] == 5
            assert body["limit"] == 2
            assert body["offset"] == 1
            assert len(body["messages"]) == 2
            assert [m["payload"] for m in body["messages"]] == [{"i": 3}, {"i": 2}]


@pytest.mark.asyncio
async def test_direct_messages_are_persisted(ws_url, http_url, running_server):
    async with websockets.connect(ws_url) as ws:
        client_id = (await recv_message(ws))["payload"]["client_id"]
        await running_server.send_direct(client_id, {"note": "private"})
        await recv_message(ws)
        await asyncio.sleep(0.1)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{http_url}/messages") as response:
            body = await response.json()
            types = [m["type"] for m in body["messages"]]
            assert "direct" in types
            direct = next(m for m in body["messages"] if m["type"] == "direct")
            assert direct["payload"] == {"note": "private"}
            assert direct["channel"] == "direct"


@pytest.mark.asyncio
async def test_messages_table_schema(running_server):
    await running_server.broadcast({"x": 1})
    cursor = await running_server.store._conn.execute("PRAGMA table_info(messages)")
    columns = [row[1] for row in await cursor.fetchall()]
    assert columns == ["id", "channel", "type", "payload", "timestamp"]
