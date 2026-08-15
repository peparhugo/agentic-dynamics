import json
import asyncio

import aiohttp
import pytest
from websockets.asyncio.client import connect

from app import NotificationServer


@pytest.fixture
async def server():
    notification_server = NotificationServer()
    await notification_server.start(websocket_port=0, health_port=0)
    yield notification_server
    await notification_server.stop()


async def connect_client(server):
    client = await connect(f"ws://127.0.0.1:{server.websocket_port}")
    welcome = json.loads(await client.recv())
    return client, welcome["payload"]["client_id"]


@pytest.mark.asyncio
async def test_clients_get_unique_ids_and_health_count(server):
    first, first_id = await connect_client(server)
    second, second_id = await connect_client(server)

    assert first_id != second_id
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://127.0.0.1:{server.health_port}/health") as response:
            assert response.status == 200
            assert await response.json() == {"connected_clients": 2}

    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    first, _ = await connect_client(server)
    second, _ = await connect_client(server)
    message = {"type": "broadcast", "payload": {"text": "hello"}}

    await first.send(json.dumps(message))
    received_first = json.loads(await first.recv())
    received_second = json.loads(await second.recv())

    assert received_first["type"] == "broadcast"
    assert received_first["payload"] == {"text": "hello"}
    assert received_second["payload"] == {"text": "hello"}
    assert isinstance(received_first["timestamp"], str)
    await first.close()
    await second.close()


@pytest.mark.asyncio
async def test_direct_message_reaches_only_target(server):
    sender, _ = await connect_client(server)
    target, target_id = await connect_client(server)

    await sender.send(
        json.dumps(
            {
                "type": "direct",
                "payload": {"client_id": target_id, "message": {"text": "private"}},
            }
        )
    )

    received = json.loads(await target.recv())
    assert received["type"] == "direct"
    assert received["payload"] == {"text": "private"}
    await sender.close()
    await target.close()


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    client, _ = await connect_client(server)
    assert server.client_count == 1
    await client.close()

    for _ in range(20):
        if server.client_count == 0:
            break
        await __import__("asyncio").sleep(0)
    assert server.client_count == 0


@pytest.mark.asyncio
async def test_channel_messages_reach_only_subscribers(server):
    alerts_client, alerts_id = await connect_client(server)
    other_client, _ = await connect_client(server)

    await alerts_client.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    subscribed = json.loads(await alerts_client.recv())
    assert subscribed["payload"] == {"subscribed": "alerts"}

    await other_client.send(
        json.dumps({"type": "subscribe", "payload": {"channel": "system"}})
    )
    await other_client.recv()
    await alerts_client.send(
        json.dumps(
            {"type": "broadcast", "channel": "alerts", "payload": {"text": "page"}}
        )
    )

    received = json.loads(await alerts_client.recv())
    assert received["channel"] == "alerts"
    assert received["payload"] == {"text": "page"}
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(other_client.recv(), timeout=0.05)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://127.0.0.1:{server.health_port}/channels") as response:
            assert await response.json() == {
                "channels": [
                    {"name": "alerts", "subscriber_count": 1},
                    {"name": "system", "subscriber_count": 1},
                ]
            }
        async with session.get(
            f"http://127.0.0.1:{server.health_port}/channels/alerts/subscribers"
        ) as response:
            assert await response.json() == {
                "channel": "alerts",
                "subscribers": [alerts_id],
            }

    await alerts_client.send(json.dumps({"type": "unsubscribe", "channel": "alerts"}))
    unsubscribed = json.loads(await alerts_client.recv())
    assert unsubscribed["payload"] == {"unsubscribed": "alerts"}
    await alerts_client.close()
    await other_client.close()


@pytest.mark.asyncio
async def test_unsubscribed_channel_is_removed(server):
    client, _ = await connect_client(server)
    await client.send(json.dumps({"type": "subscribe", "channel": "temporary"}))
    await client.recv()
    await client.send(json.dumps({"type": "unsubscribe", "channel": "temporary"}))
    await client.recv()
    assert server.channels == {}
    await client.close()
