"""
Integration tests for the Redis pub/sub backbone and SQLite persistence.

These tests exercise the cross-instance behaviour of the notification server:
multiple server instances sharing a single Redis broker must route messages to
the correct clients, and every application message must be persisted to SQLite
and retrievable via ``GET /messages``.
"""

import asyncio
import json
import urllib.request

import fakeredis.aioredis
import pytest
import websockets

from broker import MessageBroker
from notification_server import NotificationServer, decode_message, encode_message


@pytest.fixture
async def shared_redis():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield redis
    await redis.aclose()


def ws_url(server):
    return f"ws://127.0.0.1:{server.port}"


def _get(url):
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


async def _get_json(url):
    body = await asyncio.to_thread(_get, url)
    return json.loads(body)


async def wait_for_subscribers(server, channel, expected, timeout=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    url = f"http://127.0.0.1:{server.port}/channels/{channel}/subscribers"
    while True:
        subs = (await _get_json(url))["subscribers"]
        if len(subs) >= expected:
            return subs
        if loop.time() > deadline:
            raise AssertionError(f"channel {channel} never reached {expected} subscriber(s)")
        await asyncio.sleep(0.02)


def make_server(redis, db_path):
    return NotificationServer(
        broker=MessageBroker(redis=redis),
        database_url=str(db_path),
    )


async def test_cross_instance_broadcast_via_redis(shared_redis, tmp_path):
    srv1 = make_server(shared_redis, tmp_path / "a.db")
    srv2 = make_server(shared_redis, tmp_path / "b.db")
    await srv1.start(port=0)
    await srv2.start(port=0)
    try:
        async with websockets.connect(ws_url(srv1)) as ws1, websockets.connect(
            ws_url(srv2)
        ) as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(
                encode_message(
                    {"type": "broadcast", "payload": {"text": "cross"}, "timestamp": "t"}
                )
            )

            got1 = decode_message(await ws1.recv())
            got2 = decode_message(await ws2.recv())
            assert got1["payload"]["text"] == "cross"
            assert got2["payload"]["text"] == "cross"
    finally:
        await srv1.stop()
        await srv2.stop()


async def test_cross_instance_channel_delivery(shared_redis, tmp_path):
    srv1 = make_server(shared_redis, tmp_path / "a.db")
    srv2 = make_server(shared_redis, tmp_path / "b.db")
    await srv1.start(port=0)
    await srv2.start(port=0)
    try:
        async with websockets.connect(ws_url(srv1)) as ws1, websockets.connect(
            ws_url(srv2)
        ) as ws2:
            await ws1.recv()
            await ws2.recv()

            await ws1.send(
                encode_message({"type": "subscribe", "payload": {"channel": "alerts"}})
            )
            await wait_for_subscribers(srv1, "alerts", 1)

            await ws2.send(
                encode_message(
                    {"type": "broadcast", "payload": {"text": "siren"}, "channel": "alerts"}
                )
            )

            got = decode_message(await ws1.recv())
            assert got["channel"] == "alerts"
            assert got["payload"]["text"] == "siren"
    finally:
        await srv1.stop()
        await srv2.stop()


async def test_cross_instance_direct_delivery(shared_redis, tmp_path):
    srv1 = make_server(shared_redis, tmp_path / "a.db")
    srv2 = make_server(shared_redis, tmp_path / "b.db")
    await srv1.start(port=0)
    await srv2.start(port=0)
    try:
        async with websockets.connect(ws_url(srv1)) as ws1, websockets.connect(
            ws_url(srv2)
        ) as ws2:
            msg1 = decode_message(await ws1.recv())
            msg2 = decode_message(await ws2.recv())
            target = msg2["payload"]["client_id"]

            await ws1.send(
                encode_message(
                    {
                        "type": "direct",
                        "payload": {"client_id": target, "text": "hi"},
                        "timestamp": "t",
                    }
                )
            )

            got = decode_message(await ws2.recv())
            assert got["type"] == "direct"
            assert got["payload"]["text"] == "hi"
            assert got["payload"]["sender_id"] == msg1["payload"]["client_id"]
    finally:
        await srv1.stop()
        await srv2.stop()


async def test_client_state_stored_in_redis(shared_redis, tmp_path):
    srv = make_server(shared_redis, tmp_path / "a.db")
    await srv.start(port=0)
    try:
        async with websockets.connect(ws_url(srv)) as ws:
            msg = decode_message(await ws.recv())
            cid = msg["payload"]["client_id"]

            ids = await shared_redis.smembers("notify:clients")
            assert str(cid) in ids

            info = await shared_redis.hgetall(f"notify:client:{cid}")
            assert info["instance_id"] == srv.instance_id
            assert "connected_at" in info

        loop = asyncio.get_running_loop()
        deadline = loop.time() + 2.0
        while True:
            ids = await shared_redis.smembers("notify:clients")
            if str(cid) not in ids:
                break
            if loop.time() > deadline:
                raise AssertionError("client state was not cleaned up on disconnect")
            await asyncio.sleep(0.02)
    finally:
        await srv.stop()


async def test_client_id_counter_survives_restart(shared_redis, tmp_path):
    broker = MessageBroker(redis=shared_redis)

    srv1 = NotificationServer(broker=broker, database_url=str(tmp_path / "a.db"))
    await srv1.start(port=0)
    async with websockets.connect(ws_url(srv1)) as ws:
        first_id = decode_message(await ws.recv())["payload"]["client_id"]
    await srv1.stop()

    srv2 = NotificationServer(broker=broker, database_url=str(tmp_path / "b.db"))
    await srv2.start(port=0)
    async with websockets.connect(ws_url(srv2)) as ws:
        second_id = decode_message(await ws.recv())["payload"]["client_id"]
    await srv2.stop()

    assert second_id == first_id + 1


async def test_messages_persisted_to_sqlite(shared_redis, tmp_path):
    srv = make_server(shared_redis, tmp_path / "a.db")
    await srv.start(port=0)
    try:
        async with websockets.connect(ws_url(srv)) as ws1, websockets.connect(
            ws_url(srv)
        ) as ws2:
            msg2 = decode_message(await ws1.recv())
            decode_message(await ws2.recv())
            target = msg2["payload"]["client_id"]

            await ws1.send(
                encode_message(
                    {"type": "broadcast", "payload": {"text": "b"}, "timestamp": "t1"}
                )
            )
            await ws1.send(
                encode_message(
                    {"type": "direct", "payload": {"client_id": target, "text": "d"}}
                )
            )
            for _ in range(2):
                await ws1.recv()
            await ws2.recv()

        assert srv.store.count() == 2
        messages = srv.store.query(limit=10)
        types = sorted(m["type"] for m in messages)
        assert types == ["broadcast", "direct"]
    finally:
        await srv.stop()


async def test_get_messages_endpoint(shared_redis, tmp_path):
    srv = make_server(shared_redis, tmp_path / "a.db")
    await srv.start(port=0)
    try:
        async with websockets.connect(ws_url(srv)) as ws:
            await ws.recv()
            await ws.send(
                encode_message({"type": "subscribe", "payload": {"channel": "feed"}})
            )
            await wait_for_subscribers(srv, "feed", 1)
            for i in range(3):
                await ws.send(
                    encode_message(
                        {
                            "type": "broadcast",
                            "payload": {"n": i},
                            "channel": "feed",
                            "timestamp": "t",
                        }
                    )
                )
                await ws.recv()

        url = f"http://127.0.0.1:{srv.port}/messages"
        data = await _get_json(url)
        assert len(data["messages"]) == 3

        page = await _get_json(f"{url}?limit=2&offset=0")
        assert len(page["messages"]) == 2

        first = page["messages"][0]
        assert first["channel"] == "feed"
        assert first["type"] == "broadcast"
        assert first["payload"] == {"n": 2, "sender_id": 1}

        offset_page = await _get_json(f"{url}?limit=10&offset=2")
        assert len(offset_page["messages"]) == 1
        assert offset_page["messages"][0]["payload"]["n"] == 0
    finally:
        await srv.stop()
