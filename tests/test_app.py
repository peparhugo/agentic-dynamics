import asyncio
import json
import threading

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer, app, channels, clients, clients_lock


@pytest.fixture
def server():
    instance = NotificationServer(port=0)
    instance.start()
    yield instance
    instance.stop()
    with clients_lock:
        clients.clear()
        channels.clear()


def url(server):
    return f"ws://127.0.0.1:{server.port}"


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))


async def connect_client(server):
    websocket = await connect(url(server))
    welcome = await receive_json(websocket)
    assert welcome["type"] == "system"
    assert welcome["payload"]["event"] == "connected"
    assert isinstance(welcome["timestamp"], str)
    return websocket, welcome["payload"]["client_id"]


@pytest.mark.asyncio
async def test_assigns_unique_ids_and_cleans_up_disconnects(server):
    first, first_id = await connect_client(server)
    second, second_id = await connect_client(server)
    assert first_id != second_id
    assert len(clients) == 2

    await first.close()
    await second.close()
    for _ in range(50):
        if not clients:
            break
        await asyncio.sleep(0.01)
    assert clients == {}


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    first, _ = await connect_client(server)
    second, _ = await connect_client(server)
    message = {
        "type": "broadcast",
        "payload": {"text": "deployment complete"},
        "timestamp": "2026-08-13T12:00:00+00:00",
    }
    await first.send(json.dumps(message))

    assert await receive_json(first) == message
    assert await receive_json(second) == message
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_message_only_reaches_recipient(server):
    sender, _ = await connect_client(server)
    recipient, recipient_id = await connect_client(server)
    message = {
        "type": "direct",
        "payload": {"client_id": recipient_id, "text": "private"},
        "timestamp": "2026-08-13T12:00:00+00:00",
    }
    await sender.send(json.dumps(message))

    assert await receive_json(recipient) == message
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(sender.recv(), timeout=0.05)
    await sender.close()
    await recipient.close()


@pytest.mark.asyncio
async def test_invalid_messages_return_system_error(server):
    websocket, _ = await connect_client(server)
    await websocket.send("not json")
    response = await receive_json(websocket)
    assert response["type"] == "system"
    assert response["payload"] == {"error": "invalid JSON"}
    assert set(response) == {"type", "payload", "timestamp"}
    await websocket.close()


@pytest.mark.asyncio
async def test_health_reports_connected_count(server):
    websocket, _ = await connect_client(server)
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"connected_clients": 1}
    await websocket.close()


def test_websocket_loop_uses_daemon_thread(server):
    assert server._thread is not threading.main_thread()
    assert server._thread.daemon is True
    assert server._thread.is_alive()


def channel_message(message_type, channel):
    return {
        "type": message_type,
        "payload": {},
        "timestamp": "2026-08-13T12:00:00+00:00",
        "channel": channel,
    }


@pytest.mark.asyncio
async def test_channel_messages_only_reach_subscribers(server):
    alerts_client, _ = await connect_client(server)
    chat_client, _ = await connect_client(server)
    unsubscribed_client, _ = await connect_client(server)
    await alerts_client.send(json.dumps(channel_message("subscribe", "alerts")))
    await chat_client.send(json.dumps(channel_message("subscribe", "chat")))

    message = {
        "type": "broadcast",
        "payload": {"text": "warning"},
        "timestamp": "2026-08-13T12:00:00+00:00",
        "channel": "alerts",
    }
    await alerts_client.send(json.dumps(message))

    assert await receive_json(alerts_client) == message
    for websocket in (chat_client, unsubscribed_client):
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(websocket.recv(), timeout=0.05)
    await alerts_client.close()
    await chat_client.close()
    await unsubscribed_client.close()


@pytest.mark.asyncio
async def test_client_can_subscribe_to_multiple_channels_and_unsubscribe(server):
    client, _ = await connect_client(server)
    sender, _ = await connect_client(server)
    await client.send(json.dumps(channel_message("subscribe", "alerts")))
    await client.send(json.dumps(channel_message("subscribe", "chat")))

    for name in ("alerts", "chat"):
        message = {
            "type": "broadcast",
            "payload": {"channel": name},
            "timestamp": "2026-08-13T12:00:00+00:00",
            "channel": name,
        }
        await sender.send(json.dumps(message))
        assert await receive_json(client) == message

    await client.send(json.dumps(channel_message("unsubscribe", "alerts")))
    await client.send(json.dumps(channel_message("subscribe", "sync")))
    sync_message = {
        "type": "broadcast",
        "payload": {},
        "timestamp": "2026-08-13T12:00:00+00:00",
        "channel": "sync",
    }
    await client.send(json.dumps(sync_message))
    assert await receive_json(client) == sync_message
    assert "alerts" not in channels
    assert len(channels["chat"]) == 1

    await client.close()
    await sender.close()


@pytest.mark.asyncio
async def test_channel_direct_message_requires_recipient_subscription(server):
    sender, _ = await connect_client(server)
    recipient, recipient_id = await connect_client(server)
    message = {
        "type": "direct",
        "payload": {"client_id": recipient_id, "text": "private alert"},
        "timestamp": "2026-08-13T12:00:00+00:00",
        "channel": "alerts",
    }
    await sender.send(json.dumps(message))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(recipient.recv(), timeout=0.05)

    await recipient.send(json.dumps(channel_message("subscribe", "alerts")))
    await recipient.send(json.dumps(channel_message("subscribe", "ready")))
    ready_message = {
        "type": "broadcast",
        "payload": {},
        "timestamp": "2026-08-13T12:00:00+00:00",
        "channel": "ready",
    }
    await recipient.send(json.dumps(ready_message))
    assert await receive_json(recipient) == ready_message
    await sender.send(json.dumps(message))
    assert await receive_json(recipient) == message
    await sender.close()
    await recipient.close()


@pytest.mark.asyncio
async def test_channel_rest_endpoints_and_disconnect_cleanup(server):
    first, first_id = await connect_client(server)
    second, second_id = await connect_client(server)
    await first.send(json.dumps(channel_message("subscribe", "alerts")))
    await second.send(json.dumps(channel_message("subscribe", "alerts")))
    await second.send(json.dumps(channel_message("subscribe", "chat")))
    await second.send(json.dumps(channel_message("subscribe", "ready")))
    await second.send(json.dumps({
        "type": "broadcast",
        "payload": {},
        "timestamp": "2026-08-13T12:00:00+00:00",
        "channel": "ready",
    }))
    await receive_json(second)

    client = app.test_client()
    assert client.get("/channels").get_json() == {
        "channels": [
            {"name": "alerts", "subscriber_count": 2},
            {"name": "chat", "subscriber_count": 1},
            {"name": "ready", "subscriber_count": 1},
        ]
    }
    assert client.get("/channels/alerts/subscribers").get_json() == {
        "channel": "alerts",
        "subscribers": sorted([first_id, second_id]),
    }

    await second.close()
    for _ in range(50):
        if "chat" not in channels:
            break
        await asyncio.sleep(0.01)
    assert client.get("/channels").get_json() == {
        "channels": [{"name": "alerts", "subscriber_count": 1}]
    }
    await first.close()
