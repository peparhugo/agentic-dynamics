"""Integration tests for Redis pub/sub backbone and SQLite persistence."""

import asyncio

import fakeredis
import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
import websockets
from websockets.asyncio.server import serve

from app import BROKER_CHANNEL, NotificationServer, decode_message, encode_message
from broker import RedisBroker
from store import MessageStore


async def start_server(broker, store):
    ns = NotificationServer(broker=broker, store=store)
    await ns.start()
    srv = await serve(
        ns.handle, "127.0.0.1", 0, process_request=ns.process_request
    )
    port = srv.sockets[0].getsockname()[1]
    return ns, srv, port


async def connect_client(port):
    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
    hello = decode_message(await ws.recv())
    return ws, hello


async def get(port, path):
    async with httpx.AsyncClient() as client:
        return await client.get(f"http://127.0.0.1:{port}{path}")


@pytest_asyncio.fixture
async def redis_server():
    return fakeredis.FakeServer()


async def test_redis_pubsub_distributes_across_instances(redis_server):
    client1 = fakeredis.aioredis.FakeRedis(server=redis_server)
    client2 = fakeredis.aioredis.FakeRedis(server=redis_server)
    broker1 = RedisBroker(client1)
    broker2 = RedisBroker(client2)

    _, srv1, port1 = await start_server(broker1, MessageStore())
    _, srv2, port2 = await start_server(broker2, MessageStore())
    try:
        ws, _ = await connect_client(port2)
        await ws.send(encode_message({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.1)

        await broker1.publish(
            BROKER_CHANNEL,
            {
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": "cross-instance"},
                "timestamp": "2024-01-01T00:00:00+00:00",
            },
        )

        received = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
        assert received["type"] == "broadcast"
        assert received["payload"]["text"] == "cross-instance"
        await ws.close()
    finally:
        srv1.close()
        srv2.close()
        await srv1.wait_closed()
        await srv2.wait_closed()
        await broker1.close()
        await broker2.close()


async def test_redis_client_state_stored_and_removed(redis_server):
    client = fakeredis.aioredis.FakeRedis(server=redis_server)
    broker = RedisBroker(client)
    ns, srv, port = await start_server(broker, MessageStore())
    try:
        ws, hello = await connect_client(port)
        client_id = hello["payload"]["id"]
        await asyncio.sleep(0.1)

        states = await broker.all_client_states()
        assert client_id in states
        assert states[client_id]["channels"] == []

        await ws.send(encode_message({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.1)
        states = await broker.all_client_states()
        assert states[client_id]["channels"] == ["alerts"]

        await ws.close()
        await asyncio.sleep(0.1)
        states = await broker.all_client_states()
        assert client_id not in states
    finally:
        srv.close()
        await srv.wait_closed()
        await broker.close()


async def test_messages_rest_endpoint_pagination(redis_server):
    client = fakeredis.aioredis.FakeRedis(server=redis_server)
    broker = RedisBroker(client)
    store = MessageStore()
    ns, srv, port = await start_server(broker, store)
    try:
        ws, _ = await connect_client(port)
        for i in range(5):
            await ws.send(
                encode_message(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"text": f"msg-{i}"},
                    }
                )
            )
        await asyncio.sleep(0.2)

        resp = await get(port, "/messages?limit=50&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        messages = data["messages"]
        # Most recent first.
        assert messages[0]["payload"]["text"] == "msg-4"
        assert messages[0]["channel"] == "alerts"
        assert messages[0]["type"] == "broadcast"
        assert messages[0]["id"] is not None
        assert messages[0]["timestamp"] is not None

        limited = (await get(port, "/messages?limit=2&offset=0")).json()["messages"]
        assert len(limited) == 2
        assert limited[0]["payload"]["text"] == "msg-4"
        assert limited[1]["payload"]["text"] == "msg-3"

        paged = (await get(port, "/messages?limit=2&offset=2")).json()["messages"]
        assert len(paged) == 2
        assert paged[0]["payload"]["text"] == "msg-2"
        assert paged[1]["payload"]["text"] == "msg-1"

        await ws.close()
    finally:
        srv.close()
        await srv.wait_closed()
        await broker.close()


def test_message_persistence_survives_restart(tmp_path):
    db_path = str(tmp_path / "messages.db")
    store = MessageStore(db_path)
    store.save(
        {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "persisted"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
    )
    store.close()

    reopened = MessageStore(db_path)
    messages = reopened.query()
    reopened.close()

    assert len(messages) == 1
    assert messages[0]["type"] == "broadcast"
    assert messages[0]["channel"] == "alerts"
    assert messages[0]["payload"]["text"] == "persisted"
    assert messages[0]["timestamp"] == "2024-01-01T00:00:00+00:00"
