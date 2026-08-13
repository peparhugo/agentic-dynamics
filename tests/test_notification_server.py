import asyncio
import json

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer, RedisBroker, SQLiteMessageStore, create_process_request


@pytest.fixture
async def notification_server():
    server = NotificationServer()
    async with serve(
        server.handler,
        "127.0.0.1",
        0,
        process_request=create_process_request(server),
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield server, f"ws://127.0.0.1:{port}"


async def connected_client(uri: str):
    client = await connect(uri)
    connected = json.loads(await client.recv())
    return client, connected["payload"]["client_id"]


async def test_assigns_unique_client_ids_and_removes_disconnected_clients(notification_server):
    server, uri = notification_server
    first, first_id = await connected_client(uri)
    second, second_id = await connected_client(uri)

    assert first_id != second_id
    assert server.client_count == 2

    await first.close()
    for _ in range(10):
        if server.client_count == 1:
            break
        await asyncio.sleep(0.01)
    assert server.client_count == 1
    await second.close()


async def test_broadcast_reaches_all_connected_clients(notification_server):
    _, uri = notification_server
    first, _ = await connected_client(uri)
    second, _ = await connected_client(uri)
    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "client-time"}

    await first.send(json.dumps(message))
    received = [json.loads(await first.recv()), json.loads(await second.recv())]

    assert all(item["type"] == "broadcast" for item in received)
    assert all(item["payload"] == {"text": "hello"} for item in received)
    assert all(item["timestamp"] != "client-time" for item in received)
    await first.close()
    await second.close()


async def test_direct_message_reaches_only_requested_client(notification_server):
    _, uri = notification_server
    sender, _ = await connected_client(uri)
    recipient, recipient_id = await connected_client(uri)

    await sender.send(json.dumps({
        "type": "direct",
        "payload": {"client_id": recipient_id, "text": "private"},
        "timestamp": "client-time",
    }))

    received = json.loads(await recipient.recv())
    assert received["type"] == "direct"
    assert received["payload"]["text"] == "private"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)
    await sender.close()
    await recipient.close()


async def test_health_reports_connected_client_count(notification_server):
    _, uri = notification_server
    host_and_port = uri.removeprefix("ws://")
    client, _ = await connected_client(uri)

    host, port = host_and_port.split(":")
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = (await reader.read()).decode()
    writer.close()
    await writer.wait_closed()

    assert "200 OK" in response
    assert json.loads(response.split("\r\n\r\n", 1)[1]) == {"connected_clients": 1}
    await client.close()


async def get_json(host_and_port: str, path: str) -> tuple[str, object]:
    host, port = host_and_port.split(":")
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = (await reader.read()).decode()
    writer.close()
    await writer.wait_closed()
    status, body = response.split("\r\n\r\n", 1)
    return status, json.loads(body)


async def test_channel_messages_reach_only_subscribers(notification_server):
    _, uri = notification_server
    alerts_client, _ = await connected_client(uri)
    system_client, _ = await connected_client(uri)
    unsubscribed_client, _ = await connected_client(uri)

    await alerts_client.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}, "timestamp": "client-time"}))
    await system_client.send(json.dumps({"type": "subscribe", "channel": "system", "payload": {}, "timestamp": "client-time"}))
    await alerts_client.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}, "timestamp": "client-time"}))

    assert json.loads(await alerts_client.recv())["payload"] == {"text": "warning"}
    for client in (system_client, unsubscribed_client):
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.recv(), timeout=0.05)
    await alerts_client.close()
    await system_client.close()
    await unsubscribed_client.close()


async def test_unsubscribe_removes_channel_and_channel_endpoints_report_subscribers(notification_server):
    _, uri = notification_server
    host_and_port = uri.removeprefix("ws://")
    first, first_id = await connected_client(uri)
    second, second_id = await connected_client(uri)

    for client in (first, second):
        await client.send(json.dumps({"type": "subscribe", "channel": "chat", "payload": {}, "timestamp": "client-time"}))
    status, channels = await get_json(host_and_port, "/channels")
    assert "200 OK" in status
    assert channels == {"chat": 2}
    _, subscribers = await get_json(host_and_port, "/channels/chat/subscribers")
    assert subscribers == sorted([first_id, second_id])

    await first.send(json.dumps({"type": "unsubscribe", "channel": "chat", "payload": {}, "timestamp": "client-time"}))
    _, subscribers = await get_json(host_and_port, "/channels/chat/subscribers")
    assert subscribers == [second_id]
    await second.close()
    for _ in range(10):
        _, channels = await get_json(host_and_port, "/channels")
        if channels == {}:
            break
        await asyncio.sleep(0.01)
    assert channels == {}
    await first.close()


