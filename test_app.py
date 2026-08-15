import asyncio
import json
import urllib.request

import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def server():
    async with NotificationServer(port=0) as running_server:
        yield running_server


def websocket_url(server):
    return f"ws://127.0.0.1:{server.bound_port}"


async def receive_json(connection):
    return json.loads(await asyncio.wait_for(connection.recv(), timeout=1))


async def send_message(connection, message_type, payload=None, channel=None):
    notification = {
        "type": message_type,
        "payload": payload or {},
        "timestamp": "2026-08-16T12:00:00Z",
    }
    if channel is not None:
        notification["channel"] = channel
    await connection.send(json.dumps(notification))
    return notification


async def get_json(server, path):
    def request():
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.bound_port}{path}", timeout=1
        ) as response:
            return response.status, json.load(response)

    return await asyncio.to_thread(request)


@pytest.mark.asyncio
async def test_connection_gets_unique_id_and_disconnect_is_removed(server):
    async with connect(websocket_url(server)) as first, connect(
        websocket_url(server)
    ) as second:
        first_welcome, second_welcome = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        assert first_welcome["type"] == "system"
        assert first_welcome["payload"]["event"] == "connected"
        assert first_welcome["payload"]["client_id"] != second_welcome["payload"][
            "client_id"
        ]
        assert server.connected_count == 2

    await asyncio.sleep(0)
    assert server.connected_count == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients_including_sender(server):
    async with connect(websocket_url(server)) as first, connect(
        websocket_url(server)
    ) as second:
        await asyncio.gather(receive_json(first), receive_json(second))
        notification = {
            "type": "broadcast",
            "payload": {"text": "deployment complete"},
            "timestamp": "2026-08-16T12:00:00Z",
        }
        await first.send(json.dumps(notification))

        assert await receive_json(first) == notification
        assert await receive_json(second) == notification


@pytest.mark.asyncio
async def test_direct_message_only_reaches_target(server):
    async with connect(websocket_url(server)) as sender, connect(
        websocket_url(server)
    ) as recipient:
        sender_welcome, recipient_welcome = await asyncio.gather(
            receive_json(sender), receive_json(recipient)
        )
        notification = {
            "type": "direct",
            "payload": {
                "client_id": recipient_welcome["payload"]["client_id"],
                "text": "private",
            },
            "timestamp": "2026-08-16T12:00:00Z",
        }
        await sender.send(json.dumps(notification))

        assert await receive_json(recipient) == notification
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sender.recv(), timeout=0.05)
        assert sender_welcome["payload"]["client_id"] != recipient_welcome["payload"][
            "client_id"
        ]


@pytest.mark.asyncio
async def test_invalid_message_returns_formatted_system_error(server):
    async with connect(websocket_url(server)) as connection:
        await receive_json(connection)
        await connection.send("not json")
        error = await receive_json(connection)

        assert set(error) == {"type", "payload", "timestamp"}
        assert error["type"] == "system"
        assert error["payload"] == {"error": "message must be valid JSON"}


@pytest.mark.asyncio
async def test_health_returns_connected_client_count(server):
    async with connect(websocket_url(server)) as connection:
        await receive_json(connection)

        def request_health():
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.bound_port}/health", timeout=1
            ) as response:
                return response.status, json.load(response)

        status, body = await asyncio.to_thread(request_health)
        assert status == 200
        assert body == {"connected_clients": 1}


@pytest.mark.asyncio
async def test_channel_message_only_reaches_subscribers(server):
    async with connect(websocket_url(server)) as alerts, connect(
        websocket_url(server)
    ) as chat, connect(websocket_url(server)) as unsubscribed:
        await asyncio.gather(
            receive_json(alerts), receive_json(chat), receive_json(unsubscribed)
        )
        await send_message(alerts, "subscribe", channel="alerts")
        await send_message(chat, "subscribe", {"channel": "chat"})

        notification = await send_message(
            chat, "broadcast", {"text": "warning"}, channel="alerts"
        )

        assert await receive_json(alerts) == notification
        for connection in (chat, unsubscribed):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(connection.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_client_can_subscribe_to_multiple_channels_and_unsubscribe(server):
    async with connect(websocket_url(server)) as sender, connect(
        websocket_url(server)
    ) as recipient:
        await asyncio.gather(receive_json(sender), receive_json(recipient))
        await send_message(recipient, "subscribe", channel="alerts")
        await send_message(recipient, "subscribe", channel="system")

        alerts = await send_message(sender, "broadcast", channel="alerts")
        system = await send_message(sender, "broadcast", channel="system")
        assert await receive_json(recipient) == alerts
        assert await receive_json(recipient) == system

        await send_message(recipient, "unsubscribe", channel="alerts")
        await send_message(sender, "broadcast", channel="alerts")
        still_subscribed = await send_message(sender, "broadcast", channel="system")
        assert await receive_json(recipient) == still_subscribed
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(recipient.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_channel_endpoints_list_counts_and_subscriber_ids(server):
    async with connect(websocket_url(server)) as first, connect(
        websocket_url(server)
    ) as second:
        first_welcome, second_welcome = await asyncio.gather(
            receive_json(first), receive_json(second)
        )
        first_id = first_welcome["payload"]["client_id"]
        second_id = second_welcome["payload"]["client_id"]
        await send_message(first, "subscribe", channel="alerts")
        await send_message(second, "subscribe", channel="alerts")
        await send_message(second, "subscribe", channel="chat")
        await asyncio.sleep(0.01)

        status, channels = await get_json(server, "/channels")
        assert status == 200
        assert channels == {
            "channels": [
                {"name": "alerts", "subscriber_count": 2},
                {"name": "chat", "subscriber_count": 1},
            ]
        }

        status, subscribers = await get_json(server, "/channels/alerts/subscribers")
        assert status == 200
        assert subscribers == {
            "channel": "alerts",
            "subscribers": sorted([first_id, second_id]),
        }

    await asyncio.sleep(0)
    _, channels = await get_json(server, "/channels")
    assert channels == {"channels": []}
