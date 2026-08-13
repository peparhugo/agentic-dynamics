"""Integration tests for the Redis pub/sub backbone: two NotificationServer
instances sharing one (fake) Redis broker must relay messages to each
other's locally connected clients, exactly like two real server processes
pointed at the same REDIS_URL would."""

import asyncio
import json

import fakeredis
import fakeredis.aioredis as fakeredis_asyncio
import pytest
import pytest_asyncio
import websockets

from notification_server.server import NotificationServer


@pytest_asyncio.fixture
async def server_pair(tmp_path):
    shared_fake_server = fakeredis.FakeServer()

    def make_client():
        return fakeredis_asyncio.FakeRedis(server=shared_fake_server, decode_responses=True)

    server_a = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "a-events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'a-messages.db'}",
        redis_client=make_client(),
    )
    server_b = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "b-events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'b-messages.db'}",
        redis_client=make_client(),
    )
    await server_a.start()
    await server_b.start()
    port_a = server_a._server.sockets[0].getsockname()[1]
    port_b = server_b._server.sockets[0].getsockname()[1]
    try:
        yield server_a, port_a, server_b, port_b
    finally:
        await server_a.stop()
        await server_b.stop()


async def connect(port):
    ws = await websockets.connect(f"ws://localhost:{port}")
    welcome = json.loads(await ws.recv())
    return ws, welcome


async def test_broadcast_from_one_instance_reaches_client_on_another(server_pair):
    _, port_a, _, port_b = server_pair
    ws_a, _ = await connect(port_a)
    ws_b, _ = await connect(port_b)
    try:
        await ws_a.send(
            json.dumps({"type": "broadcast", "payload": {"text": "hello from A"}})
        )
        # The sender's own instance delivers locally...
        msg_a = json.loads(await ws_a.recv())
        # ...and the other instance's redis worker relays it to its own clients.
        msg_b = json.loads(await ws_b.recv())
        assert msg_a["payload"]["text"] == "hello from A"
        assert msg_b["payload"]["text"] == "hello from A"
    finally:
        await ws_a.close()
        await ws_b.close()


async def test_channel_scoped_broadcast_only_reaches_subscribers_across_instances(server_pair):
    _, port_a, _, port_b = server_pair
    ws_a, _ = await connect(port_a)
    ws_b_subscribed, _ = await connect(port_b)
    ws_b_unsubscribed, _ = await connect(port_b)
    try:
        await ws_b_subscribed.send(
            json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}})
        )
        await ws_b_subscribed.recv()

        await ws_a.send(
            json.dumps(
                {"type": "broadcast", "payload": {"channel": "alerts", "text": "fire!"}}
            )
        )
        msg = json.loads(await ws_b_subscribed.recv())
        assert msg["payload"]["text"] == "fire!"

        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws_b_unsubscribed.recv(), timeout=0.2)
    finally:
        await ws_a.close()
        await ws_b_subscribed.close()
        await ws_b_unsubscribed.close()


async def test_direct_message_reaches_target_on_another_instance(server_pair):
    _, port_a, _, port_b = server_pair
    ws_a, _ = await connect(port_a)
    ws_b, welcome_b = await connect(port_b)
    try:
        target_id = welcome_b["payload"]["client_id"]
        await ws_a.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": target_id, "content": {"text": "psst"}},
                }
            )
        )
        msg_b = json.loads(await ws_b.recv())
        assert msg_b["type"] == "direct"
        assert msg_b["payload"]["content"] == {"text": "psst"}

        # ws_a itself must not receive its own direct message.
        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws_a.recv(), timeout=0.2)
    finally:
        await ws_a.close()
        await ws_b.close()


async def test_direct_message_to_client_on_no_instance_returns_error(server_pair):
    _, port_a, _, _ = server_pair
    ws_a, _ = await connect(port_a)
    try:
        await ws_a.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": "no-such-client", "content": {}},
                }
            )
        )
        reply = json.loads(await ws_a.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws_a.close()


async def test_client_presence_is_visible_across_instances_via_redis(server_pair):
    server_a, port_a, server_b, _ = server_pair
    ws_a, welcome_a = await connect(port_a)
    try:
        client_id = welcome_a["payload"]["client_id"]
        # Instance B never saw this connection locally, but can look up the
        # client's presence via the shared Redis backend.
        assert await server_b.redis.get_client_server(client_id) == server_a.server_id
    finally:
        await ws_a.close()

    for _ in range(50):
        if await server_b.redis.get_client_server(client_id) is None:
            break
        await asyncio.sleep(0.05)
    assert await server_b.redis.get_client_server(client_id) is None
