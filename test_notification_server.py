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
