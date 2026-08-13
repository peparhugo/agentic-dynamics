"""Tests for automatic expiry of persisted messages older than the TTL."""

import asyncio
import urllib.request
import json
from datetime import datetime, timedelta, timezone

import pytest

from notification_server.server import NotificationServer


async def get_json(url: str) -> tuple:
    def _fetch():
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())

    return await asyncio.to_thread(_fetch)


def iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@pytest.mark.asyncio
async def test_cleanup_deletes_messages_older_than_ttl(make_server):
    srv = await make_server(message_ttl_days=7)
    await srv.store.save("alerts", "broadcast", {"text": "ancient"}, iso_days_ago(10))
    await srv.store.save("alerts", "broadcast", {"text": "recent"}, iso_days_ago(1))

    deleted = await srv._run_cleanup()
    assert deleted == 1

    status, body = await get_json(f"http://localhost:{srv.bound_port}/messages")
    assert status == 200
    texts = [m["payload"]["text"] for m in body["messages"]]
    assert texts == ["recent"]


@pytest.mark.asyncio
async def test_cleanup_keeps_messages_within_ttl(make_server):
    srv = await make_server(message_ttl_days=7)
    await srv.store.save("alerts", "broadcast", {"text": "six days old"}, iso_days_ago(6))

    deleted = await srv._run_cleanup()
    assert deleted == 0

    status, body = await get_json(f"http://localhost:{srv.bound_port}/messages")
    assert len(body["messages"]) == 1


@pytest.mark.asyncio
async def test_message_ttl_configurable_via_constructor(make_server):
    srv = await make_server(message_ttl_days=1)
    await srv.store.save("alerts", "broadcast", {"text": "two days old"}, iso_days_ago(2))

    deleted = await srv._run_cleanup()
    assert deleted == 1


@pytest.mark.asyncio
async def test_message_ttl_configurable_via_env_var(make_server, monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "1")
    srv = await make_server()
    assert srv.message_ttl_days == 1.0


@pytest.mark.asyncio
async def test_message_ttl_defaults_to_7_days(make_server):
    srv = await make_server()
    assert srv.message_ttl_days == 7.0


@pytest.mark.asyncio
async def test_cleanup_task_runs_automatically_on_startup(make_server):
    """The background cleanup task fires at least once as soon as the
    server starts, without any explicit trigger from the caller."""
    srv = await make_server(message_ttl_days=7, cleanup_interval_seconds=1000)
    await srv.store.save("alerts", "broadcast", {"text": "ancient"}, iso_days_ago(10))

    async def _cleaned():
        _, body = await get_json(f"http://localhost:{srv.bound_port}/messages")
        return body["messages"] == []

    async def _poll():
        while not await _cleaned():
            await asyncio.sleep(0.02)

    await asyncio.wait_for(_poll(), timeout=2.0)


@pytest.mark.asyncio
async def test_cleanup_does_not_affect_messages_in_other_channels_differently(make_server):
    """Sanity check: expiry is global across the messages table, not
    scoped to a single channel -- old messages in every channel expire."""
    srv = await make_server(message_ttl_days=7)
    await srv.store.save("alerts", "broadcast", {"text": "old alert"}, iso_days_ago(10))
    await srv.store.save("chat", "broadcast", {"text": "old chat"}, iso_days_ago(10))
    await srv.store.save("chat", "broadcast", {"text": "new chat"}, iso_days_ago(1))

    deleted = await srv._run_cleanup()
    assert deleted == 2

    status, body = await get_json(f"http://localhost:{srv.bound_port}/messages")
    texts = [m["payload"]["text"] for m in body["messages"]]
    assert texts == ["new chat"]
