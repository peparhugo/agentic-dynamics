import asyncio
import base64
import json

import pytest

from conftest import http_get, parse_http, recv_message, send_message
from notification_server import decode_frame, encode_frame


# ── Wire format ──────────────────────────────────────────────


def test_encode_decode_roundtrip():
    message = {"type": "system", "payload": {"client_id": "abc"}, "timestamp": "t"}
    assert decode_frame(encode_frame(message)) == message


def test_frame_is_base64_on_the_wire():
    frame = encode_frame({"type": "broadcast", "payload": {"x": 1}, "timestamp": "t"})
    # Re-encoding the frame should reproduce it, proving it is base64 text.
    assert base64.b64encode(base64.b64decode(frame)).decode("ascii") == frame


# ── Health endpoint ──────────────────────────────────────────


async def test_health_returns_zero_without_clients(server):
    app, port = server
    status, body = parse_http(await http_get(port))
    assert status == 200
    data = json.loads(body)
    assert data["connected_clients"] == 0
    assert app.registry.count() == 0


async def test_health_reflects_connected_clients(server, client_factory):
    _, port = server
    ws1 = await client_factory()
    ws2 = await client_factory()

    status, body = parse_http(await http_get(port))
    assert status == 200
    assert json.loads(body)["connected_clients"] == 2

    await ws1.close()
    # Give the server a moment to process the disconnect.
    await ws1.wait_closed()

    # Wait until the registry count drops to 1.
    app = server[0]
    for _ in range(100):
        if app.registry.count() == 1:
            break
        await asyncio.sleep(0.01)

    status, body = parse_http(await http_get(port))
    assert json.loads(body)["connected_clients"] == 1


# ── Connection lifecycle ─────────────────────────────────────


async def test_client_receives_unique_id_on_connect(server, client_factory):
    ws1 = await client_factory()
    ws2 = await client_factory()

    msg1 = await recv_message(ws1)
    msg2 = await recv_message(ws2)

    assert msg1["type"] == "system"
    assert msg1["payload"]["event"] == "connected"
    assert msg2["type"] == "system"
    assert msg2["payload"]["event"] == "connected"

    id1 = msg1["payload"]["client_id"]
    id2 = msg2["payload"]["client_id"]
    assert id1 and id2
    assert id1 != id2


async def test_disconnect_removes_client_from_registry(server, client_factory):
    app, _ = server
    ws = await client_factory()
    await recv_message(ws)

    assert app.registry.count() == 1

    await ws.close()
    await ws.wait_closed()

    for _ in range(100):
        if app.registry.count() == 0:
            break
        await asyncio.sleep(0.01)

    assert app.registry.count() == 0


# ── Broadcast ────────────────────────────────────────────────


async def test_broadcast_reaches_all_clients(server, client_factory):
    _, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()
    ws3 = await client_factory()

    await recv_message(ws1)
    await recv_message(ws2)
    await recv_message(ws3)

    await send_message(
        ws1, {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "x"}
    )

    for ws in (ws1, ws2, ws3):
        msg = await recv_message(ws)
        assert msg["type"] == "broadcast"
        assert msg["payload"]["text"] == "hello"
        assert "timestamp" in msg


# ── Direct messages ──────────────────────────────────────────


async def test_direct_message_reaches_only_target(server, client_factory):
    _, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()

    id1 = (await recv_message(ws1))["payload"]["client_id"]
    id2 = (await recv_message(ws2))["payload"]["client_id"]

    await send_message(
        ws1,
        {
            "type": "direct",
            "payload": {"to": id2, "message": "secret"},
            "timestamp": "x",
        },
    )

    msg = await recv_message(ws2)
    assert msg["type"] == "direct"
    assert msg["payload"]["from"] == id1
    assert msg["payload"]["message"] == "secret"

    # ws1 should receive nothing further for this direct message.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(recv_message(ws1), timeout=0.3)


async def test_direct_message_to_unknown_client_reports_error(server, client_factory):
    _, _ = server
    ws1 = await client_factory()
    await recv_message(ws1)

    await send_message(
        ws1,
        {"type": "direct", "payload": {"to": "does-not-exist"}, "timestamp": "x"},
    )

    msg = await recv_message(ws1)
    assert msg["type"] == "system"
    assert "error" in msg["payload"]


async def test_unsupported_message_type_reports_error(server, client_factory):
    _, _ = server
    ws = await client_factory()
    await recv_message(ws)

    await send_message(
        ws, {"type": "nonsense", "payload": {}, "timestamp": "x"}
    )

    msg = await recv_message(ws)
    assert msg["type"] == "system"
    assert "error" in msg["payload"]


