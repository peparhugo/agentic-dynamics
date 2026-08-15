import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def notification_server():
    server = NotificationServer()
    listener = await server.start(port=0)
    port = listener.sockets[0].getsockname()[1]
    yield server, f"ws://127.0.0.1:{port}"
    await server.stop()


async def receive_json(client):
    return json.loads(await client.recv())


@pytest.mark.asyncio
async def test_connection_receives_unique_system_identifier(notification_server):
    server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)

        assert server.client_count == 2
        assert first_message["type"] == second_message["type"] == "system"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert "timestamp" in first_message


@pytest.mark.asyncio
async def test_broadcast_reaches_every_client(notification_server):
    _, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

        messages = [await receive_json(first), await receive_json(second)]
        assert all(message["type"] == "broadcast" for message in messages)
        assert all(message["payload"] == {"text": "hello"} for message in messages)
        assert all("timestamp" in message for message in messages)


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(notification_server):
    _, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        await receive_json(first)
        target_id = (await receive_json(second))["payload"]["client_id"]
        payload = {"client_id": target_id, "text": "private"}
        await first.send(json.dumps({"type": "direct", "payload": payload}))

        message = await receive_json(second)
        assert message["type"] == "direct"
        assert message["payload"] == payload
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_disconnect_removes_client(notification_server):
    server, uri = notification_server
    client = await connect(uri)
    await receive_json(client)
    assert server.client_count == 1

    await client.close()
    for _ in range(20):
        if server.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.client_count == 0


@pytest.mark.asyncio
async def test_health_returns_connected_client_count(notification_server):
    _, uri = notification_server
    port = uri.rsplit(":", 1)[1]
    client = await connect(uri)
    await receive_json(client)

    reader, writer = await asyncio.open_connection("127.0.0.1", int(port))
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    await client.close()

    headers, body = response.split(b"\r\n\r\n", 1)
    assert b"200 OK" in headers
    assert json.loads(body) == {"connected_clients": 1}
