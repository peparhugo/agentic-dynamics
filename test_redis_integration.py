import os
import sys
import tempfile
import threading

import pytest

_temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="test_redis_")
_temp_db_path = _temp_db.name
_temp_db.close()
os.environ["DATABASE_URL"] = _temp_db_path

from fakeredis import FakeRedis
from fakeredis import FakeConnection

import server as server_module


REDIS_HOST = "127.0.0.1"
REDIS_PORT = 16379
WS_PORT = 19765
HTTP_PORT = 19080

_orig_get_redis = None
_fake_redis = None


def _setup_fakeredis():
    global _orig_get_redis, _fake_redis
    _fake_redis = FakeRedis(decode_responses=True)
    _orig_get_redis = server_module._get_redis

    def _mock_get_redis():
        return _fake_redis

    server_module._get_redis = _mock_get_redis
    server_module._redis_failed = False


def _teardown_fakeredis():
    global _orig_get_redis
    if _orig_get_redis is not None:
        server_module._get_redis = _orig_get_redis
        _orig_get_redis = None
    server_module._redis_client = None
    server_module._redis_failed = False
    server_module._redis_ready.clear()


@pytest.fixture(scope="module")
def redis_server():
    _setup_fakeredis()
    server_module.start_server("127.0.0.1", WS_PORT, HTTP_PORT)
    import time
    time.sleep(0.5)
    yield
    _teardown_fakeredis()


@pytest.fixture(autouse=True)
def reset_state():
    server_module._registry.clear()
    server_module._channels.clear()
    with server_module._db_lock:
        import sqlite3
        conn = sqlite3.connect(server_module.DATABASE_URL)
        conn.execute("DELETE FROM messages")
        conn.commit()
        conn.close()
    yield
    server_module._registry.clear()
    server_module._channels.clear()
    with server_module._db_lock:
        import sqlite3
        conn = sqlite3.connect(server_module.DATABASE_URL)
        conn.execute("DELETE FROM messages")
        conn.commit()
        conn.close()


class TestRedisPubSub:
    @pytest.mark.asyncio
    async def test_redis_pubsub_delivers_broadcast(self, redis_server):
        import asyncio
        import json
        import websockets

        async with websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws2:
            d1 = json.loads(await ws1.recv())
            d2 = json.loads(await ws2.recv())

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "redis-broadcast"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=3))
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "redis-broadcast"
            assert msg["from"] == d1["payload"]["client_id"]

    @pytest.mark.asyncio
    async def test_redis_pubsub_delivers_channel_broadcast(self, redis_server):
        import asyncio
        import json
        import websockets

        async with websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws2, \
                   websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws3:
            await ws1.recv()
            await ws2.recv()
            await ws3.recv()

            await ws1.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "redis-chan"}
            }))
            await ws2.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "redis-chan"}
            }))
            await asyncio.sleep(0.1)

            await ws1.send(json.dumps({
                "type": "broadcast",
                "channel": "redis-chan",
                "payload": {"text": "redis-channel-msg"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=3))
            assert msg["payload"]["text"] == "redis-channel-msg"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws3.recv(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_redis_pubsub_delivers_direct_message(self, redis_server):
        import asyncio
        import json
        import websockets

        async with websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws2, \
                   websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws3:
            d1 = json.loads(await ws1.recv())
            d2 = json.loads(await ws2.recv())
            await ws3.recv()

            target_id = d2["payload"]["client_id"]

            await ws1.send(json.dumps({
                "type": "direct",
                "payload": {"target": target_id, "text": "redis-direct"}
            }))

            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=3))
            assert msg["type"] == "direct"
            assert msg["payload"]["text"] == "redis-direct"
            assert msg["from"] == d1["payload"]["client_id"]

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws3.recv(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_redis_broadcast_sender_not_receives_own(self, redis_server):
        import asyncio
        import json
        import websockets

        async with websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "no-echo"}
            }))

            await asyncio.wait_for(ws2.recv(), timeout=3)

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws1.recv(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_redis_client_state_stored(self, redis_server):
        import asyncio
        import json
        import websockets

        async with websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws:
            d = json.loads(await ws.recv())
            client_id = d["payload"]["client_id"]
            await asyncio.sleep(0.2)

            stored_server = _fake_redis.hget("chat:clients", client_id)
            assert stored_server is not None

            members = _fake_redis.smembers(f"chat:server:{stored_server}:clients")
            assert client_id in members

        await asyncio.sleep(0.3)
        stored_after = _fake_redis.hget("chat:clients", client_id)
        assert stored_after is None

    @pytest.mark.asyncio
    async def test_redis_channel_subscriptions_synced(self, redis_server):
        import asyncio
        import json
        import websockets

        async with websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws:
            d = json.loads(await ws.recv())
            client_id = d["payload"]["client_id"]

            await ws.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "redis-sub"}
            }))
            await asyncio.sleep(0.2)

            server_id = _fake_redis.hget("chat:clients", client_id)
            key = f"chat:channel:{server_id}:redis-sub"
            members = _fake_redis.smembers(key)
            assert client_id in members


class TestRedisMessagePersistence:
    @pytest.mark.asyncio
    async def test_redis_messages_persisted_to_sqlite(self, redis_server):
        import asyncio
        import json
        import websockets
        from aiohttp import ClientSession

        async with websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws1, \
                   websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "redis-persist-test"}
            }))
            await asyncio.wait_for(ws2.recv(), timeout=3)
            await asyncio.sleep(0.2)

        async with ClientSession() as session:
            async with session.get(
                f"http://{REDIS_HOST}:{HTTP_PORT}/messages?limit=50&offset=0"
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                msgs = [m for m in data if m["payload"].get("text") == "redis-persist-test"]
                assert len(msgs) >= 1
                assert msgs[0]["type"] == "broadcast"

    @pytest.mark.asyncio
    async def test_redis_messages_endpoint_pagination(self, redis_server):
        import asyncio
        import json
        import websockets
        from aiohttp import ClientSession

        async def send_msg(text):
            async with websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws_send, \
                       websockets.connect(f"ws://{REDIS_HOST}:{WS_PORT}") as ws_recv:
                await ws_send.recv()
                await ws_recv.recv()
                await ws_send.send(json.dumps({
                    "type": "broadcast",
                    "payload": {"text": text}
                }))
                await asyncio.wait_for(ws_recv.recv(), timeout=3)
                await asyncio.sleep(0.1)

        for i in range(5):
            await send_msg(f"redis-page-{i}")

        async with ClientSession() as session:
            async with session.get(
                f"http://{REDIS_HOST}:{HTTP_PORT}/messages?limit=2&offset=0"
            ) as resp:
                data = await resp.json()
                assert len(data) == 2
