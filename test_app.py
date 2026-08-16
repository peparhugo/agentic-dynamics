import asyncio
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis, FakeServer
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import NotificationServer
from broker import RedisBroker
from storage import MessageStore


@pytest_asyncio.fixture
async def running_server():
    notifications = NotificationServer()
    try:
        async with serve(
            notifications.handler,
            "127.0.0.1",
            0,
            process_request=notifications.process_request,
        ) as websocket_server:
            port = websocket_server.sockets[0].getsockname()[1]
            yield notifications, port
    finally:
        await notifications.close()


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


def channel_message(message_type, channel):
    return {
        "type": message_type,
        "payload": {},
        "timestamp": "2026-08-16T00:00:00Z",
        "channel": channel,
    }


def assert_message_format(message):
    assert set(message) == {"type", "payload", "timestamp"}
    assert isinstance(message["type"], str)
    assert isinstance(message["payload"], dict)
    datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_connect_assigns_unique_ids_and_disconnects(running_server):
    notifications, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        first_message, second_message = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        assert first_message["payload"]["client_id"] != second_message["payload"][
            "client_id"
        ]
        assert len(notifications.registry) == 2
    await asyncio.sleep(0)
    assert len(notifications.registry) == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        await asyncio.gather(receive_json(first), receive_json(second))
        outgoing = {
            "type": "broadcast",
            "payload": {"text": "hello"},
            "timestamp": "2026-08-16T00:00:00Z",
        }
        await first.send(json.dumps(outgoing))
        assert await receive_json(first) == outgoing
        assert await receive_json(second) == outgoing


