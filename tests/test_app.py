import asyncio
import json

import pytest
from websockets.legacy.client import connect
from websockets.legacy.server import serve

from app import NotificationServer


@pytest.fixture
async def notification_server():
    server = NotificationServer(redis_url="memory://")
    async with serve(server.handler, "127.0.0.1", 0, process_request=server.health_response) as listener:
        port = listener.sockets[0].getsockname()[1]
        yield server, f"ws://127.0.0.1:{port}"


async def receive_json(client):
    return json.loads(await client.recv())


async def wait_for_client_count(server, expected_count):
    for _ in range(20):
        if server.client_count == expected_count:
            return
        await asyncio.sleep(0.01)
    assert server.client_count == expected_count


async def wait_for_channel_subscriber_count(server, channel, expected_count):
    for _ in range(20):
        if server.channels.get(channel) == expected_count:
            return
        await asyncio.sleep(0.01)
    assert server.channels.get(channel) == expected_count


async def test_connect_assigns_unique_client_ids_and_removes_disconnect(notification_server):
    server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        first_notice, second_notice = await asyncio.gather(receive_json(first), receive_json(second))
        assert first_notice["type"] == second_notice["type"] == "system"
        assert first_notice["payload"]["client_id"] != second_notice["payload"]["client_id"]
        assert server.client_count == 2

    await wait_for_client_count(server, 0)


async def test_broadcast_reaches_all_clients_with_standard_format(notification_server):
    _server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        await asyncio.gather(receive_json(first), receive_json(second))
        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        messages = await asyncio.gather(receive_json(first), receive_json(second))

    assert all(message["type"] == "broadcast" for message in messages)
    assert all(message["payload"] == {"text": "hello"} for message in messages)
    assert all("timestamp" in message for message in messages)


async def test_direct_message_reaches_only_its_recipient(notification_server):
    _server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        first_notice, second_notice = await asyncio.gather(receive_json(first), receive_json(second))
        recipient_id = second_notice["payload"]["client_id"]
        await first.send(json.dumps({"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}}))
        direct_message = await receive_json(second)
        assert direct_message["type"] == "direct"
        assert direct_message["payload"]["text"] == "private"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


async def test_health_endpoint_returns_connected_client_count(notification_server):
    _server, uri = notification_server
    host_and_port = uri.removeprefix("ws://")
    reader, writer = await asyncio.open_connection(*host_and_port.rsplit(":", 1))
    writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()

    assert b"200 OK" in response
    assert response.endswith(b'{"connected_clients": 0}')


async def get_json(uri, path):
    host, port = uri.removeprefix("ws://").rsplit(":", 1)
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


async def test_channel_messages_reach_only_subscribers(notification_server):
    _server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second, connect(uri) as third:
        await asyncio.gather(receive_json(first), receive_json(second), receive_json(third))
        await first.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await second.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await third.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await wait_for_channel_subscriber_count(_server, "alerts", 2)
        await first.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}}))
        messages = await asyncio.gather(receive_json(first), receive_json(second))

        assert all(message["channel"] == "alerts" for message in messages)
        assert all(message["payload"] == {"text": "warning"} for message in messages)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(third.recv(), timeout=0.05)


async def test_unsubscribe_stops_channel_delivery_and_channels_endpoints(notification_server):
    _server, uri = notification_server
    async with connect(uri) as first, connect(uri) as second:
        first_notice, second_notice = await asyncio.gather(receive_json(first), receive_json(second))
        first_id = first_notice["payload"]["client_id"]
        second_id = second_notice["payload"]["client_id"]
        await first.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await second.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await wait_for_channel_subscriber_count(_server, "alerts", 2)

        channels = await get_json(uri, "/channels")
        subscribers = await get_json(uri, "/channels/alerts/subscribers")
        assert channels.endswith(b'{"channels": {"alerts": 2}}')
        assert set(json.loads(subscribers.split(b"\r\n\r\n", 1)[1])["subscribers"]) == {first_id, second_id}

        await second.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        await wait_for_channel_subscriber_count(_server, "alerts", 1)
        await first.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}}))
        assert (await receive_json(first))["payload"]["text"] == "warning"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(second.recv(), timeout=0.05)


