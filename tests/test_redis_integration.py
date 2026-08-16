"""Integration tests for the Redis pub/sub backbone and SQLite persistence.

Redis pub/sub delivery is exercised against a shared ``fakeredis`` broker so
the tests run without a real Redis server: ``notification_server._get_redis``
is patched to return the fake broker, which all server instances share just
like a real deployment would share one Redis.
"""

import asyncio
import json
import urllib.request

import pytest
import websockets
from fakeredis import FakeRedis

import notification_server as ns
from notification_server import NotificationServer, make_message


def parse(raw) -> dict:
    return json.loads(raw)


async def http_get(url: str):
    def _get():
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())

    return await asyncio.to_thread(_get)


async def make_server() -> NotificationServer:
    srv = await NotificationServer().start()
    await asyncio.to_thread(srv.redis_ready.wait, 5)
    assert srv.redis_ready.is_set()
    return srv


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch):
    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(ns, "_get_redis", lambda: fake)
    monkeypatch.setattr(ns, "_redis_failed", False)
    monkeypatch.setattr(ns, "_redis_client", None)
    return fake


@pytest.fixture(autouse=True)
def clean_messages():
    store = ns.MessageStore()
    store.clear()
    yield
    store.clear()


# ── Redis pub/sub delivery ─────────────────────────────────────────

async def test_redis_pubsub_delivers_broadcast(patch_redis):
    srv = await make_server()
    try:
        async with websockets.connect(srv.ws_url) as a, \
                   websockets.connect(srv.ws_url) as b:
            await a.recv()
            await b.recv()
            await a.send(
                json.dumps(make_message("broadcast", {"text": "redis-broadcast"}))
            )
            msg_b = parse(await asyncio.wait_for(b.recv(), timeout=3))
            assert msg_b["type"] == "broadcast"
            assert msg_b["payload"]["text"] == "redis-broadcast"
            msg_a = parse(await asyncio.wait_for(a.recv(), timeout=3))
            assert msg_a["payload"]["text"] == "redis-broadcast"
    finally:
        await srv.stop()


async def test_redis_multiple_servers_share_backbone(patch_redis):
    srv_a = await make_server()
    srv_b = await make_server()
    try:
        async with websockets.connect(srv_a.ws_url) as a, \
                   websockets.connect(srv_b.ws_url) as b:
            await a.recv()
            await b.recv()
            await a.send(
                json.dumps(make_message("broadcast", {"text": "cross-server"}))
            )
            msg_b = parse(await asyncio.wait_for(b.recv(), timeout=3))
            assert msg_b["payload"]["text"] == "cross-server"
            msg_a = parse(await asyncio.wait_for(a.recv(), timeout=3))
            assert msg_a["payload"]["text"] == "cross-server"
    finally:
        await srv_a.stop()
        await srv_b.stop()


async def test_redis_channel_delivery_across_servers(patch_redis):
    srv_a = await make_server()
    srv_b = await make_server()
    try:
        async with websockets.connect(srv_a.ws_url) as sub_a, \
                   websockets.connect(srv_b.ws_url) as sub_b, \
                   websockets.connect(srv_b.ws_url) as non_sub:
            await sub_a.recv()
            await sub_b.recv()
            await non_sub.recv()
            await sub_a.send(
                json.dumps(make_message("subscribe", {"channel": "alerts"}))
            )
            await sub_b.send(
                json.dumps(make_message("subscribe", {"channel": "alerts"}))
            )
            await asyncio.sleep(0.1)

            async with websockets.connect(srv_a.ws_url) as sender:
                await sender.recv()
                await sender.send(
                    json.dumps(
                        make_message(
                            "broadcast", {"channel": "alerts", "text": "chan-cross"}
                        )
                    )
                )
                got_a = parse(await asyncio.wait_for(sub_a.recv(), timeout=3))
                assert got_a["payload"]["text"] == "chan-cross"
                got_b = parse(await asyncio.wait_for(sub_b.recv(), timeout=3))
                assert got_b["payload"]["text"] == "chan-cross"
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(non_sub.recv(), timeout=0.5)
    finally:
        await srv_a.stop()
        await srv_b.stop()


async def test_redis_direct_across_servers(patch_redis):
    srv_a = await make_server()
    srv_b = await make_server()
    try:
        async with websockets.connect(srv_a.ws_url) as sender, \
                   websockets.connect(srv_b.ws_url) as target_ws:
            sender_id = parse(await sender.recv())["payload"]["client_id"]
            target_id = parse(await target_ws.recv())["payload"]["client_id"]
            await sender.send(
                json.dumps(
                    make_message("direct", {"to": target_id, "data": {"note": "hey"}})
                )
            )
            msg = parse(await asyncio.wait_for(target_ws.recv(), timeout=3))
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == sender_id
            assert msg["payload"]["to"] == target_id
            assert msg["payload"]["data"] == {"note": "hey"}
    finally:
        await srv_a.stop()
        await srv_b.stop()


