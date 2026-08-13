import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from notification_server.messages import Message
from notification_server.persistence import MessageStore


def iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = MessageStore(path)
    try:
        yield s
    finally:
        s.close()
        os.remove(path)


def test_delete_expired_removes_only_old_messages(store):
    store.save(Message(type="broadcast", payload={"text": "old"}, timestamp=iso_days_ago(10)))
    store.save(Message(type="broadcast", payload={"text": "new"}, timestamp=iso_days_ago(1)))

    deleted = store.delete_expired(iso_days_ago(7))

    assert deleted == 1
    remaining = store.fetch(limit=50)
    assert [m["payload"]["text"] for m in remaining] == ["new"]


def test_delete_expired_returns_zero_when_nothing_to_delete(store):
    store.save(Message(type="broadcast", payload={"text": "new"}, timestamp=iso_days_ago(1)))
    assert store.delete_expired(iso_days_ago(7)) == 0


def test_delete_expired_on_empty_store(store):
    assert store.delete_expired(iso_days_ago(7)) == 0


async def test_cleanup_task_runs_on_server_startup(notification_server_factory):
    notification_server, _, db_path = notification_server_factory(
        message_ttl_days=7, cleanup_interval_seconds=3600
    )
    try:
        notification_server.store.save(
            Message(type="broadcast", payload={"text": "stale"}, timestamp=iso_days_ago(10))
        )
        notification_server.store.save(
            Message(type="broadcast", payload={"text": "fresh"}, timestamp=iso_days_ago(1))
        )

        await notification_server.start()
        # the cleanup loop runs its first pass immediately, before its first
        # sleep, so a brief yield is enough for it to have completed.
        for _ in range(20):
            remaining = notification_server.store.fetch(limit=50)
            if len(remaining) == 1:
                break
            await asyncio.sleep(0.05)

        remaining = notification_server.store.fetch(limit=50)
        assert [m["payload"]["text"] for m in remaining] == ["fresh"]
    finally:
        await notification_server.close()
        os.remove(db_path)


async def test_cleanup_task_reruns_periodically(notification_server_factory):
    notification_server, _, db_path = notification_server_factory(
        message_ttl_days=7, cleanup_interval_seconds=0.05
    )
    try:
        await notification_server.start()
        await asyncio.sleep(0.1)  # let at least one periodic tick pass

        notification_server.store.save(
            Message(type="broadcast", payload={"text": "stale"}, timestamp=iso_days_ago(10))
        )

        for _ in range(20):
            remaining = notification_server.store.fetch(limit=50)
            if len(remaining) == 0:
                break
            await asyncio.sleep(0.05)

        assert notification_server.store.fetch(limit=50) == []
    finally:
        await notification_server.close()
        os.remove(db_path)


async def test_close_cancels_cleanup_task_cleanly(notification_server_factory):
    notification_server, _, db_path = notification_server_factory(cleanup_interval_seconds=3600)
    try:
        await notification_server.start()
        assert notification_server._cleanup_task is not None
        assert not notification_server._cleanup_task.done()
    finally:
        await notification_server.close()
        os.remove(db_path)

    assert notification_server._cleanup_task is None


def test_message_ttl_days_configurable_via_env(monkeypatch):
    from notification_server.config import message_ttl_days

    monkeypatch.delenv("MESSAGE_TTL_DAYS", raising=False)
    assert message_ttl_days() == 7

    monkeypatch.setenv("MESSAGE_TTL_DAYS", "14")
    assert message_ttl_days() == 14


def test_rate_limit_configurable_via_env(monkeypatch):
    from notification_server.config import rate_limit

    monkeypatch.delenv("RATE_LIMIT", raising=False)
    assert rate_limit() == 100

    monkeypatch.setenv("RATE_LIMIT", "50")
    assert rate_limit() == 50
