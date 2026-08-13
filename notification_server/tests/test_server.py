import asyncio
import json
import urllib.request

import pytest
import pytest_asyncio
import websockets

from notification_server.server import NotificationServer


@pytest_asyncio.fixture
async def running_server(tmp_path):
    server = NotificationServer(
        host="localhost", port=0, storage_path=tmp_path / "events.jsonl"
    )
    await server.start()
    port = server._server.sockets[0].getsockname()[1]
    try:
        yield server, port
    finally:
        await server.stop()


async def connect(port):
    ws = await websockets.connect(f"ws://localhost:{port}")
    welcome = json.loads(await ws.recv())
    return ws, welcome


async def test_connect_assigns_unique_client_id(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, welcome2 = await connect(port)
    try:
        assert welcome1["type"] == "system"
        assert welcome1["payload"]["event"] == "connected"
        client_id1 = welcome1["payload"]["client_id"]
        client_id2 = welcome2["payload"]["client_id"]
        assert client_id1 != client_id2
        assert server.registry.count() == 2
    finally:
        await ws1.close()
        await ws2.close()


async def test_disconnect_removes_client(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    assert server.registry.count() == 1
    await ws.close()
    for _ in range(50):
        if server.registry.count() == 0:
            break
        await asyncio.sleep(0.05)
    assert server.registry.count() == 0


async def test_broadcast_reaches_all_connected_clients(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    try:
        await ws1.send(
            json.dumps({"type": "broadcast", "payload": {"text": "hello everyone"}})
        )
        msg1 = json.loads(await ws1.recv())
        msg2 = json.loads(await ws2.recv())
        assert msg1["type"] == "broadcast"
        assert msg1["payload"]["text"] == "hello everyone"
        assert msg2 == msg1
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_reaches_only_target(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, welcome2 = await connect(port)
    try:
        target_id = welcome2["payload"]["client_id"]
        await ws1.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": target_id, "content": {"text": "psst"}},
                }
            )
        )
        msg2 = json.loads(await ws2.recv())
        assert msg2["type"] == "direct"
        assert msg2["payload"]["content"] == {"text": "psst"}
        assert msg2["payload"]["sender_id"] == welcome1["payload"]["client_id"]

        # ws1 should not receive the direct message meant for ws2.
        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws1.recv(), timeout=0.2)
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_to_unknown_target_returns_error(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": "no-such-client", "content": {}},
                }
            )
        )
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_system_message_from_client_is_acknowledged(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "system", "payload": {"note": "ping"}}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "ack"
    finally:
        await ws.close()


async def test_invalid_json_returns_system_error(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send("not valid json")
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_health_endpoint_reports_connected_count(running_server):
    server, port = running_server

    def get_health():
        with urllib.request.urlopen(f"http://localhost:{port}/health") as resp:
            return resp.status, json.loads(resp.read())

    # urlopen is a blocking call; it must run off the event loop thread so
    # the server (running on that same loop) is free to accept and answer it.
    loop = asyncio.get_running_loop()

    status, body = await loop.run_in_executor(None, get_health)
    assert status == 200
    assert body == {"connected_clients": 0}

    ws, _ = await connect(port)
    try:
        status, body = await loop.run_in_executor(None, get_health)
        assert body == {"connected_clients": 1}
    finally:
        await ws.close()


async def test_events_are_persisted_to_flat_file(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "hi"}}))
    await ws.recv()
    await ws.close()
    for _ in range(50):
        events = server.storage.read_events()
        if any(e["event"] == "disconnect" for e in events):
            break
        await asyncio.sleep(0.05)

    events = server.storage.read_events()
    kinds = [e["event"] for e in events]
    assert "connect" in kinds
    assert "message" in kinds
    assert "disconnect" in kinds


def get_json(port, path):
    with urllib.request.urlopen(f"http://localhost:{port}{path}") as resp:
        return resp.status, json.loads(resp.read())


