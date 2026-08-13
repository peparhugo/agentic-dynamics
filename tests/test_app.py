import asyncio
import json

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer


@pytest.fixture
async def running_server():
    notification_server = NotificationServer()
    async with serve(notification_server.websocket_handler, "127.0.0.1", 0) as websocket_server:
        websocket_port = websocket_server.sockets[0].getsockname()[1]
        health_server = await asyncio.start_server(
            notification_server.health_handler, "127.0.0.1", 0
        )
        health_port = health_server.sockets[0].getsockname()[1]
        async with health_server:
            yield notification_server, websocket_port, health_port


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


async def health_request(port: int, path: str = "/health"):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    header, body = response.split(b"\r\n\r\n", 1)
    return header.decode(), json.loads(body)


async def test_connection_assigns_unique_ids_and_health_counts_clients(running_server):
    _, websocket_port, health_port = running_server
    async with connect(f"ws://127.0.0.1:{websocket_port}") as first, connect(
        f"ws://127.0.0.1:{websocket_port}"
    ) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)

        assert first_message["type"] == "system"
        assert first_message["payload"]["event"] == "connected"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert isinstance(first_message["timestamp"], str)
        header, body = await health_request(health_port)
        assert "200 OK" in header
        assert body == {"connected_clients": 2}


async def test_broadcast_reaches_all_clients(running_server):
    _, websocket_port, _ = running_server
    async with connect(f"ws://127.0.0.1:{websocket_port}") as sender, connect(
        f"ws://127.0.0.1:{websocket_port}"
    ) as receiver:
        await receive_json(sender)
        await receive_json(receiver)
        await sender.send(
            json.dumps(
                {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "client-time"}
            )
        )

        sender_message = await receive_json(sender)
        receiver_message = await receive_json(receiver)
        assert sender_message["type"] == receiver_message["type"] == "broadcast"
        assert sender_message["payload"] == receiver_message["payload"] == {"text": "hello"}
        assert sender_message["timestamp"] == receiver_message["timestamp"]


async def test_direct_message_only_reaches_recipient(running_server):
    _, websocket_port, _ = running_server
    async with connect(f"ws://127.0.0.1:{websocket_port}") as sender, connect(
        f"ws://127.0.0.1:{websocket_port}"
    ) as receiver:
        await receive_json(sender)
        recipient_id = (await receive_json(receiver))["payload"]["client_id"]
        payload = {"client_id": recipient_id, "text": "private"}
        await sender.send(json.dumps({"type": "direct", "payload": payload, "timestamp": "now"}))

        message = await receive_json(receiver)
        assert message["type"] == "direct"
        assert message["payload"] == payload
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


async def test_disconnect_removes_client(running_server):
    server, websocket_port, health_port = running_server
    websocket = await connect(f"ws://127.0.0.1:{websocket_port}")
    await receive_json(websocket)
    await websocket.close()

    async def wait_for_disconnect():
        while await server.clients.count():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait_for_disconnect(), timeout=1)
    _, body = await health_request(health_port)
    assert body == {"connected_clients": 0}


async def test_invalid_message_returns_system_error(running_server):
    _, websocket_port, _ = running_server
    async with connect(f"ws://127.0.0.1:{websocket_port}") as websocket:
        await receive_json(websocket)
        await websocket.send("not json")
        response = await receive_json(websocket)
        assert response["type"] == "system"
        assert response["payload"]["event"] == "error"


async def test_health_returns_not_found_for_other_paths(running_server):
    _, _, health_port = running_server
    header, body = await health_request(health_port, "/missing")
    assert "404 Not Found" in header
    assert body == {"error": "not found"}
