import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from app import BaseTransport, NotificationServer, WebSocketTransport


class FakeRedis:
    """Small shared async Redis double exercising pub/sub and hash state."""

    def __init__(self):
        self.hashes = {}
        self.subscribers = {}

    def pubsub(self):
        return FakePubSub(self)

    async def publish(self, channel, data):
        for subscriber in list(self.subscribers.get(channel, [])):
            await subscriber.messages.put({"data": data})

    async def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value

    async def hdel(self, key, field):
        self.hashes.get(key, {}).pop(field, None)

    async def hexists(self, key, field):
        return field in self.hashes.get(key, {})

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)


class FakePubSub:
    def __init__(self, broker):
        self.broker = broker
        self.channels = set()
        self.messages = asyncio.Queue()

    async def subscribe(self, channel):
        self.channels.add(channel)
        self.broker.subscribers.setdefault(channel, []).append(self)

    async def get_message(self, ignore_subscribe_messages=True, timeout=0):
        try:
            return await asyncio.wait_for(self.messages.get(), timeout)
        except asyncio.TimeoutError:
            return None

    async def aclose(self):
        for channel in self.channels:
            self.broker.subscribers[channel].remove(self)


@pytest.fixture
async def notification_server():
    server = NotificationServer()
    listener = await server.start(port=0)
    port = listener.sockets[0].getsockname()[1]
    yield server, f"ws://127.0.0.1:{port}"
    await server.stop()


async def receive_json(client):
    return json.loads(await client.recv())


async def get_json(port, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", int(port))
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b"200 OK" in headers
    return json.loads(body)


@pytest.mark.asyncio
async def test_connection_receives_unique_system_identifier(notification_server):
    server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)

        assert server.client_count == 2
        assert first_message["type"] == second_message["type"] == "system"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert "timestamp" in first_message


@pytest.mark.asyncio
async def test_broadcast_reaches_every_client(notification_server):
    _, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        await receive_json(first)
        await receive_json(second)
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

        messages = [await receive_json(first), await receive_json(second)]
        assert all(message["type"] == "broadcast" for message in messages)
        assert all(message["payload"] == {"text": "hello"} for message in messages)
        assert all("timestamp" in message for message in messages)


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(notification_server):
    _, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        await receive_json(first)
        target_id = (await receive_json(second))["payload"]["client_id"]
        payload = {"client_id": target_id, "text": "private"}
        await first.send(json.dumps({"type": "direct", "payload": payload}))

        message = await receive_json(second)
        assert message["type"] == "direct"
        assert message["payload"] == payload
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_disconnect_removes_client(notification_server):
    server, uri = notification_server
    client = await connect(uri)
    await receive_json(client)
    assert server.client_count == 1

    await client.close()
    for _ in range(20):
        if server.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.client_count == 0


@pytest.mark.asyncio
async def test_health_returns_connected_client_count(notification_server):
    _, uri = notification_server
    port = uri.rsplit(":", 1)[1]
    client = await connect(uri)
    await receive_json(client)

    reader, writer = await asyncio.open_connection("127.0.0.1", int(port))
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    await client.close()

    headers, body = response.split(b"\r\n\r\n", 1)
    assert b"200 OK" in headers
    assert json.loads(body) == {"connected_clients": 1}


