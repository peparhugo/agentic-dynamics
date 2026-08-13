import asyncio
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
