"""Integration tests for the Redis pub/sub backbone and SQLite persistence.

These tests use fakeredis (an in-memory Redis emulator) so they run without a
real Redis server. Two server instances share a single ``fakeredis.FakeServer``
to exercise the multi-instance pub/sub backbone.
"""

import asyncio
import json
import os
import shutil
import tempfile

import aiohttp
import fakeredis
import pytest
import websockets

from broker import BROADCAST_CHANNEL, client_state_key
from server import NotificationServer, build_message


def make_pair():
    """Return two FakeAsyncRedis clients backed by the same FakeServer."""
    server = fakeredis.FakeServer()
    return (
        fakeredis.FakeAsyncRedis(server=server),
        fakeredis.FakeAsyncRedis(server=server),
    )


async def connect_client(ws_url):
    """Connect a client and consume its initial 'connected' system message."""
    ws = await websockets.connect(ws_url)
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    msg = json.loads(raw)
    assert msg["type"] == "system"
    assert "client_id" in msg["payload"]
    return ws, msg["payload"]["client_id"]


async def http_get(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return resp.status, await resp.json()


# ── Redis pub/sub backbone ────────────────────────────────────────


async def test_external_publisher_reaches_connected_client():
    redis_a, _ = make_pair()
    srv = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_a)
    await srv.start()
    try:
        ws, _ = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
        try:
            payload = {"text": "from external worker"}
            message = build_message("broadcast", payload)
            wrapper = json.dumps({"origin": "external-worker", "message": message})
            await redis_a.publish(BROADCAST_CHANNEL, wrapper)
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == payload
        finally:
            await ws.close()
    finally:
        await srv.close()


async def test_broadcast_reaches_clients_on_another_instance():
    redis_a, redis_b = make_pair()
    srv_a = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_a)
    srv_b = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_b)
    await srv_a.start()
    await srv_b.start()
    try:
        ws_a, _ = await connect_client(f"ws://127.0.0.1:{srv_a.bound_port}")
        ws_b, _ = await connect_client(f"ws://127.0.0.1:{srv_b.bound_port}")
        try:
            payload = {"text": "hello across instances"}
            await ws_a.send(json.dumps({"type": "broadcast", "payload": payload}))
            received = [
                json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                for ws in (ws_a, ws_b)
            ]
            for msg in received:
                assert msg["type"] == "broadcast"
                assert msg["payload"] == payload
        finally:
            await ws_a.close()
            await ws_b.close()
    finally:
        await srv_a.close()
        await srv_b.close()


async def test_direct_message_routed_between_instances():
    redis_a, redis_b = make_pair()
    srv_a = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_a)
    srv_b = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_b)
    await srv_a.start()
    await srv_b.start()
    try:
        ws_a, _ = await connect_client(f"ws://127.0.0.1:{srv_a.bound_port}")
        ws_b, id_b = await connect_client(f"ws://127.0.0.1:{srv_b.bound_port}")
        try:
            payload = {"target": id_b, "text": "private cross-instance"}
            await ws_a.send(json.dumps({"type": "direct", "payload": payload}))
            msg = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=5))
            assert msg["type"] == "direct"
            assert msg["payload"] == payload

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws_a.recv(), timeout=0.3)
        finally:
            await ws_a.close()
            await ws_b.close()
    finally:
        await srv_a.close()
        await srv_b.close()


async def test_channel_message_cross_instance_via_shared_redis():
    redis_a, redis_b = make_pair()
    srv_a = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_a)
    srv_b = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_b)
    await srv_a.start()
    await srv_b.start()
    try:
        ws_a, _ = await connect_client(f"ws://127.0.0.1:{srv_a.bound_port}")
        ws_b, _ = await connect_client(f"ws://127.0.0.1:{srv_b.bound_port}")
        try:
            await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await asyncio.sleep(0.2)

            await ws_b.send(
                json.dumps(
                    {"type": "broadcast", "channel": "alerts", "payload": {"text": "cross-channel"}}
                )
            )
            msg = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=5))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"text": "cross-channel"}

            counts_a = await srv_a.channel_counts()
            counts_b = await srv_b.channel_counts()
            assert counts_a.get("alerts") == 1
            assert counts_b.get("alerts") == 1
        finally:
            await ws_a.close()
            await ws_b.close()
    finally:
        await srv_a.close()
        await srv_b.close()


