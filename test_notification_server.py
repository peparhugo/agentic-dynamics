import asyncio
import http.client
import json
import socket

import pytest
import websockets

from notification_server import NotificationServer, make_message


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


@pytest.fixture
async def server():
    srv = NotificationServer(host="localhost", port=free_port())
    await srv.start()
    yield srv
    await srv.stop()


async def connect(srv):
    return await websockets.connect(f"ws://{srv.host}:{srv.port}")


async def recv_json(ws, timeout=2):
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


def http_get(host, port, path, timeout=2):
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, json.loads(body)
    finally:
        conn.close()


# ── Connection lifecycle ─────────────────────────────────────────


async def test_client_receives_unique_id_on_connect(server):
    ws = await connect(server)
    try:
        welcome = await recv_json(ws)
        assert welcome["type"] == "system"
        assert welcome["payload"]["event"] == "connected"
        assert "client_id" in welcome["payload"]
    finally:
        await ws.close()


async def test_two_clients_get_different_ids(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        welcome1 = await recv_json(ws1)
        # ws2 sees its own welcome plus a "client_joined" notice is sent to ws1
        welcome2 = await recv_json(ws2)
        joined_notice = await recv_json(ws1)

        id1 = welcome1["payload"]["client_id"]
        id2 = welcome2["payload"]["client_id"]
        assert id1 != id2
        assert joined_notice["payload"]["event"] == "client_joined"
        assert joined_notice["payload"]["client_id"] == id2
    finally:
        await ws1.close()
        await ws2.close()


async def test_disconnect_removes_client_cleanly(server):
    ws1 = await connect(server)
    await recv_json(ws1)  # welcome

    ws2 = await connect(server)
    await recv_json(ws2)  # ws2 welcome
    await recv_json(ws1)  # ws1 sees join notice

    assert server.registry.count() == 2

    await ws2.close()
    # give the server a moment to process the close and broadcast client_left
    left_notice = await recv_json(ws1)
    assert left_notice["payload"]["event"] == "client_left"

    assert server.registry.count() == 1
    await ws1.close()


# ── Broadcast ─────────────────────────────────────────────────────


async def test_broadcast_reaches_all_connected_clients(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    ws3 = await connect(server)
    try:
        await recv_json(ws1)  # welcome
        await recv_json(ws2)  # welcome
        await recv_json(ws1)  # join notice for ws2
        await recv_json(ws3)  # welcome
        await recv_json(ws1)  # join notice for ws3
        await recv_json(ws2)  # join notice for ws3

        msg = {"type": "broadcast", "payload": {"text": "hello everyone"}}
        await ws1.send(json.dumps(msg))

        got1 = await recv_json(ws1)
        got2 = await recv_json(ws2)
        got3 = await recv_json(ws3)

        for got in (got1, got2, got3):
            assert got["type"] == "broadcast"
            assert got["payload"] == {"text": "hello everyone"}
            assert "timestamp" in got
    finally:
        await ws1.close()
        await ws2.close()
        await ws3.close()


# ── Direct messages ───────────────────────────────────────────────


async def test_direct_message_delivered_to_target_only(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        welcome1 = await recv_json(ws1)
        welcome2 = await recv_json(ws2)
        await recv_json(ws1)  # join notice for ws2

        target_id = welcome2["payload"]["client_id"]
        msg = {
            "type": "direct",
            "payload": {"target": target_id, "data": {"text": "psst"}},
        }
        await ws1.send(json.dumps(msg))

        got = await recv_json(ws2)
        assert got["type"] == "direct"
        assert got["payload"]["data"] == {"text": "psst"}
        assert got["payload"]["from"] == welcome1["payload"]["client_id"]

        # ws1 should NOT receive the direct message meant for ws2
        with pytest.raises(asyncio.TimeoutError):
            await recv_json(ws1, timeout=0.3)
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_to_unknown_client_returns_error(server):
    ws1 = await connect(server)
    try:
        await recv_json(ws1)  # welcome
        msg = {
            "type": "direct",
            "payload": {"target": "does-not-exist", "data": {"text": "hi"}},
        }
        await ws1.send(json.dumps(msg))

        got = await recv_json(ws1)
        assert got["type"] == "system"
        assert "not found" in got["payload"]["error"]
    finally:
        await ws1.close()


# ── System messages ───────────────────────────────────────────────


async def test_client_sending_system_message_is_rejected(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "system", "payload": {"foo": "bar"}}))
        got = await recv_json(ws)
        assert got["type"] == "system"
        assert "error" in got["payload"]
    finally:
        await ws.close()


# ── Malformed input ───────────────────────────────────────────────


async def test_invalid_json_gets_error_response(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send("not json")
        got = await recv_json(ws)
        assert got["type"] == "system"
        assert "error" in got["payload"]
    finally:
        await ws.close()


async def test_unsupported_type_gets_error_response(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "not-a-type", "payload": {}}))
        got = await recv_json(ws)
        assert got["type"] == "system"
        assert "error" in got["payload"]
    finally:
        await ws.close()


# ── REST /health ──────────────────────────────────────────────────


async def test_health_endpoint_reports_zero_with_no_clients(server):
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/health"
    )
    assert status == 200
    assert body["connected_clients"] == 0


async def test_health_endpoint_reports_connected_count(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        await recv_json(ws1)
        await recv_json(ws2)
        await recv_json(ws1)  # join notice

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/health"
        )
        assert status == 200
        assert body["connected_clients"] == 2
    finally:
        await ws1.close()
        await ws2.close()


async def test_health_endpoint_reflects_disconnect(server):
    ws1 = await connect(server)
    await recv_json(ws1)
    await ws1.close()
    await asyncio.sleep(0.2)  # allow server to process the close

    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/health"
    )
    assert status == 200
    assert body["connected_clients"] == 0


# ── Message helpers ───────────────────────────────────────────────


def test_make_message_shape():
    msg = make_message("broadcast", {"a": 1})
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"a": 1}
    assert "timestamp" in msg and isinstance(msg["timestamp"], str)
