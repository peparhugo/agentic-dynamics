"""Integration tests for the Redis pub/sub backbone and message persistence."""

import asyncio
import json
import urllib.request

import pytest
import websockets
from fakeredis import FakeServer
from fakeredis.aioredis import FakeRedis

from notification_server import (
    NotificationServer,
    RedisBus,
    decode_message,
    encode_message,
)


async def connect_client(port):
    """Connect a client and consume its initial system 'connected' message."""
    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    msg = decode_message(raw)
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "connected"
    return ws, msg["payload"]["client_id"]


async def get_json(port, path):
    url = f"http://127.0.0.1:{port}{path}"
    resp = await asyncio.to_thread(urllib.request.urlopen, url)
    return json.loads(resp.read().decode("utf-8"))


async def wait_for_channel(port, name, timeout=5):
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        channels = await get_json(port, "/channels")
        if name in channels:
            return
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"channel {name!r} not found in {channels!r}")
        await asyncio.sleep(0.05)


async def test_redis_broadcast_across_servers(tmp_path):
    fake_server = FakeServer()
    c1 = FakeRedis(server=fake_server, decode_responses=True)
    c2 = FakeRedis(server=fake_server, decode_responses=True)

    ns1 = NotificationServer(redis_client=c1, database_url=str(tmp_path / "a.db"))
    ns2 = NotificationServer(redis_client=c2, database_url=str(tmp_path / "b.db"))
    await ns1.start()
    await ns2.start()
    try:
        async with websockets.serve(
            ns1.handler, "127.0.0.1", 0, process_request=ns1.process_request
        ) as s1, websockets.serve(
            ns2.handler, "127.0.0.1", 0, process_request=ns2.process_request
        ) as s2:
            p1 = s1.sockets[0].getsockname()[1]
            p2 = s2.sockets[0].getsockname()[1]
            ws1, _ = await connect_client(p1)
            ws2, _ = await connect_client(p2)

            await ws1.send(
                encode_message({"type": "broadcast", "payload": {"text": "cross-server"}})
            )
            got = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
            assert got["type"] == "broadcast"
            assert got["payload"]["text"] == "cross-server"

            await ws1.close()
            await ws2.close()
    finally:
        await ns1.stop()
        await ns2.stop()


async def test_redis_direct_across_servers(tmp_path):
    fake_server = FakeServer()
    c1 = FakeRedis(server=fake_server, decode_responses=True)
    c2 = FakeRedis(server=fake_server, decode_responses=True)

    ns1 = NotificationServer(redis_client=c1, database_url=str(tmp_path / "a.db"))
    ns2 = NotificationServer(redis_client=c2, database_url=str(tmp_path / "b.db"))
    await ns1.start()
    await ns2.start()
    try:
        async with websockets.serve(
            ns1.handler, "127.0.0.1", 0, process_request=ns1.process_request
        ) as s1, websockets.serve(
            ns2.handler, "127.0.0.1", 0, process_request=ns2.process_request
        ) as s2:
            p1 = s1.sockets[0].getsockname()[1]
            p2 = s2.sockets[0].getsockname()[1]
            ws1, _ = await connect_client(p1)
            ws2, target_id = await connect_client(p2)

            await ws1.send(
                encode_message(
                    {"type": "direct", "payload": {"to": target_id, "text": "just you"}}
                )
            )
            got = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
            assert got["type"] == "direct"
            assert got["payload"]["text"] == "just you"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws1.recv(), timeout=0.3)

            await ws1.close()
            await ws2.close()
    finally:
        await ns1.stop()
        await ns2.stop()


