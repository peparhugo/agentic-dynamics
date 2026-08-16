"""Integration tests for the Redis pub/sub backbone and SQLite persistence."""

import asyncio
import json

import fakeredis.aioredis as fa
import pytest
import websockets
from aiohttp import ClientSession

from notifications import (
    TYPE_BROADCAST,
    TYPE_DIRECT,
    TYPE_SUBSCRIBE,
    TYPE_SYSTEM,
    NotificationServer,
)
from redis_broker import (
    BROADCAST_CHANNEL,
    RedisBackbone,
    channel_subs_key,
    client_state_key,
    clients_set_key,
    client_pubsub_channel,
)


@pytest.fixture
def fake_server():
    return fa.FakeServer()


@pytest.fixture
def redis_client(fake_server):
    return fa.FakeRedis(server=fake_server)


def make_server(fake_server=None, database_url="sqlite:///:memory:", **kwargs):
    client = kwargs.pop("redis_client", None)
    if fake_server is not None and client is None:
        client = fa.FakeRedis(server=fake_server)
    return NotificationServer(
        host="127.0.0.1",
        ws_port=0,
        rest_port=0,
        redis_client=client,
        database_url=database_url,
        **kwargs,
    )


async def open_client(ws_port, timeout=5):
    return await asyncio.wait_for(
        websockets.connect(f"ws://127.0.0.1:{ws_port}"),
        timeout=timeout,
    )


async def recv_json(ws):
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    return json.loads(raw)


async def get_json(rest_port, path):
    url = f"http://127.0.0.1:{rest_port}{path}"
    async with ClientSession() as session:
        async with session.get(url) as resp:
            return resp.status, await resp.json()


# ── RedisBackbone pub/sub unit behaviour ────────────────────


async def test_broker_pubsub_delivers_broadcast(fake_server):
    received = []

    async def dispatch(channel, message):
        received.append((channel, message))

    subscriber = RedisBackbone(redis_client=fa.FakeRedis(server=fake_server))
    publisher = RedisBackbone(redis_client=fa.FakeRedis(server=fake_server))
    await subscriber.start(dispatch)
    await publisher.start(lambda *_: None)
    try:
        await publisher.publish_broadcast({"type": "broadcast", "payload": {}})
        await asyncio.sleep(0.2)
        assert received
        channel, message = received[0]
        assert channel == BROADCAST_CHANNEL
        assert message["type"] == "broadcast"
    finally:
        await subscriber.stop()
        await publisher.stop()


async def test_broker_channel_and_direct_routing(fake_server):
    received = []

    async def dispatch(channel, message):
        received.append((channel, message))

    broker = RedisBackbone(redis_client=fa.FakeRedis(server=fake_server))
    await broker.start(dispatch)
    await broker.ensure_subscribed("alerts")
    await broker.ensure_client_channel("client-7")
    try:
        await broker.publish_channel("alerts", {"type": "broadcast"})
        await broker.publish_client("client-7", {"type": "direct"})
        await asyncio.sleep(0.2)
        channels = {c for c, _ in received}
        assert channels == {"notif:chan:alerts", "notif:client:client-7"}
    finally:
        await broker.stop()


# ── Redis pub/sub across multiple servers ───────────────────


async def test_broadcast_across_two_servers(fake_server):
    srv1 = make_server(fake_server)
    srv2 = make_server(fake_server)
    await srv1.start()
    await srv2.start()
    try:
        ws1 = await open_client(srv1.ws_bound_port)
        ws2 = await open_client(srv2.ws_bound_port)
        async with ws1, ws2:
            await recv_json(ws1)
            await recv_json(ws2)

            await ws1.send(json.dumps({
                "type": TYPE_BROADCAST,
                "payload": {"text": "shared backbone"},
            }))
            got1 = await recv_json(ws1)
            got2 = await recv_json(ws2)
            for got in (got1, got2):
                assert got["type"] == TYPE_BROADCAST
                assert got["payload"]["text"] == "shared backbone"
    finally:
        await srv1.stop()
        await srv2.stop()


