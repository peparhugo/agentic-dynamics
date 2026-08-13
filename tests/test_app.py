import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer


@pytest_asyncio.fixture
async def notification_server():
    application = NotificationServer()
    async with serve(
        application.handler,
        "127.0.0.1",
        0,
        process_request=application.process_request,
    ) as server:
        yield application, f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"


async def receive_json(client):
    return json.loads(await client.recv())


async def get_json(url, path):
    host, port = "127.0.0.1", int(url.rsplit(":", 1)[1])
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


@pytest.mark.asyncio
async def test_assigns_unique_ids_and_reports_health(notification_server):
    application, url = notification_server
    async with connect(url) as first, connect(url) as second:
        first_welcome, second_welcome = await receive_json(first), await receive_json(second)
        assert first_welcome["type"] == second_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
        assert application.connected_client_count == 2

        response = await get_json(url, "/health")
        assert b"200 OK" in response
        assert b'{"connected_clients": 2}' in response


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(notification_server):
    _, url = notification_server
    async with connect(url) as first, connect(url) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        messages = [await receive_json(first), await receive_json(second)]
        assert all(message["type"] == "broadcast" for message in messages)
        assert all(message["payload"] == {"text": "hello"} for message in messages)
        assert all("timestamp" in message for message in messages)


@pytest.mark.asyncio
async def test_direct_message_and_disconnect_removal(notification_server):
    application, url = notification_server
    async with connect(url) as first, connect(url) as second:
        first_welcome, second_welcome = await receive_json(first), await receive_json(second)
        await first.send(json.dumps({
            "type": "direct",
            "payload": {"client_id": second_welcome["payload"]["client_id"], "text": "private"},
        }))
        direct = await receive_json(second)
        assert direct["type"] == "direct"
        assert direct["payload"]["text"] == "private"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]

    await asyncio.sleep(0)
    assert application.connected_client_count == 0


@pytest.mark.asyncio
async def test_channel_subscriptions_route_messages_and_list_subscribers(notification_server):
    _, url = notification_server
    async with connect(url) as first, connect(url) as second, connect(url) as third:
        first_welcome = await receive_json(first)
        second_welcome = await receive_json(second)
        await receive_json(third)
        await first.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "alerts"}))
        await third.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "chat"}))

        channels = await get_json(url, "/channels")
        assert b'{"alerts": 2, "chat": 1}' in channels
        subscribers = await get_json(url, "/channels/alerts/subscribers")
        expected_ids = sorted([first_welcome["payload"]["client_id"], second_welcome["payload"]["client_id"]])
        assert json.loads(subscribers.split(b"\r\n\r\n", 1)[1]) == {"subscribers": expected_ids}

        await third.send(json.dumps({"type": "broadcast", "payload": {"text": "warning"}, "channel": "alerts"}))
        messages = [await receive_json(first), await receive_json(second)]
        assert all(message["payload"] == {"text": "warning"} for message in messages)
        assert all(message["channel"] == "alerts" for message in messages)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(third.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_unsubscribe_stops_channel_delivery(notification_server):
    _, url = notification_server
    async with connect(url) as first, connect(url) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "system"}))
        await first.send(json.dumps({"type": "unsubscribe", "payload": {}, "channel": "system"}))
        await second.send(json.dumps({"type": "broadcast", "payload": {}, "channel": "system"}))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)
