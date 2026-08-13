import asyncio
import json

import pytest
import fakeredis.aioredis
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import CLIENTS_KEY, NotificationServer


@pytest.fixture
async def notification_server():
    app = NotificationServer()
    server = await serve(app.handler, "127.0.0.1", 0, process_request=app.process_request)
    port = server.sockets[0].getsockname()[1]
    try:
        yield app, f"ws://127.0.0.1:{port}", port
    finally:
        server.close()
        await server.wait_closed()


async def receive_json(websocket):
    return json.loads(await websocket.recv())


async def get_json(port, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    headers, body = response.split(b"\r\n\r\n", 1)
    return headers, json.loads(body)


async def test_connections_receive_unique_client_ids(notification_server):
    _, url, _ = notification_server
    async with connect(url) as first, connect(url) as second:
        first_welcome, second_welcome = await receive_json(first), await receive_json(second)
        assert first_welcome["type"] == second_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
        assert isinstance(first_welcome["timestamp"], str)


async def test_broadcast_reaches_all_connected_clients(notification_server):
    _, url, _ = notification_server
    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "2026-01-01T00:00:00Z"}
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        await receive_json(recipient)
        await sender.send(json.dumps(message))
        assert await receive_json(sender) == message
        assert await receive_json(recipient) == message


async def test_direct_message_reaches_only_target(notification_server):
    _, url, _ = notification_server
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        recipient_id = (await receive_json(recipient))["payload"]["client_id"]
        message = {"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}, "timestamp": "2026-01-01T00:00:00Z"}
        await sender.send(json.dumps(message))
        assert await receive_json(recipient) == message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)


async def test_channel_messages_reach_only_subscribers(notification_server):
    _, url, _ = notification_server
    subscribe = {
        "type": "subscribe",
        "channel": "alerts",
        "payload": {},
        "timestamp": "2026-01-01T00:00:00Z",
    }
    message = {
        "type": "broadcast",
        "channel": "alerts",
        "payload": {"text": "warning"},
        "timestamp": "2026-01-01T00:00:00Z",
    }
    async with connect(url) as sender, connect(url) as subscriber, connect(url) as other:
        await receive_json(sender)
        await receive_json(subscriber)
        await receive_json(other)
        await subscriber.send(json.dumps(subscribe))
        await sender.send(json.dumps(message))
        assert await receive_json(subscriber) == message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other.recv(), timeout=0.05)


async def test_unsubscribe_stops_channel_delivery(notification_server):
    _, url, _ = notification_server
    async with connect(url) as client:
        await receive_json(client)
        for message_type in ("subscribe", "unsubscribe"):
            await client.send(
                json.dumps(
                    {
                        "type": message_type,
                        "channel": "chat",
                        "payload": {},
                        "timestamp": "2026-01-01T00:00:00Z",
                    }
                )
            )
        await client.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "chat",
                    "payload": {"text": "hello"},
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.recv(), timeout=0.05)


async def test_channel_endpoints_report_subscribers(notification_server):
    _, url, port = notification_server
    async with connect(url) as first, connect(url) as second:
        first_id = (await receive_json(first))["payload"]["client_id"]
        second_id = (await receive_json(second))["payload"]["client_id"]
        for websocket, channel in ((first, "alerts"), (second, "alerts"), (second, "chat")):
            await websocket.send(
                json.dumps(
                    {
                        "type": "subscribe",
                        "channel": channel,
                        "payload": {},
                        "timestamp": "2026-01-01T00:00:00Z",
                    }
                )
            )
        for _ in range(20):
            _, channels = await get_json(port, "/channels")
            if channels == {"channels": {"alerts": 2, "chat": 1}}:
                break
            await asyncio.sleep(0.01)
        assert channels == {"channels": {"alerts": 2, "chat": 1}}
        headers, subscribers = await get_json(port, "/channels/alerts/subscribers")
        assert b"200 OK" in headers
        assert subscribers == {"subscribers": sorted((first_id, second_id))}


async def test_disconnect_removes_client(notification_server):
    app, url, _ = notification_server
    websocket = await connect(url)
    await receive_json(websocket)
    assert app.client_count == 1
    await websocket.close()
    for _ in range(20):
        if app.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert app.client_count == 0


async def test_health_endpoint_returns_client_count(notification_server):
    _, url, port = notification_server
    async with connect(url) as websocket:
        await receive_json(websocket)
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b"200 OK" in headers
    assert json.loads(body) == {"connected_clients": 1}


