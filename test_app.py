import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from app import MemoryBroker, NotificationServer


@pytest_asyncio.fixture
async def notification_server():
    application = NotificationServer()
    async with application.create_server(port=0) as server:
        port = server.sockets[0].getsockname()[1]
        yield application, f"ws://127.0.0.1:{port}"


async def receive_json(connection):
    return json.loads(await connection.recv())


async def get_json(address, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", int(address.rsplit(":", 1)[1]))
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response, json.loads(response.split(b"\r\n\r\n", 1)[1])


@pytest.mark.asyncio
async def test_connect_assigns_unique_client_ids_and_health_reports_count(notification_server):
    _, address = notification_server
    async with connect(address) as first, connect(address) as second:
        first_welcome, second_welcome = await asyncio.gather(receive_json(first), receive_json(second))

        assert first_welcome["type"] == second_welcome["type"] == "system"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]

        reader, writer = await asyncio.open_connection("127.0.0.1", int(address.rsplit(":", 1)[1]))
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
        assert b"200 OK" in response
        assert b'{"connected_clients": 2}' in response


@pytest.mark.asyncio
async def test_broadcast_reaches_all_connected_clients(notification_server):
    _, address = notification_server
    async with connect(address) as sender, connect(address) as recipient:
        await receive_json(sender)
        await receive_json(recipient)
        await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "ignored"}))

        received = await asyncio.gather(receive_json(sender), receive_json(recipient))
        assert all(message["type"] == "broadcast" for message in received)
        assert all(message["payload"] == {"text": "hello"} for message in received)
        assert all(isinstance(message["timestamp"], str) for message in received)


@pytest.mark.asyncio
async def test_direct_message_and_disconnect_cleanup(notification_server):
    application, address = notification_server
    async with connect(address) as sender, connect(address) as recipient:
        await receive_json(sender)
        recipient_welcome = await receive_json(recipient)
        recipient_id = recipient_welcome["payload"]["client_id"]
        await sender.send(json.dumps({"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}}))
        message = await receive_json(recipient)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "private"

    for _ in range(10):
        if await application.clients.count() == 0:
            break
        await asyncio.sleep(0.01)
    assert await application.clients.count() == 0


@pytest.mark.asyncio
async def test_invalid_message_returns_system_error(notification_server):
    _, address = notification_server
    async with connect(address) as client:
        await receive_json(client)
        await client.send("not json")
        error = await receive_json(client)
        assert error["type"] == "system"
        assert error["payload"] == {"error": "message must be valid JSON"}


@pytest.mark.asyncio
async def test_channel_messages_only_reach_subscribers_and_unsubscribe(notification_server):
    _, address = notification_server
    async with connect(address) as sender, connect(address) as subscriber, connect(address) as other:
        await asyncio.gather(receive_json(sender), receive_json(subscriber), receive_json(other))
        await subscriber.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
        await sender.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "warning"}}))
        received = await receive_json(subscriber)
        assert received["channel"] == "alerts"
        assert received["payload"] == {"text": "warning"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other.recv(), timeout=0.05)

        await subscriber.send(json.dumps({"type": "unsubscribe", "channel": "alerts", "payload": {}}))
        await sender.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {}}))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(subscriber.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_channel_endpoints_report_active_subscriptions(notification_server):
    _, address = notification_server
    async with connect(address) as first, connect(address) as second:
        first_welcome, second_welcome = await asyncio.gather(receive_json(first), receive_json(second))
        await first.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
        await second.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))

        response, channels = await get_json(address, "/channels")
        assert b"200 OK" in response
        assert channels == {"channels": [{"name": "alerts", "subscriber_count": 2}]}

        response, subscribers = await get_json(address, "/channels/alerts/subscribers")
        assert b"200 OK" in response
        assert set(subscribers["subscribers"]) == {
            first_welcome["payload"]["client_id"],
            second_welcome["payload"]["client_id"],
        }


