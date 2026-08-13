"""Integration tests for the Redis pub/sub backbone and message persistence."""

import asyncio
import json
import os
import uuid
from datetime import datetime

import httpx
import pytest
import pytest_asyncio
import redis
from websockets.asyncio.client import connect

from broker import ConnectionState, MessageBroker, MessageStore, database_url, redis_url
from server import NotificationServer


BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _redis() -> redis.Redis:
    return redis.Redis.from_url(BROKER_URL)


def ws_uri(srv: NotificationServer) -> str:
    return f"ws://127.0.0.1:{srv.port}"


def http_uri(srv: NotificationServer) -> str:
    return f"http://127.0.0.1:{srv.port}"


@pytest_asyncio.fixture
async def channel_name():
    return f"itest:{uuid.uuid4().hex}"


async def _server(channel: str, tmp_path, name: str = "m.db") -> NotificationServer:
    srv = NotificationServer(
        port=0,
        channel=channel,
        store=MessageStore(path=str(tmp_path / name)),
    )
    await srv.start()
    return srv


async def recv_msg(ws) -> dict:
    return json.loads(await ws.recv())


async def next_pubsub_message(pubsub, timeout: float = 2.0) -> dict:
    """Poll a raw Redis pubsub connection for the next message dict."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        message = await asyncio.to_thread(pubsub.get_message)
        if message is not None and message["type"] == "message":
            return message
        await asyncio.sleep(0.02)
    raise asyncio.TimeoutError("no message received from Redis pub/sub")


@pytest.mark.asyncio
async def test_broadcast_is_published_to_redis(channel_name, tmp_path):
    srv = await _server(channel_name, tmp_path)
    subscriber = _redis().pubsub()
    subscriber.subscribe(channel_name)
    try:
        await asyncio.sleep(0.05)
        srv.broadcast({"text": "via redis"})
        msg = await next_pubsub_message(subscriber)
        envelope = json.loads(msg["data"])
        assert envelope["type"] == "broadcast"
        assert envelope["channel"] is None
        assert envelope["payload"] == {"text": "via redis"}
        assert isinstance(envelope["timestamp"], str)
    finally:
        subscriber.close()
        await srv.stop()


@pytest.mark.asyncio
async def test_redis_publish_delivers_to_connected_client(channel_name, tmp_path):
    srv = await _server(channel_name, tmp_path)
    try:
        async with connect(ws_uri(srv)) as ws:
            await recv_msg(ws)
            _redis().publish(
                channel_name,
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": None,
                        "target": None,
                        "payload": {"text": "from redis"},
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "sender": "external",
                    }
                ),
            )
            msg = await recv_msg(ws)
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"text": "from redis"}
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_channel_broadcast_via_redis_route(channel_name, tmp_path):
    srv = await _server(channel_name, tmp_path)
    try:
        async with connect(ws_uri(srv)) as sub:
            welcome = await recv_msg(sub)
            client_id = welcome["payload"]["client_id"]
            await sub.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await asyncio.sleep(0.05)

            _redis().publish(
                channel_name,
                json.dumps(
                    {
                        "type": "broadcast",
                        "channel": "alerts",
                        "target": None,
                        "payload": {"channel": "alerts", "text": "hi"},
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "sender": "external",
                    }
                ),
            )
            msg = await recv_msg(sub)
            assert msg["type"] == "broadcast"
            assert msg["payload"] == {"channel": "alerts", "text": "hi"}
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_two_servers_share_redis_backbone(channel_name, tmp_path):
    srv_a = await _server(channel_name, tmp_path, "a.db")
    srv_b = await _server(channel_name, tmp_path, "b.db")
    try:
        async with connect(ws_uri(srv_a)) as wa:
            await recv_msg(wa)
            async with connect(ws_uri(srv_b)) as wb:
                await recv_msg(wb)

                srv_a.broadcast({"text": "from A"})
                assert (await recv_msg(wb))["payload"] == {"text": "from A"}
                assert (await recv_msg(wa))["payload"] == {"text": "from A"}

                srv_b.broadcast({"text": "from B"})
                assert (await recv_msg(wa))["payload"] == {"text": "from B"}
                assert (await recv_msg(wb))["payload"] == {"text": "from B"}
    finally:
        await srv_a.stop()
        await srv_b.stop()


@pytest.mark.asyncio
async def test_direct_reaches_client_on_other_instance(channel_name, tmp_path):
    srv_a = await _server(channel_name, tmp_path, "a.db")
    srv_b = await _server(channel_name, tmp_path, "b.db")
    try:
        async with connect(ws_uri(srv_b)) as wb:
            welcome = await recv_msg(wb)
            target = welcome["payload"]["client_id"]

            sent = await srv_a.direct(target, {"text": "private"})
            assert sent is False  # client is on the other instance

            msg = await recv_msg(wb)
            assert msg["type"] == "direct"
            assert msg["payload"] == {"text": "private"}
    finally:
        await srv_a.stop()
        await srv_b.stop()


@pytest.mark.asyncio
async def test_connect_registers_state_in_redis(channel_name, tmp_path):
    srv = await _server(channel_name, tmp_path)
    try:
        async with connect(ws_uri(srv)) as ws:
            welcome = await recv_msg(ws)
            client_id = welcome["payload"]["client_id"]
            assert client_id in srv.state.known_clients()

            await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
            await ws.send(json.dumps({"type": "subscribe", "channel": "system"}))
            await asyncio.sleep(0.1)

            assert srv.state.channels_of(client_id) == {"alerts", "system"}
            assert srv.state.subscribers("alerts") == [client_id]
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_client_state_survives_server_restart(channel_name, tmp_path):
    store = MessageStore(path=str(tmp_path / "m.db"))
    srv = NotificationServer(port=0, channel=channel_name, store=store)
    await srv.start()
    try:
        srv.state.register("client-42")
        srv.state.subscribe("client-42", "alerts")
        srv.state.subscribe("client-42", "system")
        assert srv.state.subscribers("alerts") == ["client-42"]
    finally:
        await srv.stop()

    srv2 = NotificationServer(port=0, channel=channel_name, store=store)
    await srv2.start()
    try:
        assert "client-42" in srv2.state.known_clients()
        assert srv2.state.channels_of("client-42") == {"alerts", "system"}

        srv2.registry.add("client-42", object())
        restored = srv2.restore_state()
        assert restored == {"client-42": ["alerts", "system"]}
        assert srv2.subscribers("alerts") == ["client-42"]
        assert srv2.registry.channels_of("client-42") == {"alerts", "system"}
    finally:
        await srv2.stop()


@pytest.mark.asyncio
async def test_messages_persisted_to_sqlite(channel_name, tmp_path):
    store = MessageStore(path=str(tmp_path / "m.db"))
    srv = NotificationServer(port=0, channel=channel_name, store=store)
    await srv.start()
    try:
        srv.broadcast({"text": "one"})
        srv.broadcast({"channel": "alerts", "text": "two"})

        messages = store.list_messages()
        assert len(messages) == 2

        newest = messages[0]
        assert newest["type"] == "broadcast"
        assert newest["channel"] == "alerts"
        assert newest["payload"] == {"channel": "alerts", "text": "two"}
        assert isinstance(newest["id"], int)
        assert isinstance(newest["timestamp"], str)
        datetime.fromisoformat(newest["timestamp"])

        older = messages[1]
        assert older["channel"] is None
        assert older["payload"] == {"text": "one"}
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_direct_message_persisted(channel_name, tmp_path):
    store = MessageStore(path=str(tmp_path / "m.db"))
    srv = NotificationServer(port=0, channel=channel_name, store=store)
    await srv.start()
    try:
        async with connect(ws_uri(srv)) as ws:
            welcome = await recv_msg(ws)
            await srv.direct(welcome["payload"]["client_id"], {"text": "pm"})

        messages = store.list_messages()
        direct = [m for m in messages if m["type"] == "direct"]
        assert len(direct) == 1
        assert direct[0]["payload"] == {"text": "pm"}
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_messages_endpoint_returns_history(channel_name, tmp_path):
    srv = await _server(channel_name, tmp_path)
    try:
        for i in range(5):
            srv.broadcast({"text": f"msg-{i}"})

        async with httpx.AsyncClient() as http:
            r = await http.get(f"{http_uri(srv)}/messages")
            assert r.status_code == 200
            body = r.json()
            assert len(body["messages"]) == 5
            assert body["messages"][0]["payload"] == {"text": "msg-4"}
            assert body["messages"][0]["type"] == "broadcast"
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_messages_endpoint_limit_and_offset(channel_name, tmp_path):
    srv = await _server(channel_name, tmp_path)
    try:
        for i in range(5):
            srv.broadcast({"text": f"msg-{i}"})

        async with httpx.AsyncClient() as http:
            r = await http.get(f"{http_uri(srv)}/messages?limit=2&offset=0")
            msgs = r.json()["messages"]
            assert len(msgs) == 2
            assert [m["payload"] for m in msgs] == [
                {"text": "msg-4"},
                {"text": "msg-3"},
            ]

            r = await http.get(f"{http_uri(srv)}/messages?limit=2&offset=2")
            msgs = r.json()["messages"]
            assert [m["payload"] for m in msgs] == [
                {"text": "msg-2"},
                {"text": "msg-1"},
            ]

            r = await http.get(f"{http_uri(srv)}/messages?limit=3&offset=3")
            assert [m["payload"] for m in r.json()["messages"]] == [
                {"text": "msg-1"},
                {"text": "msg-0"},
            ]
    finally:
        await srv.stop()


def test_database_url_env_var(monkeypatch, tmp_path):
    db = tmp_path / "env.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    from broker import sqlite_path

    assert sqlite_path() == str(db)
    store = MessageStore()
    store.store_message("alerts", "broadcast", {"a": 1}, "2026-01-01T00:00:00+00:00")
    assert store.count() == 1
    assert store.list_messages()[0]["payload"] == {"a": 1}


def test_redis_url_env_var(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/3")
    assert redis_url() == "redis://localhost:6379/3"
    assert ConnectionState(url="redis://localhost:6379/3").namespace == "notif"


def test_message_store_schema_columns(tmp_path):
    store = MessageStore(path=str(tmp_path / "schema.db"))
    store.store_message("ch", "broadcast", {"k": "v"}, "2026-01-01T00:00:00+00:00")
    row = store.list_messages()[0]
    assert set(row.keys()) == {"id", "channel", "type", "payload", "timestamp"}


def test_message_broker_default_channel():
    broker = MessageBroker(url=BROKER_URL)
    assert broker.channel == MessageBroker.DEFAULT_CHANNEL
    assert broker.ping() is True
