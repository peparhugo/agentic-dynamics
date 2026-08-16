import asyncio
import json

import aiohttp
import pytest
from websockets.asyncio.client import connect


async def drain_system(ws):
    msg = json.loads(await ws.recv())
    assert msg["type"] == "system"
    return msg


async def connect_client(server):
    ws = await connect(server.ws_url)
    msg = await drain_system(ws)
    assert msg["payload"]["event"] == "connected"
    return ws, msg["payload"]["client_id"]


async def subscribe(ws, channel):
    await ws.send(json.dumps({"type": "subscribe", "channel": channel}))
    ack = json.loads(await ws.recv())
    assert ack["type"] == "system"
    assert ack["payload"]["event"] == "subscribed"
    assert ack["payload"]["channel"] == channel


async def unsubscribe(ws, channel):
    await ws.send(json.dumps({"type": "unsubscribe", "channel": channel}))
    ack = json.loads(await ws.recv())
    assert ack["type"] == "system"
    assert ack["payload"]["event"] == "unsubscribed"
    assert ack["payload"]["channel"] == channel


async def expect_no_message(ws, timeout=0.2):
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws.recv(), timeout=timeout)


@pytest.mark.asyncio
async def test_subscribe_receives_channel_message(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await subscribe(ws_a, "alerts")

    await ws_b.send(
        json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "hi"}})
    )

    msg = json.loads(await ws_a.recv())
    assert msg["type"] == "broadcast"
    assert msg["channel"] == "alerts"
    assert msg["payload"] == {"text": "hi"}

    await expect_no_message(ws_b)

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_channel_message_not_delivered_to_non_subscribers(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await subscribe(ws_a, "alerts")

    await ws_a.send(
        json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "x"}})
    )

    msg = json.loads(await ws_a.recv())
    assert msg["type"] == "broadcast"
    assert msg["channel"] == "alerts"

    await expect_no_message(ws_b)

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await subscribe(ws_a, "alerts")
    await unsubscribe(ws_a, "alerts")

    await ws_b.send(
        json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "y"}})
    )

    await expect_no_message(ws_a)
    await expect_no_message(ws_b)

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_client_subscribed_to_multiple_channels(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await subscribe(ws_a, "alerts")
    await subscribe(ws_a, "system")

    await ws_b.send(
        json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"n": 1}})
    )
    await ws_b.send(
        json.dumps({"type": "broadcast", "channel": "system", "payload": {"n": 2}})
    )

    first = json.loads(await ws_a.recv())
    second = json.loads(await ws_a.recv())
    assert {first["payload"]["n"], second["payload"]["n"]} == {1, 2}
    assert {first["channel"], second["channel"]} == {"alerts", "system"}

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_channels_endpoint_lists_active_channels(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await subscribe(ws_a, "alerts")
    await subscribe(ws_b, "alerts")
    await subscribe(ws_b, "system")

    async with aiohttp.ClientSession() as session:
        async with session.get(server.channels_url) as resp:
            assert resp.status == 200
            body = await resp.json()

    assert body["channels"] == [
        {"name": "alerts", "subscribers": 2},
        {"name": "system", "subscribers": 1},
    ]

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_lists_ids(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await subscribe(ws_a, "alerts")
    await subscribe(ws_b, "alerts")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{server.channels_url}/alerts/subscribers") as resp:
            assert resp.status == 200
            body = await resp.json()

    assert body["channel"] == "alerts"
    assert sorted(body["subscribers"]) == sorted([id_a, id_b])

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_channels_endpoint_excludes_inactive_channels(server):
    ws_a, id_a = await connect_client(server)

    await subscribe(ws_a, "alerts")
    await unsubscribe(ws_a, "alerts")

    async with aiohttp.ClientSession() as session:
        async with session.get(server.channels_url) as resp:
            body = await resp.json()

    assert body["channels"] == []

    await ws_a.close()


@pytest.mark.asyncio
async def test_disconnect_removes_client_from_channels(server):
    ws_a, id_a = await connect_client(server)
    ws_b, id_b = await connect_client(server)

    await subscribe(ws_a, "alerts")
    await subscribe(ws_b, "alerts")

    await ws_a.close()

    msg = json.loads(await ws_b.recv())
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "disconnected"
    assert msg["payload"]["client_id"] == id_a

    async with aiohttp.ClientSession() as session:
        async with session.get(server.channels_url) as resp:
            body = await resp.json()

    assert body["channels"] == [{"name": "alerts", "subscribers": 1}]

    await ws_b.close()