async def test_pubsub_delivers_channel_messages_between_server_instances():
    first_server = NotificationServer(redis_url="memory://")
    second_server = NotificationServer(redis_url="memory://")
    async with serve(first_server.handler, "127.0.0.1", 0) as first_listener, serve(
        second_server.handler, "127.0.0.1", 0
    ) as second_listener:
        first_port = first_listener.sockets[0].getsockname()[1]
        second_port = second_listener.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{first_port}") as subscriber, connect(
            f"ws://127.0.0.1:{second_port}"
        ) as publisher:
            await asyncio.gather(receive_json(subscriber), receive_json(publisher))
            await subscriber.send(json.dumps({"type": "subscribe", "payload": {"channel": "shared"}}))
            await wait_for_channel_subscriber_count(first_server, "shared", 1)
            await publisher.send(
                json.dumps({"type": "broadcast", "channel": "shared", "payload": {"text": "across servers"}})
            )
            assert (await receive_json(subscriber))["payload"] == {"text": "across servers"}


async def test_messages_endpoint_returns_sqlite_history(tmp_path):
    database = tmp_path / "messages.db"
    server = NotificationServer(redis_url="memory://", database_url=str(database))
    async with serve(server.handler, "127.0.0.1", 0, process_request=server.health_response) as listener:
        port = listener.sockets[0].getsockname()[1]
        uri = f"ws://127.0.0.1:{port}"
        async with connect(uri) as client:
            await receive_json(client)
            await client.send(json.dumps({"type": "broadcast", "payload": {"text": "saved"}}))
            await receive_json(client)

        response = await get_json(uri, "/messages?limit=1&offset=0")

    history = json.loads(response.split(b"\r\n\r\n", 1)[1])
    assert history["messages"][0]["type"] == "broadcast"
    assert history["messages"][0]["payload"] == {"text": "saved"}
    assert history["messages"][0]["channel"] is None


async def test_rate_limit_returns_error_for_client(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "2")
    server = NotificationServer(redis_url="memory://")
    async with serve(server.handler, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as client:
            await receive_json(client)
            for number in range(2):
                await client.send(json.dumps({"type": "broadcast", "payload": {"number": number}}))
                assert (await receive_json(client))["type"] == "broadcast"

            await client.send(json.dumps({"type": "broadcast", "payload": {"number": 3}}))
            error = await receive_json(client)

    await server.close()
    assert error["type"] == "system"
    assert error["payload"] == {"event": "error", "message": "rate limit exceeded"}


async def test_history_filters_channel_returns_chronological_pages(tmp_path):
    database = tmp_path / "history.db"
    server = NotificationServer(redis_url="memory://", database_url=str(database))
    async with serve(server.handler, "127.0.0.1", 0, process_request=server.health_response) as listener:
        port = listener.sockets[0].getsockname()[1]
        uri = f"ws://127.0.0.1:{port}"
        async with connect(uri) as client:
            await receive_json(client)
            for channel, text in (("alerts", "first"), ("other", "ignored"), ("alerts", "second")):
                await client.send(json.dumps({"type": "broadcast", "channel": channel, "payload": {"text": text}}))

        first_page = await get_json(uri, "/history?channel=alerts&limit=1")
        second_page = await get_json(uri, "/history?channel=alerts&limit=1&offset=1")

    await server.close()
    first_history = json.loads(first_page.split(b"\r\n\r\n", 1)[1])
    second_history = json.loads(second_page.split(b"\r\n\r\n", 1)[1])
    assert [message["payload"]["text"] for message in first_history["messages"]] == ["first"]
    assert first_history["has_more"] is True
    assert [message["payload"]["text"] for message in second_history["messages"]] == ["second"]
    assert second_history["has_more"] is False


async def test_startup_cleanup_removes_expired_messages(monkeypatch, tmp_path):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "1")
    server = NotificationServer(redis_url="memory://", database_url=str(tmp_path / "expiry.db"))
    server._store.save(
        {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "old"},
            "timestamp": "2000-01-01T00:00:00+00:00",
        }
    )

    await server.start()
    await asyncio.sleep(0)
    messages, has_more = server._store.history("alerts", None, 50, 0)
    await server.close()

    assert messages == []
    assert has_more is False
