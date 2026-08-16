import asyncio
import json
from pathlib import Path
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


@pytest.mark.asyncio
async def test_channel_subscription_routes_and_unsubscribes(server):
    first = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    second = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    try:
        await first.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "payload": {"channel": "system"}}))
        await asyncio.sleep(0)

        await first.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "alert"}}))
        assert (await receive_message(first))["payload"]["text"] == "alert"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(second.recv(), 0.05)

        await first.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        await asyncio.sleep(0)
        await first.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "ignored"}}))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), 0.05)
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_channel_endpoints_list_subscribers(server):
    websocket = await websockets.connect(f"ws://127.0.0.1:{server.port}")
    try:
        await websocket.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        for _ in range(10):
            if "alerts" in server.channels:
                break
            await asyncio.sleep(0.01)

        def request(path):
            with urlopen(f"http://127.0.0.1:{server.port}{path}") as response:
                return response.status, json.loads(response.read())

        status, channels = await asyncio.to_thread(request, "/channels")
        assert status == 200
        assert channels == {"channels": [{"name": "alerts", "subscriber_count": 1}]}
        client_id = next(iter(server.clients))
        status, subscribers = await asyncio.to_thread(request, "/channels/alerts/subscribers")
        assert status == 200
        assert subscribers == {"channel": "alerts", "subscribers": [client_id]}
    finally:
        await websocket.close()


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path: Path):
    instance = NotificationServer(port=0, database_url=str(tmp_path / "messages.db"), redis_url="redis://127.0.0.1:1")
    await instance.start()
    try:
        await instance.broadcast({"text": "one", "channel": "history"})
        await instance.broadcast({"text": "two"}, "system")

        def request():
            with urlopen(f"http://127.0.0.1:{instance.port}/messages?limit=1&offset=1") as response:
                return response.status, json.loads(response.read())

        status, body = await asyncio.to_thread(request)
        assert status == 200
        assert body["messages"][0]["payload"] == {"text": "two"}
        assert body["messages"][0]["type"] == "system"
    finally:
        await instance.stop()


@pytest.mark.asyncio
async def test_broker_distributes_messages_between_server_instances():
    first = NotificationServer(port=0, redis_url="redis://127.0.0.1:1")
    second = NotificationServer(port=0, redis_url="redis://127.0.0.1:1")
    await first.start()
    await second.start()
    try:
        import websockets
        client = await websockets.connect(f"ws://127.0.0.1:{second.port}")
        try:
            await client.send(json.dumps({"type": "subscribe", "channel": "shared"}))
            await asyncio.sleep(0)
            await first.broadcast({"channel": "shared", "text": "from another server"})
            message = json.loads(await asyncio.wait_for(client.recv(), 1))
            assert message["payload"]["text"] == "from another server"
        finally:
            await client.close()
    finally:
        await first.stop()
        await second.stop()


@pytest.mark.asyncio
async def test_rate_limit_returns_error_for_messages_over_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "2")
    instance = NotificationServer(port=0, redis_url="redis://127.0.0.1:1")
    await instance.start()
    websocket = await websockets.connect(f"ws://127.0.0.1:{instance.port}?client_id=limited-client")
    try:
        await websocket.send(json.dumps({"type": "broadcast", "payload": {"number": 1}}))
        await websocket.recv()
        await websocket.send(json.dumps({"type": "broadcast", "payload": {"number": 2}}))
        await websocket.recv()
        await websocket.send(json.dumps({"type": "broadcast", "payload": {"number": 3}}))
        error = await asyncio.wait_for(receive_message(websocket), 1)
        assert error["type"] == "error"
        assert error["payload"] == {"error": "rate limit exceeded"}
    finally:
        await websocket.close()
        await instance.stop()


@pytest.mark.asyncio
async def test_history_filters_by_channel_and_since(tmp_path: Path):
    instance = NotificationServer(port=0, database_url=str(tmp_path / "history.db"), redis_url="redis://127.0.0.1:1")
    await instance.start()
    try:
        await instance.broadcast({"channel": "history", "text": "first"})
        first_timestamp = (await instance.store.history("history", None, 10))[0][0]["timestamp"]
        await instance.broadcast({"channel": "history", "text": "second"})
        await instance.broadcast({"channel": "other", "text": "ignored"})

        def request():
            with urlopen(
                f"http://127.0.0.1:{instance.port}/history?channel=history&since={first_timestamp}&limit=1"
            ) as response:
                return response.status, json.loads(response.read())

        status, body = await asyncio.to_thread(request)
        assert status == 200
        assert [message["payload"]["text"] for message in body["messages"]] == ["second"]
        assert body["has_more"] is False
    finally:
        await instance.stop()
