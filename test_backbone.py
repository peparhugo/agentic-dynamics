"""Integration tests for the Redis pub/sub backbone and SQLite persistence."""

import asyncio
import json
import time

import aiohttp
import fakeredis
import fakeredis.aioredis
import pytest
from websockets.asyncio.client import connect

from broker import FANOUT_CHANNEL, KEY_PREFIX, MessageStore, RedisBroker
from server import NotificationServer


async def recv_json(ws, timeout=5.0):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout))


async def recv_nothing(ws, timeout=0.2):
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws.recv(), timeout)


async def wait_until(cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await cond():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met within timeout")


@pytest.fixture
def fakeredis_server():
    return fakeredis.FakeServer()


def make_server(fs, db_path):
    """Build a server that shares the given (fake) Redis with other servers."""
    backbone = RedisBroker(server=fs)
    store = MessageStore(str(db_path))
    return NotificationServer(backbone=backbone, store=store)


async def start(srv):
    await srv.start(host="localhost", port=0)
    return srv._server.sockets[0].getsockname()[1]


async def redis_client(fs):
    return fakeredis.aioredis.FakeRedis(server=fs, decode_responses=True)


# ── Redis pub/sub backbone ─────────────────────────────────────


async def test_redis_channel_receives_published_event(fakeredis_server, tmp_path):
    raw = await redis_client(fakeredis_server)
    pubsub = raw.pubsub()
    await pubsub.subscribe(FANOUT_CHANNEL)
    await asyncio.sleep(0.05)

    srv = make_server(fakeredis_server, tmp_path / "hist.db")
    port = await start(srv)
    received = []

    async def reader():
        async for msg in pubsub.listen():
            if msg.get("type") == "message":
                received.append(json.loads(msg["data"]))
                return

    task = asyncio.create_task(reader())
    async with connect(f"ws://localhost:{port}") as ws:
        await recv_json(ws)
        await ws.send(
            json.dumps(
                {"type": "broadcast", "channel": "news", "payload": {"text": "hi"}}
            )
        )
        await asyncio.sleep(0.1)

    await asyncio.wait_for(task, timeout=3.0)
    await srv.stop()
    await pubsub.aclose()
    await raw.aclose()

    assert received, "no event was received on the Redis pub/sub channel"
    event = received[0]
    assert event["message"]["type"] == "broadcast"
    assert event["message"]["payload"] == {"text": "hi"}
    assert event["channel"] == "news"


async def test_multiple_servers_share_redis_backbone(fakeredis_server, tmp_path):
    srv_a = make_server(fakeredis_server, tmp_path / "a.db")
    srv_b = make_server(fakeredis_server, tmp_path / "b.db")
    port_a = await start(srv_a)
    port_b = await start(srv_b)

    async with connect(f"ws://localhost:{port_a}") as ws_a, connect(
        f"ws://localhost:{port_b}"
    ) as ws_b:
        welcome_a = await recv_json(ws_a)
        welcome_b = await recv_json(ws_b)
        id_a = welcome_a["payload"]["client_id"]
        id_b = welcome_b["payload"]["client_id"]
        assert id_a != id_b

        await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await ws_b.send(json.dumps({"type": "subscribe", "channel": "alerts"}))

        probe = await redis_client(fakeredis_server)
        async def _subs_ready():
            return (await probe.smembers(f"{KEY_PREFIX}subs:alerts")) == {id_a, id_b}
        await wait_until(_subs_ready)
        await probe.aclose()

        await ws_a.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"text": "cluster"},
                }
            )
        )
        assert (await recv_json(ws_a))["payload"] == {"text": "cluster"}
        assert (await recv_json(ws_b))["payload"] == {"text": "cluster"}

        # Direct messages cross server boundaries through the same backbone.
        await ws_a.send(
            json.dumps(
                {"type": "direct", "payload": {"target_id": id_b, "text": "psst"}}
            )
        )
        direct = await recv_json(ws_b)
        assert direct["type"] == "direct"
        assert direct["payload"] == {"target_id": id_b, "text": "psst"}
        await recv_nothing(ws_a)

    await srv_a.stop()
    await srv_b.stop()


