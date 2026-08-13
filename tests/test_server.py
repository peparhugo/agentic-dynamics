import asyncio
import json

import aiohttp
import pytest
import websockets


async def recv_json(ws, timeout=2):
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


async def connect_and_get_id(uri):
    ws = await websockets.connect(uri)
    welcome = await recv_json(ws)
    assert welcome["type"] == "system"
    assert welcome["payload"]["event"] == "connected"
    return ws, welcome["payload"]["client_id"]


async def test_client_receives_unique_id_on_connect(running_server):
    _, uri, _ = running_server
    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        assert id1 != id2
        assert isinstance(id1, str) and id1
    finally:
        await ws1.close()
        await ws2.close()


async def test_health_endpoint_reports_connected_count(running_server):
    notification_server, uri, health_url = running_server

    async with aiohttp.ClientSession() as session:
        async with session.get(health_url) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["connected_clients"] == 0

        ws1, _ = await connect_and_get_id(uri)
        ws2, _ = await connect_and_get_id(uri)
        try:
            # give the registry a moment to settle (connections are already
            # registered synchronously before the welcome message is sent).
            async with session.get(health_url) as resp:
                data = await resp.json()
                assert data["connected_clients"] == 2
        finally:
            await ws1.close()
            await ws2.close()


async def test_broadcast_reaches_all_connected_clients(running_server):
    _, uri, _ = running_server
    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    ws3, id3 = await connect_and_get_id(uri)
    try:
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "hello everyone"}}))

        for ws in (ws1, ws2, ws3):
            msg = await recv_json(ws)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello everyone"
            assert msg["payload"]["from"] == id1
    finally:
        await ws1.close()
        await ws2.close()
        await ws3.close()


async def test_direct_message_delivered_only_to_target(running_server):
    _, uri, _ = running_server
    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    ws3, id3 = await connect_and_get_id(uri)
    try:
        await ws1.send(json.dumps({"type": "direct", "payload": {"target": id2, "text": "psst"}}))

        msg = await recv_json(ws2)
        assert msg["type"] == "direct"
        assert msg["payload"]["from"] == id1
        assert msg["payload"]["text"] == "psst"

        # ws3 should not receive anything; recv should time out.
        with pytest.raises(asyncio.TimeoutError):
            await recv_json(ws3, timeout=0.3)
    finally:
        await ws1.close()
        await ws2.close()
        await ws3.close()


async def test_direct_message_unknown_target_returns_system_error(running_server):
    _, uri, _ = running_server
    ws1, _ = await connect_and_get_id(uri)
    try:
        await ws1.send(json.dumps({"type": "direct", "payload": {"target": "no-such-client"}}))
        msg = await recv_json(ws1)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]
    finally:
        await ws1.close()


async def test_direct_message_missing_target_returns_system_error(running_server):
    _, uri, _ = running_server
    ws1, _ = await connect_and_get_id(uri)
    try:
        await ws1.send(json.dumps({"type": "direct", "payload": {}}))
        msg = await recv_json(ws1)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]
    finally:
        await ws1.close()


async def test_invalid_message_gets_system_error_and_keeps_connection_open(running_server):
    _, uri, _ = running_server
    ws1, _ = await connect_and_get_id(uri)
    try:
        await ws1.send("not even json")
        msg = await recv_json(ws1)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]

        # connection should still be usable afterwards.
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "still alive"}}))
        msg2 = await recv_json(ws1)
        assert msg2["type"] == "broadcast"
        assert msg2["payload"]["text"] == "still alive"
    finally:
        await ws1.close()


async def subscribe(ws, channel):
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": channel}}))
    ack = await recv_json(ws)
    assert ack["type"] == "system"
    assert ack["payload"]["event"] == "subscribed"
    assert ack["payload"]["channel"] == channel
    return ack


async def unsubscribe(ws, channel):
    await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": channel}}))
    ack = await recv_json(ws)
    assert ack["type"] == "system"
    assert ack["payload"]["event"] == "unsubscribed"
    assert ack["payload"]["channel"] == channel
    return ack


async def test_subscribe_acknowledged(running_server):
    _, uri, _ = running_server
    ws, _ = await connect_and_get_id(uri)
    try:
        await subscribe(ws, "alerts")
    finally:
        await ws.close()


async def test_missing_channel_on_subscribe_returns_system_error(running_server):
    _, uri, _ = running_server
    ws, _ = await connect_and_get_id(uri)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
        msg = await recv_json(ws)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]
    finally:
        await ws.close()


async def test_missing_channel_on_unsubscribe_returns_system_error(running_server):
    _, uri, _ = running_server
    ws, _ = await connect_and_get_id(uri)
    try:
        await ws.send(json.dumps({"type": "unsubscribe", "payload": {}}))
        msg = await recv_json(ws)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]
    finally:
        await ws.close()


