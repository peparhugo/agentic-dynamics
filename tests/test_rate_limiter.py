import asyncio
import json

import fakeredis
import pytest

from notification_server.rate_limiter import RateLimiter


@pytest.fixture
def client():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


async def test_allows_messages_within_limit(client):
    limiter = RateLimiter(client, limit=3)
    assert await limiter.allow("c1")
    assert await limiter.allow("c1")
    assert await limiter.allow("c1")


async def test_blocks_messages_over_limit(client):
    limiter = RateLimiter(client, limit=3)
    for _ in range(3):
        assert await limiter.allow("c1")
    assert not await limiter.allow("c1")
    assert not await limiter.allow("c1")


async def test_limit_is_tracked_per_client(client):
    limiter = RateLimiter(client, limit=1)
    assert await limiter.allow("c1")
    assert not await limiter.allow("c1")
    # a different client has its own independent counter.
    assert await limiter.allow("c2")


async def test_counter_shared_across_instances_on_same_backend():
    fake_server = fakeredis.FakeServer()
    client_a = fakeredis.FakeAsyncRedis(server=fake_server, decode_responses=True)
    client_b = fakeredis.FakeAsyncRedis(server=fake_server, decode_responses=True)
    limiter_a = RateLimiter(client_a, limit=2)
    limiter_b = RateLimiter(client_b, limit=2)

    assert await limiter_a.allow("c1")
    assert await limiter_b.allow("c1")
    # third message across either instance should now be blocked.
    assert not await limiter_a.allow("c1")


async def test_rate_limit_blocks_client_over_websocket(running_server_factory):
    async with running_server_factory(rate_limit=3) as (notification_server, uri, health_url):
        import websockets

        ws = await websockets.connect(uri)
        try:
            welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert welcome["payload"]["event"] == "connected"

            for _ in range(3):
                await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "hi"}}))
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                assert msg["type"] == "broadcast"

            # fourth message within the same window should be rejected with
            # an explicit error, not silently dropped -- the connection
            # stays open and the client is told what happened.
            await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "over limit"}}))
            error_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert error_msg["type"] == "system"
            assert "rate limit" in error_msg["payload"]["error"].lower()

            # the connection is still usable for other requests (e.g. it is
            # not disconnected as a side effect of being rate limited).
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws.recv(), timeout=0.3)
        finally:
            await ws.close()


async def test_rate_limit_is_configurable_via_constructor(running_server_factory):
    async with running_server_factory(rate_limit=1) as (notification_server, uri, health_url):
        import websockets

        ws = await websockets.connect(uri)
        try:
            await asyncio.wait_for(ws.recv(), timeout=2)  # welcome

            await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "first"}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert msg["payload"]["text"] == "first"

            await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "second"}}))
            error_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert "error" in error_msg["payload"]
        finally:
            await ws.close()
