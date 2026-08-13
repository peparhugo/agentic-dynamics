"""Tests for per-client rate limiting backed by Redis counters.

The rate limit is configurable through the ``RATE_LIMIT`` environment variable
and enforced per client id. When a client exceeds its budget the server replies
with an error message instead of silently dropping the message.
"""

import asyncio
import json

import pytest
import websockets

from broker import rate_limit_key
from server import NotificationServer


async def connect_client(ws_url):
    """Connect a client and consume its initial 'connected' system message."""
    ws = await websockets.connect(ws_url)
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    msg = json.loads(raw)
    assert msg["type"] == "system"
    assert "client_id" in msg["payload"]
    return ws, msg["payload"]["client_id"]


async def test_rate_limit_returns_error_message_after_limit():
    srv = NotificationServer(
        host="127.0.0.1", port=0, rate_limit=3, rate_limit_window=60
    )
    await srv.start()
    try:
        ws, _ = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
        try:
            for n in range(3):
                await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert msg["type"] == "broadcast"
                assert msg["payload"] == {"n": n}

            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 4}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "system"
            assert "rate limit" in msg["payload"]["error"]
        finally:
            await ws.close()
    finally:
        await srv.close()


async def test_rate_limit_is_per_client():
    srv = NotificationServer(
        host="127.0.0.1", port=0, rate_limit=2, rate_limit_window=60
    )
    await srv.start()
    try:
        ws1, id1 = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
        ws2, id2 = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
        assert id1 != id2
        try:
            for n in range(2):
                await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
                for ws in (ws1, ws2):
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    assert msg["payload"] == {"n": n}

            await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
            msg = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
            assert msg["type"] == "system"
            assert "rate limit" in msg["payload"]["error"]

            await ws2.send(json.dumps({"type": "broadcast", "payload": {"n": 10}}))
            msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"n": 10}
        finally:
            await ws1.close()
            await ws2.close()
    finally:
        await srv.close()


async def test_rate_limit_counter_uses_redis_with_expiry():
    srv = NotificationServer(
        host="127.0.0.1", port=0, rate_limit=5, rate_limit_window=60
    )
    await srv.start()
    try:
        ws, client_id = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
        try:
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
            await asyncio.wait_for(ws.recv(), timeout=5)

            key = rate_limit_key(client_id)
            raw = await srv.redis.get(key)
            assert raw is not None
            assert int(raw) == 1
            ttl = await srv.redis.ttl(key)
            assert ttl > 0 and ttl <= 60
        finally:
            await ws.close()
    finally:
        await srv.close()


async def test_rate_limit_disabled_when_zero():
    srv = NotificationServer(
        host="127.0.0.1", port=0, rate_limit=0, rate_limit_window=60
    )
    await srv.start()
    try:
        ws, _ = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
        try:
            for n in range(5):
                await ws.send(json.dumps({"type": "broadcast", "payload": {"n": n}}))
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert msg["type"] == "broadcast"
        finally:
            await ws.close()
    finally:
        await srv.close()


async def test_rate_limit_read_from_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "1")
    srv = NotificationServer(host="127.0.0.1", port=0)
    try:
        assert srv.rate_limit == 1
        assert srv.rate_limit_window == 60
        await srv.start()
        ws, _ = await connect_client(f"ws://127.0.0.1:{srv.bound_port}")
        try:
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "broadcast"

            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "system"
            assert "rate limit" in msg["payload"]["error"]
        finally:
            await ws.close()
    finally:
        await srv.close()