async def test_channel_message_delivered_only_to_subscribers(running_server):
    _, uri, _ = running_server
    ws1, id1 = await connect_and_get_id(uri)  # publisher, not subscribed
    ws2, id2 = await connect_and_get_id(uri)  # subscribed to alerts
    ws3, id3 = await connect_and_get_id(uri)  # not subscribed
    try:
        await subscribe(ws2, "alerts")

        await ws1.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "server is down"},
        }))

        msg = await recv_json(ws2)
        assert msg["type"] == "broadcast"
        assert msg["channel"] == "alerts"
        assert msg["payload"]["text"] == "server is down"
        assert msg["payload"]["from"] == id1

        with pytest.raises(asyncio.TimeoutError):
            await recv_json(ws1, timeout=0.3)
        with pytest.raises(asyncio.TimeoutError):
            await recv_json(ws3, timeout=0.3)
    finally:
        await ws1.close()
        await ws2.close()
        await ws3.close()


async def test_message_without_channel_still_broadcasts_to_all(running_server):
    _, uri, _ = running_server
    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        await subscribe(ws2, "alerts")

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "no channel here"}}))

        msg1 = await recv_json(ws1)
        msg2 = await recv_json(ws2)
        assert msg1["payload"]["text"] == "no channel here"
        assert msg2["payload"]["text"] == "no channel here"
    finally:
        await ws1.close()
        await ws2.close()


async def test_unsubscribe_stops_channel_delivery(running_server):
    _, uri, _ = running_server
    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        await subscribe(ws2, "alerts")
        await unsubscribe(ws2, "alerts")

        await ws1.send(json.dumps({
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "should not arrive"},
        }))

        with pytest.raises(asyncio.TimeoutError):
            await recv_json(ws2, timeout=0.3)
    finally:
        await ws1.close()
        await ws2.close()


async def test_client_can_subscribe_to_multiple_channels(running_server):
    _, uri, _ = running_server
    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        await subscribe(ws2, "alerts")
        await subscribe(ws2, "chat")

        await ws1.send(json.dumps({"type": "broadcast", "channel": "chat", "payload": {"text": "hi"}}))
        msg = await recv_json(ws2)
        assert msg["channel"] == "chat"
        assert msg["payload"]["text"] == "hi"
    finally:
        await ws1.close()
        await ws2.close()


async def test_channels_endpoint_lists_active_channels_and_counts(running_server):
    notification_server, uri, health_url = running_server
    channels_url = health_url.replace("/health", "/channels")

    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        await subscribe(ws1, "alerts")
        await subscribe(ws2, "alerts")
        await subscribe(ws2, "chat")

        async with aiohttp.ClientSession() as session:
            async with session.get(channels_url) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data == {"alerts": 2, "chat": 1}
    finally:
        await ws1.close()
        await ws2.close()


async def test_channels_endpoint_empty_when_no_subscriptions(running_server):
    _, _, health_url = running_server
    channels_url = health_url.replace("/health", "/channels")

    async with aiohttp.ClientSession() as session:
        async with session.get(channels_url) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data == {}


async def test_channel_subscribers_endpoint_lists_subscriber_ids(running_server):
    _, uri, health_url = running_server
    base = health_url.replace("/health", "")

    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        await subscribe(ws1, "alerts")
        await subscribe(ws2, "alerts")

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base}/channels/alerts/subscribers") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert sorted(data) == sorted([id1, id2])
    finally:
        await ws1.close()
        await ws2.close()


async def test_channel_subscribers_endpoint_unknown_channel_is_empty(running_server):
    _, _, health_url = running_server
    base = health_url.replace("/health", "")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base}/channels/does-not-exist/subscribers") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data == []


async def test_disconnect_removes_client_from_channel_subscriptions(running_server):
    notification_server, uri, health_url = running_server
    base = health_url.replace("/health", "")

    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        await subscribe(ws1, "alerts")
        await ws1.close()

        for _ in range(50):
            if id1 not in notification_server.channel_registry.subscribers("alerts"):
                break
            await asyncio.sleep(0.05)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base}/channels/alerts/subscribers") as resp:
                data = await resp.json()
                assert id1 not in data
    finally:
        await ws2.close()


async def test_disconnect_cleans_up_registry(running_server):
    notification_server, uri, health_url = running_server
    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)

    assert notification_server.registry.count() == 2

    await ws1.close()

    # the server needs a beat to notice the closed connection and clean up.
    for _ in range(50):
        if notification_server.registry.count() == 1:
            break
        await asyncio.sleep(0.05)

    assert notification_server.registry.count() == 1
    assert notification_server.registry.get(id1) is None
    assert notification_server.registry.get(id2) is not None

    notice = await recv_json(ws2)
    assert notice["type"] == "system"
    assert notice["payload"]["event"] == "disconnected"
    assert notice["payload"]["client_id"] == id1

    async with aiohttp.ClientSession() as session:
        async with session.get(health_url) as resp:
            data = await resp.json()
            assert data["connected_clients"] == 1

    await ws2.close()
