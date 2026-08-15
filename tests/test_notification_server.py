import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest_asyncio.fixture
async def notification_server():
    server = NotificationServer()
    await server.start(port=0)
    yield server
    await server.stop()


async def receive_json(websocket):
    return json.loads(await websocket.recv())


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
