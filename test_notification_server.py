import asyncio
import json
import os

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


async def http_json(server: NotificationServer, path: str) -> tuple[str, dict]:
    reader, writer = await asyncio.open_connection("127.0.0.1", server.http_port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    status = response.split(b"\r\n", 1)[0].decode()
    return status, json.loads(response.split(b"\r\n\r\n", 1)[1])


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


@pytest.mark.asyncio
async def test_channel_broadcast_only_reaches_subscribers(server):
    subscribed = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    other = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    try:
        await asyncio.gather(subscribed.recv(), other.recv())
        await subscribed.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
        for _ in range(20):
            if "alerts" in server.channels:
                break
            await asyncio.sleep(0.01)
        await server.broadcast({"text": "warning"}, channel="alerts")
        received = json.loads(await subscribed.recv())
        assert received["channel"] == "alerts"
        assert received["payload"] == {"text": "warning"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other.recv(), timeout=0.05)
    finally:
        await subscribed.close()
        await other.close()


@pytest.mark.asyncio
async def test_subscriptions_are_dynamic_and_exposed_over_http(server):
    client = await websockets.connect(f"ws://127.0.0.1:{server.websocket_port}")
    try:
        client_id = json.loads(await client.recv())["payload"]["client_id"]
        await client.send(json.dumps({
            "type": "subscribe", "payload": {"channel": "system"},
        }))
        for _ in range(20):
            if "system" in server.channels:
                break
            await asyncio.sleep(0.01)
        status, listing = await http_json(server, "/channels")
        assert status == "HTTP/1.1 200 OK"
        assert listing == {"channels": [{"name": "system", "subscriber_count": 1}]}
        status, subscribers = await http_json(server, "/channels/system/subscribers")
        assert status == "HTTP/1.1 200 OK"
        assert subscribers == {"channel": "system", "subscribers": [client_id]}

        await client.send(json.dumps({"type": "unsubscribe", "channel": "system", "payload": {}}))
        for _ in range(20):
            if "system" not in server.channels:
                break
            await asyncio.sleep(0.01)
        status, listing = await http_json(server, "/channels")
        assert status == "HTTP/1.1 200 OK"
        assert listing == {"channels": []}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path):
    instance = NotificationServer(websocket_port=0, http_port=0,
                                  database_url=str(tmp_path / "messages.sqlite"),
                                  redis_url="redis://127.0.0.1:6399/0")
    await instance.start()
    try:
        await instance.broadcast({"text": "one"}, channel="alerts")
        await instance.broadcast({"text": "two"})
        status, response = await http_json(instance, "/messages?limit=1&offset=1")
        assert status == "HTTP/1.1 200 OK"
        assert len(response["messages"]) == 1
        assert response["messages"][0]["payload"] == {"text": "two"}
        assert response["messages"][0]["channel"] is None
    finally:
        await instance.stop()


@pytest.mark.asyncio
async def test_servers_share_redis_pubsub(tmp_path):
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    first = NotificationServer(websocket_port=0, http_port=0,
                               redis_url=redis_url,
                               database_url=str(tmp_path / "first.sqlite"))
    second = NotificationServer(websocket_port=0, http_port=0,
                                redis_url=redis_url,
                                database_url=str(tmp_path / "second.sqlite"))
    await first.start()
    await second.start()
    if first._redis is None or second._redis is None:
        await first.stop()
        await second.stop()
        pytest.skip("Redis is not available")
    client = await websockets.connect(f"ws://127.0.0.1:{second.websocket_port}")
    try:
        await client.recv()
        await first.broadcast({"text": "from another server"})
        received = json.loads(await asyncio.wait_for(client.recv(), timeout=1))
        assert received["payload"] == {"text": "from another server"}
    finally:
        await client.close()
        await first.stop()
        await second.stop()
