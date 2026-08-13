import asyncio
import json

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer, create_process_request


@pytest.fixture
async def notification_server():
    server = NotificationServer()
    async with serve(
        server.handler,
        "127.0.0.1",
        0,
        process_request=create_process_request(server),
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield server, f"ws://127.0.0.1:{port}"


async def connected_client(uri: str):
    client = await connect(uri)
    connected = json.loads(await client.recv())
    return client, connected["payload"]["client_id"]


async def test_assigns_unique_client_ids_and_removes_disconnected_clients(notification_server):
    server, uri = notification_server
    first, first_id = await connected_client(uri)
    second, second_id = await connected_client(uri)

    assert first_id != second_id
    assert server.client_count == 2

    await first.close()
    for _ in range(10):
        if server.client_count == 1:
            break
        await asyncio.sleep(0.01)
    assert server.client_count == 1
    await second.close()


async def test_broadcast_reaches_all_connected_clients(notification_server):
    _, uri = notification_server
    first, _ = await connected_client(uri)
    second, _ = await connected_client(uri)
    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "client-time"}

    await first.send(json.dumps(message))
    received = [json.loads(await first.recv()), json.loads(await second.recv())]

    assert all(item["type"] == "broadcast" for item in received)
    assert all(item["payload"] == {"text": "hello"} for item in received)
    assert all(item["timestamp"] != "client-time" for item in received)
    await first.close()
    await second.close()


async def test_direct_message_reaches_only_requested_client(notification_server):
    _, uri = notification_server
    sender, _ = await connected_client(uri)
    recipient, recipient_id = await connected_client(uri)

    await sender.send(json.dumps({
        "type": "direct",
        "payload": {"client_id": recipient_id, "text": "private"},
        "timestamp": "client-time",
    }))

    received = json.loads(await recipient.recv())
    assert received["type"] == "direct"
    assert received["payload"]["text"] == "private"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)
    await sender.close()
    await recipient.close()


async def test_health_reports_connected_client_count(notification_server):
    _, uri = notification_server
    host_and_port = uri.removeprefix("ws://")
    client, _ = await connected_client(uri)

    host, port = host_and_port.split(":")
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = (await reader.read()).decode()
    writer.close()
    await writer.wait_closed()

    assert "200 OK" in response
    assert json.loads(response.split("\r\n\r\n", 1)[1]) == {"connected_clients": 1}
    await client.close()
