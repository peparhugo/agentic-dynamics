"""
Tests for rate limiting, message history queries, and message expiry.
"""

import asyncio
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
import websockets

from notification_server import NotificationServer, decode_message, encode_message
from store import MessageStore


def ws_url(server):
    return f"ws://127.0.0.1:{server.port}"


def _get(url):
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


async def _get_json(url):
    body = await asyncio.to_thread(_get, url)
    return json.loads(body)


# ── Rate limiting ─────────────────────────────────────────────


async def test_rate_limit_exceeded_returns_error(tmp_path):
    srv = NotificationServer(database_url=str(tmp_path / "m.db"), rate_limit=5)
    await srv.start(port=0)
    try:
        async with websockets.connect(ws_url(srv)) as ws:
            await ws.recv()  # system connect message

            for i in range(5):
                await ws.send(
                    encode_message({"type": "broadcast", "payload": {"n": i}})
                )
            for i in range(5):
                got = decode_message(await ws.recv())
                assert got["type"] == "broadcast"

            # Sixth message exceeds the limit and must be rejected with an error.
            await ws.send(
                encode_message({"type": "broadcast", "payload": {"n": 99}})
            )
            err = decode_message(await ws.recv())
            assert err["type"] == "error"
            assert "rate limit" in err["payload"]["message"]

        assert srv.store.count() == 5
    finally:
        await srv.stop()


async def test_rate_limit_is_per_client(tmp_path):
    srv = NotificationServer(database_url=str(tmp_path / "m.db"), rate_limit=2)
    await srv.start(port=0)
    try:
        async with websockets.connect(ws_url(srv)) as ws1, websockets.connect(
            ws_url(srv)
        ) as ws2:
            id1 = decode_message(await ws1.recv())["payload"]["client_id"]
            id2 = decode_message(await ws2.recv())["payload"]["client_id"]

            # ws1 hits its limit by sending two direct messages to ws2.
            for i in range(2):
                await ws1.send(
                    encode_message(
                        {"type": "direct", "payload": {"client_id": id2, "n": i}}
                    )
                )
            for i in range(2):
                got = decode_message(await ws2.recv())
                assert got["type"] == "direct"

            # ws1 is now rate-limited.
            await ws1.send(
                encode_message(
                    {"type": "direct", "payload": {"client_id": id2, "n": 3}}
                )
            )
            err = decode_message(await ws1.recv())
            assert err["type"] == "error"

            # ws2 is unaffected and can still deliver to ws1.
            await ws2.send(
                encode_message(
                    {"type": "direct", "payload": {"client_id": id1, "text": "ok"}}
                )
            )
            got = decode_message(await ws1.recv())
            assert got["type"] == "direct"
            assert got["payload"]["text"] == "ok"
    finally:
        await srv.stop()


# ── History queries ───────────────────────────────────────────


async def test_history_endpoint_filters_and_orders(tmp_path):
    store = MessageStore(str(tmp_path / "m.db"))
    srv = NotificationServer(store=store)
    await srv.start(port=0)
    try:
        now = datetime.now(timezone.utc)
        t = [now + timedelta(seconds=i) for i in range(4)]

        store.save(
            {"type": "broadcast", "payload": {"n": 0}, "channel": "alpha", "timestamp": t[0].isoformat()}
        )
        store.save(
            {"type": "broadcast", "payload": {"n": 1}, "channel": "alpha", "timestamp": t[1].isoformat()}
        )
        store.save(
            {"type": "broadcast", "payload": {"n": 2}, "channel": "beta", "timestamp": t[2].isoformat()}
        )
        store.save(
            {"type": "broadcast", "payload": {"n": 3}, "channel": "alpha", "timestamp": t[3].isoformat()}
        )
        store.save({"type": "broadcast", "payload": {"n": 4}, "timestamp": t[3].isoformat()})

        base = f"http://127.0.0.1:{srv.port}/history"

        data = await _get_json(f"{base}?channel=alpha")
        assert data["has_more"] is False
        assert [m["payload"]["n"] for m in data["messages"]] == [0, 1, 3]

        page = await _get_json(f"{base}?channel=alpha&limit=2")
        assert page["has_more"] is True
        assert [m["payload"]["n"] for m in page["messages"]] == [0, 1]

        since = urllib.parse.quote(t[1].isoformat())
        since_page = await _get_json(f"{base}?channel=alpha&since={since}")
        assert [m["payload"]["n"] for m in since_page["messages"]] == [1, 3]

        beta = await _get_json(f"{base}?channel=beta")
        assert [m["payload"]["n"] for m in beta["messages"]] == [2]
    finally:
        await srv.stop()


async def test_history_messages_are_chronological(tmp_path):
    store = MessageStore(str(tmp_path / "m.db"))
    srv = NotificationServer(store=store)
    await srv.start(port=0)
    try:
        now = datetime.now(timezone.utc)
        for i in range(5):
            store.save(
                {
                    "type": "broadcast",
                    "payload": {"n": i},
                    "channel": "feed",
                    "timestamp": (now + timedelta(seconds=i)).isoformat(),
                }
            )

        data = await _get_json(
            f"http://127.0.0.1:{srv.port}/history?channel=feed"
        )
        timestamps = [m["timestamp"] for m in data["messages"]]
        assert timestamps == sorted(timestamps)
        assert [m["payload"]["n"] for m in data["messages"]] == [0, 1, 2, 3, 4]
    finally:
        await srv.stop()


# ── Message expiry ────────────────────────────────────────────


def test_delete_older_than_days_removes_old_messages(tmp_path):
    store = MessageStore(str(tmp_path / "m.db"))
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    recent = datetime.now(timezone.utc).isoformat()

    store.save({"type": "broadcast", "payload": {}, "timestamp": old})
    store.save({"type": "broadcast", "payload": {}, "timestamp": recent})
    assert store.count() == 2

    removed = store.delete_older_than_days(7)
    assert removed == 1
    assert store.count() == 1
    assert store.query()[0]["timestamp"] == recent


async def test_server_startup_cleans_old_messages(tmp_path):
    store = MessageStore(str(tmp_path / "m.db"))
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    recent = datetime.now(timezone.utc).isoformat()

    store.save({"type": "broadcast", "payload": {}, "timestamp": old})
    store.save({"type": "broadcast", "payload": {}, "timestamp": recent})

    srv = NotificationServer(store=store, message_ttl_days=7)
    await srv.start(port=0)
    try:
        await asyncio.sleep(0.1)
        assert srv.store.count() == 1
    finally:
        await srv.stop()


# ── Configuration ─────────────────────────────────────────────


def test_config_from_env_vars(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "17")
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    srv = NotificationServer(database_url=":memory:")
    assert srv.rate_limit == 17
    assert srv.message_ttl_days == 3
