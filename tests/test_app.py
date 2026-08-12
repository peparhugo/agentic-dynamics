import asyncio
import json

import pytest
import pytest_asyncio
import websockets

from app import NotificationServer


async def health(port: int) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest_asyncio.fixture
async def server(unused_tcp_port_factory):
    instance = NotificationServer(
        websocket_port=unused_tcp_port_factory(), health_port=unused_tcp_port_factory()
    )
    await instance.start()
    yield instance
    await instance.stop()


@pytest.mark.asyncio
async def test_connect_assigns_id_and_health_count(server):
    async with websockets.connect(f"ws://127.0.0.1:{server.websocket_port}") as client:
        message = json.loads(await client.recv())
        assert message["type"] == "system"
        assert "client_id" in message["payload"]
        assert server.client_count == 1
        assert (await health(server.health_port))["clients"] == 1
    await asyncio.sleep(0)
    assert server.client_count == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    first = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    second = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    await first.recv()
    await second.recv()
    await server.broadcast({"text": "hello"})
    messages = [json.loads(await client.recv()) for client in (first, second)]
    assert all(message["type"] == "broadcast" for message in messages)
    assert all(message["payload"] == {"text": "hello"} for message in messages)
    await first.close()
    await second.close()
