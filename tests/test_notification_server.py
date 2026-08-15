import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from app import InMemoryBroker, NotificationServer, RedisBroker


@pytest_asyncio.fixture
async def notification_server():
    server = NotificationServer()
    await server.start(port=0)
    yield server
    await server.stop()


async def receive_json(websocket):
    return json.loads(await websocket.recv())


async def get_json(server, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest.mark.asyncio
async def test_connect_assigns_unique_client_ids_and_health_reports_count(notification_server):
    uri = f"ws://127.0.0.1:{notification_server.port}"
    async with connect(uri) as first, connect(uri) as second:
        first_connected = await receive_json(first)
        second_connected = await receive_json(second)

        assert first_connected["type"] == "system"
        assert first_connected["payload"]["event"] == "connected"
        assert first_connected["payload"]["client_id"] != second_connected["payload"]["client_id"]

        reader, writer = await asyncio.open_connection("127.0.0.1", notification_server.port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()

        assert b"200 OK" in response
        assert json.loads(response.split(b"\r\n\r\n", 1)[1]) == {"connected_clients": 2}


@pytest.mark.asyncio
async def test_broadcast_reaches_every_client(notification_server):
    uri = f"ws://127.0.0.1:{notification_server.port}"
    async with connect(uri) as first, connect(uri) as second:
        await receive_json(first)
        await receive_json(second)

        await first.send(json.dumps({"type": "broadcast", "payload": {"message": "hello"}}))
        received = [await receive_json(first), await receive_json(second)]

        assert all(message["type"] == "broadcast" for message in received)
        assert all(message["payload"]["message"] == "hello" for message in received)
        assert all(message["timestamp"] for message in received)


@pytest.mark.asyncio
async def test_direct_message_and_disconnect_removal(notification_server):
    uri = f"ws://127.0.0.1:{notification_server.port}"
    async with connect(uri) as first, connect(uri) as second:
        first_connected = await receive_json(first)
        second_connected = await receive_json(second)
        second_id = second_connected["payload"]["client_id"]

        await first.send(json.dumps({"type": "direct", "payload": {"client_id": second_id, "message": "private"}}))
        direct_message = await receive_json(second)

        assert direct_message["type"] == "direct"
        assert direct_message["payload"]["message"] == "private"
        assert direct_message["payload"]["sender_id"] == first_connected["payload"]["client_id"]

    await asyncio.sleep(0)
    assert notification_server.client_count == 0


@pytest.mark.asyncio
async def test_channel_messages_reach_only_subscribers_and_endpoints_report_members(notification_server):
    uri = f"ws://127.0.0.1:{notification_server.port}"
    async with connect(uri) as first, connect(uri) as second, connect(uri) as third:
        first_id = (await receive_json(first))["payload"]["client_id"]
        second_id = (await receive_json(second))["payload"]["client_id"]
        await receive_json(third)

        await first.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await second.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
        assert (await receive_json(first))["payload"] == {"event": "subscribed", "channel": "alerts"}
        assert (await receive_json(second))["payload"] == {"event": "subscribed", "channel": "alerts"}

        assert await get_json(notification_server, "/channels") == {"channels": [{"name": "alerts", "subscriber_count": 2}]}
        assert await get_json(notification_server, "/channels/alerts/subscribers") == {"channel": "alerts", "subscribers": sorted([first_id, second_id])}

        await third.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "message": "notice"}}))
        assert (await receive_json(first))["payload"]["message"] == "notice"
        assert (await receive_json(second))["payload"]["message"] == "notice"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(third.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_unsubscribe_removes_channel_and_unscoped_messages_still_broadcast(notification_server):
    uri = f"ws://127.0.0.1:{notification_server.port}"
    async with connect(uri) as first, connect(uri) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await receive_json(first)
        await first.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "chat"}}))
        assert (await receive_json(first))["payload"] == {"event": "unsubscribed", "channel": "chat"}
        assert await get_json(notification_server, "/channels") == {"channels": []}

        await first.send(json.dumps({"type": "broadcast", "payload": {"message": "everyone"}}))
        assert (await receive_json(first))["payload"]["message"] == "everyone"
        assert (await receive_json(second))["payload"]["message"] == "everyone"


@pytest.mark.asyncio
async def test_messages_endpoint_persists_published_messages(tmp_path):
    server = NotificationServer(database_url=f"sqlite:///{tmp_path / 'history.sqlite'}")
    await server.start(port=0)
    try:
        uri = f"ws://127.0.0.1:{server.port}"
        async with connect(uri) as client:
            await receive_json(client)
            await client.send(json.dumps({"type": "subscribe", "payload": {"channel": "audit"}}))
            await receive_json(client)
            await client.send(json.dumps({"type": "broadcast", "payload": {"channel": "audit", "message": "saved"}}))
            await receive_json(client)

        page = await get_json(server, "/messages?limit=1&offset=0")
        assert len(page["messages"]) == 1
        message = page["messages"][0]
        assert message["type"] == "broadcast"
        assert message["channel"] == "audit"
        assert message["payload"]["message"] == "saved"
        assert message["id"]
        assert message["timestamp"]
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_across_server_instances():
    fakeredis = pytest.importorskip("fakeredis.aioredis")
    redis = fakeredis.FakeRedis()
    first_server = NotificationServer(broker=RedisBroker(redis))
    second_server = NotificationServer(broker=RedisBroker(redis))
    await first_server.start(port=0)
    await second_server.start(port=0)
    try:
        first_uri = f"ws://127.0.0.1:{first_server.port}"
        second_uri = f"ws://127.0.0.1:{second_server.port}"
        async with connect(first_uri) as first, connect(second_uri) as second:
            await receive_json(first)
            await receive_json(second)
            await first.send(json.dumps({"type": "broadcast", "payload": {"message": "shared"}}))
            assert (await receive_json(first))["payload"]["message"] == "shared"
            assert (await receive_json(second))["payload"]["message"] == "shared"
    finally:
        await first_server.stop()
        await second_server.stop()
        await redis.aclose()
