import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from notification_server import NotificationServer


async def get_json(port: int, path: str) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    body = response.split(b"\r\n\r\n", 1)[1]
    return json.loads(body)


async def health(port: int) -> dict:
    return await get_json(port, "/health")


@pytest.fixture
async def running_server():
    server = NotificationServer()
    async with server.listen(port=0) as listener:
        port = listener.sockets[0].getsockname()[1]
        yield server, port


@pytest.mark.asyncio
async def test_connect_assigns_id_and_health_reports_clients(running_server):
    server, port = running_server
    assert await health(port) == {"connected_clients": 0}

    async with connect(f"ws://127.0.0.1:{port}") as client:
        welcome = json.loads(await client.recv())
        assert welcome["type"] == "system"
        assert welcome["payload"]["event"] == "connected"
        assert len(welcome["payload"]["client_id"]) == 32
        assert "timestamp" in welcome
        assert await health(port) == {"connected_clients": 1}

    for _ in range(10):
        if server.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.client_count == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(f"ws://127.0.0.1:{port}") as second:
        await first.recv()
        await second.recv()
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        received = [json.loads(await first.recv()), json.loads(await second.recv())]

    assert all(message["type"] == "broadcast" for message in received)
    assert all(message["payload"] == {"text": "hello"} for message in received)
    assert all("timestamp" in message for message in received)


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as sender, connect(f"ws://127.0.0.1:{port}") as recipient:
        await sender.recv()
        target_id = json.loads(await recipient.recv())["payload"]["client_id"]
        await sender.send(json.dumps({"type": "direct", "payload": {"client_id": target_id, "text": "private"}}))
        message = json.loads(await recipient.recv())
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_invalid_messages_return_system_error(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as client:
        await client.recv()
        await client.send("not json")
        error = json.loads(await client.recv())
        assert error["type"] == "system"
        assert error["payload"]["event"] == "error"


@pytest.mark.asyncio
async def test_channel_messages_only_reach_subscribers(running_server):
    _, port = running_server
    async with (
        connect(f"ws://127.0.0.1:{port}") as sender,
        connect(f"ws://127.0.0.1:{port}") as subscriber,
        connect(f"ws://127.0.0.1:{port}") as other,
    ):
        await sender.recv()
        await subscriber.recv()
        await other.recv()
        await subscriber.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
        await sender.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "urgent"}}))

        received = json.loads(await subscriber.recv())
        assert received["channel"] == "alerts"
        assert received["payload"] == {"text": "urgent"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_channel_endpoints_and_unsubscribe(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as client:
        client_id = json.loads(await client.recv())["payload"]["client_id"]
        await client.send(json.dumps({"type": "subscribe", "channel": "system", "payload": {}}))
        assert await get_json(port, "/channels") == {"system": 1}
        assert await get_json(port, "/channels/system/subscribers") == {
            "channel": "system",
            "subscribers": [client_id],
        }

        await client.send(json.dumps({"type": "unsubscribe", "channel": "system", "payload": {}}))
        assert await get_json(port, "/channels") == {}
        assert await get_json(port, "/channels/system/subscribers") == {
            "channel": "system",
            "subscribers": [],
        }
