"""Tests for the /history REST endpoint and message expiry."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
from websockets.asyncio.client import connect

from server import NotificationServer


async def http_get(host: str, port: int, path: str) -> str:
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


def parse_json(raw: str) -> dict:
    status_line, _, body = raw.partition("\r\n\r\n")
    assert status_line.split(" ")[1] == "200", status_line
    return json.loads(body)


async def recv_json(ws):
    return json.loads(await ws.recv())


async def subscribe(ws, channel):
    await ws.send(
        json.dumps({"type": "subscribe", "payload": {"channel": channel}})
    )
    return await recv_json(ws)


def make_server(tmp_path, name="history.db"):
    return NotificationServer(port=0, database_url=f"sqlite:///{tmp_path / name}")


# ── /history endpoint ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_returns_chronological_channel_messages(tmp_path):
    srv = make_server(tmp_path)
    await srv.start()
    try:
        for i in range(5):
            await srv.broadcast({"i": i}, channel="alerts")
        raw = await http_get(srv.host, srv.bound_port, "/history?channel=alerts")
        body = parse_json(raw)
        assert [m["payload"]["i"] for m in body["messages"]] == [0, 1, 2, 3, 4]
        assert all(m["channel"] == "alerts" for m in body["messages"])
        assert body["has_more"] is False
        assert body["limit"] == 50
        assert body["offset"] == 0
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_history_since_filter(tmp_path):
    base = datetime.now(timezone.utc) - timedelta(minutes=30)
    srv = make_server(tmp_path)
    await srv.start()
    try:
        for i, mins in enumerate([0, 5, 10, 15, 20]):
            srv.store.insert(
                "alerts",
                "broadcast",
                {"i": i},
                (base + timedelta(minutes=mins)).isoformat(),
            )
        since = (base + timedelta(minutes=10)).isoformat()
        raw = await http_get(
            srv.host,
            srv.bound_port,
            f"/history?channel=alerts&since={quote(since)}",
        )
        body = parse_json(raw)
        assert [m["payload"]["i"] for m in body["messages"]] == [2, 3, 4]
        assert body["has_more"] is False
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_history_pagination_has_more(tmp_path):
    srv = make_server(tmp_path)
    await srv.start()
    try:
        for i in range(5):
            await srv.broadcast({"i": i}, channel="alerts")

        raw1 = await http_get(
            srv.host, srv.bound_port, "/history?channel=alerts&limit=2"
        )
        body1 = parse_json(raw1)
        assert [m["payload"]["i"] for m in body1["messages"]] == [0, 1]
        assert body1["has_more"] is True

        raw2 = await http_get(
            srv.host, srv.bound_port, "/history?channel=alerts&limit=2&offset=2"
        )
        body2 = parse_json(raw2)
        assert [m["payload"]["i"] for m in body2["messages"]] == [2, 3]
        assert body2["has_more"] is True

        raw3 = await http_get(
            srv.host, srv.bound_port, "/history?channel=alerts&limit=2&offset=4"
        )
        body3 = parse_json(raw3)
        assert [m["payload"]["i"] for m in body3["messages"]] == [4]
        assert body3["has_more"] is False
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_history_filters_by_channel(tmp_path):
    srv = make_server(tmp_path)
    await srv.start()
    try:
        await srv.broadcast({"i": 1}, channel="alerts")
        await srv.broadcast({"i": 2}, channel="chat")
        raw = await http_get(srv.host, srv.bound_port, "/history?channel=alerts")
        body = parse_json(raw)
        assert len(body["messages"]) == 1
        assert body["messages"][0]["channel"] == "alerts"
        assert body["messages"][0]["payload"] == {"i": 1}
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_history_defaults(tmp_path):
    srv = make_server(tmp_path)
    await srv.start()
    try:
        raw = await http_get(srv.host, srv.bound_port, "/history")
        body = parse_json(raw)
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert isinstance(body["messages"], list)
        assert body["has_more"] is False
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_history_records_client_broadcasts(tmp_path):
    srv = make_server(tmp_path)
    await srv.start()
    try:
        async with connect(f"ws://{srv.host}:{srv.bound_port}") as a:
            await recv_json(a)
            await subscribe(a, "alerts")
            await a.send(
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"message": "hello"},
                    }
                )
            )
            await asyncio.wait_for(recv_json(a), timeout=2)

        raw = await http_get(
            srv.host, srv.bound_port, "/history?channel=alerts"
        )
        body = parse_json(raw)
        assert len(body["messages"]) == 1
        assert body["messages"][0]["type"] == "broadcast"
        assert body["messages"][0]["payload"] == {"message": "hello"}
    finally:
        await srv.stop()


# ── message expiry ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cleanup_removes_expired_messages(tmp_path):
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=8)).isoformat()
    recent = (now - timedelta(hours=1)).isoformat()
    srv = make_server(tmp_path)
    srv.store.insert("alerts", "broadcast", {"old": True}, old)
    srv.store.insert("alerts", "broadcast", {"recent": True}, recent)
    assert srv.store.count() == 2
    removed = srv.store.cleanup(ttl_days=7)
    assert removed == 1
    assert srv.store.count() == 1
    await srv.stop()


@pytest.mark.asyncio
async def test_cleanup_keeps_recent_messages(tmp_path):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=1)).isoformat()
    srv = make_server(tmp_path)
    srv.store.insert("alerts", "broadcast", {"recent": True}, recent)
    removed = srv.store.cleanup(ttl_days=7)
    assert removed == 0
    assert srv.store.count() == 1
    await srv.stop()


@pytest.mark.asyncio
async def test_cleanup_runs_on_server_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "7")
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=8)).isoformat()
    recent = (now - timedelta(hours=1)).isoformat()
    srv = make_server(tmp_path)
    srv.store.insert("alerts", "broadcast", {"old": True}, old)
    srv.store.insert("alerts", "broadcast", {"recent": True}, recent)
    assert srv.store.count() == 2
    await srv.start()
    try:
        await asyncio.sleep(0.2)
        assert srv.store.count() == 1
        raw = await http_get(srv.host, srv.bound_port, "/history")
        body = parse_json(raw)
        assert [m["payload"] for m in body["messages"]] == [{"recent": True}]
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_cleanup_ttl_env_respected(tmp_path, monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "0")
    now = datetime.now(timezone.utc)
    just_now = now.isoformat()
    srv = make_server(tmp_path)
    srv.store.insert("alerts", "broadcast", {"fresh": True}, just_now)
    await srv.start()
    try:
        await asyncio.sleep(0.2)
        assert srv.store.count() == 0
    finally:
        await srv.stop()
