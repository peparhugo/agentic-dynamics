import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from urllib.request import urlopen

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import MemoryBroker, MessageStore, NotificationServer


@pytest.fixture
async def notification_server():
    application = NotificationServer()
    async with serve(
        application.handler,
        "127.0.0.1",
        0,
        process_request=application.process_request,
    ) as server:
        port = server.sockets[0].getsockname()[1]
        yield application, f"ws://127.0.0.1:{port}", port


async def receive_json(websocket):
    return json.loads(await websocket.recv())


def fetch_health(port):
    with urlopen(f"http://127.0.0.1:{port}/health") as response:
        return json.loads(response.read())


def fetch_json(port, path):
    with urlopen(f"http://127.0.0.1:{port}{path}") as response:
        return json.loads(response.read())


async def start_application(application):
    await application.start()
    server = await serve(
        application.handler,
        "127.0.0.1",
        0,
        process_request=application.process_request,
    )
    return server, f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"


async def test_clients_receive_unique_ids_and_health_count(notification_server):
    application, url, port = notification_server
    async with connect(url) as first, connect(url) as second:
        first_connected = await receive_json(first)
        second_connected = await receive_json(second)

        assert first_connected["type"] == "system"
        assert first_connected["payload"]["client_id"] != second_connected["payload"]["client_id"]

        assert await asyncio.to_thread(fetch_health, port) == {"connected_clients": 2}
        assert application.client_count == 2


async def test_broadcast_reaches_all_clients(notification_server):
    _, url, _ = notification_server
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        await receive_json(recipient)

        await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        delivered = await asyncio.gather(receive_json(sender), receive_json(recipient))

        assert all(message["type"] == "broadcast" for message in delivered)
        assert all(message["payload"] == {"text": "hello"} for message in delivered)
        assert all(message["timestamp"] for message in delivered)


async def test_direct_message_and_disconnect_removal(notification_server):
    application, url, _ = notification_server
    async with connect(url) as sender, connect(url) as recipient:
        await receive_json(sender)
        recipient_connected = await receive_json(recipient)
        recipient_id = recipient_connected["payload"]["client_id"]

        await sender.send(json.dumps({"type": "direct", "payload": {"client_id": recipient_id, "text": "private"}}))
        assert (await receive_json(recipient))["payload"]["text"] == "private"

    for _ in range(20):
        if application.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert application.client_count == 0


async def test_channel_subscriptions_route_messages_and_are_listed(notification_server):
    _, url, port = notification_server
    async with connect(url) as sender, connect(url) as alerts_recipient, connect(url) as chat_recipient:
        await asyncio.gather(
            receive_json(sender), receive_json(alerts_recipient), receive_json(chat_recipient)
        )
        await alerts_recipient.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await chat_recipient.send(json.dumps({"type": "subscribe", "payload": {}, "channel": "chat"}))

        channels = await asyncio.to_thread(fetch_json, port, "/channels")
        assert channels == {
            "channels": [
                {"name": "alerts", "subscriber_count": 1},
                {"name": "chat", "subscriber_count": 1},
            ]
        }

        await sender.send(
            json.dumps({"type": "broadcast", "payload": {"text": "warning"}, "channel": "alerts"})
        )
        delivered = await receive_json(alerts_recipient)
        assert delivered["channel"] == "alerts"
        assert delivered["payload"] == {"text": "warning"}
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(chat_recipient.recv(), timeout=0.05)

        await alerts_recipient.send(json.dumps({"type": "unsubscribe", "payload": {}, "channel": "alerts"}))
        assert await asyncio.to_thread(fetch_json, port, "/channels/alerts/subscribers") == {
            "channel": "alerts",
            "subscribers": [],
        }


async def test_shared_broker_delivers_channel_messages_between_server_instances(tmp_path):
    broker = MemoryBroker()
    first = NotificationServer(broker=broker, store=MessageStore(str(tmp_path / "first.db")))
    second = NotificationServer(broker=broker, store=MessageStore(str(tmp_path / "second.db")))
    first_server, first_url = await start_application(first)
    second_server, second_url = await start_application(second)
    try:
        async with connect(first_url) as sender, connect(second_url) as recipient:
            await asyncio.gather(receive_json(sender), receive_json(recipient))
            await recipient.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await asyncio.sleep(0.01)
            await sender.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "shared"}}))
            assert (await receive_json(recipient))["payload"] == {"text": "shared"}
    finally:
        first_server.close()
        second_server.close()
        await first_server.wait_closed()
        await second_server.wait_closed()
        await first.close()
        await second.close()


async def test_messages_endpoint_returns_persisted_notifications(notification_server):
    _, url, port = notification_server
    async with connect(url) as sender:
        await receive_json(sender)
        await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "first"}}))
        await receive_json(sender)
        await sender.send(json.dumps({"type": "subscribe", "channel": "ops"}))
        await sender.send(json.dumps({"type": "system", "payload": {"event": "notice"}, "channel": "ops"}))
        await receive_json(sender)

        history = await asyncio.to_thread(fetch_json, port, "/messages?limit=1&offset=0")
        assert len(history["messages"]) == 1
        assert history["messages"][0]["channel"] == "ops"
        assert history["messages"][0]["payload"] == {"event": "notice"}

        previous = await asyncio.to_thread(fetch_json, port, "/messages?limit=1&offset=1")
        assert previous["messages"][0]["channel"] is None
        assert previous["messages"][0]["payload"] == {"text": "first"}


async def test_rate_limit_returns_error_without_publishing(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "2")
    application = NotificationServer()
    server, url = await start_application(application)
    try:
        async with connect(url) as sender:
            await receive_json(sender)
            for text in ("first", "second"):
                await sender.send(json.dumps({"type": "broadcast", "payload": {"text": text}}))
                assert (await receive_json(sender))["payload"] == {"text": text}

            await sender.send(json.dumps({"type": "broadcast", "payload": {"text": "blocked"}}))
            error = await receive_json(sender)
            assert error["type"] == "system"
            assert error["payload"] == {"event": "error", "message": "rate limit exceeded"}
    finally:
        server.close()
        await server.wait_closed()
        await application.close()


async def test_history_filters_channel_since_and_paginates(notification_server):
    _, url, port = notification_server
    since = datetime.now(timezone.utc)
    async with connect(url) as sender:
        await receive_json(sender)
        await sender.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        for text in ("first", "second", "third"):
            await sender.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": text}}))
            await receive_json(sender)
        await sender.send(json.dumps({"type": "broadcast", "channel": "other", "payload": {"text": "ignored"}}))

        query = f"/history?channel=alerts&since={quote(since.isoformat())}&limit=2"
        history = await asyncio.to_thread(fetch_json, port, query)
        assert [message["payload"]["text"] for message in history["messages"]] == ["first", "second"]
        assert history["has_more"] is True

        next_page = await asyncio.to_thread(fetch_json, port, f"{query}&offset=2")
        assert [message["payload"]["text"] for message in next_page["messages"]] == ["third"]
        assert next_page["has_more"] is False


async def test_startup_removes_expired_messages(tmp_path, monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "7")
    store = MessageStore(str(tmp_path / "messages.db"))
    store.save(
        {
            "type": "system",
            "payload": {"event": "old"},
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
        }
    )
    application = NotificationServer(store=store)
    await application.start()
    try:
        await asyncio.sleep(0.01)
        assert store.list(limit=50, offset=0) == []
    finally:
        await application.close()
