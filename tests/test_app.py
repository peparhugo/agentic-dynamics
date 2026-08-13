import asyncio
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import fakeredis.aioredis
import pytest
import websockets

from app import NotificationServer, close_async_resource


@pytest.fixture
async def running_server():
    notification_server = NotificationServer()
    websocket_server = await websockets.serve(
        notification_server.handler,
        "127.0.0.1",
        0,
        process_request=notification_server.process_request,
    )
    port = websocket_server.sockets[0].getsockname()[1]
    try:
        yield notification_server, f"ws://127.0.0.1:{port}", port
    finally:
        websocket_server.close()
        await websocket_server.wait_closed()
        await notification_server.close()


async def start_server(notification_server):
    websocket_server = await websockets.serve(
        notification_server.handler,
        "127.0.0.1",
        0,
        process_request=notification_server.process_request,
    )
    port = websocket_server.sockets[0].getsockname()[1]
    return websocket_server, f"ws://127.0.0.1:{port}", port


async def connect(uri):
    websocket = await websockets.connect(uri)
    welcome = json.loads(await websocket.recv())
    return websocket, welcome


async def wait_for_client_count(server, expected):
    deadline = asyncio.get_running_loop().time() + 1
    while server.clients.count != expected:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"client count did not reach {expected}")
        await asyncio.sleep(0.01)


async def fetch_json(port, path):
    def fetch():
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as response:
            return response.status, json.load(response)

    return await asyncio.to_thread(fetch)


@pytest.mark.asyncio
async def test_connect_assigns_unique_ids_and_disconnects_cleanly(running_server):
    server, uri, _ = running_server
    first, first_welcome = await connect(uri)
    second, second_welcome = await connect(uri)

    assert first_welcome["type"] == "system"
    assert first_welcome["payload"]["client_id"] != second_welcome["payload"]["client_id"]
    assert first_welcome["timestamp"].endswith("+00:00")
    assert server.clients.count == 2

    await first.close()
    await second.close()
    await wait_for_client_count(server, 0)
    assert server.clients.count == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_connected_clients(running_server):
    _, uri, _ = running_server
    first, _ = await connect(uri)
    second, _ = await connect(uri)

    await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    first_message, second_message = await asyncio.gather(first.recv(), second.recv())

    for raw in (first_message, second_message):
        message = json.loads(raw)
        assert message["type"] == "broadcast"
        assert message["payload"] == {"text": "hello"}
        assert isinstance(message["timestamp"], str)

    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_message_only_reaches_recipient(running_server):
    _, uri, _ = running_server
    sender, _ = await connect(uri)
    recipient, welcome = await connect(uri)

    await sender.send(
        json.dumps(
            {
                "type": "direct",
                "payload": {
                    "client_id": welcome["payload"]["client_id"],
                    "message": {"text": "private"},
                },
            }
        )
    )

    message = json.loads(await recipient.recv())
    assert message["type"] == "direct"
    assert message["payload"] == {"text": "private"}
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)

    await sender.close()
    await recipient.close()


@pytest.mark.asyncio
async def test_invalid_message_returns_system_error(running_server):
    _, uri, _ = running_server
    websocket, _ = await connect(uri)

    await websocket.send("not json")
    response = json.loads(await websocket.recv())

    assert response["type"] == "system"
    assert response["payload"] == {"error": "invalid JSON"}
    await websocket.close()


@pytest.mark.asyncio
async def test_health_returns_connected_client_count(running_server):
    _, uri, port = running_server
    websocket, _ = await connect(uri)

    def fetch_health():
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
            return response.status, json.load(response)

    status, body = await asyncio.to_thread(fetch_health)
    assert status == 200
    assert body == {"connected_clients": 1}
    await websocket.close()


