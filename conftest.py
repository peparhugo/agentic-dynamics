import contextlib

import fakeredis
import fakeredis.aioredis as fakeaioredis
import pytest_asyncio

import notification_server as ns


@pytest_asyncio.fixture(autouse=True)
async def _isolated_redis_and_db(tmp_path, monkeypatch):
    """Every test gets its own fake Redis backend (so no real redis-server
    is required) and its own throwaway SQLite file, and starts with no
    Redis worker task running so notification_server lazily boots a fresh
    one bound to the fake client on first use."""
    fake_server = fakeredis.FakeServer()
    client = fakeaioredis.FakeRedis(server=fake_server, decode_responses=True)

    monkeypatch.setattr(ns, "redis_client", client)
    monkeypatch.setattr(ns, "DATABASE_URL", str(tmp_path / "notifications-test.db"))
    monkeypatch.setattr(ns, "_worker_task", None)
    monkeypatch.setattr(ns, "_db_ready", False)

    yield fake_server

    if ns._worker_task is not None:
        ns._worker_task.cancel()
        with contextlib.suppress(Exception):
            await ns._worker_task
    await client.aclose()
