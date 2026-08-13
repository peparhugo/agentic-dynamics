import asyncio
import json

import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

import app
from app import NotificationServer


@pytest.fixture
async def notification_server():
    server = NotificationServer()
    async with serve(
        server.websocket_handler,
        "127.0.0.1",
        0,
        process_request=server.health_response,
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        yield server, f"ws://127.0.0.1:{port}", port


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
    status, body = response.split(b"\r\n\r\n", 1)
    return status, json.loads(body)


async def test_connect_assigns_unique_client_ids(notification_server):
    _, url, _ = notification_server
    async with connect(url) as first, connect(url) as second:
        first_welcome = await receive_json(first)
        second_welcome = await receive_json(second)

    assert first_welcome["type"] == "system"
    assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
    assert isinstance(first_welcome["timestamp"], str)


async def test_broadcast_reaches_all_connected_clients(notification_server):
    _, url, _ = notification_server
    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "2026-01-01T00:00:00+00:00"}
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        await receive_json(recipient)
        await sender.send(json.dumps(message))

        assert await receive_json(sender) == message
        assert await receive_json(recipient) == message


async def test_direct_message_reaches_only_target_client(notification_server):
    _, url, _ = notification_server
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        recipient_id = (await receive_json(recipient))["payload"]["client_id"]
        message = {
            "type": "direct",
            "payload": {"client_id": recipient_id, "text": "private"},
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        await sender.send(json.dumps(message))

        assert await receive_json(recipient) == message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(recipient.recv(), timeout=0.05)


async def test_disconnected_client_is_removed(notification_server):
    server, url, _ = notification_server
    async with connect(url) as websocket:
        await receive_json(websocket)
        assert server.client_count == 1

    for _ in range(10):
        if server.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert server.client_count == 0


async def test_health_reports_connected_client_count(notification_server):
    _, url, port = notification_server
    async with connect(url) as websocket:
        await receive_json(websocket)
        status, body = await get_json(port, "/health")

    assert b"200 OK" in status
    assert body == {"connected_clients": 1}


async def test_channel_message_reaches_only_subscribers(notification_server):
    _, url, _ = notification_server
    subscribe = {
        "type": "subscribe",
        "channel": "alerts",
        "payload": {},
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    message = {
        "type": "broadcast",
        "channel": "alerts",
        "payload": {"text": "warning"},
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    async with connect(url) as sender, connect(url) as subscriber, connect(url) as other:
        await receive_json(sender)
        await receive_json(subscriber)
        await receive_json(other)
        await subscriber.send(json.dumps(subscribe))
        await sender.send(json.dumps(message))

        assert await receive_json(subscriber) == message
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other.recv(), timeout=0.05)


async def test_client_can_subscribe_to_multiple_channels_and_unsubscribe(notification_server):
    _, url, _ = notification_server
    async with connect(url) as client:
        await receive_json(client)
        for message_type, channel in [
            ("subscribe", "alerts"),
            ("subscribe", "system"),
            ("unsubscribe", "alerts"),
        ]:
            await client.send(
                json.dumps(
                    {
                        "type": message_type,
                        "channel": channel,
                        "payload": {},
                        "timestamp": "2026-01-01T00:00:00+00:00",
                    }
                )
            )

        await client.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {},
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            )
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(client.recv(), timeout=0.05)

        system_message = {
            "type": "broadcast",
            "channel": "system",
            "payload": {},
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        await client.send(json.dumps(system_message))
        assert await receive_json(client) == system_message


async def test_channel_endpoints_list_active_channels_and_subscribers(notification_server):
    _, url, port = notification_server
    subscribe = {
        "type": "subscribe",
        "channel": "alerts",
        "payload": {},
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    async with connect(url) as first, connect(url) as second:
        first_id = (await receive_json(first))["payload"]["client_id"]
        second_id = (await receive_json(second))["payload"]["client_id"]
        await first.send(json.dumps(subscribe))
        await second.send(json.dumps(subscribe))
        await asyncio.sleep(0)

        status, channels = await get_json(port, "/channels")
        subscriber_status, subscribers = await get_json(port, "/channels/alerts/subscribers")

    assert b"200 OK" in status
    assert channels == {"channels": [{"name": "alerts", "subscriber_count": 2}]}
    assert b"200 OK" in subscriber_status
    assert subscribers == {"subscribers": sorted([first_id, second_id])}


async def test_messages_endpoint_persists_message_history(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    server = NotificationServer(database_url=database_url)
    async with serve(
        server.websocket_handler,
        "127.0.0.1",
        0,
        process_request=server.health_response,
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        message = {
            "type": "broadcast",
            "payload": {"text": "stored"},
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        async with connect(f"ws://127.0.0.1:{port}") as websocket:
            await receive_json(websocket)
            await websocket.send(json.dumps(message))
            assert await receive_json(websocket) == message
        status, body = await get_json(port, "/messages?limit=50&offset=0")

    await server.close()
    assert b"200 OK" in status
    assert body == {
        "messages": [
            {
                "id": 1,
                "channel": None,
                "type": "broadcast",
                "payload": {"text": "stored"},
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        ]
    }


async def test_history_returns_channel_messages_in_chronological_pages(tmp_path):
    server = NotificationServer(database_url=f"sqlite:///{tmp_path / 'history.db'}")
    async with serve(
        server.websocket_handler,
        "127.0.0.1",
        0,
        process_request=server.health_response,
    ) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as websocket:
            await receive_json(websocket)
            await websocket.send(json.dumps({
                "type": "subscribe",
                "channel": "alerts",
                "payload": {},
                "timestamp": "2026-01-01T00:00:00+00:00",
            }))
            await asyncio.sleep(0)
            for timestamp, text in [
                ("2026-01-01T00:00:02+00:00", "second"),
                ("2026-01-01T00:00:01+00:00", "first"),
                ("2026-01-01T00:00:03+00:00", "third"),
            ]:
                await websocket.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": text}, "timestamp": timestamp}))
                assert (await receive_json(websocket))["payload"]["text"] == text

        status, first_page = await get_json(port, "/history?channel=alerts&since=2026-01-01T00:00:00%2B00:00&limit=2")
        _, second_page = await get_json(port, "/history?channel=alerts&since=2026-01-01T00:00:00%2B00:00&limit=2&offset=2")

    await server.close()
    assert b"200 OK" in status
    assert [message["payload"]["text"] for message in first_page["messages"]] == ["first", "second"]
    assert first_page["has_more"] is True
    assert [message["payload"]["text"] for message in second_page["messages"]] == ["third"]
    assert second_page["has_more"] is False


async def test_rate_limit_uses_redis_counter_per_client(monkeypatch, tmp_path):
    redis_server = fakeredis.aioredis.FakeServer()
    monkeypatch.setenv("RATE_LIMIT", "2")
    monkeypatch.setattr(
        app.redis_async,
        "from_url",
        lambda *args, **kwargs: fakeredis.aioredis.FakeRedis(server=redis_server, decode_responses=True),
    )
    server = NotificationServer("redis://broker", f"sqlite:///{tmp_path / 'rate-limit.db'}")
    async with serve(server.websocket_handler, "127.0.0.1", 0) as websocket_server:
        port = websocket_server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as websocket:
            await receive_json(websocket)
            message = {"type": "broadcast", "payload": {}, "timestamp": "2026-01-01T00:00:00+00:00"}
            await websocket.send(json.dumps(message))
            assert await receive_json(websocket) == message
            await websocket.send(json.dumps(message))
            assert await receive_json(websocket) == message
            await websocket.send(json.dumps(message))
            response = await receive_json(websocket)

    await server.close()
    assert response["type"] == "system"
    assert response["payload"] == {"error": "rate limit exceeded"}


async def test_redis_pubsub_delivers_between_server_instances(monkeypatch, tmp_path):
    redis_server = fakeredis.aioredis.FakeServer()
    monkeypatch.setattr(
        app.redis_async,
        "from_url",
        lambda *args, **kwargs: fakeredis.aioredis.FakeRedis(server=redis_server, decode_responses=True),
    )
    first = NotificationServer("redis://broker", f"sqlite:///{tmp_path / 'first.db'}")
    second = NotificationServer("redis://broker", f"sqlite:///{tmp_path / 'second.db'}")
    async with serve(first.websocket_handler, "127.0.0.1", 0) as first_ws, serve(
        second.websocket_handler, "127.0.0.1", 0
    ) as second_ws:
        first_port = first_ws.sockets[0].getsockname()[1]
        second_port = second_ws.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{first_port}") as sender, connect(
            f"ws://127.0.0.1:{second_port}"
        ) as recipient:
            await receive_json(sender)
            recipient_id = (await receive_json(recipient))["payload"]["client_id"]
            message = {
                "type": "direct",
                "payload": {"client_id": recipient_id, "text": "cross-instance"},
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
            await sender.send(json.dumps(message))
            assert await asyncio.wait_for(receive_json(recipient), timeout=1) == message

    await first.close()
    await second.close()
