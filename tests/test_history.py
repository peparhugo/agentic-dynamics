"""Tests for the /history REST endpoint and message expiry cleanup."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import websockets
from aiohttp import ClientSession

from message_store import MessageStore
from notifications import (
    TYPE_BROADCAST,
    TYPE_SUBSCRIBE,
    NotificationServer,
)


async def open_client(ws_port, timeout=5):
    return await asyncio.wait_for(
        websockets.connect(f"ws://127.0.0.1:{ws_port}"),
        timeout=timeout,
    )


async def recv_json(ws):
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    return json.loads(raw)


async def get_json(rest_port, path, params=None):
    url = f"http://127.0.0.1:{rest_port}{path}"
    async with ClientSession() as session:
        async with session.get(url, params=params) as resp:
            return resp.status, await resp.json()


async def _start_server(**kwargs):
    srv = NotificationServer(
        host="127.0.0.1",
        ws_port=0,
        rest_port=0,
        database_url="sqlite:///:memory:",
        **kwargs,
    )
    await srv.start()
    return srv


# ── MessageStore.history unit behaviour ─────────────────────


async def test_store_history_orders_chronologically():
    store = MessageStore(database_url="sqlite:///:memory:")
    await store.start()
    try:
        t0 = datetime.now(timezone.utc)
        t1 = (t0 + timedelta(seconds=1)).isoformat()
        t2 = (t0 + timedelta(seconds=2)).isoformat()
        t3 = (t0 + timedelta(seconds=3)).isoformat()
        await store.store("alerts", TYPE_BROADCAST, {"text": "a"}, t1)
        await store.store("chat", TYPE_BROADCAST, {"text": "b"}, t2)
        await store.store("alerts", TYPE_BROADCAST, {"text": "c"}, t3)

        messages, has_more = await store.history(channel="alerts")
        assert [m["payload"]["text"] for m in messages] == ["a", "c"]
        assert [m["channel"] for m in messages] == ["alerts", "alerts"]
        assert has_more is False

        messages, _ = await store.history(channel="alerts", since=t2)
        assert [m["payload"]["text"] for m in messages] == ["c"]

        messages, has_more = await store.history(limit=1)
        assert [m["payload"]["text"] for m in messages] == ["a"]
        assert has_more is True
    finally:
        await store.stop()


async def test_store_history_empty_when_no_channel():
    store = MessageStore(database_url="sqlite:///:memory:")
    await store.start()
    try:
        messages, has_more = await store.history(channel="missing")
        assert messages == []
        assert has_more is False
    finally:
        await store.stop()


# ── REST /history integration ───────────────────────────────


async def test_history_channel_filter_and_chronological_order():
    srv = await _start_server()
    try:
        ws = await open_client(srv.ws_bound_port)
        async with ws:
            await recv_json(ws)
            await ws.send(json.dumps({
                "type": TYPE_SUBSCRIBE,
                "payload": {"channel": "alerts"},
            }))
            await recv_json(ws)
            for text in ("first", "second", "third"):
                await ws.send(json.dumps({
                    "type": TYPE_BROADCAST,
                    "channel": "alerts",
                    "payload": {"text": text},
                }))
                await recv_json(ws)
            await ws.send(json.dumps({
                "type": TYPE_BROADCAST,
                "payload": {"text": "plain"},
            }))
            await recv_json(ws)

        status, body = await get_json(
            srv.rest_bound_port, "/history?channel=alerts"
        )
        assert status == 200
        assert body["channel"] == "alerts"
        assert body["has_more"] is False
        texts = [m["payload"]["text"] for m in body["messages"]]
        assert texts == ["first", "second", "third"]
        assert all(m["channel"] == "alerts" for m in body["messages"])
        stamps = [m["timestamp"] for m in body["messages"]]
        assert stamps == sorted(stamps)
    finally:
        await srv.stop()


async def test_history_since_filter_is_inclusive():
    srv = await _start_server()
    try:
        ws = await open_client(srv.ws_bound_port)
        received = []
        async with ws:
            await recv_json(ws)
            for text in ("first", "second", "third"):
                await ws.send(json.dumps({
                    "type": TYPE_BROADCAST,
                    "payload": {"text": text},
                }))
                received.append(await recv_json(ws))

        since = received[1]["timestamp"]
        status, body = await get_json(
            srv.rest_bound_port, "/history", params={"since": since}
        )
        assert status == 200
        assert body["since"] == since
        texts = [m["payload"]["text"] for m in body["messages"]]
        assert texts == ["second", "third"]
    finally:
        await srv.stop()


async def test_history_pagination_has_more():
    srv = await _start_server()
    try:
        ws = await open_client(srv.ws_bound_port)
        async with ws:
            await recv_json(ws)
            for i in range(5):
                await ws.send(json.dumps({
                    "type": TYPE_BROADCAST,
                    "payload": {"text": f"msg-{i}"},
                }))
                await recv_json(ws)

        status, body = await get_json(
            srv.rest_bound_port, "/history?channel=broadcast&limit=2"
        )
        assert status == 200
        assert body["limit"] == 2
        assert len(body["messages"]) == 2
        assert body["has_more"] is True

        last_ts = body["messages"][-1]["timestamp"]
        status, body2 = await get_json(
            srv.rest_bound_port,
            "/history",
            params={"channel": "broadcast", "limit": 4, "since": last_ts},
        )
        assert status == 200
        assert body2["has_more"] is False
        texts = [m["payload"]["text"] for m in body2["messages"]]
        assert texts == ["msg-1", "msg-2", "msg-3", "msg-4"]
        assert texts == sorted(texts)
    finally:
        await srv.stop()


# ── Message expiry ──────────────────────────────────────────


async def test_store_cleanup_expired_deletes_old_messages():
    store = MessageStore(database_url="sqlite:///:memory:")
    await store.start()
    try:
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=10)).isoformat()
        recent = now.isoformat()
        await store.store("alerts", TYPE_BROADCAST, {"text": "old"}, old)
        await store.store("alerts", TYPE_BROADCAST, {"text": "new"}, recent)
        assert await store.count() == 2

        deleted = await store.cleanup_expired(7)
        assert deleted == 1
        assert await store.count() == 1
        messages, _ = await store.history(channel="alerts")
        assert [m["payload"]["text"] for m in messages] == ["new"]
    finally:
        await store.stop()


async def test_cleanup_background_task_runs_on_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "7")
    db_url = f"sqlite:///{tmp_path}/ttl.db"
    store = MessageStore(database_url=db_url)
    await store.start()
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    await store.store("alerts", TYPE_BROADCAST, {"text": "ancient"}, old)
    await store.stop()

    srv = NotificationServer(
        host="127.0.0.1",
        ws_port=0,
        rest_port=0,
        database_url=db_url,
    )
    await srv.start()
    try:
        await asyncio.sleep(0.2)
        status, body = await get_json(srv.rest_bound_port, "/messages")
        assert status == 200
        assert body["total"] == 0
    finally:
        await srv.stop()