async def test_subscribe_acknowledges_and_registers_client(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"] == {"event": "subscribed", "channel": "alerts"}
        assert server.channels.subscribers("alerts") != set()
    finally:
        await ws.close()


async def test_subscribe_without_channel_returns_error(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_unsubscribe_removes_client_from_channel(running_server):
    server, port = running_server
    ws, welcome = await connect(port)
    try:
        client_id = welcome["payload"]["client_id"]
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws.recv()
        await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        reply = json.loads(await ws.recv())
        assert reply["payload"] == {"event": "unsubscribed", "channel": "alerts"}
        assert client_id not in server.channels.subscribers("alerts")
    finally:
        await ws.close()


async def test_channel_message_delivered_only_to_subscribers(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    ws3, _ = await connect(port)
    try:
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await ws2.recv()

        await ws1.send(
            json.dumps(
                {"type": "broadcast", "payload": {"channel": "alerts", "text": "fire!"}}
            )
        )
        msg1 = json.loads(await ws1.recv())
        assert msg1["type"] == "broadcast"
        assert msg1["payload"]["text"] == "fire!"
        assert msg1["payload"]["channel"] == "alerts"

        # ws2 (subscribed to a different channel) and ws3 (subscribed to
        # nothing) must not receive the channel-scoped message.
        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws2.recv(), timeout=0.2)
        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws3.recv(), timeout=0.2)
    finally:
        await ws1.close()
        await ws2.close()
        await ws3.close()


async def test_message_without_channel_still_broadcasts_to_all(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    try:
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()

        await ws2.send(json.dumps({"type": "broadcast", "payload": {"text": "hi all"}}))
        msg1 = json.loads(await ws1.recv())
        msg2 = json.loads(await ws2.recv())
        assert msg1["payload"]["text"] == "hi all"
        assert msg2 == msg1
    finally:
        await ws1.close()
        await ws2.close()


async def test_client_can_subscribe_to_multiple_channels(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, _ = await connect(port)
    try:
        client_id = welcome1["payload"]["client_id"]
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await ws1.recv()

        await ws2.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "chat", "text": "hey"}})
        )
        msg = json.loads(await ws1.recv())
        assert msg["payload"]["text"] == "hey"
        assert client_id in server.channels.subscribers("alerts")
        assert client_id in server.channels.subscribers("chat")
    finally:
        await ws1.close()
        await ws2.close()


async def test_disconnect_removes_client_from_all_channels(running_server):
    server, port = running_server
    ws, welcome = await connect(port)
    client_id = welcome["payload"]["client_id"]
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await ws.recv()
    assert client_id in server.channels.subscribers("alerts")

    await ws.close()
    for _ in range(50):
        if client_id not in server.channels.subscribers("alerts"):
            break
        await asyncio.sleep(0.05)
    assert client_id not in server.channels.subscribers("alerts")
    assert server.channels.channels() == {}


async def test_channels_endpoint_lists_active_channels_and_counts(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    try:
        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(None, get_json, port, "/channels")
        assert status == 200
        assert body == {"channels": []}

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws2.recv()
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await ws2.recv()

        status, body = await loop.run_in_executor(None, get_json, port, "/channels")
        assert status == 200
        assert body == {
            "channels": [
                {"name": "alerts", "subscriber_count": 2},
                {"name": "chat", "subscriber_count": 1},
            ]
        }
    finally:
        await ws1.close()
        await ws2.close()


async def test_channel_subscribers_endpoint_lists_subscriber_ids(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, welcome2 = await connect(port)
    try:
        client_id1 = welcome1["payload"]["client_id"]
        client_id2 = welcome2["payload"]["client_id"]
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws2.recv()

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, get_json, port, "/channels/alerts/subscribers"
        )
        assert status == 200
        assert body["channel"] == "alerts"
        assert sorted(body["subscribers"]) == sorted([client_id1, client_id2])
    finally:
        await ws1.close()
        await ws2.close()


async def test_channel_subscribers_endpoint_empty_for_unknown_channel(running_server):
    server, port = running_server
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, get_json, port, "/channels/does-not-exist/subscribers"
    )
    assert status == 200
    assert body == {"channel": "does-not-exist", "subscribers": []}
