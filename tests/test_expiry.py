import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import app


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest.mark.asyncio
async def test_expire_removes_only_old_messages(running_server):
    old = _iso(datetime.now(timezone.utc) - timedelta(days=10))
    recent = _iso(datetime.now(timezone.utc) - timedelta(days=1))
    await running_server.store.save("alerts", "broadcast", {"old": True}, old)
    await running_server.store.save("alerts", "broadcast", {"recent": True}, recent)

    deleted = await running_server.store.expire(7)

    assert deleted == 1
    remaining = await running_server.store.history(limit=100)
    assert [m["payload"] for m in remaining] == [{"recent": True}]


@pytest.mark.asyncio
async def test_expire_default_ttl_is_seven_days():
    server = app.NotificationServer(database_url=":memory:")
    assert server.message_ttl_days == 7


@pytest.mark.asyncio
async def test_message_ttl_env_var(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    server = app.NotificationServer(database_url=":memory:")
    assert server.message_ttl_days == 3


@pytest.mark.asyncio
async def test_expire_non_positive_ttl_removes_nothing(running_server):
    await running_server.store.save("alerts", "broadcast", {"x": 1}, app.utcnow_iso())
    deleted = await running_server.store.expire(0)
    assert deleted == 0
    assert await running_server.store.count() == 1


@pytest.mark.asyncio
async def test_background_cleanup_removes_expired_messages():
    server = app.NotificationServer(
        database_url=":memory:",
        message_ttl_days=7,
        cleanup_interval_seconds=0.05,
    )
    await server.start(ws_host="127.0.0.1", ws_port=0,
                       http_host="127.0.0.1", http_port=0)
    try:
        old = _iso(datetime.now(timezone.utc) - timedelta(days=8))
        await server.store.save("alerts", "broadcast", {"old": True}, old)
        await asyncio.sleep(0.3)
        assert await server.store.count() == 0
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_background_cleanup_keeps_recent_messages():
    server = app.NotificationServer(
        database_url=":memory:",
        cleanup_interval_seconds=0.05,
    )
    await server.start(ws_host="127.0.0.1", ws_port=0,
                       http_host="127.0.0.1", http_port=0)
    try:
        await server.store.save("alerts", "broadcast", {"fresh": True}, app.utcnow_iso())
        await asyncio.sleep(0.2)
        assert await server.store.count() == 1
    finally:
        await server.stop()