@pytest.mark.asyncio
async def test_channel_broadcast_only_reaches_subscribers(running_server):
    _, uri, _ = running_server
    sender, _ = await connect(uri)
    alerts_client, _ = await connect(uri)
    other_client, _ = await connect(uri)

    await alerts_client.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await other_client.send(json.dumps({"type": "subscribe", "channel": "chat"}))
    await sender.send(
        json.dumps(
            {
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": "warning"},
            }
        )
    )

    message = json.loads(await alerts_client.recv())
    assert message["type"] == "broadcast"
    assert message["channel"] == "alerts"
    assert message["payload"] == {"text": "warning"}
    for websocket in (sender, other_client):
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(websocket.recv(), timeout=0.05)

    await sender.close()
    await alerts_client.close()
    await other_client.close()


@pytest.mark.asyncio
async def test_unsubscribe_stops_channel_delivery(running_server):
    _, uri, _ = running_server
    sender, _ = await connect(uri)
    subscriber, _ = await connect(uri)

    await subscriber.send(json.dumps({"type": "subscribe", "channel": "system"}))
    await subscriber.send(json.dumps({"type": "unsubscribe", "channel": "system"}))
    await sender.send(
        json.dumps(
            {"type": "broadcast", "channel": "system", "payload": {"ok": True}}
        )
    )

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(subscriber.recv(), timeout=0.05)
    await sender.close()
    await subscriber.close()


@pytest.mark.asyncio
async def test_client_can_subscribe_to_multiple_channels(running_server):
    _, uri, _ = running_server
    sender, _ = await connect(uri)
    subscriber, _ = await connect(uri)

    for channel in ("alerts", "chat"):
        await subscriber.send(json.dumps({"type": "subscribe", "channel": channel}))
        await sender.send(
            json.dumps(
                {"type": "broadcast", "channel": channel, "payload": {"value": channel}}
            )
        )

    messages = [json.loads(await subscriber.recv()) for _ in range(2)]
    assert [message["channel"] for message in messages] == ["alerts", "chat"]
    await sender.close()
    await subscriber.close()


@pytest.mark.asyncio
async def test_channels_endpoints_and_disconnect_cleanup(running_server):
    server, uri, port = running_server
    first, first_welcome = await connect(uri)
    second, second_welcome = await connect(uri)
    for websocket in (first, second):
        await websocket.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await second.send(json.dumps({"type": "subscribe", "channel": "chat"}))

    status, channels = await fetch_json(port, "/channels")
    assert status == 200
    assert channels == {"channels": {"alerts": 2, "chat": 1}}
    status, subscribers = await fetch_json(port, "/channels/alerts/subscribers")
    assert status == 200
    assert subscribers == {
        "channel": "alerts",
        "subscribers": sorted(
            [first_welcome["payload"]["client_id"], second_welcome["payload"]["client_id"]]
        ),
    }

    await second.close()
    await wait_for_client_count(server, 1)
    _, channels = await fetch_json(port, "/channels")
    assert channels == {"channels": {"alerts": 1}}
    await first.close()