async def test_redis_channel_routing_across_servers(tmp_path):
    fake_server = FakeServer()
    c1 = FakeRedis(server=fake_server, decode_responses=True)
    c2 = FakeRedis(server=fake_server, decode_responses=True)

    ns1 = NotificationServer(redis_client=c1, database_url=str(tmp_path / "a.db"))
    ns2 = NotificationServer(redis_client=c2, database_url=str(tmp_path / "b.db"))
    await ns1.start()
    await ns2.start()
    try:
        async with websockets.serve(
            ns1.handler, "127.0.0.1", 0, process_request=ns1.process_request
        ) as s1, websockets.serve(
            ns2.handler, "127.0.0.1", 0, process_request=ns2.process_request
        ) as s2:
            p1 = s1.sockets[0].getsockname()[1]
            p2 = s2.sockets[0].getsockname()[1]
            ws1, _ = await connect_client(p1)
            ws2, _ = await connect_client(p2)

            await ws2.send(encode_message({"type": "subscribe", "channel": "alerts"}))
            await wait_for_channel(p2, "alerts")

            await ws1.send(
                encode_message(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "payload": {"text": "alert!"},
                    }
                )
            )
            got = decode_message(await asyncio.wait_for(ws2.recv(), timeout=5))
            assert got["type"] == "broadcast"
            assert got["payload"]["text"] == "alert!"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws1.recv(), timeout=0.3)

            await ws1.close()
            await ws2.close()
    finally:
        await ns1.stop()
        await ns2.stop()


async def test_redis_client_state_survives(tmp_path):
    fake_server = FakeServer()
    c1 = FakeRedis(server=fake_server, decode_responses=True)

    ns1 = NotificationServer(redis_client=c1, database_url=str(tmp_path / "a.db"))
    await ns1.start()
    try:
        async with websockets.serve(
            ns1.handler, "127.0.0.1", 0, process_request=ns1.process_request
        ) as s1:
            p1 = s1.sockets[0].getsockname()[1]
            ws, client_id = await connect_client(p1)

            await asyncio.sleep(0.1)
            assert client_id in await ns1.bus.connected_clients()
            stored = json.loads(await c1.get(RedisBus.CLIENT_KEY_PREFIX + client_id))
            assert stored["server_id"] == ns1.server_id
            assert stored["client_id"] == client_id

            await ws.close()
            await ws.wait_closed()
            await asyncio.sleep(0.1)
            assert client_id not in await ns1.bus.connected_clients()
    finally:
        await ns1.stop()


async def test_message_persistence(tmp_path):
    db = str(tmp_path / "history.db")
    ns = NotificationServer(database_url=db)
    async with websockets.serve(
        ns.handler, "127.0.0.1", 0, process_request=ns.process_request
    ) as s:
        port = s.sockets[0].getsockname()[1]
        ws, _ = await connect_client(port)

        await ws.send(encode_message({"type": "broadcast", "payload": {"text": "hello"}}))
        got = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))
        assert got["payload"]["text"] == "hello"

        messages = await get_json(port, "/messages")
        assert len(messages) >= 1
        msg = messages[0]
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "hello"}
        assert msg["channel"] is None
        assert msg["timestamp"]

        await ws.close()


async def test_message_persistence_limit_offset(tmp_path):
    db = str(tmp_path / "history.db")
    ns = NotificationServer(database_url=db)
    async with websockets.serve(
        ns.handler, "127.0.0.1", 0, process_request=ns.process_request
    ) as s:
        port = s.sockets[0].getsockname()[1]
        ws, _ = await connect_client(port)

        for i in range(5):
            await ws.send(encode_message({"type": "broadcast", "payload": {"n": i}}))
            _ = decode_message(await asyncio.wait_for(ws.recv(), timeout=5))

        page = await get_json(port, "/messages?limit=2&offset=0")
        assert len(page) == 2
        assert page[0]["payload"]["n"] == 4
        assert page[1]["payload"]["n"] == 3

        page2 = await get_json(port, "/messages?limit=2&offset=2")
        assert page2[0]["payload"]["n"] == 2
        assert page2[1]["payload"]["n"] == 1

        await ws.close()


def test_env_config(monkeypatch, tmp_path):
    db = str(tmp_path / "env.db")
    monkeypatch.setenv("DATABASE_URL", db)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    ns = NotificationServer()
    assert ns.store.database_url == db
    assert ns.bus is not None
    assert ns.bus.redis_url == "redis://localhost:6379/0"
