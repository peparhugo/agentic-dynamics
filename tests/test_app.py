import asyncio
import json
import urllib.request

import pytest
import websockets

from app import NotificationServer


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
