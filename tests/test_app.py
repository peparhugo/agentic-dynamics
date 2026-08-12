import asyncio
import json

import pytest
import pytest_asyncio
import websockets

from app import NotificationServer


async def http_health(host: str, port: int) -> dict:
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(port=0)
    running = await instance.start()
    instance.port = running.sockets[0].getsockname()[1]
    yield instance
    await instance.stop()


@pytest.mark.asyncio
async def test_connect_broadcast_and_health(server):
    uri = f"ws://{server.host}:{server.port}/"
    async with websockets.connect(uri) as first, websockets.connect(uri) as second:
        assert await http_health(server.host, server.port) == {
            "status": "ok", "connected_clients": 2
        }
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        for client in (first, second):
            message = json.loads(await asyncio.wait_for(client.recv(), 1))
            assert message["type"] == "broadcast"
            assert message["payload"] == {"text": "hello"}
            assert isinstance(message["timestamp"], str)


@pytest.mark.asyncio
async def test_disconnect_is_removed(server):
    uri = f"ws://{server.host}:{server.port}/"
    client = await websockets.connect(uri)
    assert server.connected_client_count == 1
    await client.close()
    for _ in range(20):
        if server.connected_client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.connected_client_count == 0


@pytest.mark.asyncio
async def test_client_ids_are_monotonic_and_direct_messages_work(server):
    uri = f"ws://{server.host}:{server.port}/"
    async with websockets.connect(uri) as first, websockets.connect(uri) as second:
        ids = sorted(server.clients)
        assert ids[1] > ids[0] >= 1
        await first.send(json.dumps({"type": "direct", "payload": {"client_id": ids[1], "value": 3}}))
        message = json.loads(await asyncio.wait_for(second.recv(), 1))
        assert message["type"] == "direct"
        assert message["payload"]["value"] == 3