# ── Client connection state in Redis ──────────────────────────────


async def test_connection_state_stored_in_redis_and_visible_to_other_instances():
    redis_a, redis_b = make_pair()
    srv_a = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_a)
    await srv_a.start()
    try:
        ws, client_id = await connect_client(f"ws://127.0.0.1:{srv_a.bound_port}")
        try:
            state = await redis_b.get(client_state_key(client_id))
            assert state is not None
            parsed = json.loads(state)
            assert parsed["client_id"] == client_id
            assert parsed["connected"] is True

            srv_b = NotificationServer(host="127.0.0.1", port=0, redis_client=redis_b)
            try:
                await srv_b.start()
                st = await srv_b.client_state(client_id)
                assert st is not None
                assert st["client_id"] == client_id
            finally:
                await srv_b.close()
        finally:
            await ws.close()

        for _ in range(50):
            if await redis_a.get(client_state_key(client_id)) is None:
                break
            await asyncio.sleep(0.02)
        assert await redis_a.get(client_state_key(client_id)) is None
    finally:
        await srv_a.close()


# ── SQLite message persistence ────────────────────────────────────


async def test_messages_persisted_and_served_via_rest_endpoint():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "messages.db")
    srv = NotificationServer(host="127.0.0.1", port=0, database_url=db_path)
    await srv.start()
    ws, client_id = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
    try:
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
        await ws.send(
            json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"n": 3}})
        )
        await ws.send(
            json.dumps({"type": "direct", "payload": {"target": client_id, "text": "hi"}})
        )
        await asyncio.sleep(0.2)

        status, body = await http_get(f"http://127.0.0.1:{srv.bound_port}/messages")
        assert status == 200
        assert body["total"] == 4
        assert len(body["messages"]) == 4
        expected_keys = {"id", "channel", "type", "payload", "timestamp"}
        for msg in body["messages"]:
            assert set(msg.keys()) == expected_keys
            assert isinstance(msg["payload"], dict)
            assert isinstance(msg["timestamp"], str) and msg["timestamp"]

        assert body["messages"][0]["type"] == "direct"
        assert body["messages"][1]["type"] == "broadcast"
        assert body["messages"][1]["channel"] == "alerts"
        assert body["messages"][1]["payload"] == {"n": 3}

        status, body = await http_get(
            f"http://127.0.0.1:{srv.bound_port}/messages?limit=2&offset=0"
        )
        assert status == 200
        assert body["total"] == 4
        assert len(body["messages"]) == 2

        status, body = await http_get(
            f"http://127.0.0.1:{srv.bound_port}/messages?limit=2&offset=2"
        )
        assert status == 200
        assert len(body["messages"]) == 2
        assert body["messages"][-1]["payload"] == {"n": 1}
    finally:
        await ws.close()
        await srv.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_messages_survive_server_restart():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "messages.db")
    srv = NotificationServer(host="127.0.0.1", port=0, database_url=db_path)
    await srv.start()
    ws, _ = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
    try:
        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 42}}))
        await asyncio.sleep(0.2)
    finally:
        await ws.close()
        await srv.close()

    srv2 = NotificationServer(host="127.0.0.1", port=0, database_url=db_path)
    await srv2.start()
    try:
        status, body = await http_get(f"http://127.0.0.1:{srv2.bound_port}/messages")
        assert status == 200
        assert body["total"] == 1
        assert body["messages"][0]["payload"] == {"n": 42}
    finally:
        await srv2.close()
        shutil.rmtree(tmpdir, ignore_errors=True)
