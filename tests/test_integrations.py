import asyncio
from datetime import datetime, timedelta, timezone
import json

import fakeredis
import pytest
from websockets.asyncio.client import connect

from app import (
    REDIS_CLIENTS_KEY,
    MessageStore,
    NotificationServer,
    app,
    channels,
    clients,
    clients_lock,
)


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))


async def connect_client(server):
    websocket = await connect(f"ws://127.0.0.1:{server.port}")
    welcome = await receive_json(websocket)
    return websocket, welcome["payload"]["client_id"]


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def integration_servers(tmp_path, redis_client):
    store = MessageStore(f"sqlite:///{tmp_path / 'messages.db'}")
    first = NotificationServer(port=0, redis_client=redis_client, message_store=store)
    second = NotificationServer(port=0, redis_client=redis_client, message_store=store)
    first.start()
    second.start()
    yield first, second, store
    first.stop()
    second.stop()
    store.close()
    with clients_lock:
        clients.clear()
        channels.clear()


@pytest.mark.asyncio
async def test_redis_pubsub_distributes_between_server_instances(
    integration_servers, redis_client
):
    first_server, second_server, _ = integration_servers
    sender, sender_id = await connect_client(first_server)
    recipient, recipient_id = await connect_client(second_server)
    assert redis_client.hget(REDIS_CLIENTS_KEY, sender_id) == first_server.server_id
    assert redis_client.hget(REDIS_CLIENTS_KEY, recipient_id) == second_server.server_id

    broadcast = {
        "type": "broadcast",
        "payload": {"text": "shared"},
        "timestamp": "2026-08-13T12:00:00+00:00",
    }
    await sender.send(json.dumps(broadcast))
    assert await receive_json(sender) == broadcast
    assert await receive_json(recipient) == broadcast

    direct = {
        "type": "direct",
        "payload": {"client_id": recipient_id, "text": "private"},
        "timestamp": "2026-08-13T12:01:00+00:00",
    }
    await sender.send(json.dumps(direct))
    assert await receive_json(recipient) == direct
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)

    await sender.close()
    await recipient.close()
    for _ in range(50):
        if redis_client.hlen(REDIS_CLIENTS_KEY) == 0:
            break
        await asyncio.sleep(0.01)
    assert redis_client.hlen(REDIS_CLIENTS_KEY) == 0


@pytest.mark.asyncio
async def test_messages_are_persisted_and_paginated(integration_servers, monkeypatch):
    first_server, _, store = integration_servers
    websocket, _ = await connect_client(first_server)
    messages = [
        {
            "type": "broadcast",
            "payload": {"number": number},
            "timestamp": f"2026-08-13T12:0{number}:00+00:00",
            "channel": "updates",
        }
        for number in range(3)
    ]
    for message in messages:
        await websocket.send(json.dumps(message))

    for _ in range(50):
        if len(store.list(50, 0)) == 3:
            break
        await asyncio.sleep(0.01)
    monkeypatch.setattr("app.get_message_store", lambda: store)
    response = app.test_client().get("/messages?limit=2&offset=1")
    assert response.status_code == 200
    result = response.get_json()["messages"]
    assert [item["payload"]["number"] for item in result] == [1, 0]
    assert set(result[0]) == {"id", "channel", "type", "payload", "timestamp"}
    assert app.test_client().get("/messages?limit=bad").status_code == 400
    await websocket.close()


@pytest.mark.asyncio
async def test_rate_limit_is_enforced_per_client_with_redis(tmp_path, redis_client):
    store = MessageStore(f"sqlite:///{tmp_path / 'rate-limit.db'}")
    server = NotificationServer(
        port=0, redis_client=redis_client, message_store=store, rate_limit=2
    )
    server.start()
    sender, _ = await connect_client(server)
    receiver, _ = await connect_client(server)
    try:
        messages = [
            {
                "type": "broadcast",
                "payload": {"number": number},
                "timestamp": f"2026-08-13T12:0{number}:00+00:00",
            }
            for number in range(3)
        ]
        for message in messages:
            await sender.send(json.dumps(message))

        sender_responses = [await receive_json(sender) for _ in range(3)]
        broadcasts = [item for item in sender_responses if item["type"] == "broadcast"]
        errors = [item for item in sender_responses if item["type"] == "system"]
        assert broadcasts == messages[:2]
        assert len(errors) == 1
        assert errors[0]["payload"] == {"error": "rate limit exceeded"}
        assert await receive_json(receiver) == messages[0]
        assert await receive_json(receiver) == messages[1]
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(receiver.recv(), timeout=0.05)
        assert len(store.list(50, 0)) == 2
    finally:
        await sender.close()
        await receiver.close()
        server.stop()
        store.close()


def test_history_filters_orders_and_paginates(tmp_path, monkeypatch):
    store = MessageStore(f"sqlite:///{tmp_path / 'history.db'}")
    try:
        for channel, number, timestamp in [
            ("updates", 3, "2026-08-13T12:03:00+00:00"),
            ("other", 9, "2026-08-13T12:02:00+00:00"),
            ("updates", 1, "2026-08-13T12:01:00+00:00"),
            ("updates", 2, "2026-08-13T12:02:00+00:00"),
        ]:
            store.save(
                {
                    "type": "broadcast",
                    "payload": {"number": number},
                    "timestamp": timestamp,
                    "channel": channel,
                }
            )
        monkeypatch.setattr("app.get_message_store", lambda: store)

        response = app.test_client().get(
            "/history?channel=updates&since=2026-08-13T12:01:30Z&limit=1"
        )
        assert response.status_code == 200
        result = response.get_json()
        assert [message["payload"]["number"] for message in result["messages"]] == [2]
        assert result["has_more"] is True

        response = app.test_client().get(
            "/history?channel=updates&since=2026-08-13T12:02:30%2B00:00"
        )
        assert [message["payload"]["number"] for message in response.get_json()["messages"]] == [3]
        assert response.get_json()["has_more"] is False
        assert app.test_client().get("/history?channel=updates").status_code == 400
        assert (
            app.test_client()
            .get("/history?channel=updates&since=not-a-date")
            .status_code
            == 400
        )
    finally:
        store.close()


def test_expired_messages_are_cleaned_up_on_startup(tmp_path):
    store = MessageStore(f"sqlite:///{tmp_path / 'expiry.db'}")
    now = datetime.now(timezone.utc)
    for number, timestamp in [
        (1, now - timedelta(days=8)),
        (2, now - timedelta(days=1)),
    ]:
        store.save(
            {
                "type": "broadcast",
                "payload": {"number": number},
                "timestamp": timestamp.isoformat(),
                "channel": "updates",
            }
        )
    server = NotificationServer(port=0, message_store=store, message_ttl_days=7)
    server.start()
    try:
        for _ in range(50):
            if len(store.list(50, 0)) == 1:
                break
            import time

            time.sleep(0.01)
        assert [message["payload"]["number"] for message in store.list(50, 0)] == [2]
    finally:
        server.stop()
        store.close()
