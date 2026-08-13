"""Integration tests for the Redis-backed pub/sub bus and SQLite persistence.

Uses fakeredis so the suite doesn't need a real Redis server. Multiple
NotificationServer instances sharing one `fakeredis.aioredis.FakeServer`
stand in for multiple server processes sharing one real Redis broker.
"""
import asyncio
import json
from urllib.request import urlopen

import pytest
import websockets
from fakeredis import aioredis as fakeredis_aioredis

from notification_server.server import NotificationServer


class _Instance:
    def __init__(self, app, server, ws_url, http_url):
        self.app = app
        self.server = server
        self.ws_url = ws_url
        self.http_url = http_url


@pytest.fixture
def redis_backend():
    return fakeredis_aioredis.FakeServer()


@pytest.fixture
async def make_instance(redis_backend, tmp_path):
    instances = []

    async def _make(server_id="server-a", db_path=None, shared_db=None):
        client = fakeredis_aioredis.FakeRedis(server=redis_backend)
        db = shared_db or db_path or str(tmp_path / f"{server_id}.db")
        app = NotificationServer(redis_client=client, db_path=db, server_id=server_id)
        server = await websockets.serve(
            app.handler, "localhost", 0, process_request=app.process_request
        )
        port = server.sockets[0].getsockname()[1]
        instance = _Instance(app, server, f"ws://localhost:{port}", f"http://localhost:{port}")
        instances.append(instance)
        return instance

    yield _make

    for instance in instances:
        instance.server.close()
        await instance.server.wait_closed()
        await instance.app.close()


async def _connected(client):
    msg = json.loads(await client.recv())
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "connected"
    return msg["payload"]["client_id"]


def _fetch(http_url, path):
    with urlopen(f"{http_url}{path}", timeout=2) as resp:
        return resp.status, json.loads(resp.read())


async def test_broadcast_still_works_through_the_redis_bus(make_instance):
    instance = await make_instance()
    async with websockets.connect(instance.ws_url) as c1, websockets.connect(instance.ws_url) as c2:
        c1_id = await _connected(c1)
        await _connected(c2)
        await c1.recv()  # client_joined for c2

        await c1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello via redis"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))

        msg_on_c1 = json.loads(await c1.recv())
        msg_on_c2 = json.loads(await c2.recv())
        assert msg_on_c1 == msg_on_c2
        assert msg_on_c1["payload"]["text"] == "hello via redis"
        assert msg_on_c1["payload"]["from"] == c1_id


