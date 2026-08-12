import asyncio
import json

import aiohttp
import pytest
import websockets

from conftest import recv_message


async def _wait_channel_count(server, channel, expected, timeout: float = 5.0) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while server.channels.count(channel) != expected:
        if loop.time() >= deadline:
            raise AssertionError(
                f"channel {channel!r} count is {server.channels.count(channel)}, expected {expected}"
            )
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_subscribe_and_channel_routing(ws_url, running_server):
    async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
        id1 = (await recv_message(ws1))["payload"]["client_id"]
        await recv_message(ws2)

        await ws1.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await ws2.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        await _wait_channel_count(running_server, "alerts", 1)

        await running_server.broadcast({"alert": "down"}, channel="alerts")

        message = await recv_message(ws1)
        assert message["type"] == "broadcast"
        assert message["payload"] == {"alert": "down"}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), 0.2)
        assert id1


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery(ws_url, running_server):
    async with websockets.connect(ws_url) as ws:
        await recv_message(ws)
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await ws.send(json.dumps({"type": "unsubscribe", "channel": "alerts"}))

        await asyncio.sleep(0.1)
        assert running_server.channels.count("alerts") == 0


@pytest.mark.asyncio
async def test_client_can_subscribe_to_multiple_channels(ws_url, running_server):
    async with websockets.connect(ws_url) as ws:
        await recv_message(ws)
        for channel in ("alerts", "system", "chat"):
            await ws.send(json.dumps({"type": "subscribe", "channel": channel}))

        await asyncio.sleep(0.1)
        assert running_server.channels.count("alerts") == 1
        assert running_server.channels.count("system") == 1
        assert running_server.channels.count("chat") == 1


@pytest.mark.asyncio
async def test_client_broadcast_with_channel_field(ws_url, running_server):
    async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
        await recv_message(ws1)
        await recv_message(ws2)

        await ws1.send(json.dumps({"type": "subscribe", "channel": "system"}))
        await ws2.send(json.dumps({"type": "subscribe", "channel": "other"}))

        await ws1.send(json.dumps({
            "type": "broadcast",
            "channel": "system",
            "payload": {"notice": "only subscribers"},
        }))

        message = await recv_message(ws1)
        assert message["payload"] == {"notice": "only subscribers"}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), 0.2)


@pytest.mark.asyncio
async def test_channels_endpoint_lists_active_channels(ws_url, http_url, running_server):
    async with websockets.connect(ws_url) as ws:
        await recv_message(ws)
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await asyncio.sleep(0.1)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{http_url}/channels") as response:
                assert response.status == 200
                body = await response.json()
                channels = {
                    entry["name"]: entry["subscribers"]
                    for entry in body["channels"]
                }
                assert channels["alerts"] == 1


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint(ws_url, http_url, running_server):
    async with websockets.connect(ws_url) as ws:
        client_id = (await recv_message(ws))["payload"]["client_id"]
        await ws.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        await asyncio.sleep(0.1)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{http_url}/channels/chat/subscribers") as response:
                assert response.status == 200
                body = await response.json()
                assert body["name"] == "chat"
                assert body["subscribers"] == [client_id]


@pytest.mark.asyncio
async def test_disconnect_removes_from_channels(ws_url, running_server):
    ws = await websockets.connect(ws_url)
    await recv_message(ws)
    await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await asyncio.sleep(0.1)
    assert running_server.channels.count("alerts") == 1

    await ws.close()
    loop = asyncio.get_event_loop()
    deadline = loop.time() + 5.0
    while running_server.channels.count("alerts") != 0:
        if loop.time() >= deadline:
            raise AssertionError("channel membership not cleaned up after disconnect")
        await asyncio.sleep(0.01)