@pytest.mark.asyncio
async def test_broker_distributes_messages_between_server_instances(tmp_path):
    broker = MemoryBroker()
    first_app = NotificationServer(broker=broker, database_url=str(tmp_path / "first.db"))
    second_app = NotificationServer(broker=broker, database_url=str(tmp_path / "second.db"))
    async with first_app.create_server(port=0) as first_server, second_app.create_server(port=0) as second_server:
        first_address = f"ws://127.0.0.1:{first_server.sockets[0].getsockname()[1]}"
        second_address = f"ws://127.0.0.1:{second_server.sockets[0].getsockname()[1]}"
        async with connect(first_address) as sender, connect(second_address) as recipient:
            await asyncio.gather(receive_json(sender), receive_json(recipient))
            await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "shared"}}))
            assert (await receive_json(recipient))["payload"] == {"text": "shared"}


@pytest.mark.asyncio
async def test_messages_endpoint_returns_persisted_history(tmp_path):
    application = NotificationServer(database_url=str(tmp_path / "messages.db"))
    async with application.create_server(port=0) as server:
        address = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
        async with connect(address) as client:
            await receive_json(client)
            await client.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
            await client.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "first"}}))
            await receive_json(client)
            await client.send(json.dumps({"type": "broadcast", "payload": {"text": "second"}}))
            await receive_json(client)

        response, history = await get_json(address, "/messages?limit=1&offset=0")
        assert b"200 OK" in response
        assert history["messages"][0]["payload"] == {"text": "second"}
        assert history["messages"][0]["channel"] is None

        _, history = await get_json(address, "/messages?limit=1&offset=1")
        assert history["messages"][0]["channel"] == "alerts"
        assert history["messages"][0]["payload"] == {"text": "first"}


@pytest.mark.asyncio
async def test_rate_limit_returns_error_without_dropping_connection(tmp_path):
    application = NotificationServer(database_url=str(tmp_path / "messages.db"), rate_limit=2)
    async with application.create_server(port=0) as server:
        address = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
        async with connect(address) as client:
            await receive_json(client)
            for number in range(2):
                await client.send(json.dumps({"type": "broadcast", "payload": {"number": number}}))
                assert (await receive_json(client))["payload"] == {"number": number}

            await client.send(json.dumps({"type": "broadcast", "payload": {"number": 3}}))
            assert (await receive_json(client))["payload"] == {"error": "rate limit exceeded"}

            await client.send("not json")
            assert (await receive_json(client))["payload"] == {"error": "message must be valid JSON"}


@pytest.mark.asyncio
async def test_history_returns_chronological_channel_messages_with_pagination(tmp_path):
    application = NotificationServer(database_url=str(tmp_path / "messages.db"))
    async with application.create_server(port=0) as server:
        address = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
        since = datetime.now(timezone.utc).isoformat()
        async with connect(address) as client:
            await receive_json(client)
            await client.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
            for text in ("first", "second", "third"):
                await client.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": text}}))
                await receive_json(client)
            await client.send(json.dumps({"type": "broadcast", "channel": "other", "payload": {"text": "ignored"}}))

        query = urlencode({"channel": "alerts", "since": since, "limit": 2})
        response, history = await get_json(address, f"/history?{query}")
        assert b"200 OK" in response
        assert [message["payload"]["text"] for message in history["messages"]] == ["first", "second"]
        assert history["has_more"] is True

        response, history = await get_json(address, f"/history?{query}&offset=2")
        assert b"200 OK" in response
        assert [message["payload"]["text"] for message in history["messages"]] == ["third"]
        assert history["has_more"] is False


@pytest.mark.asyncio
async def test_startup_removes_messages_older_than_configured_ttl(tmp_path):
    database_url = str(tmp_path / "messages.db")
    application = NotificationServer(database_url=database_url, message_ttl_days=7)
    old_message = application.message("broadcast", {"text": "old"})
    old_message["timestamp"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    await application.messages.add(old_message)
    await application.start()
    assert await application.messages.list(10, 0) == []
    await application.close()
