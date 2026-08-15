import asyncio
import json
from urllib.request import urlopen

import pytest
import pytest_asyncio
import websockets

from app import NotificationServer


@pytest_asyncio.fixture
async def server():
    instance = NotificationServer(port=0)
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()


async def receive_message(websocket):
    return json.loads(await websocket.recv())


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_with_wire_format(server):
    first = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    second = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    try:
        await asyncio.sleep(0)
        assert server.client_count == 2
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        messages = await asyncio.gather(receive_message(first), receive_message(second))
        assert all(message["type"] == "broadcast" for message in messages)
        assert all(message["payload"] == {"text": "hello"} for message in messages)
        assert all(isinstance(message["timestamp"], str) for message in messages)
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(server):
    first = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    second = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    try:
        for _ in range(10):
            if server.client_count == 2:
                break
            await asyncio.sleep(0)
        target_id = next(client_id for client_id, client in server.clients.items() if client is not None)
        await first.send(json.dumps({"type": "direct", "payload": {"target_id": target_id, "text": "private"}}))
        target = await asyncio.wait_for(second.recv() if server.clients[target_id] is second else first.recv(), 1)
        assert json.loads(target)["payload"] == {"text": "private"}
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_health_endpoint_and_disconnect_cleanup(server):
    websocket = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    try:
        await asyncio.sleep(0)
        def request_health():
            with urlopen(f"http://127.0.0.1:{server.port}/health") as response:
                return response.status, json.loads(response.read())

        status, body = await asyncio.to_thread(request_health)
        assert status == 200
        assert body == {"status": "ok", "connected_clients": 1}
    finally:
        await websocket.close()
    for _ in range(10):
        if server.client_count == 0:
            break
        await asyncio.sleep(0)
    assert server.client_count == 0
