import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest_asyncio.fixture
async def notification_server():
    application = NotificationServer()
    async with application.create_server(port=0) as server:
        port = server.sockets[0].getsockname()[1]
        yield application, f"ws://127.0.0.1:{port}"


async def receive_json(connection):
    return json.loads(await connection.recv())


@pytest.mark.asyncio
async def test_connect_assigns_unique_client_ids_and_health_reports_count(notification_server):
    _, address = notification_server
    async with connect(address) as first, connect(address) as second:
        first_welcome, second_welcome = await asyncio.gather(receive_json(first), receive_json(second))

        assert first_welcome["type"] == second_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]

        reader, writer = await asyncio.open_connection("127.0.0.1", int(address.rsplit(":", 1)[1]))
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
        assert b"200 OK" in response
        assert b'{"connected_clients": 2}' in response


@pytest.mark.asyncio
async def test_broadcast_reaches_all_connected_clients(notification_server):
    _, address = notification_server
    async with connect(address) as sender, connect(address) as recipient:
        await receive_json(sender)
        await receive_json(recipient)
        await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "ignored"}))

        received = await asyncio.gather(receive_json(sender), receive_json(recipient))
        assert all(message["type"] == "broadcast" for message in received)
        assert all(message["payload"] == {"text": "hello"} for message in received)
        assert all(isinstance(message["timestamp"], str) for message in received)


@pytest.mark.asyncio
async def test_direct_message_and_disconnect_cleanup(notification_server):
    application, address = notification_server
    async with connect(address) as sender, connect(address) as recipient:
        await receive_json(sender)
        recipient_welcome = await receive_json(recipient)
        recipient_id = recipient_welcome["payload"]["client_id"]
        await sender.send(json.dumps({"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}}))
        message = await receive_json(recipient)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "private"

    for _ in range(10):
        if await application.clients.count() == 0:
            break
        await asyncio.sleep(0.01)
    assert await application.clients.count() == 0


@pytest.mark.asyncio
async def test_invalid_message_returns_system_error(notification_server):
    _, address = notification_server
    async with connect(address) as client:
        await receive_json(client)
        await client.send("not json")
        error = await receive_json(client)
        assert error["type"] == "system"
        assert error["payload"] == {"error": "message must be valid JSON"}