async def test_messages_endpoint_returns_persisted_messages(tmp_path):
    store = SQLiteMessageStore(f"sqlite:///{tmp_path / 'messages.db'}")
    server = NotificationServer(message_store=store)
    async with serve(server.handler, "127.0.0.1", 0, process_request=create_process_request(server)) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        uri = f"ws://127.0.0.1:{port}"
        client, _ = await connected_client(uri)
        await client.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}, "timestamp": "client-time"}))
        await asyncio.sleep(0.01)
        await client.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "saved"}, "timestamp": "client-time"}))
        await client.recv()

        _, messages = await get_json(f"127.0.0.1:{port}", "/messages?limit=50&offset=0")
        assert len(messages) == 2
        broadcast = messages[0]
        assert broadcast["channel"] == "alerts"
        assert broadcast["type"] == "broadcast"
        assert broadcast["payload"] == {"text": "saved"}
        await client.close()
    await server.close()


async def test_history_returns_channel_messages_since_timestamp_in_order(tmp_path):
    store = SQLiteMessageStore(f"sqlite:///{tmp_path / 'messages.db'}")
    await store.save({"type": "broadcast", "channel": "alerts", "payload": {"text": "old"}, "timestamp": "2026-01-01T00:00:00+00:00"})
    await store.save({"type": "broadcast", "channel": "other", "payload": {"text": "other"}, "timestamp": "2026-01-02T00:00:00+00:00"})
    await store.save({"type": "broadcast", "channel": "alerts", "payload": {"text": "first"}, "timestamp": "2026-01-02T00:00:00+00:00"})
    await store.save({"type": "broadcast", "channel": "alerts", "payload": {"text": "second"}, "timestamp": "2026-01-03T00:00:00+00:00"})
    server = NotificationServer(message_store=store)
    async with serve(server.handler, "127.0.0.1", 0, process_request=create_process_request(server)) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        status, history = await get_json(
            f"127.0.0.1:{port}", "/history?channel=alerts&since=2026-01-02T00%3A00%3A00%2B00%3A00&limit=1"
        )

    assert "200 OK" in status
    assert history["has_more"] is True
    assert [message["payload"] for message in history["messages"]] == [{"text": "first"}]
    assert [message["timestamp"] for message in history["messages"]] == ["2026-01-02T00:00:00+00:00"]
    await server.close()


async def test_rate_limit_returns_error_without_dropping_message():
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    server = NotificationServer(broker=RedisBroker(redis))
    server._rate_limit = 2
    async with serve(server.handler, "127.0.0.1", 0) as websocket_server:
        uri = f"ws://127.0.0.1:{websocket_server.sockets[0].getsockname()[1]}"
        client, _ = await connected_client(uri)
        message = json.dumps({"type": "broadcast", "payload": {"text": "allowed"}, "timestamp": "client-time"})
        await client.send(message)
        assert json.loads(await client.recv())["payload"] == {"text": "allowed"}
        await client.send(message)
        assert json.loads(await client.recv())["payload"] == {"text": "allowed"}
        await client.send(message)
        error = json.loads(await client.recv())
        assert error["payload"] == {"event": "error", "detail": "rate limit exceeded"}
        await client.close()
    await server.close()


async def test_redis_pubsub_delivers_channel_messages_between_server_instances():
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    first_server = NotificationServer(broker=RedisBroker(redis))
    second_server = NotificationServer(broker=RedisBroker(redis))
    await first_server.start()
    await second_server.start()
    async with serve(first_server.handler, "127.0.0.1", 0) as first_websocket_server:
        async with serve(second_server.handler, "127.0.0.1", 0) as second_websocket_server:
            first_uri = f"ws://127.0.0.1:{first_websocket_server.sockets[0].getsockname()[1]}"
            second_uri = f"ws://127.0.0.1:{second_websocket_server.sockets[0].getsockname()[1]}"
            publisher, _ = await connected_client(first_uri)
            subscriber, _ = await connected_client(second_uri)
            await subscriber.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}, "timestamp": "client-time"}))
            await asyncio.sleep(0.01)
            await publisher.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "shared"}, "timestamp": "client-time"}))

            received = json.loads(await asyncio.wait_for(subscriber.recv(), timeout=1))
            assert received["payload"] == {"text": "shared"}
            await publisher.close()
            await subscriber.close()
    await first_server.close()
    await second_server.close()
