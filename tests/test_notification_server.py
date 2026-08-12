import asyncio
import json
import tempfile
import urllib.request

import pytest
import pytest_asyncio
import websockets
import fakeredis.aioredis

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


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated():
    with tempfile.NamedTemporaryFile(suffix=".db") as database:
        instance = NotificationServer(websocket_port=0, http_port=0,
                                      database_url=f"sqlite:///{database.name}")
        await instance.start()
        try:
            socket = await websockets.connect(f"ws://127.0.0.1:{instance.websocket_port}")
            await receive_json(socket)
            await socket.send(json.dumps({"type": "subscribe", "channel": "audit",
                                          "payload": {}}))
            await socket.send(json.dumps({"type": "broadcast", "channel": "audit",
                                          "payload": {"text": "stored"}}))
            await receive_json(socket)
            response = await asyncio.to_thread(
                urllib.request.urlopen,
                f"http://127.0.0.1:{instance.http_port}/messages?limit=1&offset=0",
            )
            body = json.loads(response.read())
            assert len(body["messages"]) == 1
            assert body["messages"][0]["channel"] == "audit"
            assert body["messages"][0]["payload"] == {"text": "stored"}
            await socket.close()
        finally:
            await instance.stop()


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    first = NotificationServer(websocket_port=0, http_port=0, redis_client=redis)
    second = NotificationServer(websocket_port=0, http_port=0, redis_client=redis)
    await first.start()
    await second.start()
    sender = await websockets.connect(f"ws://127.0.0.1:{first.websocket_port}")
    receiver = await websockets.connect(f"ws://127.0.0.1:{second.websocket_port}")
    try:
        await receive_json(sender)
        await receive_json(receiver)
        await receiver.send(json.dumps({"type": "subscribe", "channel": "shared",
                                         "payload": {}}))
        receiver_id = next(iter(second.clients))
        state_channels = []
        for _ in range(20):
            state_channels = json.loads(
                await redis.hget(f"notifications:client:{receiver_id}", "channels")
            )
            if state_channels == ["shared"]:
                break
            await asyncio.sleep(0.01)
        assert state_channels == ["shared"]
        await sender.send(json.dumps({"type": "broadcast", "channel": "shared",
                                      "payload": {"text": "cross-instance"}}))
        message = await asyncio.wait_for(receive_json(receiver), timeout=1)
        assert message["payload"] == {"text": "cross-instance"}
    finally:
        await sender.close()
        await receiver.close()
        await first.stop()
        await second.stop()
