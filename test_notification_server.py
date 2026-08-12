import json
import asyncio

import aiohttp
import pytest
from websockets.asyncio.client import connect

from notification_server import NotificationServer


@pytest.fixture
async def server():
    instance = NotificationServer(websocket_port=0, health_port=0)
    await instance.start()
    yield instance
    await instance.stop()


async def receive_json(socket):
    return json.loads(await socket.recv())


@pytest.mark.asyncio
async def test_assigns_ids_broadcasts_and_reports_health(server):
    url = f"ws://{server.host}:{server.websocket_port}"
    async with connect(url) as first, connect(url) as second:
        first_connected = await receive_json(first)
        second_connected = await receive_json(second)
        assert first_connected["type"] == "system"
        assert first_connected["payload"]["client_id"] != second_connected["payload"]["client_id"]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://{server.host}:{server.health_port}/health"
            ) as response:
                assert response.status == 200
                assert await response.json() == {"connected_clients": 2}

        await first.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
        assert (await receive_json(first))["payload"] == {"text": "hello"}
        assert (await receive_json(second))["payload"] == {"text": "hello"}

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{server.host}:{server.health_port}/health") as response:
            assert (await response.json())["connected_clients"] == 0


@pytest.mark.asyncio
async def test_direct_message_only_reaches_recipient(server):
    url = f"ws://{server.host}:{server.websocket_port}"
    async with connect(url) as sender, connect(url) as recipient:
        sender_info = await receive_json(sender)
        recipient_info = await receive_json(recipient)
        await sender.send(json.dumps({
            "type": "direct",
            "payload": {"recipient_id": recipient_info["payload"]["client_id"], "value": 3},
        }))
        assert (await receive_json(recipient))["payload"]["value"] == 3
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(recipient.recv(), timeout=0.05)


@pytest.mark.asyncio
async def test_rejects_invalid_messages_with_system_error(server):
    url = f"ws://{server.host}:{server.websocket_port}"
    async with connect(url) as socket:
        await receive_json(socket)
        await socket.send("not json")
        response = await receive_json(socket)
        assert response["type"] == "system"
        assert "error" in response["payload"]


@pytest.mark.asyncio
async def test_channel_messages_only_reach_subscribers_and_can_unsubscribe(server):
    url = f"ws://{server.host}:{server.websocket_port}"
    async with connect(url) as alerts_client, connect(url) as other_client:
        alerts_info = await receive_json(alerts_client)
        await receive_json(other_client)
        channel = "alerts"

        await alerts_client.send(json.dumps({
            "type": "subscribe", "payload": {"channel": channel}
        }))
        await alerts_client.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": channel, "text": "first"},
        }))
        assert (await receive_json(alerts_client))["payload"]["text"] == "first"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(other_client.recv(), timeout=0.05)

        await alerts_client.send(json.dumps({
            "type": "unsubscribe", "payload": {"channel": channel}
        }))
        await alerts_client.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": channel, "text": "second"},
        }))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(alerts_client.recv(), timeout=0.05)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://{server.host}:{server.health_port}/channels"
            ) as response:
                assert await response.json() == {"channels": []}
            async with session.get(
                f"http://{server.host}:{server.health_port}/channels/{channel}/subscribers"
            ) as response:
                assert await response.json() == {"subscribers": []}


@pytest.mark.asyncio
async def test_multiple_channel_subscriptions_and_channel_rest_listing(server):
    url = f"ws://{server.host}:{server.websocket_port}"
    async with connect(url) as first, connect(url) as second:
        first_id = (await receive_json(first))["payload"]["client_id"]
        second_id = (await receive_json(second))["payload"]["client_id"]
        for channel in ("alerts", "system"):
            await first.send(json.dumps({
                "type": "subscribe", "payload": {"channel": channel}
            }))
        await second.send(json.dumps({
            "type": "subscribe", "payload": {"channel": "alerts"}
        }))

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://{server.host}:{server.health_port}/channels"
            ) as response:
                assert await response.json() == {"channels": [
                    {"name": "alerts", "subscriber_count": 2},
                    {"name": "system", "subscriber_count": 1},
                ]}
            async with session.get(
                f"http://{server.host}:{server.health_port}/channels/alerts/subscribers"
            ) as response:
                assert (await response.json())["subscribers"] == sorted(
                    [first_id, second_id]
                )
