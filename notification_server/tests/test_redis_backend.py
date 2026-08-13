import asyncio

import fakeredis.aioredis as fakeredis_asyncio
import pytest
import pytest_asyncio

from notification_server.redis_backend import RedisBackend, make_redis_client


@pytest_asyncio.fixture
async def backend():
    client = fakeredis_asyncio.FakeRedis(decode_responses=True)
    backend = RedisBackend(client, channel="test:channel")
    try:
        yield backend
    finally:
        await backend.close()


def test_make_redis_client_falls_back_to_fakeredis_without_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    client = make_redis_client()
    assert isinstance(client, fakeredis_asyncio.FakeRedis)


async def test_make_redis_client_uses_real_redis_when_url_given(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    client = make_redis_client(redis_url="redis://localhost:6399")
    try:
        assert not isinstance(client, fakeredis_asyncio.FakeRedis)
    finally:
        await client.aclose()


async def test_publish_and_listen_round_trip(backend):
    await backend.subscribe()

    async def publisher():
        await asyncio.sleep(0.05)
        await backend.publish({"hello": "world"})

    asyncio.create_task(publisher())
    async for envelope in backend.listen():
        assert envelope == {"hello": "world"}
        break


async def test_register_and_get_client_server(backend):
    await backend.register_client("client-1", "server-a")
    assert await backend.get_client_server("client-1") == "server-a"


async def test_get_client_server_unknown_returns_none(backend):
    assert await backend.get_client_server("does-not-exist") is None


async def test_unregister_client_removes_presence(backend):
    await backend.register_client("client-1", "server-a")
    await backend.unregister_client("client-1")
    assert await backend.get_client_server("client-1") is None


async def test_all_clients_lists_every_registered_client(backend):
    await backend.register_client("client-1", "server-a")
    await backend.register_client("client-2", "server-b")
    assert await backend.all_clients() == {"client-1": "server-a", "client-2": "server-b"}