async def test_invalid_base64_frame_reports_error(server, client_factory):
    _, _ = server
    ws = await client_factory()
    await recv_message(ws)

    await ws.send("!!! not valid base64 !!!")

    msg = await recv_message(ws)
    assert msg["type"] == "system"
    assert "error" in msg["payload"]


# ── Channels ─────────────────────────────────────────────────


async def _wait_for_channel(app, name, count):
    for _ in range(100):
        if app.channels.counts().get(name, 0) == count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"channel {name!r} never reached count {count}")


async def test_subscribe_receives_only_channel_broadcast(server, client_factory):
    app, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()
    await recv_message(ws1)
    await recv_message(ws2)

    await send_message(ws1, {"type": "subscribe", "payload": {"channel": "alerts"}})
    await _wait_for_channel(app, "alerts", 1)

    await send_message(
        ws2, {"type": "broadcast", "channel": "alerts", "payload": {"text": "hello"}}
    )

    msg = await recv_message(ws1)
    assert msg["type"] == "broadcast"
    assert msg["channel"] == "alerts"
    assert msg["payload"]["text"] == "hello"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(recv_message(ws2), timeout=0.3)


async def test_unsubscribe_stops_delivery(server, client_factory):
    app, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()
    await recv_message(ws1)
    await recv_message(ws2)

    await send_message(ws1, {"type": "subscribe", "payload": {"channel": "alerts"}})
    await _wait_for_channel(app, "alerts", 1)

    await send_message(ws1, {"type": "unsubscribe", "payload": {"channel": "alerts"}})
    await _wait_for_channel(app, "alerts", 0)

    await send_message(
        ws2, {"type": "broadcast", "channel": "alerts", "payload": {"text": "gone"}}
    )

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(recv_message(ws1), timeout=0.3)


async def test_client_can_subscribe_to_multiple_channels(server, client_factory):
    app, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()
    await recv_message(ws1)
    await recv_message(ws2)

    await send_message(ws1, {"type": "subscribe", "channel": "alerts"})
    await send_message(ws1, {"type": "subscribe", "channel": "chat"})
    await _wait_for_channel(app, "alerts", 1)
    await _wait_for_channel(app, "chat", 1)

    await send_message(
        ws2, {"type": "broadcast", "channel": "alerts", "payload": {"text": "a"}}
    )
    await send_message(
        ws2, {"type": "broadcast", "channel": "chat", "payload": {"text": "c"}}
    )

    msg_a = await recv_message(ws1)
    msg_c = await recv_message(ws1)
    assert msg_a["payload"]["text"] == "a"
    assert msg_c["payload"]["text"] == "c"


async def test_broadcast_without_channel_still_reaches_all(server, client_factory):
    app, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()
    await recv_message(ws1)
    await recv_message(ws2)

    await send_message(ws1, {"type": "subscribe", "payload": {"channel": "alerts"}})
    await _wait_for_channel(app, "alerts", 1)

    await send_message(ws1, {"type": "broadcast", "payload": {"text": "all"}})

    for ws in (ws1, ws2):
        msg = await recv_message(ws)
        assert msg["type"] == "broadcast"
        assert msg["payload"]["text"] == "all"


async def test_channels_endpoint_lists_counts(server, client_factory):
    app, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()
    ws3 = await client_factory()
    await recv_message(ws1)
    await recv_message(ws2)
    await recv_message(ws3)

    await send_message(ws1, {"type": "subscribe", "payload": {"channel": "alerts"}})
    await send_message(ws2, {"type": "subscribe", "payload": {"channel": "alerts"}})
    await send_message(ws3, {"type": "subscribe", "payload": {"channel": "chat"}})
    await _wait_for_channel(app, "alerts", 2)
    await _wait_for_channel(app, "chat", 1)

    _, port = server
    status, body = parse_http(await http_get(port, "/channels"))
    assert status == 200
    data = json.loads(body)
    assert data == {"alerts": 2, "chat": 1}


async def test_channel_subscribers_endpoint_lists_ids(server, client_factory):
    app, _ = server
    ws1 = await client_factory()
    ws2 = await client_factory()
    id1 = (await recv_message(ws1))["payload"]["client_id"]
    await recv_message(ws2)

    await send_message(ws1, {"type": "subscribe", "payload": {"channel": "alerts"}})
    await _wait_for_channel(app, "alerts", 1)

    _, port = server
    status, body = parse_http(await http_get(port, "/channels/alerts/subscribers"))
    assert status == 200
    data = json.loads(body)
    assert data == [id1]
