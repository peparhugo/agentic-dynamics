import asyncio
import json

import aiohttp
import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis, FakeServer
from websockets.asyncio.client import connect

from notification_server import (
    KEY_CHANNEL_SUBS,
    KEY_CLIENT_INSTANCE,
    NotificationServer,
)


async def drain_system(ws):
    msg = json.loads(await ws.recv())
    assert msg["type"] == "system"
    return msg


async def connect_client(server):
    ws = await connect(server.ws_url)
    msg = await drain_system(ws)
    assert msg["payload"]["event"] == "connected"
    return ws, msg["payload"]["client_id"]


async def subscribe(ws, channel):
    await ws.send(json.dumps({"type": "subscribe", "channel": channel}))
    ack = json.loads(await ws.recv())
    assert ack["type"] == "system"
    assert ack["payload"]["event"] == "subscribed"
    assert ack["payload"]["channel"] == channel


class RedisEnv:
    def __init__(self, tmp_path):
        self.shared = FakeServer()
        self.tmp_path = tmp_path
        self._servers = []
        self._clients = []
        self._n = 0
        self.redis = FakeAsyncRedis(server=self.shared, decode_responses=True)
        self._clients.append(self.redis)

    async def make_server(self):
        db = str(self.tmp_path / f"messages_{self._n}.db")
        self._n += 1
        redis = FakeAsyncRedis(server=self.shared, decode_responses=True)
        self._clients.append(redis)
        srv = NotificationServer(
            host="127.0.0.1", port=0, redis=redis, database_url=db
        )
        await srv.start()
        self._servers.append(srv)
        return srv

    async def close(self):
        for srv in self._servers:
            await srv.stop()
        for r in self._clients:
            try:
                await r.aclose()
            except Exception:
                pass


@pytest_asyncio.fixture
async def redis_env(tmp_path):
    env = RedisEnv(tmp_path)
    yield env
    await env.close()


@pytest.mark.asyncio
async def test_channel_message_delivered_across_instances(redis_env):
    srv1 = await redis_env.make_server()
    srv2 = await redis_env.make_server()

    ws_a, id_a = await connect_client(srv1)
    ws_b, id_b = await connect_client(srv2)

    await subscribe(ws_a, "alerts")

    await ws_b.send(
        json.dumps(
            {"type": "broadcast", "channel": "alerts", "payload": {"text": "hi"}}
        )
    )

    msg = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=5))
    assert msg["type"] == "broadcast"
    assert msg["channel"] == "alerts"
    assert msg["payload"] == {"text": "hi"}

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_broadcast_delivered_across_instances(redis_env):
    srv1 = await redis_env.make_server()
    srv2 = await redis_env.make_server()

    ws_a, id_a = await connect_client(srv1)
    ws_b, id_b = await connect_client(srv2)

    await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

    for ws in (ws_a, ws_b):
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "hello"}

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_direct_message_across_instances(redis_env):
    srv1 = await redis_env.make_server()
    srv2 = await redis_env.make_server()

    ws_a, id_a = await connect_client(srv1)
    ws_b, id_b = await connect_client(srv2)

    await ws_a.send(
        json.dumps({"type": "direct", "payload": {"target": id_b, "text": "ping"}})
    )

    msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
    assert msg["type"] == "direct"
    assert msg["payload"]["target"] == id_b
    assert msg["payload"]["sender"] == id_a
    assert msg["payload"]["text"] == "ping"

    await ws_a.close()
    await ws_b.close()


@pytest.mark.asyncio
async def test_client_state_stored_in_redis(redis_env):
    srv = await redis_env.make_server()
    ws, client_id = await connect_client(srv)

    instance = await redis_env.redis.get(
        KEY_CLIENT_INSTANCE.format(client_id=client_id)
    )
    assert instance == srv.instance_id

    await ws.close()


@pytest.mark.asyncio
async def test_subscription_state_stored_in_redis(redis_env):
    srv = await redis_env.make_server()
    ws, client_id = await connect_client(srv)

    await subscribe(ws, "alerts")

    members = await redis_env.redis.smembers(KEY_CHANNEL_SUBS.format(channel="alerts"))
    assert client_id in members

    await ws.close()


@pytest.mark.asyncio
async def test_messages_persisted_and_retrievable(redis_env):
    srv = await redis_env.make_server()
    ws, client_id = await connect_client(srv)

    await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "persist me"}}))
    await asyncio.wait_for(ws.recv(), timeout=5)

    async with aiohttp.ClientSession() as session:
        async with session.get(srv.messages_url) as resp:
            assert resp.status == 200
            body = await resp.json()

    assert len(body["messages"]) == 1
    message = body["messages"][0]
    assert message["type"] == "broadcast"
    assert message["payload"] == {"text": "persist me"}
    assert message["channel"] is None
    assert isinstance(message["timestamp"], str)
    assert isinstance(message["id"], int)

    await ws.close()


@pytest.mark.asyncio
async def test_messages_endpoint_supports_limit_and_offset(redis_env):
    srv = await redis_env.make_server()
    ws, client_id = await connect_client(srv)

    for n in range(3):
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
        await asyncio.wait_for(ws.recv(), timeout=5)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{srv.messages_url}?limit=2&offset=1") as resp:
            assert resp.status == 200
            body = await resp.json()

    assert len(body["messages"]) == 2
    assert [m["payload"]["n"] for m in body["messages"]] == [1, 0]

    await ws.close()
