"""Tests for the /history REST endpoint and message expiry cleanup."""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from websockets.asyncio.server import serve

from app import NotificationServer
from broker import LocalBroker
from store import MessageStore


async def start_server(ns):
    await ns.start()
    srv = await serve(ns.handle, "127.0.0.1", 0, process_request=ns.process_request)
    port = srv.sockets[0].getsockname()[1]
    return srv, port


async def get(port, path):
    async with httpx.AsyncClient() as client:
        return await client.get(f"http://127.0.0.1:{port}{path}")


def iso(dt):
    return dt.isoformat()


@pytest_asyncio.fixture
async def server():
    ns = NotificationServer(broker=LocalBroker(), store=MessageStore())
    srv, port = await start_server(ns)
    yield ns, port
    srv.close()
    await srv.wait_closed()
    await ns.close()


async def test_history_returns_chronological_and_paginated(server):
    ns, port = server
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        ns.store.save(
            {
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": f"msg-{i}"},
                "timestamp": iso(base + timedelta(seconds=i)),
            }
        )
    ns.store.save(
        {
            "type": "broadcast",
            "channel": "other",
            "payload": {"text": "not-alerts"},
            "timestamp": iso(base + timedelta(seconds=1)),
        }
    )

    resp = await get(port, "/history?channel=alerts&limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_more"] is False
    messages = data["messages"]
    assert [m["payload"]["text"] for m in messages] == [
        "msg-0",
        "msg-1",
        "msg-2",
        "msg-3",
        "msg-4",
    ]
    assert all(m["channel"] == "alerts" for m in messages)


async def test_history_pagination_has_more(server):
    ns, port = server
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        ns.store.save(
            {
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": f"msg-{i}"},
                "timestamp": iso(base + timedelta(seconds=i)),
            }
        )

    resp = await get(port, "/history?channel=alerts&limit=2")
    data = resp.json()
    assert data["has_more"] is True
    messages = data["messages"]
    assert len(messages) == 2
    assert [m["payload"]["text"] for m in messages] == ["msg-0", "msg-1"]


async def test_history_since_filters_time_range(server):
    ns, port = server
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        ns.store.save(
            {
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": f"msg-{i}"},
                "timestamp": iso(base + timedelta(seconds=i)),
            }
        )

    since = iso(base + timedelta(seconds=2))
    resp = await get(port, f"/history?channel=alerts&since={since}&limit=50")
    data = resp.json()
    assert data["has_more"] is False
    assert [m["payload"]["text"] for m in data["messages"]] == [
        "msg-2",
        "msg-3",
        "msg-4",
    ]


async def test_history_requires_channel(server):
    _, port = server
    resp = await get(port, "/history?limit=50")
    assert resp.status_code == 400


async def test_delete_older_than_removes_expired():
    store = MessageStore()
    old = datetime(2024, 1, 1, tzinfo=timezone.utc)
    recent = datetime(2026, 8, 1, tzinfo=timezone.utc)
    store.save(
        {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "old"},
            "timestamp": iso(old),
        }
    )
    store.save(
        {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "recent"},
            "timestamp": iso(recent),
        }
    )

    deleted = store.delete_older_than(iso(datetime(2026, 1, 1, tzinfo=timezone.utc)))
    assert deleted == 1
    remaining = store.query(limit=10)
    assert [m["payload"]["text"] for m in remaining] == ["recent"]


async def test_cleanup_expired_uses_message_ttl_days():
    ns = NotificationServer(broker=LocalBroker(), store=MessageStore(), message_ttl_days=7)
    now = datetime.now(timezone.utc)
    ns.store.save(
        {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "expired"},
            "timestamp": iso(now - timedelta(days=8)),
        }
    )
    ns.store.save(
        {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "fresh"},
            "timestamp": iso(now),
        }
    )

    deleted = ns.cleanup_expired()
    assert deleted == 1
    remaining = ns.store.query(limit=10)
    assert [m["payload"]["text"] for m in remaining] == ["fresh"]


async def test_cleanup_runs_in_background_on_startup():
    ns = NotificationServer(
        broker=LocalBroker(),
        store=MessageStore(),
        message_ttl_days=7,
        cleanup_interval=0.05,
    )
    now = datetime.now(timezone.utc)
    ns.store.save(
        {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "expired"},
            "timestamp": iso(now - timedelta(days=8)),
        }
    )
    ns.store.save(
        {
            "type": "broadcast",
            "channel": "alerts",
            "payload": {"text": "fresh"},
            "timestamp": iso(now),
        }
    )

    await ns.start()
    try:
        for _ in range(20):
            if ns.store.count() == 1:
                break
            await asyncio.sleep(0.05)
        remaining = ns.store.query(limit=10)
        assert [m["payload"]["text"] for m in remaining] == ["fresh"]
    finally:
        await ns.close()