@pytest.mark.asyncio
async def test_redis_pubsub_delivers_across_server_instances(tmp_path):
    redis_server = fakeredis.FakeServer()
    first_redis = fakeredis.aioredis.FakeRedis(
        server=redis_server, decode_responses=True
    )
    second_redis = fakeredis.aioredis.FakeRedis(
        server=redis_server, decode_responses=True
    )
    first_app = NotificationServer(
        redis_client=first_redis, database_url=str(tmp_path / "first.db")
    )
    second_app = NotificationServer(
        redis_client=second_redis, database_url=str(tmp_path / "second.db")
    )
    first_server, first_uri, _ = await start_server(first_app)
    second_server, second_uri, _ = await start_server(second_app)
    sender, _ = await connect(first_uri)
    recipient, _ = await connect(second_uri)

    try:
        await sender.send(
            json.dumps({"type": "broadcast", "payload": {"text": "shared"}})
        )
        sender_message, recipient_message = await asyncio.gather(
            sender.recv(), recipient.recv()
        )
        assert json.loads(sender_message)["payload"] == {"text": "shared"}
        assert json.loads(recipient_message)["payload"] == {"text": "shared"}
    finally:
        await sender.close()
        await recipient.close()
        first_server.close()
        second_server.close()
        await first_server.wait_closed()
        await second_server.wait_closed()
        await first_app.close()
        await second_app.close()
        await close_async_resource(first_redis)
        await close_async_resource(second_redis)


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path):
    database = tmp_path / "messages.db"
    app = NotificationServer(database_url=f"sqlite:///{database}")
    websocket_server, uri, port = await start_server(app)
    websocket, _ = await connect(uri)

    try:
        await websocket.send(json.dumps({"type": "subscribe", "channel": "history"}))
        for value in (1, 2):
            await websocket.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "history",
                        "payload": {"value": value},
                    }
                )
            )
            await websocket.recv()

        status, body = await fetch_json(port, "/messages?limit=1&offset=1")
        assert status == 200
        assert len(body["messages"]) == 1
        assert body["messages"][0]["channel"] == "history"
        assert body["messages"][0]["type"] == "broadcast"
        assert body["messages"][0]["payload"] == {"value": 2}
        assert body["messages"][0]["timestamp"].endswith("+00:00")
    finally:
        await websocket.close()
        websocket_server.close()
        await websocket_server.wait_closed()
        await app.close()

    reopened = NotificationServer(database_url=str(database))
    assert [message["payload"] for message in reopened.messages.list(50, 0)] == [
        {"value": 1},
        {"value": 2},
    ]
    await reopened.close()


@pytest.mark.asyncio
async def test_rate_limit_returns_error_and_keeps_connection_open(tmp_path):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app = NotificationServer(
        redis_client=redis,
        database_url=str(tmp_path / "rate-limit.db"),
        rate_limit=2,
    )
    websocket_server, uri, _ = await start_server(app)
    websocket, _ = await connect(uri)

    try:
        for value in (1, 2):
            await websocket.send(
                json.dumps({"type": "broadcast", "payload": {"value": value}})
            )
            assert json.loads(await websocket.recv())["payload"] == {"value": value}

        await websocket.send(
            json.dumps({"type": "broadcast", "payload": {"value": 3}})
        )
        error = json.loads(await websocket.recv())
        assert error["type"] == "system"
        assert error["payload"] == {"error": "rate limit exceeded"}
        assert websocket.state.name == "OPEN"
    finally:
        await websocket.close()
        websocket_server.close()
        await websocket_server.wait_closed()
        await app.close()
        await close_async_resource(redis)


@pytest.mark.asyncio
async def test_history_filters_orders_and_paginates(tmp_path):
    app = NotificationServer(database_url=str(tmp_path / "history.db"))
    websocket_server, _, port = await start_server(app)
    now = datetime.now(timezone.utc)
    timestamps = [
        (now - timedelta(minutes=3)).isoformat(),
        (now - timedelta(minutes=2)).isoformat(),
        (now - timedelta(minutes=1)).isoformat(),
    ]
    app.messages.add(
        {
            "type": "broadcast",
            "channel": "other",
            "payload": {"value": 0},
            "timestamp": timestamps[0],
        }
    )
    for value, timestamp in zip((1, 2, 3), timestamps):
        app.messages.add(
            {
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"value": value},
                "timestamp": timestamp,
            }
        )

    try:
        since = quote((now - timedelta(minutes=2, seconds=30)).isoformat())
        status, first_page = await fetch_json(
            port, f"/history?channel=alerts&since={since}&limit=1"
        )
        assert status == 200
        assert [message["payload"] for message in first_page["messages"]] == [
            {"value": 2}
        ]
        assert first_page["has_more"] is True

        status, full_page = await fetch_json(
            port, f"/history?channel=alerts&since={since}&limit=50"
        )
        assert status == 200
        assert [message["payload"] for message in full_page["messages"]] == [
            {"value": 2},
            {"value": 3},
        ]
        assert full_page["has_more"] is False
    finally:
        websocket_server.close()
        await websocket_server.wait_closed()
        await app.close()
