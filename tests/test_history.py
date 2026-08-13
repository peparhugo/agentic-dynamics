"""Tests for persistent message history (REST /history) and message expiry.

The ``GET /history`` endpoint returns messages for a channel/time range in
chronological order, paginated with a ``has_more`` flag. Messages older than
``MESSAGE_TTL_DAYS`` days (default 7) are purged by a background task that
runs on server startup.
"""

import asyncio
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone

from urllib.parse import urlencode

import aiohttp
import websockets

from messages import utc_now
from server import NotificationServer
from storage import MessageStore


async def connect_client(ws_url):
    """Connect a client and consume its initial 'connected' system message."""
    ws = await websockets.connect(ws_url)
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    msg = json.loads(raw)
    assert msg["type"] == "system"
    assert "client_id" in msg["payload"]
    return ws, msg["payload"]["client_id"]


async def http_get(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return resp.status, await resp.json()


async def send_channel_messages(ws, channel, count, base="msg"):
    """Send ``count`` channel messages separated by short sleeps."""
    for n in range(count):
        await ws.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": channel,
                    "payload": {"text": f"{base}-{n}"},
                }
            )
        )
        await asyncio.sleep(0.01)


# ── /history endpoint ────────────────────────────────────────────


async def test_history_returns_chronological_messages_for_channel():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "history.db")
    srv = NotificationServer(
        host="127.0.0.1", port=0, database_url=db_path
    )
    await srv.start()
    ws, _ = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
    try:
        await send_channel_messages(ws, "alerts", 3)
        await ws.send(
            json.dumps(
                {"type": "broadcast", "channel": "other", "payload": {"text": "x"}}
            )
        )
        await asyncio.sleep(0.2)

        status, body = await http_get(
            f"http://127.0.0.1:{srv.bound_port}/history?channel=alerts"
        )
        assert status == 200
        assert body["channel"] == "alerts"
        assert body["has_more"] is False
        messages = body["messages"]
        assert [m["payload"] for m in messages] == [
            {"text": "msg-0"},
            {"text": "msg-1"},
            {"text": "msg-2"},
        ]
        expected_keys = {"id", "channel", "type", "payload", "timestamp"}
        for msg in messages:
            assert set(msg.keys()) == expected_keys
            assert msg["channel"] == "alerts"
            assert isinstance(msg["payload"], dict)
            assert isinstance(msg["timestamp"], str) and msg["timestamp"]
        timestamps = [m["timestamp"] for m in messages]
        assert timestamps == sorted(timestamps)
    finally:
        await ws.close()
        await srv.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_history_filters_by_since_and_paginates_with_has_more():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "history.db")
    srv = NotificationServer(
        host="127.0.0.1", port=0, database_url=db_path
    )
    await srv.start()
    ws, _ = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
    try:
        await send_channel_messages(ws, "alerts", 5)
        await asyncio.sleep(0.2)

        base_url = f"http://127.0.0.1:{srv.bound_port}/history"

        status, body = await http_get(f"{base_url}?channel=alerts&limit=2")
        assert status == 200
        assert len(body["messages"]) == 2
        assert body["has_more"] is True
        page1 = [m["payload"] for m in body["messages"]]

        cursor = body["messages"][-1]["timestamp"]
        query = urlencode({"channel": "alerts", "since": cursor, "limit": 2})
        status, body = await http_get(f"{base_url}?{query}")
        assert status == 200
        assert len(body["messages"]) == 2
        assert body["has_more"] is True
        page2 = [m["payload"] for m in body["messages"]]

        cursor = body["messages"][-1]["timestamp"]
        query = urlencode({"channel": "alerts", "since": cursor, "limit": 2})
        status, body = await http_get(f"{base_url}?{query}")
        assert status == 200
        assert len(body["messages"]) == 1
        assert body["has_more"] is False
        page3 = [m["payload"] for m in body["messages"]]

        assert page1 + page2 + page3 == [
            {"text": "msg-0"},
            {"text": "msg-1"},
            {"text": "msg-2"},
            {"text": "msg-3"},
            {"text": "msg-4"},
        ]
    finally:
        await ws.close()
        await srv.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_history_without_channel_returns_all_channels():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "history.db")
    srv = NotificationServer(
        host="127.0.0.1", port=0, database_url=db_path
    )
    await srv.start()
    ws, _ = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
    try:
        await send_channel_messages(ws, "alerts", 2)
        await ws.send(
            json.dumps(
                {"type": "broadcast", "channel": "chat", "payload": {"text": "hi"}}
            )
        )
        await asyncio.sleep(0.2)

        status, body = await http_get(
            f"http://127.0.0.1:{srv.bound_port}/history"
        )
        assert status == 200
        assert len(body["messages"]) == 3
        channels = {m["channel"] for m in body["messages"]}
        assert channels == {"alerts", "chat"}

        status, body = await http_get(
            f"http://127.0.0.1:{srv.bound_port}/history?channel=missing"
        )
        assert status == 200
        assert body["messages"] == []
        assert body["has_more"] is False
    finally:
        await ws.close()
        await srv.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_history_rejects_invalid_since_timestamp():
    srv = NotificationServer(host="127.0.0.1", port=0)
    await srv.start()
    try:
        status, _ = await http_get(
            f"http://127.0.0.1:{srv.bound_port}/history?since=not-a-timestamp"
        )
        assert status == 400
    finally:
        await srv.close()


# ── Message expiry ───────────────────────────────────────────────


async def test_startup_cleanup_removes_expired_messages():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "expiry.db")
    store = MessageStore(db_path)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent_ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store.add("alerts", "broadcast", {"text": "old"}, old_ts)
    store.add("alerts", "broadcast", {"text": "fresh"}, utc_now())
    store.add("alerts", "broadcast", {"text": "recent"}, recent_ts)
    assert store.count() == 3
    store.close()

    srv = NotificationServer(
        host="127.0.0.1", port=0, database_url=db_path, message_ttl_days=7
    )
    await srv.start()
    try:
        status, body = await http_get(
            f"http://127.0.0.1:{srv.bound_port}/history?channel=alerts"
        )
        assert status == 200
        texts = [m["payload"]["text"] for m in body["messages"]]
        assert texts == ["recent", "fresh"]
    finally:
        await srv.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_delete_older_than_removes_only_expired():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "expiry.db")
    store = MessageStore(db_path)
    store.add("a", "broadcast", {"n": 1}, utc_now())
    old_ts = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    store.add("a", "broadcast", {"n": 2}, old_ts)
    removed = store.delete_older_than(7)
    assert removed == 1
    messages, _ = store.history(channel="a")
    assert [m["payload"] for m in messages] == [{"n": 1}]
    store.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


async def test_message_ttl_days_read_from_env(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    srv = NotificationServer(host="127.0.0.1", port=0)
    try:
        assert srv.message_ttl_days == 3
    finally:
        await srv.close()