async def test_redis_pubsub_delivers_between_server_instances(tmp_path):
    redis_server = fakeredis.aioredis.FakeServer()
    first_app = NotificationServer(
        redis_client=fakeredis.aioredis.FakeRedis(server=redis_server),
        database_url=str(tmp_path / "first.db"),
    )
    second_app = NotificationServer(
        redis_client=fakeredis.aioredis.FakeRedis(server=redis_server),
        database_url=str(tmp_path / "second.db"),
    )
    await first_app.start()
    await second_app.start()
    first_server = await serve(first_app.handler, "127.0.0.1", 0, process_request=first_app.process_request)
    second_server = await serve(second_app.handler, "127.0.0.1", 0, process_request=second_app.process_request)
    first_port = first_server.sockets[0].getsockname()[1]
    second_port = second_server.sockets[0].getsockname()[1]
    try:
        async with connect(f"ws://127.0.0.1:{first_port}") as sender, connect(f"ws://127.0.0.1:{second_port}") as recipient:
            await receive_json(sender)
            recipient_id = (await receive_json(recipient))["payload"]["client_id"]
            state = await second_app._broker._redis.hget(CLIENTS_KEY, recipient_id)
            assert state == second_app._instance_id.encode()
            message = {"type": "broadcast", "payload": {"text": "shared"}, "timestamp": "2026-01-01T00:00:00Z"}
            await sender.send(json.dumps(message))
            assert await receive_json(sender) == message
            assert await receive_json(recipient) == message
    finally:
        first_server.close()
        second_server.close()
        await first_server.wait_closed()
        await second_server.wait_closed()
        await first_app.close()
        await second_app.close()


async def test_messages_endpoint_returns_persisted_messages(tmp_path):
    app = NotificationServer(database_url=str(tmp_path / "messages.db"))
    server = await serve(app.handler, "127.0.0.1", 0, process_request=app.process_request)
    port = server.sockets[0].getsockname()[1]
    message = {"type": "broadcast", "payload": {"text": "saved"}, "timestamp": "2026-01-01T00:00:00Z"}
    try:
        async with connect(f"ws://127.0.0.1:{port}") as websocket:
            await receive_json(websocket)
            await websocket.send(json.dumps(message))
            assert await receive_json(websocket) == message
        _, body = await get_json(port, "/messages?limit=1&offset=0")
        assert body == {"messages": [{"id": 1, "channel": None, **message}]}
        _, body = await get_json(port, "/messages?limit=1&offset=1")
        assert body == {"messages": []}
    finally:
        server.close()
        await server.wait_closed()
        await app.close()


async def test_rate_limit_rejects_messages_after_client_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    app = NotificationServer()
    server = await serve(app.handler, "127.0.0.1", 0, process_request=app.process_request)
    port = server.sockets[0].getsockname()[1]
    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "2026-01-01T00:00:00Z"}
    try:
        async with connect(f"ws://127.0.0.1:{port}") as websocket:
            await receive_json(websocket)
            await websocket.send(json.dumps(message))
            assert await receive_json(websocket) == message
            await websocket.send(json.dumps(message))
            error = await receive_json(websocket)
            assert error["type"] == "system"
            assert error["payload"] == {"error": "rate limit exceeded"}
    finally:
        server.close()
        await server.wait_closed()
        await app.close()


async def test_history_filters_by_channel_since_and_paginates(tmp_path):
    app = NotificationServer(database_url=str(tmp_path / "history.db"))
    server = await serve(app.handler, "127.0.0.1", 0, process_request=app.process_request)
    port = server.sockets[0].getsockname()[1]
    messages = [
        {"type": "broadcast", "channel": "alerts", "payload": {"number": 1}, "timestamp": "2026-01-01T00:00:00Z"},
        {"type": "broadcast", "channel": "other", "payload": {"number": 2}, "timestamp": "2026-01-01T00:01:00Z"},
        {"type": "broadcast", "channel": "alerts", "payload": {"number": 3}, "timestamp": "2026-01-01T00:02:00Z"},
        {"type": "broadcast", "channel": "alerts", "payload": {"number": 4}, "timestamp": "2026-01-01T00:03:00Z"},
    ]
    try:
        for message in messages:
            await app.broadcast(message)
        _, body = await get_json(port, "/history?channel=alerts&since=2026-01-01T00:01:00Z&limit=1")
        assert body["has_more"] is True
        assert [message["payload"]["number"] for message in body["messages"]] == [3]
        _, body = await get_json(port, "/history?channel=alerts&since=2026-01-01T00:01:00Z&limit=1&offset=1")
        assert body["has_more"] is False
        assert [message["payload"]["number"] for message in body["messages"]] == [4]
    finally:
        server.close()
        await server.wait_closed()
        await app.close()
