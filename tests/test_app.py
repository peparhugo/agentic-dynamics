import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def running_server():
    notification_server = NotificationServer()
    server = await notification_server.start(port=0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield notification_server, f"ws://127.0.0.1:{port}"
    finally:
        server.close()
        await server.wait_closed()


async def receive_json(connection):
    return json.loads(await asyncio.wait_for(connection.recv(), timeout=1))


async def test_connections_receive_unique_ids_and_health_count(running_server):
    _, url = running_server
    async with connect(url) as first, connect(url) as second:
        first_welcome = await receive_json(first)
        second_welcome = await receive_json(second)

        assert first_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]

        reader, writer = await asyncio.open_connection("127.0.0.1", url.rsplit(":", 1)[1])
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=1)
        writer.close()
        await writer.wait_closed()
        assert b'"connected_clients": 2' in response


async def test_broadcast_reaches_all_connected_clients(running_server):
    _, url = running_server
    async with connect(url) as first, connect(url) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

        received = [await receive_json(first), await receive_json(second)]
        assert all(message["type"] == "broadcast" for message in received)
        assert all(message["payload"] == {"text": "hello"} for message in received)
        assert all("timestamp" in message for message in received)


async def test_direct_message_reaches_only_target(running_server):
    _, url = running_server
    async with connect(url) as first, connect(url) as second:
        await receive_json(first)
        target_id = (await receive_json(second))["payload"]["client_id"]
        await first.send(json.dumps({"type": "direct", "payload": {"client_id": target_id, "text": "private"}}))

        message = await receive_json(second)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.1)


async def test_disconnected_client_is_removed(running_server):
    notification_server, url = running_server
    connection = await connect(url)
    await receive_json(connection)
    assert len(notification_server.clients) == 1

    await connection.close()
    for _ in range(20):
        if len(notification_server.clients) == 0:
            break
        await asyncio.sleep(0.01)
    assert len(notification_server.clients) == 0