@pytest.mark.asyncio
async def test_direct_reaches_only_target(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        _, second_welcome = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        outgoing = {
            "type": "direct",
            "payload": {
                "client_id": second_welcome["payload"]["client_id"],
                "text": "private",
            },
            "timestamp": "2026-08-16T00:00:00Z",
        }
        await first.send(json.dumps(outgoing))
        assert await receive_json(second) == outgoing
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_invalid_message_returns_formatted_system_error(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send("not json")
        error = await receive_json(websocket)
        assert_message_format(error)
        assert error["type"] == "system"
        assert error["payload"]["event"] == "error"


@pytest.mark.asyncio
async def test_health_reports_connected_clients(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)

        def get_health():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
                return response.status, response.headers, json.load(response)

        status, headers, body = await asyncio.to_thread(get_health)
        assert status == 200
        assert headers.get_content_type() == "application/json"
        assert body == {"connected_clients": 1}


@pytest.mark.asyncio
async def test_channel_messages_reach_only_subscribers(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second, connect(f"ws://127.0.0.1:{port}") as third:
        await asyncio.gather(
            receive_json(first), receive_json(second), receive_json(third)
        )
        await first.send(json.dumps(channel_message("subscribe", "alerts")))
        await second.send(json.dumps(channel_message("subscribe", "alerts")))
        await asyncio.sleep(0.01)

        outgoing = channel_message("broadcast", "alerts")
        outgoing["payload"] = {"text": "channel only"}
        await first.send(json.dumps(outgoing))

        assert await receive_json(first) == outgoing
        assert await receive_json(second) == outgoing
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(third.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_unsubscribe_and_disconnect_remove_channel_membership(running_server):
    notifications, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        welcome = await receive_json(websocket)
        client_id = welcome["payload"]["client_id"]
        await websocket.send(json.dumps(channel_message("subscribe", "chat")))
        await asyncio.sleep(0.01)
        assert notifications.registry.subscribers("chat") == [client_id]

        await websocket.send(json.dumps(channel_message("unsubscribe", "chat")))
        await asyncio.sleep(0.01)
        assert notifications.registry.channels() == {}

        await websocket.send(json.dumps(channel_message("subscribe", "chat")))
        await asyncio.sleep(0.01)
    await asyncio.sleep(0)
    assert notifications.registry.channels() == {}


@pytest.mark.asyncio
async def test_channel_rest_endpoints(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        first_welcome, second_welcome = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        await first.send(json.dumps(channel_message("subscribe", "system alerts")))
        await second.send(json.dumps(channel_message("subscribe", "system alerts")))
        await asyncio.sleep(0.01)

        def get_json(path):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as response:
                return response.status, response.headers.get_content_type(), json.load(response)

        channels = await asyncio.to_thread(get_json, "/channels")
        subscribers = await asyncio.to_thread(
            get_json, "/channels/system%20alerts/subscribers"
        )

        assert channels == (200, "application/json", {"channels": {"system alerts": 2}})
        assert subscribers == (
            200,
            "application/json",
            {
                "channel": "system alerts",
                "subscribers": sorted(
                    [
                        first_welcome["payload"]["client_id"],
                        second_welcome["payload"]["client_id"],
                    ]
                ),
            },
        )


@pytest.mark.asyncio
async def test_redis_pubsub_distributes_between_server_instances():
    redis_server = FakeServer()
    first_redis = FakeAsyncRedis(server=redis_server, decode_responses=True)
    second_redis = FakeAsyncRedis(server=redis_server, decode_responses=True)
    first_server = NotificationServer(broker=RedisBroker(client=first_redis))
    second_server = NotificationServer(broker=RedisBroker(client=second_redis))
    await asyncio.gather(first_server.start(), second_server.start())

    try:
        async with serve(
            first_server.handler,
            "127.0.0.1",
            0,
            process_request=first_server.process_request,
        ) as first_listener, serve(
            second_server.handler,
            "127.0.0.1",
            0,
            process_request=second_server.process_request,
        ) as second_listener:
            first_port = first_listener.sockets[0].getsockname()[1]
            second_port = second_listener.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{first_port}") as first, connect(
                f"ws://127.0.0.1:{second_port}"
            ) as second:
                await asyncio.gather(receive_json(first), receive_json(second))
                assert await first_server.broker.connected_count() == 2

                outgoing = {
                    "type": "broadcast",
                    "payload": {"text": "through redis"},
                    "timestamp": "2026-08-16T00:00:00Z",
                }
                await first.send(json.dumps(outgoing))

                assert await receive_json(first) == outgoing
                assert await receive_json(second) == outgoing
    finally:
        await asyncio.gather(first_server.close(), second_server.close())
        await asyncio.gather(first_redis.aclose(), second_redis.aclose())


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(tmp_path):
    database_path = tmp_path / "messages.sqlite3"
    notifications = NotificationServer(
        store=MessageStore(f"sqlite:///{database_path}")
    )
    try:
        async with serve(
            notifications.handler,
            "127.0.0.1",
            0,
            process_request=notifications.process_request,
        ) as websocket_server:
            port = websocket_server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as websocket:
                await receive_json(websocket)
                await websocket.send(json.dumps(channel_message("subscribe", "history")))
                await asyncio.sleep(0.01)
                for number in (1, 2):
                    message = {
                        "type": "broadcast",
                        "payload": {"number": number},
                        "timestamp": f"2026-08-16T00:00:0{number}Z",
                        "channel": "history",
                    }
                    await websocket.send(json.dumps(message))
                    await receive_json(websocket)

                def get_messages():
                    url = f"http://127.0.0.1:{port}/messages?limit=1&offset=1"
                    with urllib.request.urlopen(url) as response:
                        return response.status, json.load(response)

                status, body = await asyncio.to_thread(get_messages)
                assert status == 200
                assert body == {
                    "messages": [
                        {
                            "id": 2,
                            "channel": "history",
                            "type": "broadcast",
                            "payload": {"number": 1},
                            "timestamp": "2026-08-16T00:00:01Z",
                        }
                    ]
                }
    finally:
        await notifications.close()

    reopened = MessageStore(f"sqlite:///{database_path}")
    try:
        broadcasts = [
            message for message in reopened.list() if message["type"] == "broadcast"
        ]
        assert [message["payload"]["number"] for message in broadcasts] == [2, 1]
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_redis_rate_limit_returns_error_without_publishing_message():
    redis = FakeAsyncRedis(decode_responses=True)
    notifications = NotificationServer(
        broker=RedisBroker(client=redis), rate_limit=2
    )
    try:
        async with serve(
            notifications.handler,
            "127.0.0.1",
            0,
            process_request=notifications.process_request,
        ) as websocket_server:
            port = websocket_server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as websocket:
                welcome = await receive_json(websocket)
                client_id = welcome["payload"]["client_id"]
                message = {
                    "type": "broadcast",
                    "payload": {"text": "allowed"},
                    "timestamp": "2026-08-16T00:00:00Z",
                }
                for _ in range(2):
                    await websocket.send(json.dumps(message))
                    assert await receive_json(websocket) == message

                await websocket.send(json.dumps(message))
                error = await receive_json(websocket)

                assert error["type"] == "system"
                assert error["payload"] == {
                    "event": "error",
                    "detail": "rate limit exceeded",
                }
                assert await redis.get(
                    RedisBroker._rate_limit_key(client_id)
                ) == "3"
                assert notifications.store.list() == [
                    {
                        "id": 2,
                        "channel": None,
                        "type": "broadcast",
                        "payload": {"text": "allowed"},
                        "timestamp": "2026-08-16T00:00:00Z",
                    },
                    {
                        "id": 1,
                        "channel": None,
                        "type": "broadcast",
                        "payload": {"text": "allowed"},
                        "timestamp": "2026-08-16T00:00:00Z",
                    },
                ]
    finally:
        await notifications.close()
        await redis.aclose()


@pytest.mark.asyncio
async def test_history_filters_channel_and_since_in_chronological_pages(tmp_path):
    store = MessageStore(f"sqlite:///{tmp_path / 'history.sqlite3'}")
    for channel, number, timestamp in (
        ("news", 3, "2026-08-16T00:00:03Z"),
        ("other", 2, "2026-08-16T00:00:02Z"),
        ("news", 1, "2026-08-16T00:00:01Z"),
        ("news", 2, "2026-08-16T00:00:02Z"),
    ):
        store.save(
            {
                "type": "broadcast",
                "channel": channel,
                "payload": {"number": number},
                "timestamp": timestamp,
            }
        )
    notifications = NotificationServer(store=store)
    try:
        async with serve(
            notifications.handler,
            "127.0.0.1",
            0,
            process_request=notifications.process_request,
        ) as websocket_server:
            port = websocket_server.sockets[0].getsockname()[1]
            query = urlencode(
                {
                    "channel": "news",
                    "since": "2026-08-16T00:00:01Z",
                    "limit": 2,
                }
            )

            def get_history():
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/history?{query}"
                ) as response:
                    return response.status, json.load(response)

            status, body = await asyncio.to_thread(get_history)

            assert status == 200
            assert body["has_more"] is True
            assert [message["payload"]["number"] for message in body["messages"]] == [
                1,
                2,
            ]
            assert all(message["channel"] == "news" for message in body["messages"])
    finally:
        await notifications.close()


@pytest.mark.asyncio
async def test_startup_cleanup_removes_messages_older_than_configured_ttl(tmp_path):
    store = MessageStore(f"sqlite:///{tmp_path / 'expiry.sqlite3'}")
    now = datetime.now(timezone.utc)
    for age, label in ((3, "expired"), (1, "current")):
        store.save(
            {
                "type": "system",
                "channel": "maintenance",
                "payload": {"label": label},
                "timestamp": (now - timedelta(days=age)).isoformat(),
            }
        )
    notifications = NotificationServer(store=store, message_ttl_days=2)
    try:
        await notifications.start()
        for _ in range(20):
            if len(store.list()) == 1:
                break
            await asyncio.sleep(0.01)

        assert [message["payload"]["label"] for message in store.list()] == [
            "current"
        ]
    finally:
        await notifications.close()
