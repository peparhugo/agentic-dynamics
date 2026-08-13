"""Tests for the WebSocket-based notification server."""

import asyncio
import inspect
import json

import pytest
from websockets.asyncio.client import connect

from notification_server import NotificationApp, build_message

# All tests use asyncio_mode = auto (see pytest.ini).


@pytest.fixture
async def app():
    instance = NotificationApp()
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()


async def connect_client(app):
    """Open a websocket client and consume its connect notice."""
    ws = await connect(app.url)
    notice = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    assert notice["type"] == "system"
    assert notice["payload"]["event"] == "connect"
    return ws, notice["payload"]["client_id"]


async def http_get(app, path="/health"):
    """Issue a plain HTTP GET request to the server."""
    reader, writer = await asyncio.open_connection(app.host, app.port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: {app.host}\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    data = await reader.read()
    writer.close()
    await writer.wait_closed()
    raw = data.decode("utf-8", "replace")
    head, _, body = raw.partition("\r\n\r\n")
    status = int(head.split(" ")[1])
    return status, body


async def expect_no_message(ws, timeout=0.3):
    """Assert that no message arrives on *ws* within *timeout*."""
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws.recv(), timeout=timeout)


async def wait_for_condition(cond, timeout=3.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        result = cond()
        if inspect.isawaitable(result):
            result = await result
        if result:
            return True
        await asyncio.sleep(0.02)
    return False


async def count_is(app, expected):
    return await app.notifier.registry.count() == expected


# ── Connect & identity ────────────────────────────────────────────────


async def test_connect_assigns_unique_ids(app):
    ws_a, id_a = await connect_client(app)
    ws_b, id_b = await connect_client(app)
    try:
        assert isinstance(id_a, str) and id_a
        assert isinstance(id_b, str) and id_b
        assert id_a != id_b
        assert await app.notifier.registry.count() == 2
        assert set(await app.notifier.registry.ids()) == {id_a, id_b}
    finally:
        await ws_a.close()
        await ws_b.close()


async def test_connect_notice_reports_count(app):
    ws_a, id_a = await connect_client(app)
    ws_b, id_b = await connect_client(app)
    try:
        assert id_a == "1"
        assert id_b == "2"
    finally:
        await ws_a.close()
        await ws_b.close()


# ── Message format ────────────────────────────────────────────────────


async def test_message_format_contract(app):
    ws, _ = await connect_client(app)
    try:
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert set(msg.keys()) == {"type", "payload", "timestamp"}
        assert msg["type"] == "broadcast"
        assert isinstance(msg["payload"], dict)
        assert isinstance(msg["timestamp"], str)
        from datetime import datetime

        datetime.fromisoformat(msg["timestamp"])
    finally:
        await ws.close()


async def test_build_message_helper():
    msg = build_message("system", {"hello": "world"})
    assert msg["type"] == "system"
    assert msg["payload"] == {"hello": "world"}
    assert isinstance(msg["timestamp"], str)


# ── Broadcast ─────────────────────────────────────────────────────────


async def test_broadcast_reaches_all_connected_clients(app):
    ws_a, _ = await connect_client(app)
    ws_b, _ = await connect_client(app)
    ws_c, _ = await connect_client(app)
    try:
        payload = {"text": "hello everyone", "n": 3}
        await ws_a.send(json.dumps({"type": "broadcast", "payload": payload}))
        for ws in (ws_a, ws_b, ws_c):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == payload
    finally:
        await ws_a.close()
        await ws_b.close()
        await ws_c.close()


async def test_broadcast_from_two_clients(app):
    ws_a, _ = await connect_client(app)
    ws_b, _ = await connect_client(app)
    try:
        await ws_a.send(json.dumps({"type": "broadcast", "payload": {"from": "a"}}))
        await ws_b.send(json.dumps({"type": "broadcast", "payload": {"from": "b"}}))
        seen_a = {
            json.loads(await asyncio.wait_for(ws_a.recv(), timeout=5))["payload"]["from"]
            for _ in range(2)
        }
        seen_b = {
            json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))["payload"]["from"]
            for _ in range(2)
        }
        assert seen_a == {"a", "b"}
        assert seen_b == {"a", "b"}
    finally:
        await ws_a.close()
        await ws_b.close()


# ── Direct messages ───────────────────────────────────────────────────


async def test_direct_message_to_specific_client(app):
    ws_a, id_a = await connect_client(app)
    ws_b, id_b = await connect_client(app)
    try:
        payload = {"text": "private note"}
        await ws_a.send(
            json.dumps({"type": "direct", "target_id": id_b, "payload": payload})
        )
        msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
        assert msg["type"] == "direct"
        assert msg["payload"] == payload
        # The sender must not receive its own direct message.
        await expect_no_message(ws_a)
    finally:
        await ws_a.close()
        await ws_b.close()


async def test_direct_to_unknown_target_errors(app):
    ws, _ = await connect_client(app)
    try:
        await ws.send(
            json.dumps(
                {"type": "direct", "target_id": "nope", "payload": {"x": 1}}
            )
        )
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "error"
        assert "not found" in msg["payload"]["message"]
    finally:
        await ws.close()


async def test_direct_without_target_id_errors(app):
    ws, _ = await connect_client(app)
    try:
        await ws.send(json.dumps({"type": "direct", "payload": {"x": 1}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "error"
    finally:
        await ws.close()


# ── Disconnect ────────────────────────────────────────────────────────


async def test_client_disconnect_clean_removal(app):
    ws_a, id_a = await connect_client(app)
    ws_b, _ = await connect_client(app)
    try:
        assert await app.notifier.registry.count() == 2

        await ws_a.close()

        # Client B is notified about the disconnect.
        msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "disconnect"
        assert msg["payload"]["client_id"] == id_a
        assert msg["payload"]["connected_clients"] == 1

        removed = await wait_for_condition(lambda: count_is(app, 1))
        assert removed
        assert id_a not in await app.notifier.registry.ids()
        assert await app.notifier.registry.count() == 1
    finally:
        await ws_a.close()
        await ws_b.close()


# ── REST /health ──────────────────────────────────────────────────────


async def test_health_reports_connected_count(app):
    status, body = await http_get(app)
    assert status == 200
    payload = json.loads(body)
    assert payload["status"] == "ok"
    assert payload["connected_clients"] == 0

    ws_a, _ = await connect_client(app)
    ws_b, _ = await connect_client(app)
    try:
        status, body = await http_get(app)
        assert status == 200
        assert json.loads(body)["connected_clients"] == 2
    finally:
        await ws_a.close()
        await ws_b.close()


async def test_health_after_disconnect(app):
    ws_a, _ = await connect_client(app)
    ws_b, _ = await connect_client(app)
    await ws_a.close()
    await ws_b.close()
    ok = await wait_for_condition(lambda: count_is(app, 0))
    assert ok
    status, body = await http_get(app)
    assert status == 200
    assert json.loads(body)["connected_clients"] == 0


# ── Bad input handling ────────────────────────────────────────────────


async def test_invalid_json_gets_error_response(app):
    ws, _ = await connect_client(app)
    try:
        await ws.send("{not valid json!!")
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_unsupported_message_type_gets_error(app):
    ws, _ = await connect_client(app)
    try:
        await ws.send(json.dumps({"type": "teleport", "payload": {}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "error"
        assert "teleport" in msg["payload"]["message"]
    finally:
        await ws.close()


async def test_client_submitted_system_messages_are_ignored(app):
    ws, _ = await connect_client(app)
    try:
        await ws.send(json.dumps({"type": "system", "payload": {"spoof": True}}))
        await expect_no_message(ws)
    finally:
        await ws.close()
