import asyncio
import json
import urllib.request

import pytest
import pytest_asyncio
import websockets

from app import NotificationServer


async def receive_json(socket):
    return json.loads(await socket.recv())


@pytest_asyncio.fixture
async def running_server():
    instance = NotificationServer(websocket_port=0, http_port=0)
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()


@pytest.mark.asyncio
async def test_assigns_unique_ids_and_health_count(running_server):
    uri = f"ws://127.0.0.1:{running_server.websocket_port}"
    first = await websockets.connect(uri)
    second = await websockets.connect(uri)
    try:
        first_system = await receive_json(first)
        second_system = await receive_json(second)
        first_id = first_system["payload"]["client_id"]
        second_id = second_system["payload"]["client_id"]
        assert first_id != second_id
        assert first_system["type"] == second_system["type"] == "system"
        assert running_server.client_count == 2

        response = await asyncio.to_thread(
            urllib.request.urlopen,
            f"http://127.0.0.1:{running_server.http_port}/health",
        )
        assert json.loads(response.read()) == {"connected_clients": 2}
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(running_server):
    uri = f"ws://127.0.0.1:{running_server.websocket_port}"
    first = await websockets.connect(uri)
    second = await websockets.connect(uri)
    try:
        await receive_json(first)
        await receive_json(second)
        message = {"type": "broadcast", "payload": {"text": "hello"}}
        await first.send(json.dumps(message))
        received = await asyncio.gather(receive_json(first), receive_json(second))
        assert all(item["type"] == "broadcast" for item in received)
        assert all(item["payload"] == {"text": "hello"} for item in received)
        assert all(isinstance(item["timestamp"], str) for item in received)
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(running_server):
    uri = f"ws://127.0.0.1:{running_server.websocket_port}"
    sender = await websockets.connect(uri)
    target = await websockets.connect(uri)
    observer = await websockets.connect(uri)
    try:
        sender_id = (await receive_json(sender))["payload"]["client_id"]
        target_id = (await receive_json(target))["payload"]["client_id"]
        await receive_json(observer)
        await sender.send(json.dumps({
            "type": "direct",
            "payload": {"client_id": target_id, "text": "private"},
            "timestamp": "2026-01-01T00:00:00+00:00",
        }))
        received = await asyncio.wait_for(receive_json(target), timeout=1)
        assert received["payload"]["text"] == "private"
        assert received["timestamp"] == "2026-01-01T00:00:00+00:00"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(receive_json(observer), timeout=0.1)
        assert sender_id
    finally:
        await sender.close()
        await target.close()
        await observer.close()


@pytest.mark.asyncio
async def test_disconnect_removes_client(running_server):
    socket = await websockets.connect(
        f"ws://127.0.0.1:{running_server.websocket_port}"
    )
    await receive_json(socket)
    assert running_server.client_count == 1
    await socket.close()
    for _ in range(20):
        if running_server.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert running_server.client_count == 0