@pytest.mark.asyncio
async def test_channel_messages_reach_only_subscribers(notification_server):
    server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second, connect(uri) as third:
        await receive_json(first)
        await receive_json(second)
        await receive_json(third)
        await first.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        await third.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        for _ in range(20):
            if {name: len(subscribers) for name, subscribers in server.channels.items()} == {
                "alerts": 2,
                "chat": 2,
            }:
                break
            await asyncio.sleep(0.01)
        assert {name: len(subscribers) for name, subscribers in server.channels.items()} == {
            "alerts": 2,
            "chat": 2,
        }

        await first.send(
            json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "urgent"}})
        )

        first_message = await receive_json(first)
        second_message = await receive_json(second)
        assert first_message["channel"] == second_message["channel"] == "alerts"
        assert first_message["payload"] == second_message["payload"] == {"text": "urgent"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(third.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_unsubscribe_and_channel_endpoints(notification_server):
    server, uri = notification_server
    port = uri.rsplit(":", 1)[1]
    async with connect(uri) as first, connect(uri) as second:
        first_id = (await receive_json(first))["payload"]["client_id"]
        second_id = (await receive_json(second))["payload"]["client_id"]
        await first.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await second.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        for _ in range(20):
            if len(server.channels.get("alerts", set())) == 2:
                break
            await asyncio.sleep(0.01)

        assert await get_json(port, "/channels") == {
            "channels": [{"name": "alerts", "subscriber_count": 2}]
        }
        assert await get_json(port, "/channels/alerts/subscribers") == {
            "channel": "alerts",
            "subscribers": sorted([first_id, second_id]),
        }

        await second.send(json.dumps({"type": "unsubscribe", "channel": "alerts"}))
        for _ in range(20):
            if len(server.channels.get("alerts", set())) == 1:
                break
            await asyncio.sleep(0.01)
        await first.send(
            json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "only first"}})
        )
        assert (await receive_json(first))["payload"] == {"text": "only first"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(second.recv(), timeout=0.05)
        assert await get_json(port, "/channels/alerts/subscribers") == {
            "channel": "alerts",
            "subscribers": [first_id],
        }


@pytest.mark.asyncio
async def test_messages_endpoint_persists_paginated_history(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    server = NotificationServer(database_url=database_url)
    listener = await server.start(port=0)
    port = listener.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}"
    try:
        async with connect(uri) as client:
            await receive_json(client)
            for text in ("one", "two", "three"):
                await client.send(json.dumps({"type": "broadcast", "payload": {"text": text}}))
                await receive_json(client)

            history = await get_json(port, "/messages?limit=2&offset=1")
            assert [message["payload"] for message in history["messages"]] == [
                {"text": "two"},
                {"text": "three"},
            ]
            assert all(message["id"] and message["timestamp"] for message in history["messages"])
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_between_server_instances_and_tracks_clients(tmp_path):
    broker = FakeRedis()
    first = NotificationServer(redis_client=broker, database_url=f"sqlite:///{tmp_path / 'first.db'}")
    second = NotificationServer(redis_client=broker, database_url=f"sqlite:///{tmp_path / 'second.db'}")
    first_listener = await first.start(port=0)
    second_listener = await second.start(port=0)
    first_uri = f"ws://127.0.0.1:{first_listener.sockets[0].getsockname()[1]}"
    second_uri = f"ws://127.0.0.1:{second_listener.sockets[0].getsockname()[1]}"
    try:
        async with connect(first_uri) as publisher, connect(second_uri) as subscriber:
            await receive_json(publisher)
            client_id = (await receive_json(subscriber))["payload"]["client_id"]
            await subscriber.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            for _ in range(20):
                state = await broker.hget("notifications:clients", client_id)
                if state == json.dumps({"channels": ["alerts"]}):
                    break
                await asyncio.sleep(0.01)
            assert json.loads(await broker.hget("notifications:clients", client_id)) == {"channels": ["alerts"]}

            await publisher.send(
                json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "shared"}})
            )
            message = await receive_json(subscriber)
            assert message["payload"] == {"text": "shared"}
            assert message["channel"] == "alerts"
    finally:
        await first.stop()
        await second.stop()


def test_websocket_is_the_default_transport(monkeypatch):
    monkeypatch.delenv("TRANSPORT", raising=False)
    assert isinstance(NotificationServer().transport, WebSocketTransport)


def test_transport_is_selected_from_configuration(monkeypatch):
    monkeypatch.setenv("TRANSPORT", "polling")
    with pytest.raises(ValueError, match="unsupported transport: polling"):
        NotificationServer()


class RecordingTransport(BaseTransport):
    def __init__(self):
        super().__init__()
        self.sent = []

    async def on_connect(self, client):
        pass

    async def on_disconnect(self, client):
        pass

    async def send_message(self, client, message):
        self.sent.append((client, message))

    async def broadcast(self, clients, message):
        for client in clients:
            await self.send_message(client, message)
        return []


@pytest.mark.asyncio
async def test_core_routes_messages_through_an_injected_transport():
    transport = RecordingTransport()
    server = NotificationServer(transport=transport)
    client = object()
    await server._on_connect(client)
    await server.broadcast({"text": "hello"})

    assert transport.server is server
    assert [message["type"] for _, message in transport.sent] == ["system", "broadcast"]
    await server.stop()
