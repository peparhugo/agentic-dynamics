import asyncio
import json
import urllib.request

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from app import MessageStore, NotificationServer


@pytest.fixture
async def running_server(unused_tcp_port):
    notification_server = NotificationServer(store=MessageStore(":memory:"))
    try:
        async with serve(
            notification_server.handler,
            "127.0.0.1",
            unused_tcp_port,
            process_request=notification_server.process_request,
        ):
            yield notification_server, unused_tcp_port
    finally:
        await notification_server.close()


async def receive_json(websocket):
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=1))


def valid_message(message_type, payload, channel=None):
    outgoing = {
        "type": message_type,
        "payload": payload,
        "timestamp": "2026-01-01T00:00:00Z",
    }
    if channel is not None:
        outgoing["channel"] = channel
    return outgoing


async def assert_no_message(websocket):
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(websocket.recv(), timeout=0.05)


async def fetch_json(port, path):
    def fetch():
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as response:
            return response.status, json.load(response)

    return await asyncio.to_thread(fetch)


@pytest.mark.asyncio
async def test_assigns_unique_client_ids(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        first_message = await receive_json(first)
        second_message = await receive_json(second)

        assert first_message["type"] == "system"
        assert first_message["payload"]["event"] == "connected"
        assert first_message["payload"]["client_id"] != second_message["payload"]["client_id"]
        assert isinstance(first_message["timestamp"], str)


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_including_sender(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        await receive_json(first)
        await receive_json(second)
        outgoing = valid_message("broadcast", {"text": "hello"})
        await first.send(json.dumps(outgoing))

        assert await receive_json(first) == outgoing
        assert await receive_json(second) == outgoing


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second:
        await receive_json(first)
        second_id = (await receive_json(second))["payload"]["client_id"]
        outgoing = valid_message("direct", {"client_id": second_id, "text": "private"})
        await first.send(json.dumps(outgoing))

        assert await receive_json(second) == outgoing
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(first.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_disconnect_removes_client(running_server):
    notification_server, port = running_server
    websocket = await connect(f"ws://127.0.0.1:{port}")
    await receive_json(websocket)
    assert len(notification_server.clients) == 1

    await websocket.close()
    for _ in range(20):
        if len(notification_server.clients) == 0:
            break
        await asyncio.sleep(0.01)
    assert len(notification_server.clients) == 0


@pytest.mark.asyncio
async def test_health_reports_connected_clients(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)

        def fetch_health():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as response:
                return response.status, json.load(response)

        status, body = await asyncio.to_thread(fetch_health)
        assert status == 200
        assert body == {"connected_clients": 1}


@pytest.mark.asyncio
async def test_invalid_messages_return_system_error(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send("not-json")
        response = await receive_json(websocket)

        assert response["type"] == "system"
        assert response["payload"] == {"error": "invalid JSON"}
        assert isinstance(response["timestamp"], str)


@pytest.mark.asyncio
async def test_channel_message_only_reaches_subscribers(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as first, connect(
        f"ws://127.0.0.1:{port}"
    ) as second, connect(f"ws://127.0.0.1:{port}") as third:
        await receive_json(first)
        await receive_json(second)
        await receive_json(third)
        await first.send(json.dumps(valid_message("subscribe", {}, "alerts")))
        await second.send(json.dumps(valid_message("subscribe", {}, "alerts")))

        outgoing = valid_message("broadcast", {"text": "warning"}, "alerts")
        await third.send(json.dumps(outgoing))

        assert await receive_json(first) == outgoing
        assert await receive_json(second) == outgoing
        await assert_no_message(third)


@pytest.mark.asyncio
async def test_client_can_subscribe_to_multiple_channels_and_unsubscribe(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as subscriber, connect(
        f"ws://127.0.0.1:{port}"
    ) as sender:
        await receive_json(subscriber)
        await receive_json(sender)
        for channel in ("alerts", "chat"):
            await subscriber.send(json.dumps(valid_message("subscribe", {}, channel)))

        alerts = valid_message("broadcast", {"text": "warning"}, "alerts")
        chat = valid_message("broadcast", {"text": "hello"}, "chat")
        await sender.send(json.dumps(alerts))
        await sender.send(json.dumps(chat))
        assert await receive_json(subscriber) == alerts
        assert await receive_json(subscriber) == chat

        await subscriber.send(json.dumps(valid_message("unsubscribe", {}, "alerts")))
        await sender.send(json.dumps(alerts))
        await sender.send(json.dumps(chat))
        assert await receive_json(subscriber) == chat
        await assert_no_message(subscriber)


@pytest.mark.asyncio
async def test_channel_direct_message_requires_target_subscription(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as sender, connect(
        f"ws://127.0.0.1:{port}"
    ) as target:
        await receive_json(sender)
        target_id = (await receive_json(target))["payload"]["client_id"]
        outgoing = valid_message(
            "direct", {"client_id": target_id, "text": "private"}, "chat"
        )

        await sender.send(json.dumps(outgoing))
        await assert_no_message(target)
        await target.send(json.dumps(valid_message("subscribe", {}, "chat")))
        await sender.send(json.dumps(outgoing))
        assert await receive_json(target) == outgoing


@pytest.mark.asyncio
async def test_channel_rest_endpoints_and_disconnect_cleanup(running_server):
    _, port = running_server
    first = await connect(f"ws://127.0.0.1:{port}")
    second = await connect(f"ws://127.0.0.1:{port}")
    try:
        first_id = (await receive_json(first))["payload"]["client_id"]
        second_id = (await receive_json(second))["payload"]["client_id"]
        await first.send(json.dumps(valid_message("subscribe", {}, "alerts")))
        await second.send(json.dumps(valid_message("subscribe", {}, "alerts")))
        await second.send(json.dumps(valid_message("subscribe", {}, "chat room")))

        assert await fetch_json(port, "/channels") == (
            200,
            {"channels": {"alerts": 2, "chat room": 1}},
        )
        assert await fetch_json(port, "/channels/alerts/subscribers") == (
            200,
            {"channel": "alerts", "subscribers": sorted([first_id, second_id])},
        )
        assert await fetch_json(port, "/channels/chat%20room/subscribers") == (
            200,
            {"channel": "chat room", "subscribers": [second_id]},
        )

        await second.close()
        for _ in range(20):
            if (await fetch_json(port, "/channels"))[1] == {
                "channels": {"alerts": 1}
            }:
                break
            await asyncio.sleep(0.01)
        assert await fetch_json(port, "/channels") == (
            200,
            {"channels": {"alerts": 1}},
        )
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_subscription_requires_non_empty_channel(running_server):
    _, port = running_server
    async with connect(f"ws://127.0.0.1:{port}") as websocket:
        await receive_json(websocket)
        await websocket.send(json.dumps(valid_message("subscribe", {})))
        response = await receive_json(websocket)
        assert response["payload"] == {"error": "subscribe message requires channel"}

        outgoing = valid_message("subscribe", {}, "")
        await websocket.send(json.dumps(outgoing))
        response = await receive_json(websocket)
        assert response["payload"] == {"error": "channel must be a non-empty string"}
