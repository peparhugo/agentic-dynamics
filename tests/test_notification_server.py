import asyncio
import json

import pytest
import pytest_asyncio
import websockets

from notification_server import NotificationServer, make_message


async def http_health(server: NotificationServer) -> dict:
    port = server._http_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(websocket_port=0, http_port=0)
    await instance.start()
    yield instance
    await instance.stop()


def websocket_url(server: NotificationServer) -> str:
    port = server._websocket_server.sockets[0].getsockname()[1]
    return f"ws://127.0.0.1:{port}"


@pytest.mark.asyncio
async def test_assigns_unique_ids_and_health_counts_clients(server):
    first = await websockets.connect(websocket_url(server))
    second = await websockets.connect(websocket_url(server))
    first_message = json.loads(await first.recv())
    second_message = json.loads(await second.recv())

    assert first_message["type"] == "system"
    assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
    assert (await http_health(server))["connected_clients"] == 2

    await first.close()
    await asyncio.sleep(0)
    assert (await http_health(server))["connected_clients"] == 1
    await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_every_client(server):
    first = await websockets.connect(websocket_url(server))
    second = await websockets.connect(websocket_url(server))
    await first.recv()
    await second.recv()

    await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    messages = [json.loads(await client.recv()) for client in (first, second)]
    assert all(message["type"] == "broadcast" for message in messages)
    assert all(message["payload"] == {"text": "hello"} for message in messages)
    assert all(isinstance(message["timestamp"], str) for message in messages)
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_message_targets_client(server):
    first = await websockets.connect(websocket_url(server))
    second = await websockets.connect(websocket_url(server))
    first_id = json.loads(await first.recv())["payload"]["client_id"]
    second_id = json.loads(await second.recv())["payload"]["client_id"]

    await first.send(json.dumps({
        "type": "direct",
        "payload": {"client_id": second_id, "text": "private"},
    }))
    message = json.loads(await second.recv())
    assert message["type"] == "direct"
    assert message["payload"]["text"] == "private"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(first.recv(), timeout=0.05)
    await first.close()
    await second.close()


def test_make_message_rejects_invalid_type():
    with pytest.raises(ValueError):
        make_message("unknown", {})
