"""Tests for the WebSocket-based notification server."""

import asyncio
import json
from datetime import datetime

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from server import NotificationServer, make_message


# ── helpers ────────────────────────────────────────────────────


async def http_get(host: str, port: int, path: str = "/health") -> str:
    """Issue a minimal HTTP/1.1 GET and return the raw response text."""
    reader, writer = await asyncio.open_connection(host, port)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    writer.write(request.encode("ascii"))
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    return raw.decode("utf-8", "replace")


def parse_health(raw: str) -> dict:
    status_line, _, body = raw.partition("\r\n\r\n")
    assert status_line.split(" ")[1] == "200", status_line
    return json.loads(body)


# ── fixtures ───────────────────────────────────────────────────


@pytest_asyncio.fixture
async def server():
    srv = NotificationServer(port=0)
    await srv.start()
    yield srv
    await srv.stop()


@pytest_asyncio.fixture
async def base_uri(server):
    return f"ws://{server.host}:{server.bound_port}"


@pytest_asyncio.fixture
async def health_url(server):
    return f"{server.host}:{server.bound_port}"


async def recv_json(ws):
    return json.loads(await ws.recv())


# ── message format ─────────────────────────────────────────────


def test_make_message_has_canonical_shape():
    msg = make_message("system", {"hello": "world"})
    assert set(msg) == {"type", "payload", "timestamp"}
    assert msg["type"] == "system"
    assert msg["payload"] == {"hello": "world"}
    assert isinstance(msg["timestamp"], str)
    datetime.fromisoformat(msg["timestamp"])


def test_make_message_supports_all_types():
    for msg_type in ("broadcast", "direct", "system"):
        assert make_message(msg_type, {})["type"] == msg_type


def test_make_message_rejects_unknown_type():
    with pytest.raises(ValueError):
        make_message("teleport", {})


# ── connection lifecycle ───────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_assigns_unique_client_ids(base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        msg_a = await recv_json(a)
        msg_b = await recv_json(b)
        assert msg_a["type"] == "system"
        assert msg_b["type"] == "system"
        id_a = msg_a["payload"]["client_id"]
        id_b = msg_b["payload"]["client_id"]
        assert id_a != id_b
        assert isinstance(id_a, str) and id_a
        assert isinstance(id_b, str) and id_b


@pytest.mark.asyncio
async def test_client_count_tracks_connections(server, base_uri):
    assert await server.client_count() == 0
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        assert await server.client_count() == 2
    await asyncio.sleep(0.1)
    assert await server.client_count() == 0


@pytest.mark.asyncio
async def test_disconnect_removes_client(base_uri, server):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        assert await server.client_count() == 2
    await asyncio.sleep(0.1)
    assert await server.client_count() == 0


# ── broadcast ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_broadcast_reaches_all_clients(base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        await a.send(
            json.dumps({"type": "broadcast", "payload": {"message": "hello"}})
        )
        msg_a = await recv_json(a)
        msg_b = await recv_json(b)
        assert msg_a["type"] == "broadcast"
        assert msg_b["type"] == "broadcast"
        assert msg_a["payload"]["message"] == "hello"
        assert msg_b["payload"]["message"] == "hello"
        assert msg_a["timestamp"] == msg_b["timestamp"]


@pytest.mark.asyncio
async def test_server_broadcast_api_delivers_to_all(server, base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        sent = await server.broadcast({"message": "announcement"})
        assert sent == 2
        msg_a = await recv_json(a)
        msg_b = await recv_json(b)
        assert msg_a["type"] == "broadcast"
        assert msg_b["payload"] == {"message": "announcement"}


# ── direct messages ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_direct_message_delivers_to_target(base_uri):
    async with connect(base_uri) as a, connect(base_uri) as b:
        msg_a = await recv_json(a)
        msg_b = await recv_json(b)
        id_a = msg_a["payload"]["client_id"]
        id_b = msg_b["payload"]["client_id"]

        await a.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"to": id_b, "message": "hi b"},
                }
            )
        )
        received = await recv_json(b)
        assert received["type"] == "direct"
        assert received["payload"]["message"] == "hi b"
        assert received["payload"]["from"] == id_a
        assert received["payload"]["to"] == id_b


@pytest.mark.asyncio
async def test_direct_to_unknown_target_returns_error(base_uri):
    async with connect(base_uri) as a:
        await recv_json(a)
        await a.send(
            json.dumps(
                {"type": "direct", "payload": {"to": "client-999", "message": "x"}}
            )
        )
        error = await recv_json(a)
        assert error["type"] == "system"
        assert "unknown target" in error["payload"]["error"]


@pytest.mark.asyncio
async def test_direct_without_target_returns_error(base_uri):
    async with connect(base_uri) as a:
        await recv_json(a)
        await a.send(json.dumps({"type": "direct", "payload": {"message": "x"}}))
        error = await recv_json(a)
        assert error["type"] == "system"
        assert "target" in error["payload"]["error"]


# ── malformed input ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_json_returns_error(base_uri):
    async with connect(base_uri) as a:
        await recv_json(a)
        await a.send("this is not json")
        error = await recv_json(a)
        assert error["type"] == "system"
        assert "invalid JSON" in error["payload"]["error"]


@pytest.mark.asyncio
async def test_unsupported_message_type_returns_error(base_uri):
    async with connect(base_uri) as a:
        await recv_json(a)
        await a.send(json.dumps({"type": "teleport", "payload": {}}))
        error = await recv_json(a)
        assert error["type"] == "system"
        assert "unsupported message type" in error["payload"]["error"]


# ── health endpoint ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_reports_zero_clients(health_url):
    raw = await http_get(*health_url.split(":"))
    body = parse_health(raw)
    assert body["status"] == "ok"
    assert body["clients"] == 0
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_health_reports_connected_client_count(server, base_uri, health_url):
    async with connect(base_uri) as a, connect(base_uri) as b:
        await recv_json(a)
        await recv_json(b)
        raw = await http_get(*health_url.split(":"))
        assert parse_health(raw)["clients"] == 2
    await asyncio.sleep(0.1)
    raw = await http_get(*health_url.split(":"))
    assert parse_health(raw)["clients"] == 0
