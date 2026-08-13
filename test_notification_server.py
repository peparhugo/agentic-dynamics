import asyncio
import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from notification_server import (
    BROADCAST,
    DIRECT,
    SUBSCRIBE,
    SYSTEM,
    UNSUBSCRIBE,
    NotificationServer,
    build_message,
)

@pytest_asyncio.fixture
async def server(tmp_path):
    srv = NotificationServer(
        host="127.0.0.1",
        port=0,
        log_path=tmp_path / "events.jsonl",
    )
    await srv.start()
    try:
        yield srv
    finally:
        await srv.close()


async def open_client(server):
    ws = await connect(f"ws://127.0.0.1:{server.port}")
    welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    return ws, welcome


async def http_get(port, path="/health"):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    data = await reader.read()
    writer.close()
    await writer.wait_closed()
    return data


# -- message format -----------------------------------------------------


def test_build_message_format():
    msg = build_message(BROADCAST, {"text": "hello"})
    assert set(msg) == {"type", "payload", "timestamp"}
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"text": "hello"}
    assert isinstance(msg["timestamp"], str) and msg["timestamp"]


# -- connection lifecycle -------------------------------------------------


async def test_client_gets_system_welcome_with_unique_id(server):
    ws, welcome = await open_client(server)
    assert welcome["type"] == SYSTEM
    assert welcome["payload"]["event"] == "connected"
    client_id = welcome["payload"]["client_id"]
    assert isinstance(client_id, str) and len(client_id) == 32
    await ws.close()


async def test_each_client_gets_unique_id(server):
    ws1, welcome1 = await open_client(server)
    ws2, welcome2 = await open_client(server)
    assert welcome1["payload"]["client_id"] != welcome2["payload"]["client_id"]
    await ws1.close()
    await ws2.close()


async def test_disconnect_clean_removal(server):
    ws, _ = await open_client(server)
    assert server.registry.count() == 1
    await ws.close()
    for _ in range(50):
        if server.registry.count() == 0:
            break
        await asyncio.sleep(0.05)
    assert server.registry.count() == 0


# -- broadcasting -----------------------------------------------------------


async def test_broadcast_delivered_to_all_clients(server):
    ws_a, _ = await open_client(server)
    ws_b, _ = await open_client(server)
    ws_c, _ = await open_client(server)

    await ws_a.send(json.dumps({
        "type": BROADCAST,
        "payload": {"text": "hello everyone"},
    }))

    received = []
    for ws in (ws_a, ws_b, ws_c):
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        received.append(msg)
    for msg in received:
        assert msg["type"] == BROADCAST
        assert msg["payload"]["text"] == "hello everyone"
    assert len({msg["payload"]["sender"] for msg in received}) == 1

    for ws in (ws_a, ws_b, ws_c):
        await ws.close()


async def test_server_broadcast_api(server):
    ws_a, _ = await open_client(server)
    ws_b, _ = await open_client(server)
    assert await server.broadcast({"text": "from server"}) == 2
    for ws in (ws_a, ws_b):
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == BROADCAST
        assert msg["payload"]["text"] == "from server"
    await ws_a.close()
    await ws_b.close()


# -- direct messages ------------------------------------------------------


async def test_direct_message_only_to_target(server):
    ws_a, welcome_a = await open_client(server)
    ws_b, welcome_b = await open_client(server)
    id_b = welcome_b["payload"]["client_id"]

    await ws_a.send(json.dumps({
        "type": DIRECT,
        "payload": {"target": id_b, "text": "only you"},
    }))

    msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
    assert msg["type"] == DIRECT
    assert msg["payload"]["text"] == "only you"
    assert msg["payload"]["target"] == id_b

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws_a.recv(), timeout=0.3)

    await ws_a.close()
    await ws_b.close()


async def test_direct_unknown_target_returns_false(server):
    ws, _ = await open_client(server)
    await ws.close()
    for _ in range(50):
        if server.registry.count() == 0:
            break
        await asyncio.sleep(0.05)
    assert await server.send_direct("does-not-exist", {"text": "x"}) is False


# -- health endpoint -----------------------------------------------------


async def test_health_returns_connected_count(server):
    ws1, _ = await open_client(server)
    ws2, _ = await open_client(server)

    raw = await http_get(server.port, "/health")
    status = raw.split(b" ", 2)[1].decode()
    body = raw.split(b"\r\n\r\n", 1)[1]
    payload = json.loads(body)
    assert status == "200"
    assert payload["status"] == "ok"
    assert payload["connected_clients"] == 2

    await ws1.close()
    await ws2.close()
    for _ in range(50):
        if server.registry.count() == 0:
            break
        await asyncio.sleep(0.05)

    raw = await http_get(server.port, "/health")
    body = raw.split(b"\r\n\r\n", 1)[1]
    assert json.loads(body)["connected_clients"] == 0


# -- flat-file persistence -------------------------------------------------


async def test_events_persisted_to_flat_file(server, tmp_path):
    ws, welcome = await open_client(server)
    client_id = welcome["payload"]["client_id"]
    await ws.close()
    for _ in range(50):
        if server.registry.count() == 0:
            break
        await asyncio.sleep(0.05)

    log_file = tmp_path / "events.jsonl"
    assert log_file.exists()
    records = [json.loads(line) for line in log_file.read_text().splitlines()]
    events = [r["event"] for r in records]
    assert "connected" in events
    assert "disconnected" in events
    assert any(
        r["event"] == "connected" and r["data"]["client_id"] == client_id
        for r in records
    )