async def test_direct_message_delivered_across_server_instances(make_instance):
    instance_a = await make_instance(server_id="server-a")
    instance_b = await make_instance(server_id="server-b")

    async with websockets.connect(instance_a.ws_url) as a, websockets.connect(instance_b.ws_url) as b:
        a_id = await _connected(a)
        b_id = await _connected(b)
        await a.recv()  # client_joined for b, fanned in over the shared bus

        await a.send(json.dumps({
            "type": "direct",
            "payload": {"target": b_id, "text": "cross-instance psst"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))

        direct_msg = json.loads(await b.recv())
        assert direct_msg["type"] == "direct"
        assert direct_msg["payload"]["text"] == "cross-instance psst"
        assert direct_msg["payload"]["from"] == a_id

        # 'a' must not receive its own direct message.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(a.recv(), timeout=0.2)


async def test_direct_message_to_unknown_target_still_errors_cross_instance(make_instance):
    instance_a = await make_instance(server_id="server-a")
    instance_b = await make_instance(server_id="server-b")

    async with websockets.connect(instance_a.ws_url) as a, websockets.connect(instance_b.ws_url) as _b:
        await _connected(a)
        await _connected(_b)
        await a.recv()  # client_joined for _b

        await a.send(json.dumps({
            "type": "direct",
            "payload": {"target": "does-not-exist-anywhere", "text": "hi"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        err = json.loads(await a.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_channel_broadcast_reaches_subscribers_on_other_instances(make_instance):
    instance_a = await make_instance(server_id="server-a")
    instance_b = await make_instance(server_id="server-b")

    async with websockets.connect(instance_a.ws_url) as a, websockets.connect(instance_b.ws_url) as b:
        a_id = await _connected(a)
        await _connected(b)
        await a.recv()  # client_joined for b

        await a.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await a.recv()  # subscribed ack

        await b.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await b.recv()  # subscribed ack

        await a.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "fire!"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))

        msg_on_a = json.loads(await a.recv())
        msg_on_b = json.loads(await b.recv())
        assert msg_on_a == msg_on_b
        assert msg_on_a["payload"]["text"] == "fire!"
        assert msg_on_a["payload"]["from"] == a_id


async def test_channels_endpoint_reports_subscribers_across_instances(make_instance):
    instance_a = await make_instance(server_id="server-a")
    instance_b = await make_instance(server_id="server-b")
    loop = asyncio.get_running_loop()

    async with websockets.connect(instance_a.ws_url) as a, websockets.connect(instance_b.ws_url) as b:
        await _connected(a)
        await _connected(b)
        await a.recv()  # client_joined for b

        for client in (a, b):
            await client.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
                "timestamp": "2026-08-13T00:00:00+00:00",
            }))
            await client.recv()  # subscribed ack

        status, body = await loop.run_in_executor(None, _fetch, instance_a.http_url, "/channels")
        assert status == 200
        assert body == {"channels": [{"name": "alerts", "subscribers": 2}]}

        # Querying instance_b should show the exact same cluster-wide view.
        status, body = await loop.run_in_executor(None, _fetch, instance_b.http_url, "/channels")
        assert body == {"channels": [{"name": "alerts", "subscribers": 2}]}


async def test_health_endpoint_reports_connected_clients_across_instances(make_instance):
    instance_a = await make_instance(server_id="server-a")
    instance_b = await make_instance(server_id="server-b")
    loop = asyncio.get_running_loop()

    async with websockets.connect(instance_a.ws_url) as a:
        await _connected(a)
        async with websockets.connect(instance_b.ws_url) as b:
            await _connected(b)

            status, body = await loop.run_in_executor(None, _fetch, instance_a.http_url, "/health")
            assert status == 200
            assert body == {"connected_clients": 2}

            status, body = await loop.run_in_executor(None, _fetch, instance_b.http_url, "/health")
            assert body == {"connected_clients": 2}


async def test_broadcast_messages_are_persisted_and_listed_via_rest(make_instance):
    instance = await make_instance()
    loop = asyncio.get_running_loop()

    async with websockets.connect(instance.ws_url) as c1, websockets.connect(instance.ws_url) as c2:
        c1_id = await _connected(c1)
        await _connected(c2)
        await c1.recv()  # client_joined for c2

        for client in (c1, c2):
            await client.send(json.dumps({
                "type": "subscribe",
                "payload": {"channel": "alerts"},
                "timestamp": "2026-08-13T00:00:00+00:00",
            }))
            await client.recv()  # subscribed ack

        await c1.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "fire!"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await c1.recv()
        await c2.recv()

        status, body = await loop.run_in_executor(None, _fetch, instance.http_url, "/messages")
        assert status == 200
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert len(body["messages"]) == 1
        stored = body["messages"][0]
        assert stored["type"] == "broadcast"
        assert stored["channel"] == "alerts"
        assert stored["payload"]["text"] == "fire!"
        assert stored["payload"]["from"] == c1_id
        assert isinstance(stored["timestamp"], str) and stored["timestamp"]


async def test_direct_messages_are_persisted_with_null_channel(make_instance):
    instance = await make_instance()
    loop = asyncio.get_running_loop()

    async with websockets.connect(instance.ws_url) as c1, websockets.connect(instance.ws_url) as c2:
        c1_id = await _connected(c1)
        c2_id = await _connected(c2)
        await c1.recv()  # client_joined for c2

        await c1.send(json.dumps({
            "type": "direct",
            "payload": {"target": c2_id, "text": "psst"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await c2.recv()

        status, body = await loop.run_in_executor(None, _fetch, instance.http_url, "/messages")
        assert status == 200
        assert len(body["messages"]) == 1
        stored = body["messages"][0]
        assert stored["type"] == "direct"
        assert stored["channel"] is None
        assert stored["payload"]["from"] == c1_id


async def test_control_plane_messages_are_not_persisted(make_instance):
    instance = await make_instance()
    loop = asyncio.get_running_loop()

    async with websockets.connect(instance.ws_url) as client:
        await _connected(client)
        await client.send(json.dumps({
            "type": "subscribe",
            "payload": {"channel": "alerts"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await client.recv()  # subscribed ack

    await asyncio.sleep(0.05)
    status, body = await loop.run_in_executor(None, _fetch, instance.http_url, "/messages")
    assert status == 200
    assert body["messages"] == []


async def test_messages_endpoint_respects_limit_and_offset(make_instance):
    instance = await make_instance()
    loop = asyncio.get_running_loop()

    async with websockets.connect(instance.ws_url) as client:
        await _connected(client)
        for i in range(5):
            await client.send(json.dumps({
                "type": "broadcast",
                "payload": {"seq": i},
                "timestamp": "2026-08-13T00:00:00+00:00",
            }))
            await client.recv()

        status, body = await loop.run_in_executor(
            None, _fetch, instance.http_url, "/messages?limit=2&offset=1"
        )
        assert status == 200
        assert body["limit"] == 2
        assert body["offset"] == 1
        # Most-recent-first ordering: skip seq=4, then seq=3, seq=2.
        assert [m["payload"]["seq"] for m in body["messages"]] == [3, 2]


async def test_messages_endpoint_survives_server_restart(make_instance, tmp_path):
    shared_db = str(tmp_path / "shared_history.db")
    instance = await make_instance(server_id="server-a", shared_db=shared_db)
    loop = asyncio.get_running_loop()

    async with websockets.connect(instance.ws_url) as client:
        await _connected(client)
        await client.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "before restart"},
            "timestamp": "2026-08-13T00:00:00+00:00",
        }))
        await client.recv()

    instance.server.close()
    await instance.server.wait_closed()
    await instance.app.close()

    restarted = await make_instance(server_id="server-a", shared_db=shared_db)
    status, body = await loop.run_in_executor(None, _fetch, restarted.http_url, "/messages")
    assert status == 200
    assert len(body["messages"]) == 1
    assert body["messages"][0]["payload"]["text"] == "before restart"
