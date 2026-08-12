import asyncio
import json

import pytest
import pytest_asyncio
import websockets

from notification_server import NotificationServer


async def health_count(server: NotificationServer) -> int:
    reader, writer = await asyncio.open_connection("127.0.0.1", server.http_port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])["connected_clients"]


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(websocket_port=0, http_port=0)
    await instance.start()
    yield instance
    await instance.stop()


@pytest.mark.asyncio
async def test_assigns_unique_ids_and_reports_connections(server):
    first = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    second = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    try:
        first_id = json.loads(await first.recv())["payload"]["client_id"]
        second_id = json.loads(await second.recv())["payload"]["client_id"]
        assert first_id != second_id
        assert await health_count(server) == 2
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    clients = [
        await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
        for _ in range(2)
    ]
    try:
        await asyncio.gather(*(client.recv() for client in clients))
        await server.broadcast({"text": "hello"})
        received = [json.loads(await client.recv()) for client in clients]
        assert all(item["type"] == "broadcast" for item in received)
        assert all(item["payload"] == {"text": "hello"} for item in received)
        assert all(isinstance(item["timestamp"], str) for item in received)
    finally:
        await asyncio.gather(*(client.close() for client in clients))


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    client = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    await client.recv()
    assert await health_count(server) == 1
    await client.close()
    for _ in range(20):
        if await health_count(server) == 0:
            break
        await asyncio.sleep(0.01)
    assert await health_count(server) == 0


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(server):
    sender = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    target = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    try:
        await sender.recv()
        target_id = json.loads(await target.recv())["payload"]["client_id"]
        await sender.send(json.dumps({
            "type": "direct",
            "payload": {"client_id": target_id, "text": "private"},
        }))
        received = json.loads(await asyncio.wait_for(target.recv(), timeout=1))
        assert received["type"] == "direct"
        assert received["payload"] == {"text": "private"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)
    finally:
        await sender.close()
        await target.close()
