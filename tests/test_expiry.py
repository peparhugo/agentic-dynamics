import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from notification_server.expiry import MessageExpiry
from notification_server.store import MessageStore


@pytest.fixture
def store(tmp_path):
    return MessageStore(str(tmp_path / "messages.db"))


def _iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


async def test_run_once_deletes_messages_older_than_ttl(store):
    store.record("broadcast", {"text": "old"}, _iso(10))
    store.record("broadcast", {"text": "new"}, _iso(1))
    expiry = MessageExpiry(store, ttl_days=7)

    deleted = await expiry.run_once()

    assert deleted == 1
    remaining = store.list_messages()
    assert [m["payload"]["text"] for m in remaining] == ["new"]


async def test_run_once_keeps_messages_within_ttl(store):
    store.record("broadcast", {"text": "recent"}, _iso(2))
    expiry = MessageExpiry(store, ttl_days=7)

    deleted = await expiry.run_once()

    assert deleted == 0
    assert len(store.list_messages()) == 1


async def test_start_runs_cleanup_immediately(store):
    store.record("broadcast", {"text": "old"}, _iso(10))
    expiry = MessageExpiry(store, ttl_days=7, interval_seconds=3600)

    await expiry.start()
    try:
        await asyncio.sleep(0.05)
        assert store.list_messages() == []
    finally:
        await expiry.stop()


async def test_start_is_idempotent(store):
    expiry = MessageExpiry(store, ttl_days=7, interval_seconds=3600)
    await expiry.start()
    task = expiry._task
    await expiry.start()
    assert expiry._task is task
    await expiry.stop()


async def test_stop_is_idempotent(store):
    expiry = MessageExpiry(store, ttl_days=7, interval_seconds=3600)
    await expiry.start()
    await expiry.stop()
    await expiry.stop()
    assert expiry._task is None


async def test_loop_repeats_on_interval(store):
    expiry = MessageExpiry(store, ttl_days=7, interval_seconds=0.05)
    await expiry.start()
    try:
        await asyncio.sleep(0.02)
        store.record("broadcast", {"text": "old"}, _iso(10))
        await asyncio.sleep(0.1)
        assert store.list_messages() == []
    finally:
        await expiry.stop()


def test_from_env_reads_message_ttl_days(store, monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "14")
    expiry = MessageExpiry.from_env(store)
    assert expiry.ttl_days == 14


def test_from_env_defaults_to_seven_days(store, monkeypatch):
    monkeypatch.delenv("MESSAGE_TTL_DAYS", raising=False)
    expiry = MessageExpiry.from_env(store)
    assert expiry.ttl_days == 7
