import asyncio
import json

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer


@pytest.fixture
async def notification_server():
    server = NotificationServer()
    async with serve(
        server.websocket_handler,
        "127.0.0.1",
        0,
        process_request=server.health_response,
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield server, f"ws://127.0.0.1:{port}", port


async def receive_json(websocket):
    return json.loads(await websocket.recv())


async def test_connect_assigns_unique_client_ids(notification_server):
    _, url, _ = notification_server
    async with connect(url) as first, connect(url) as second:
        first_welcome = await receive_json(first)
        second_welcome = await receive_json(second)

    assert first_welcome["type"] == "system"
    assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
    assert isinstance(first_welcome["timestamp"], str)


async def test_broadcast_reaches_all_connected_clients(notification_server):
    _, url, _ = notification_server
    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "2026-01-01T00:00:00+00:00"}
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        await receive_json(recipient)
        await sender.send(json.dumps(message))

        assert await receive_json(sender) == message
        assert await receive_json(recipient) == message


async def test_direct_message_reaches_only_target_client(notification_server):
    _, url, _ = notification_server
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        recipient_id = (await receive_json(recipient))["payload"]["client_id"]
        message = {
            "type": "direct",
            "payload": {"client_id": recipient_id, "text": "private"},
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        await sender.send(json.dumps(message))

        assert await receive_json(recipient) == message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(recipient.recv(), timeout=0.05)


async def test_disconnected_client_is_removed(notification_server):
    server, url, _ = notification_server
    async with connect(url) as websocket:
        await receive_json(websocket)
        assert server.client_count == 1

    for _ in range(10):
        if server.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.client_count == 0


async def test_health_reports_connected_client_count(notification_server):
    _, url, port = notification_server
    async with connect(url) as websocket:
        await receive_json(websocket)
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()

    assert b"200 OK" in response
    assert json.loads(response.split(b"\r\n\r\n", 1)[1]) == {"connected_clients": 1}