# ── Connection state stored in Redis ───────────────────────────────

async def test_redis_client_state_stored(patch_redis):
    fake = patch_redis
    srv = await make_server()
    try:
        async with websockets.connect(srv.ws_url) as ws:
            cid = parse(await ws.recv())["payload"]["client_id"]
            await asyncio.sleep(0.1)
            assert fake.hget("chat:clients", cid) == srv.server_id
            assert cid in fake.smembers(f"chat:server:{srv.server_id}:clients")

        await asyncio.sleep(0.2)
        assert fake.hget("chat:clients", cid) is None
        assert cid not in fake.smembers(f"chat:server:{srv.server_id}:clients")
    finally:
        await srv.stop()


async def test_redis_channel_subscription_synced(patch_redis):
    fake = patch_redis
    srv = await make_server()
    try:
        async with websockets.connect(srv.ws_url) as ws:
            cid = parse(await ws.recv())["payload"]["client_id"]
            await ws.send(json.dumps(make_message("subscribe", {"channel": "redis-sub"})))
            await asyncio.sleep(0.1)
            assert cid in fake.smembers(f"chat:channel:{srv.server_id}:redis-sub")

            await ws.send(
                json.dumps(make_message("unsubscribe", {"channel": "redis-sub"}))
            )
            await asyncio.sleep(0.1)
            assert cid not in fake.smembers(f"chat:channel:{srv.server_id}:redis-sub")
    finally:
        await srv.stop()


async def test_client_state_survives_server_restart(patch_redis):
    fake = patch_redis
    srv_a = await make_server()
    ws = await websockets.connect(srv_a.ws_url)
    cid = parse(await ws.recv())["payload"]["client_id"]
    await ws.send(json.dumps(make_message("subscribe", {"channel": "persist"})))
    await asyncio.sleep(0.1)
    assert fake.hget("chat:clients", cid) == srv_a.server_id

    await srv_a.stop()
    await asyncio.sleep(0.2)
    assert fake.hget("chat:clients", cid) == srv_a.server_id
    assert cid in fake.smembers(f"chat:channel:{srv_a.server_id}:persist")

    srv_b = await make_server()
    try:
        assert fake.hget("chat:clients", cid) == srv_a.server_id
    finally:
        await srv_b.stop()
        await ws.close()


# ── SQLite persistence / REST history ──────────────────────────────

async def test_messages_endpoint_returns_history(patch_redis):
    srv = await make_server()
    try:
        async with websockets.connect(srv.ws_url) as a, \
                   websockets.connect(srv.ws_url) as b:
            await a.recv()
            await b.recv()
            await a.send(json.dumps(make_message("broadcast", {"text": "persist-me"})))
            await asyncio.wait_for(b.recv(), timeout=3)
            await asyncio.sleep(0.1)

        data = await http_get(f"{srv.http_url}/messages?limit=50&offset=0")
        assert isinstance(data, list)
        assert data
        matched = [m for m in data if m["payload"].get("text") == "persist-me"]
        assert len(matched) >= 1
        assert matched[0]["type"] == "broadcast"
        assert set(matched[0]) == {"id", "channel", "type", "payload", "timestamp"}
    finally:
        await srv.stop()


async def test_messages_endpoint_pagination(patch_redis):
    srv = await make_server()
    try:
        async def send_one(text: str):
            async with websockets.connect(srv.ws_url) as a, \
                       websockets.connect(srv.ws_url) as b:
                await a.recv()
                await b.recv()
                await a.send(json.dumps(make_message("broadcast", {"text": text})))
                await asyncio.wait_for(b.recv(), timeout=3)
                await asyncio.sleep(0.05)

        for i in range(5):
            await send_one(f"page-{i}")

        page1 = await http_get(f"{srv.http_url}/messages?limit=2&offset=0")
        assert len(page1) == 2
        page2 = await http_get(f"{srv.http_url}/messages?limit=2&offset=2")
        assert len(page2) == 2
        assert not {m["id"] for m in page1} & {m["id"] for m in page2}

        default = await http_get(f"{srv.http_url}/messages")
        assert len(default) == 5
    finally:
        await srv.stop()


async def test_direct_message_is_persisted(patch_redis):
    srv = await make_server()
    try:
        async with websockets.connect(srv.ws_url) as a, \
                   websockets.connect(srv.ws_url) as b:
            a_id = parse(await a.recv())["payload"]["client_id"]
            b_id = parse(await b.recv())["payload"]["client_id"]
            await a.send(
                json.dumps(
                    make_message("direct", {"to": b_id, "data": {"note": "stored"}})
                )
            )
            msg = parse(await asyncio.wait_for(b.recv(), timeout=3))
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == a_id
            await asyncio.sleep(0.1)

        data = await http_get(f"{srv.http_url}/messages?limit=50&offset=0")
        matched = [m for m in data if m["type"] == "direct"]
        assert len(matched) >= 1
        assert matched[0]["payload"]["data"] == {"note": "stored"}
    finally:
        await srv.stop()