async def test_connection_state_survives_server_restart(fakeredis_server, tmp_path):
    db = tmp_path / "hist.db"
    srv = make_server(fakeredis_server, db)
    port = await start(srv)

    # A live client subscribes through the real WebSocket path; the state lands
    # in Redis (connection state is not only in server memory).
    async with connect(f"ws://localhost:{port}") as ws:
        welcome = await recv_json(ws)
        cid = welcome["payload"]["client_id"]
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        probe = await redis_client(fakeredis_server)
        async def _channel_recorded():
            return "alerts" in (await probe.smembers(f"{KEY_PREFIX}channels:{cid}"))
        await wait_until(_channel_recorded)
        await probe.aclose()
        await ws.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"text": "before-restart"},
                }
            )
        )
        assert (await recv_json(ws))["payload"] == {"text": "before-restart"}
    # Let the disconnect cleanup finish before simulating the crash below.
    await asyncio.sleep(0.2)

    # Simulate a crash: the state that was in Redis is exactly what a fresh
    # server hydrates from when it boots on the same Redis + SQLite.
    await srv._backbone.subscribe(cid, "alerts")
    await srv._backbone.register_client(cid)
    await srv.stop()

    srv2 = make_server(fakeredis_server, db)
    port2 = await start(srv2)
    assert srv2.channel_subscribers("alerts") == [cid]
    assert srv2.subscribed_channels(cid) == ["alerts"]

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:{port2}/messages") as resp:
            assert resp.status == 200
            body = await resp.json()
    assert any(
        m["type"] == "broadcast" and m["payload"] == {"text": "before-restart"}
        for m in body["messages"]
    )
    await srv2.stop()


# ── Message persistence ────────────────────────────────────────


async def test_messages_persistence_and_rest_endpoint(tmp_path):
    db = tmp_path / "hist.db"
    srv = NotificationServer(store=MessageStore(str(db)))
    port = await start(srv)
    async with connect(f"ws://localhost:{port}") as ws:
        welcome = await recv_json(ws)
        cid = welcome["payload"]["client_id"]
        await srv.broadcast({"text": "one"}, channel="news")
        await srv.broadcast({"text": "two"})
        await srv.send_direct(cid, {"text": "three"})
        assert (await recv_json(ws))["payload"] == {"text": "two"}
        assert (await recv_json(ws))["payload"] == {"text": "three"}

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"http://localhost:{port}/messages?limit=50&offset=0"
        ) as resp:
            assert resp.status == 200
            body = await resp.json()

    assert body["limit"] == 50
    assert body["offset"] == 0
    msgs = body["messages"]
    for msg in msgs:
        assert set(msg) >= {"id", "channel", "type", "payload", "timestamp"}
    assert msgs[0]["type"] == "direct" and msgs[0]["payload"] == {"text": "three"}
    assert msgs[1]["type"] == "broadcast" and msgs[1]["payload"] == {"text": "two"}
    assert msgs[2]["type"] == "broadcast"
    assert msgs[2]["payload"] == {"text": "one"}
    assert msgs[2]["channel"] == "news"
    assert msgs[3]["type"] == "system" and msgs[3]["payload"]["event"] == "connected"

    # limit returns only the newest N messages.
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:{port}/messages?limit=2") as resp:
            page = await resp.json()
    assert [m["payload"].get("text") for m in page["messages"]] == ["three", "two"]

    # offset skips the newest messages.
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"http://localhost:{port}/messages?limit=1&offset=1"
        ) as resp:
            page2 = await resp.json()
    assert page2["messages"][0]["payload"] == {"text": "two"}

    # Persisted history outlives the server instance that wrote it.
    srv2 = NotificationServer(store=MessageStore(str(db)))
    port2 = await start(srv2)
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:{port2}/messages") as resp:
            assert resp.status == 200
            body2 = await resp.json()
    assert len(body2["messages"]) >= 4
    await srv.stop()
    await srv2.stop()


async def test_messages_endpoint_defaults(tmp_path):
    db = tmp_path / "hist.db"
    srv = NotificationServer(store=MessageStore(str(db)))
    port = await start(srv)
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:{port}/messages") as resp:
            assert resp.status == 200
            body = await resp.json()
    assert body["messages"] == []
    assert body["limit"] == 50
    assert body["offset"] == 0
    await srv.stop()
