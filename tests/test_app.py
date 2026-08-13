import asyncio
import json

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer


@pytest.fixture
async def notification_server():
    app = NotificationServer()
    server = await serve(app.handler, "127.0.0.1", 0, process_request=app.process_request)
    port = server.sockets[0].getsockname()[1]
    try:
        yield app, f"ws://127.0.0.1:{port}", port
    finally:
        server.close()
        await server.wait_closed()


async def receive_json(websocket):
    return json.loads(await websocket.recv())


async def get_json(port, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    headers, body = response.split(b"\r\n\r\n", 1)
    return headers, json.loads(body)


async def test_connections_receive_unique_client_ids(notification_server):
    _, url, _ = notification_server
    async with connect(url) as first, connect(url) as second:
        first_welcome, second_welcome = await receive_json(first), await receive_json(second)
        assert first_welcome["type"] == second_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
        assert isinstance(first_welcome["timestamp"], str)


async def test_broadcast_reaches_all_connected_clients(notification_server):
    _, url, _ = notification_server
    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "2026-01-01T00:00:00Z"}
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        await receive_json(recipient)
        await sender.send(json.dumps(message))
        assert await receive_json(sender) == message
        assert await receive_json(recipient) == message


async def test_direct_message_reaches_only_target(notification_server):
    _, url, _ = notification_server
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        recipient_id = (await receive_json(recipient))["payload"]["client_id"]
        message = {"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}, "timestamp": "2026-01-01T00:00:00Z"}
        await sender.send(json.dumps(message))
        assert await receive_json(recipient) == message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


async def test_channel_messages_reach_only_subscribers(notification_server):
    _, url, _ = notification_server
    subscribe = {
        "type": "subscribe",
        "channel": "alerts",
        "payload": {},
        "timestamp": "2026-01-01T00:00:00Z",
    }
    message = {
        "type": "broadcast",
        "channel": "alerts",
        "payload": {"text": "warning"},
        "timestamp": "2026-01-01T00:00:00Z",
    }
    async with connect(url) as sender, connect(url) as subscriber, connect(url) as other:
        await receive_json(sender)
        await receive_json(subscriber)
        await receive_json(other)
        await subscriber.send(json.dumps(subscribe))
        await sender.send(json.dumps(message))
        assert await receive_json(subscriber) == message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other.recv(), timeout=0.05)


async def test_unsubscribe_stops_channel_delivery(notification_server):
    _, url, _ = notification_server
    async with connect(url) as client:
        await receive_json(client)
        for message_type in ("subscribe", "unsubscribe"):
            await client.send(
                json.dumps(
                    {
                        "type": message_type,
                        "channel": "chat",
                        "payload": {},
                        "timestamp": "2026-01-01T00:00:00Z",
                    }
                )
            )
        await client.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "chat",
                    "payload": {"text": "hello"},
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.recv(), timeout=0.05)


async def test_channel_endpoints_report_subscribers(notification_server):
    _, url, port = notification_server
    async with connect(url) as first, connect(url) as second:
        first_id = (await receive_json(first))["payload"]["client_id"]
        second_id = (await receive_json(second))["payload"]["client_id"]
        for websocket, channel in ((first, "alerts"), (second, "alerts"), (second, "chat")):
            await websocket.send(
                json.dumps(
                    {
                        "type": "subscribe",
                        "channel": channel,
                        "payload": {},
                        "timestamp": "2026-01-01T00:00:00Z",
                    }
                )
            )
        for _ in range(20):
            _, channels = await get_json(port, "/channels")
            if channels == {"channels": {"alerts": 2, "chat": 1}}:
                break
            await asyncio.sleep(0.01)
        assert channels == {"channels": {"alerts": 2, "chat": 1}}
        headers, subscribers = await get_json(port, "/channels/alerts/subscribers")
        assert b"200 OK" in headers
        assert subscribers == {"subscribers": sorted((first_id, second_id))}


async def test_disconnect_removes_client(notification_server):
    app, url, _ = notification_server
    websocket = await connect(url)
    await receive_json(websocket)
    assert app.client_count == 1
    await websocket.close()
    for _ in range(20):
        if app.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert app.client_count == 0


async def test_health_endpoint_returns_client_count(notification_server):
    _, url, port = notification_server
    async with connect(url) as websocket:
        await receive_json(websocket)
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b"200 OK" in headers
    assert json.loads(body) == {"connected_clients": 1}