async def test_channel_message_crosses_servers(fake_server):
    srv1 = make_server(fake_server)
    srv2 = make_server(fake_server)
    await srv1.start()
    await srv2.start()
    try:
        subscriber = await open_client(srv1.ws_bound_port)
        sender = await open_client(srv2.ws_bound_port)
        bystander = await open_client(srv2.ws_bound_port)
        async with subscriber, sender, bystander:
            await recv_json(subscriber)
            await recv_json(sender)
            await recv_json(bystander)

            await subscriber.send(json.dumps({
                "type": TYPE_SUBSCRIBE,
                "payload": {"channel": "alerts"},
            }))
            await recv_json(subscriber)

            await sender.send(json.dumps({
                "type": TYPE_BROADCAST,
                "channel": "alerts",
                "payload": {"text": "cross-server alert"},
            }))
            got = await recv_json(subscriber)
            assert got["type"] == TYPE_BROADCAST
            assert got["payload"]["text"] == "cross-server alert"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(bystander.recv(), timeout=0.5)
    finally:
        await srv1.stop()
        await srv2.stop()


async def test_direct_message_across_servers(fake_server):
    srv1 = make_server(fake_server)
    srv2 = make_server(fake_server)
    await srv1.start()
    await srv2.start()
    try:
        ws_sender = await open_client(srv1.ws_bound_port)
        ws_target = await open_client(srv2.ws_bound_port)
        async with ws_sender, ws_target:
            sender_id = (await recv_json(ws_sender))["payload"]["client_id"]
            target_id = (await recv_json(ws_target))["payload"]["client_id"]

            await ws_sender.send(json.dumps({
                "type": TYPE_DIRECT,
                "payload": {"target_id": target_id, "text": "psst"},
            }))
            got = await recv_json(ws_target)
            assert got["type"] == TYPE_DIRECT
            assert got["payload"]["text"] == "psst"
            assert got["payload"]["sender"] == sender_id

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws_sender.recv(), timeout=0.5)
    finally:
        await srv1.stop()
        await srv2.stop()


async def test_direct_to_unknown_client_errors_across_servers(fake_server):
    srv1 = make_server(fake_server)
    srv2 = make_server(fake_server)
    await srv1.start()
    await srv2.start()
    try:
        async with await open_client(srv1.ws_bound_port) as ws:
            await recv_json(ws)
            await ws.send(json.dumps({
                "type": TYPE_DIRECT,
                "payload": {"target_id": "client-does-not-exist"},
            }))
            got = await recv_json(ws)
            assert got["type"] == TYPE_SYSTEM
            assert "error" in got["payload"]
    finally:
        await srv1.stop()
        await srv2.stop()


# ── Redis-backed client connection state ────────────────────


async def test_client_state_stored_in_redis(fake_server, redis_client):
    srv = make_server(fake_server)
    await srv.start()
    try:
        ws = await open_client(srv.ws_bound_port)
        async with ws:
            welcome = await recv_json(ws)
            client_id = welcome["payload"]["client_id"]
            assert await redis_client.sismember(clients_set_key(), client_id)
            assert await redis_client.get(client_state_key(client_id))

            await ws.send(json.dumps({
                "type": TYPE_SUBSCRIBE,
                "payload": {"channel": "alerts"},
            }))
            await recv_json(ws)

            assert await redis_client.sismember(
                channel_subs_key("alerts"), client_id
            )
    finally:
        await srv.stop()