# -- channel subscriptions --------------------------------------------------


async def test_subscribe_receives_channel_messages(server):
    ws_alerts, _ = await open_client(server)
    ws_system, _ = await open_client(server)
    ws_bystander, _ = await open_client(server)

    await ws_alerts.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channel": "alerts"},
    }))
    await ws_system.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channels": ["alerts", "system"]},
    }))
    await asyncio.sleep(0.05)

    await ws_alerts.send(json.dumps({
        "type": BROADCAST,
        "channel": "alerts",
        "payload": {"text": "fire in the datacenter"},
    }))

    received_alerts = json.loads(await asyncio.wait_for(ws_alerts.recv(), timeout=5))
    received_system = json.loads(await asyncio.wait_for(ws_system.recv(), timeout=5))
    assert received_alerts["payload"]["text"] == "fire in the datacenter"
    assert received_system["payload"]["text"] == "fire in the datacenter"
    assert received_alerts["type"] == BROADCAST

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws_bystander.recv(), timeout=0.3)

    for ws in (ws_alerts, ws_system, ws_bystander):
        await ws.close()


async def test_message_without_channel_still_broadcasts(server):
    ws_a, _ = await open_client(server)
    ws_b, _ = await open_client(server)

    await ws_a.send(json.dumps({
        "type": SUBSCRIBE,
        "channel": "chat",
    }))

    await ws_b.send(json.dumps({
        "type": BROADCAST,
        "payload": {"text": "no channel -> everyone"},
    }))

    for ws in (ws_a, ws_b):
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["payload"]["text"] == "no channel -> everyone"

    await ws_a.close()
    await ws_b.close()


async def test_channel_messages_not_delivered_to_other_channel(server):
    ws_alerts, _ = await open_client(server)
    ws_chat, _ = await open_client(server)

    await ws_alerts.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channel": "alerts"},
    }))
    await ws_chat.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channel": "chat"},
    }))
    await asyncio.sleep(0.05)

    await ws_alerts.send(json.dumps({
        "type": BROADCAST,
        "channel": "alerts",
        "payload": {"text": "alert only"},
    }))

    msg = json.loads(await asyncio.wait_for(ws_alerts.recv(), timeout=5))
    assert msg["payload"]["text"] == "alert only"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws_chat.recv(), timeout=0.3)

    await ws_alerts.close()
    await ws_chat.close()


async def test_unsubscribe_stops_delivery(server):
    ws_a, _ = await open_client(server)
    ws_b, _ = await open_client(server)

    await ws_a.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channel": "alerts"},
    }))
    await ws_b.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channel": "alerts"},
    }))
    await ws_a.send(json.dumps({
        "type": UNSUBSCRIBE,
        "payload": {"channel": "alerts"},
    }))
    await asyncio.sleep(0.05)

    await ws_b.send(json.dumps({
        "type": BROADCAST,
        "channel": "alerts",
        "payload": {"text": "post-unsubscribe"},
    }))

    msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
    assert msg["payload"]["text"] == "post-unsubscribe"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws_a.recv(), timeout=0.3)

    await ws_a.close()
    await ws_b.close()


async def test_client_can_subscribe_to_multiple_channels(server):
    ws, _ = await open_client(server)

    await ws.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channels": ["alerts", "system"]},
    }))
    await asyncio.sleep(0.05)

    assert server.channel_subscribers("alerts")
    assert server.channel_snapshot()["alerts"]
    assert server.channel_snapshot()["system"]

    await ws.close()


async def test_disconnect_removes_from_channels(server):
    ws, welcome = await open_client(server)
    client_id = welcome["payload"]["client_id"]

    await ws.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channel": "alerts"},
    }))
    await asyncio.sleep(0.05)
    assert client_id in server.channel_subscribers("alerts")

    await ws.close()
    for _ in range(50):
        if server.registry.count() == 0:
            break
        await asyncio.sleep(0.05)

    assert server.channels.has("alerts") is False


async def test_get_channels_endpoint(server):
    ws, _ = await open_client(server)
    await ws.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channels": ["alerts", "system"]},
    }))
    await asyncio.sleep(0.05)

    raw = await http_get(server.port, "/channels")
    status = raw.split(b" ", 2)[1].decode()
    body = raw.split(b"\r\n\r\n", 1)[1]
    payload = json.loads(body)
    assert status == "200"
    assert payload["count"] == 2
    by_name = {c["name"]: c for c in payload["channels"]}
    assert by_name["alerts"]["subscribers"] == 1
    assert by_name["system"]["subscribers"] == 1

    await ws.close()


async def test_get_channel_subscribers_endpoint(server):
    ws, welcome = await open_client(server)
    client_id = welcome["payload"]["client_id"]
    await ws.send(json.dumps({
        "type": SUBSCRIBE,
        "payload": {"channel": "alerts"},
    }))
    await asyncio.sleep(0.05)

    raw = await http_get(server.port, "/channels/alerts/subscribers")
    status = raw.split(b" ", 2)[1].decode()
    body = raw.split(b"\r\n\r\n", 1)[1]
    payload = json.loads(body)
    assert status == "200"
    assert payload["channel"] == "alerts"
    assert payload["subscribers"] == [client_id]

    await ws.close()