async def test_client_disconnect_cleans_redis_state(fake_server, redis_client):
    srv = make_server(fake_server)
    await srv.start()
    try:
        ws = await open_client(srv.ws_bound_port)
        welcome = await recv_json(ws)
        client_id = welcome["payload"]["client_id"]
        await ws.send(json.dumps({
            "type": TYPE_SUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        await recv_json(ws)
        await ws.close()
        await asyncio.sleep(0.2)
        assert not await redis_client.sismember(clients_set_key(), client_id)
        assert await redis_client.get(client_state_key(client_id)) is None
        assert not await redis_client.sismember(
            channel_subs_key("alerts"), client_id
        )
    finally:
        await srv.stop()


async def test_client_state_survives_server_restart(fake_server, redis_client):
    srv_a = make_server(fake_server)
    await srv_a.start()
    ws = await open_client(srv_a.ws_bound_port)
    welcome = await recv_json(ws)
    client_id = welcome["payload"]["client_id"]
    await ws.send(json.dumps({
        "type": TYPE_SUBSCRIBE,
        "payload": {"channel": "alerts"},
    }))
    await recv_json(ws)
    await ws.close()
    await srv_a.stop()

    assert await redis_client.sismember(clients_set_key(), client_id)
    assert await redis_client.get(client_state_key(client_id))

    srv_b = make_server(fake_server)
    await srv_b.start()
    try:
        status, body = await get_json(srv_b.rest_bound_port, "/channels")
        assert status == 200
        channels = {c["name"]: c["subscribers"] for c in body["channels"]}
        assert channels == {"alerts": 1}
        status, body = await get_json(
            srv_b.rest_bound_port, "/channels/alerts/subscribers"
        )
        assert status == 200
        assert client_id in body["subscribers"]
    finally:
        await srv_b.stop()


# ── SQLite message persistence ──────────────────────────────


async def test_message_history_persists_and_is_queryable(tmp_path):
    db_url = f"sqlite:///{tmp_path}/history.db"
    srv = NotificationServer(
        host="127.0.0.1", ws_port=0, rest_port=0, database_url=db_url
    )
    await srv.start()
    try:
        ws1 = await open_client(srv.ws_bound_port)
        ws2 = await open_client(srv.ws_bound_port)
        async with ws1, ws2:
            await recv_json(ws1)
            target_id = (await recv_json(ws2))["payload"]["client_id"]

            await ws1.send(json.dumps({
                "type": TYPE_BROADCAST,
                "payload": {"text": "hello everyone"},
            }))
            await recv_json(ws1)
            await recv_json(ws2)

            await ws2.send(json.dumps({
                "type": TYPE_SUBSCRIBE,
                "payload": {"channel": "alerts"},
            }))
            await recv_json(ws2)

            await ws1.send(json.dumps({
                "type": TYPE_BROADCAST,
                "channel": "alerts",
                "payload": {"text": "channel hello"},
            }))
            await recv_json(ws2)

            await ws1.send(json.dumps({
                "type": TYPE_DIRECT,
                "payload": {"target_id": target_id, "text": "private"},
            }))
            await recv_json(ws2)

        status, body = await get_json(
            srv.rest_bound_port, "/messages?limit=50&offset=0"
        )
        assert status == 200
        assert body["total"] == 3
        assert body["limit"] == 50
        assert body["offset"] == 0

        by_channel = {m["channel"]: m for m in body["messages"]}
        assert set(by_channel) == {"broadcast", "alerts", "direct"}
        assert by_channel["broadcast"]["payload"]["text"] == "hello everyone"
        assert by_channel["alerts"]["payload"]["text"] == "channel hello"
        assert by_channel["direct"]["payload"]["text"] == "private"
        for message in body["messages"]:
            assert set(message) >= {
                "id", "channel", "type", "payload", "timestamp"
            }
            assert message["type"] == TYPE_BROADCAST or message["type"] == TYPE_DIRECT

        status, body = await get_json(
            srv.rest_bound_port, "/messages?limit=2&offset=0"
        )
        assert len(body["messages"]) == 2
        assert body["total"] == 3

        status, body = await get_json(
            srv.rest_bound_port, "/messages?limit=2&offset=2"
        )
        assert len(body["messages"]) == 1
        assert body["total"] == 3
    finally:
        await srv.stop()


async def test_history_persists_across_restart(tmp_path):
    db_url = f"sqlite:///{tmp_path}/history.db"
    srv_a = NotificationServer(
        host="127.0.0.1", ws_port=0, rest_port=0, database_url=db_url
    )
    await srv_a.start()
    ws = await open_client(srv_a.ws_bound_port)
    async with ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": TYPE_BROADCAST,
            "payload": {"text": "stored before restart"},
        }))
        await recv_json(ws)
    await srv_a.stop()

    srv_b = NotificationServer(
        host="127.0.0.1", ws_port=0, rest_port=0, database_url=db_url
    )
    await srv_b.start()
    try:
        status, body = await get_json(srv_b.rest_bound_port, "/messages")
        assert status == 200
        assert body["total"] == 1
        assert body["messages"][0]["payload"]["text"] == "stored before restart"
    finally:
        await srv_b.stop()


async def test_messages_endpoint_with_redis_backbone(fake_server, tmp_path):
    db_url = f"sqlite:///{tmp_path}/backbone.db"
    srv = make_server(fake_server, database_url=db_url)
    await srv.start()
    try:
        ws1 = await open_client(srv.ws_bound_port)
        ws2 = await open_client(srv.ws_bound_port)
        async with ws1, ws2:
            await recv_json(ws1)
            await recv_json(ws2)
            await ws1.send(json.dumps({
                "type": TYPE_BROADCAST,
                "payload": {"text": "via redis backbone"},
            }))
            await recv_json(ws1)
            await recv_json(ws2)

        status, body = await get_json(srv.rest_bound_port, "/messages")
        assert status == 200
        assert body["total"] == 1
        assert body["messages"][0]["payload"]["text"] == "via redis backbone"
    finally:
        await srv.stop()
