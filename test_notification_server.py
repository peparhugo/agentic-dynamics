import asyncio
import http.client
import json
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import fakeredis
import pytest
import websockets

from notification_server import NotificationServer, make_message, utc_now_iso


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def make_server(**kwargs) -> NotificationServer:
    """Build a NotificationServer wired to an isolated in-memory fake Redis
    and an in-memory SQLite database, so tests never touch a real Redis
    instance or leave files behind."""
    kwargs.setdefault("redis_client", fakeredis.aioredis.FakeRedis(decode_responses=True))
    kwargs.setdefault("database_url", ":memory:")
    return NotificationServer(host="localhost", port=free_port(), **kwargs)


@pytest.fixture
async def server():
    srv = make_server()
    await srv.start()
    yield srv
    await srv.stop()


async def connect(srv):
    return await websockets.connect(f"ws://{srv.host}:{srv.port}")


async def recv_json(ws, timeout=2):
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


def http_get(host, port, path, timeout=2):
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, json.loads(body)
    finally:
        conn.close()


# ── Connection lifecycle ─────────────────────────────────────────


async def test_client_receives_unique_id_on_connect(server):
    ws = await connect(server)
    try:
        welcome = await recv_json(ws)
        assert welcome["type"] == "system"
        assert welcome["payload"]["event"] == "connected"
        assert "client_id" in welcome["payload"]
    finally:
        await ws.close()


async def test_two_clients_get_different_ids(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        welcome1 = await recv_json(ws1)
        # ws2 sees its own welcome plus a "client_joined" notice is sent to ws1
        welcome2 = await recv_json(ws2)
        joined_notice = await recv_json(ws1)

        id1 = welcome1["payload"]["client_id"]
        id2 = welcome2["payload"]["client_id"]
        assert id1 != id2
        assert joined_notice["payload"]["event"] == "client_joined"
        assert joined_notice["payload"]["client_id"] == id2
    finally:
        await ws1.close()
        await ws2.close()


async def test_disconnect_removes_client_cleanly(server):
    ws1 = await connect(server)
    await recv_json(ws1)  # welcome

    ws2 = await connect(server)
    await recv_json(ws2)  # ws2 welcome
    await recv_json(ws1)  # ws1 sees join notice

    assert server.registry.count() == 2

    await ws2.close()
    # give the server a moment to process the close and broadcast client_left
    left_notice = await recv_json(ws1)
    assert left_notice["payload"]["event"] == "client_left"

    assert server.registry.count() == 1
    await ws1.close()


# ── Broadcast ─────────────────────────────────────────────────────


async def test_broadcast_reaches_all_connected_clients(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    ws3 = await connect(server)
    try:
        await recv_json(ws1)  # welcome
        await recv_json(ws2)  # welcome
        await recv_json(ws1)  # join notice for ws2
        await recv_json(ws3)  # welcome
        await recv_json(ws1)  # join notice for ws3
        await recv_json(ws2)  # join notice for ws3

        msg = {"type": "broadcast", "payload": {"text": "hello everyone"}}
        await ws1.send(json.dumps(msg))

        got1 = await recv_json(ws1)
        got2 = await recv_json(ws2)
        got3 = await recv_json(ws3)

        for got in (got1, got2, got3):
            assert got["type"] == "broadcast"
            assert got["payload"] == {"text": "hello everyone"}
            assert "timestamp" in got
    finally:
        await ws1.close()
        await ws2.close()
        await ws3.close()


# ── Direct messages ───────────────────────────────────────────────


async def test_direct_message_delivered_to_target_only(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        welcome1 = await recv_json(ws1)
        welcome2 = await recv_json(ws2)
        await recv_json(ws1)  # join notice for ws2

        target_id = welcome2["payload"]["client_id"]
        msg = {
            "type": "direct",
            "payload": {"target": target_id, "data": {"text": "psst"}},
        }
        await ws1.send(json.dumps(msg))

        got = await recv_json(ws2)
        assert got["type"] == "direct"
        assert got["payload"]["data"] == {"text": "psst"}
        assert got["payload"]["from"] == welcome1["payload"]["client_id"]

        # ws1 should NOT receive the direct message meant for ws2
        with pytest.raises(asyncio.TimeoutError):
            await recv_json(ws1, timeout=0.3)
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_to_unknown_client_returns_error(server):
    ws1 = await connect(server)
    try:
        await recv_json(ws1)  # welcome
        msg = {
            "type": "direct",
            "payload": {"target": "does-not-exist", "data": {"text": "hi"}},
        }
        await ws1.send(json.dumps(msg))

        got = await recv_json(ws1)
        assert got["type"] == "system"
        assert "not found" in got["payload"]["error"]
    finally:
        await ws1.close()


# ── System messages ───────────────────────────────────────────────


async def test_client_sending_system_message_is_rejected(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "system", "payload": {"foo": "bar"}}))
        got = await recv_json(ws)
        assert got["type"] == "system"
        assert "error" in got["payload"]
    finally:
        await ws.close()


# ── Malformed input ───────────────────────────────────────────────


async def test_invalid_json_gets_error_response(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send("not json")
        got = await recv_json(ws)
        assert got["type"] == "system"
        assert "error" in got["payload"]
    finally:
        await ws.close()


async def test_unsupported_type_gets_error_response(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "not-a-type", "payload": {}}))
        got = await recv_json(ws)
        assert got["type"] == "system"
        assert "error" in got["payload"]
    finally:
        await ws.close()


# ── REST /health ──────────────────────────────────────────────────


async def test_health_endpoint_reports_zero_with_no_clients(server):
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/health"
    )
    assert status == 200
    assert body["connected_clients"] == 0


async def test_health_endpoint_reports_connected_count(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        await recv_json(ws1)
        await recv_json(ws2)
        await recv_json(ws1)  # join notice

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/health"
        )
        assert status == 200
        assert body["connected_clients"] == 2
    finally:
        await ws1.close()
        await ws2.close()


async def test_health_endpoint_reflects_disconnect(server):
    ws1 = await connect(server)
    await recv_json(ws1)
    await ws1.close()
    await asyncio.sleep(0.2)  # allow server to process the close

    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/health"
    )
    assert status == 200
    assert body["connected_clients"] == 0


# ── Channel subscriptions ────────────────────────────────────────


async def test_subscribe_confirms_and_appears_in_channel_list(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        confirm = await recv_json(ws)
        assert confirm["type"] == "system"
        assert confirm["payload"]["event"] == "subscribed"
        assert confirm["payload"]["channel"] == "alerts"

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/channels"
        )
        assert status == 200
        assert body["channels"] == [{"name": "alerts", "subscribers": 1}]
    finally:
        await ws.close()


async def test_unsubscribe_removes_client_from_channel(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)  # subscribed confirmation

        await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        confirm = await recv_json(ws)
        assert confirm["payload"]["event"] == "unsubscribed"
        assert confirm["payload"]["channel"] == "alerts"

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/channels"
        )
        assert status == 200
        assert body["channels"] == []
    finally:
        await ws.close()


async def test_subscribe_without_channel_returns_error(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
        got = await recv_json(ws)
        assert got["type"] == "system"
        assert "error" in got["payload"]
    finally:
        await ws.close()


async def test_client_can_subscribe_to_multiple_channels(server):
    ws = await connect(server)
    try:
        welcome = await recv_json(ws)
        client_id = welcome["payload"]["client_id"]

        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await recv_json(ws)

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/channels/alerts/subscribers"
        )
        assert status == 200
        assert body == {"channel": "alerts", "subscribers": [client_id]}

        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/channels/chat/subscribers"
        )
        assert status == 200
        assert body == {"channel": "chat", "subscribers": [client_id]}
    finally:
        await ws.close()


async def test_channel_message_reaches_only_subscribers(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    ws3 = await connect(server)
    try:
        await recv_json(ws1)  # welcome
        await recv_json(ws2)  # welcome
        await recv_json(ws1)  # join notice for ws2
        await recv_json(ws3)  # welcome
        await recv_json(ws1)  # join notice for ws3
        await recv_json(ws2)  # join notice for ws3

        # only ws1 and ws2 subscribe to "alerts"; ws3 stays unsubscribed
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1)
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws2)

        await ws1.send(
            json.dumps(
                {"type": "broadcast", "payload": {"channel": "alerts", "text": "fire"}}
            )
        )

        got1 = await recv_json(ws1)
        got2 = await recv_json(ws2)
        assert got1["payload"] == {"channel": "alerts", "text": "fire"}
        assert got2["payload"] == {"channel": "alerts", "text": "fire"}

        with pytest.raises(asyncio.TimeoutError):
            await recv_json(ws3, timeout=0.3)
    finally:
        await ws1.close()
        await ws2.close()
        await ws3.close()


async def test_message_without_channel_still_broadcasts_to_all(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        await recv_json(ws1)  # welcome
        await recv_json(ws2)  # welcome
        await recv_json(ws1)  # join notice for ws2

        # ws2 subscribes to a channel, but an unscoped broadcast should still reach it
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await recv_json(ws2)

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "hi all"}}))
        got1 = await recv_json(ws1)
        got2 = await recv_json(ws2)
        assert got1["payload"] == {"text": "hi all"}
        assert got2["payload"] == {"text": "hi all"}
    finally:
        await ws1.close()
        await ws2.close()


async def test_disconnect_removes_channel_subscription(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        welcome1 = await recv_json(ws1)  # welcome
        await recv_json(ws2)  # welcome
        await recv_json(ws1)  # join notice for ws2

        client1_id = welcome1["payload"]["client_id"]
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1)

        await ws1.close()
        await recv_json(ws2)  # client_left notice
        await asyncio.sleep(0.1)

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/channels/alerts/subscribers"
        )
        assert status == 200
        assert client1_id not in body["subscribers"]
        assert body["subscribers"] == []
    finally:
        await ws2.close()


async def test_channels_endpoint_empty_with_no_subscriptions(server):
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/channels"
    )
    assert status == 200
    assert body == {"channels": []}


async def test_unknown_channel_subscribers_endpoint_returns_empty_list(server):
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/channels/does-not-exist/subscribers"
    )
    assert status == 200
    assert body == {"channel": "does-not-exist", "subscribers": []}


# ── Message helpers ───────────────────────────────────────────────


def test_make_message_shape():
    msg = make_message("broadcast", {"a": 1})
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"a": 1}
    assert "timestamp" in msg and isinstance(msg["timestamp"], str)


# ── Redis-backed configuration ─────────────────────────────────────


async def test_config_defaults_pulled_from_env_vars(monkeypatch, tmp_path):
    db_path = str(tmp_path / "env-configured.db")
    monkeypatch.setenv("REDIS_URL", "redis://example-broker:6399/2")
    monkeypatch.setenv("DATABASE_URL", db_path)

    srv = NotificationServer(host="localhost", port=free_port())
    try:
        assert srv.redis_url == "redis://example-broker:6399/2"
        assert srv.database_url == db_path
    finally:
        await srv.redis.close()
        srv.messages.close()


# ── Client connection state stored in Redis ──────────────────────────


async def test_client_registration_recorded_in_redis(server):
    ws = await connect(server)
    try:
        welcome = await recv_json(ws)
        client_id = welcome["payload"]["client_id"]

        owner = await server.redis.hget("notify:clients", client_id)
        assert owner == server.server_id
    finally:
        await ws.close()


async def test_client_disconnect_clears_redis_state(server):
    ws = await connect(server)
    welcome = await recv_json(ws)
    client_id = welcome["payload"]["client_id"]

    await ws.close()
    await asyncio.sleep(0.2)

    owner = await server.redis.hget("notify:clients", client_id)
    assert owner is None


async def test_channel_subscription_recorded_in_redis(server):
    ws = await connect(server)
    try:
        welcome = await recv_json(ws)
        client_id = welcome["payload"]["client_id"]

        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)

        channels = await server.state.channels_of(client_id)
        assert channels == {"alerts"}

        await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)

        channels = await server.state.channels_of(client_id)
        assert channels == set()
    finally:
        await ws.close()


# ── Message persistence (SQLite) ───────────────────────────────────────


async def test_broadcast_message_is_persisted_and_listed(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "history me"}}))
        await recv_json(ws)  # delivered back via the redis worker

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/messages"
        )
        assert status == 200
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert len(body["messages"]) == 1
        entry = body["messages"][0]
        assert entry["type"] == "broadcast"
        assert entry["channel"] is None
        assert entry["payload"] == {"text": "history me"}
        assert "timestamp" in entry and "id" in entry
    finally:
        await ws.close()


async def test_channel_broadcast_is_persisted_with_channel_name(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)  # subscribed confirmation

        await ws.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "fire"}})
        )
        await recv_json(ws)  # delivered back

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/messages"
        )
        assert status == 200
        assert body["messages"][0]["channel"] == "alerts"
    finally:
        await ws.close()


async def test_direct_message_is_persisted(server):
    ws1 = await connect(server)
    ws2 = await connect(server)
    try:
        welcome1 = await recv_json(ws1)
        welcome2 = await recv_json(ws2)
        await recv_json(ws1)  # join notice

        target_id = welcome2["payload"]["client_id"]
        await ws1.send(
            json.dumps({"type": "direct", "payload": {"target": target_id, "data": {"x": 1}}})
        )
        await recv_json(ws2)  # the direct message itself

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/messages"
        )
        assert status == 200
        entry = body["messages"][0]
        assert entry["type"] == "direct"
        assert entry["payload"]["data"] == {"x": 1}
        assert entry["payload"]["from"] == welcome1["payload"]["client_id"]
    finally:
        await ws1.close()
        await ws2.close()


async def test_messages_endpoint_respects_limit_and_offset(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        for i in range(5):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
            await recv_json(ws)

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/messages?limit=2&offset=1"
        )
        assert status == 200
        assert body["limit"] == 2
        assert body["offset"] == 1
        assert len(body["messages"]) == 2
        # newest-first ordering: skipping the very newest (n=4), next two are n=3, n=2
        assert [m["payload"]["n"] for m in body["messages"]] == [3, 2]
    finally:
        await ws.close()


async def test_messages_endpoint_defaults_when_params_missing_or_invalid(server):
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/messages?limit=not-a-number"
    )
    assert status == 200
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["messages"] == []


# ── Multi-instance Redis backbone ───────────────────────────────────────


async def make_shared_instances(shared_database_url=None):
    """Two NotificationServer instances wired to the same fake Redis backend,
    simulating multiple server processes sharing one Redis broker."""
    fake_server = fakeredis.FakeServer()

    def redis_client():
        return fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True)

    srv1 = NotificationServer(
        host="localhost",
        port=free_port(),
        redis_client=redis_client(),
        database_url=shared_database_url or ":memory:",
    )
    srv2 = NotificationServer(
        host="localhost",
        port=free_port(),
        redis_client=redis_client(),
        database_url=shared_database_url or ":memory:",
    )
    await srv1.start()
    await srv2.start()
    return srv1, srv2


async def test_broadcast_reaches_clients_on_a_different_server_instance():
    srv1, srv2 = await make_shared_instances()
    try:
        ws1 = await connect(srv1)
        ws2 = await connect(srv2)
        try:
            await recv_json(ws1)  # welcome on srv1
            await recv_json(ws2)  # welcome on srv2

            await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "cluster-wide"}}))

            got1 = await recv_json(ws1)
            got2 = await recv_json(ws2)
            assert got1["payload"] == {"text": "cluster-wide"}
            assert got2["payload"] == {"text": "cluster-wide"}
        finally:
            await ws1.close()
            await ws2.close()
    finally:
        await srv1.stop()
        await srv2.stop()


async def test_channel_broadcast_reaches_only_subscribers_across_instances():
    srv1, srv2 = await make_shared_instances()
    try:
        ws1 = await connect(srv1)  # subscriber, on instance 1
        ws2 = await connect(srv2)  # subscriber, on instance 2
        ws3 = await connect(srv2)  # not subscribed, on instance 2
        try:
            await recv_json(ws1)  # welcome
            await recv_json(ws2)  # welcome
            await recv_json(ws3)  # welcome
            await recv_json(ws2)  # join notice for ws3 (local to srv2)

            await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
            await recv_json(ws1)
            await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
            await recv_json(ws2)
            await asyncio.sleep(0.2)  # let both workers finish subscribing in Redis

            await ws1.send(
                json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "fire"}})
            )

            got1 = await recv_json(ws1)
            got2 = await recv_json(ws2)
            assert got1["payload"]["text"] == "fire"
            assert got2["payload"]["text"] == "fire"

            with pytest.raises(asyncio.TimeoutError):
                await recv_json(ws3, timeout=0.3)
        finally:
            await ws1.close()
            await ws2.close()
            await ws3.close()
    finally:
        await srv1.stop()
        await srv2.stop()


async def test_direct_message_routes_to_client_on_another_instance():
    srv1, srv2 = await make_shared_instances()
    try:
        ws1 = await connect(srv1)
        ws2 = await connect(srv2)
        try:
            welcome1 = await recv_json(ws1)
            welcome2 = await recv_json(ws2)
            target_id = welcome2["payload"]["client_id"]

            await ws1.send(
                json.dumps(
                    {"type": "direct", "payload": {"target": target_id, "data": {"hi": True}}}
                )
            )

            got = await recv_json(ws2)
            assert got["type"] == "direct"
            assert got["payload"]["data"] == {"hi": True}
            assert got["payload"]["from"] == welcome1["payload"]["client_id"]

            # ws1 should not see its own direct message
            with pytest.raises(asyncio.TimeoutError):
                await recv_json(ws1, timeout=0.3)
        finally:
            await ws1.close()
            await ws2.close()
    finally:
        await srv1.stop()
        await srv2.stop()


# ── Rate limiting ────────────────────────────────────────────────────


async def test_messages_within_limit_are_all_processed():
    srv = make_server(rate_limit=5)
    await srv.start()
    try:
        ws = await connect(srv)
        try:
            await recv_json(ws)  # welcome
            for i in range(4):
                await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
                got = await recv_json(ws)
                assert got["type"] == "broadcast"
                assert got["payload"] == {"n": i}
        finally:
            await ws.close()
    finally:
        await srv.stop()


async def test_messages_over_limit_get_rate_limit_error_not_dropped():
    srv = make_server(rate_limit=3)
    await srv.start()
    try:
        ws = await connect(srv)
        try:
            await recv_json(ws)  # welcome

            for i in range(3):
                await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
                await recv_json(ws)

            # 4th message this window should be rejected with an error, not silently dropped
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 99}}))
            got = await recv_json(ws)
            assert got["type"] == "system"
            assert "rate limit" in got["payload"]["error"].lower()
        finally:
            await ws.close()
    finally:
        await srv.stop()


async def test_rate_limit_is_tracked_per_client():
    srv = make_server(rate_limit=2)
    await srv.start()
    try:
        ws1 = await connect(srv)
        ws2 = await connect(srv)
        try:
            await recv_json(ws1)  # welcome
            await recv_json(ws2)  # welcome
            await recv_json(ws1)  # join notice for ws2

            # exhaust ws1's limit
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": 0}}))
            await recv_json(ws1)
            await recv_json(ws2)
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
            await recv_json(ws1)
            await recv_json(ws2)
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
            got1 = await recv_json(ws1)
            assert got1["type"] == "system"
            assert "rate limit" in got1["payload"]["error"].lower()

            # ws2 still has its own untouched budget
            await ws2.send(json.dumps({"type": "broadcast", "payload": {"n": 3}}))
            got2 = await recv_json(ws2)
            assert got2["type"] == "broadcast"
            assert got2["payload"] == {"n": 3}
        finally:
            await ws1.close()
            await ws2.close()
    finally:
        await srv.stop()


async def test_rate_limit_default_pulled_from_env_var(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "17")
    srv = make_server()
    try:
        assert srv.rate_limit == 17
    finally:
        await srv.redis.close()
        srv.messages.close()


# ── Message history endpoint ────────────────────────────────────────


async def test_history_requires_channel_param(server):
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/history"
    )
    assert status == 400
    assert "error" in body


async def test_history_returns_channel_messages_in_chronological_order(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)

        for i in range(3):
            await ws.send(
                json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "n": i}})
            )
            await recv_json(ws)

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/history?channel=alerts"
        )
        assert status == 200
        assert body["channel"] == "alerts"
        assert body["has_more"] is False
        assert [m["payload"]["n"] for m in body["messages"]] == [0, 1, 2]
    finally:
        await ws.close()


async def test_history_only_returns_messages_for_requested_channel(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await recv_json(ws)

        await ws.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "a"}})
        )
        await recv_json(ws)
        await ws.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "chat", "text": "c"}})
        )
        await recv_json(ws)

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/history?channel=chat"
        )
        assert status == 200
        assert len(body["messages"]) == 1
        assert body["messages"][0]["payload"]["text"] == "c"
    finally:
        await ws.close()


async def test_history_paginates_with_has_more_and_since_cursor(server):
    ws = await connect(server)
    try:
        await recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)

        for i in range(5):
            await ws.send(
                json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "n": i}})
            )
            await recv_json(ws)

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, http_get, server.host, server.port, "/history?channel=alerts&limit=2"
        )
        assert status == 200
        assert body["has_more"] is True
        assert [m["payload"]["n"] for m in body["messages"]] == [0, 1]

        cursor = body["messages"][-1]["timestamp"]
        status, body2 = await loop.run_in_executor(
            None,
            http_get,
            server.host,
            server.port,
            f"/history?channel=alerts&limit=2&since={quote(cursor, safe='')}",
        )
        assert status == 200
        assert [m["payload"]["n"] for m in body2["messages"]] == [2, 3]
        assert body2["has_more"] is True
    finally:
        await ws.close()


async def test_history_empty_for_channel_with_no_messages(server):
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/history?channel=nowhere"
    )
    assert status == 200
    assert body["messages"] == []
    assert body["has_more"] is False


# ── Message expiry / cleanup ────────────────────────────────────────


async def test_expired_messages_are_purged_by_cleanup(server):
    old_timestamp = (
        datetime.now(timezone.utc) - timedelta(days=10)
    ).isoformat()
    recent_timestamp = utc_now_iso()

    await asyncio.to_thread(
        server.messages.save, "alerts", "broadcast", {"text": "old"}, old_timestamp
    )
    await asyncio.to_thread(
        server.messages.save, "alerts", "broadcast", {"text": "new"}, recent_timestamp
    )

    deleted = await server._cleanup_expired_messages()
    assert deleted == 1

    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, http_get, server.host, server.port, "/history?channel=alerts"
    )
    assert status == 200
    assert [m["payload"]["text"] for m in body["messages"]] == ["new"]


async def test_message_ttl_days_default_pulled_from_env_var(monkeypatch):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "3")
    srv = make_server()
    try:
        assert srv.message_ttl_days == 3
    finally:
        await srv.redis.close()
        srv.messages.close()


async def test_cleanup_task_starts_on_startup_and_stops_on_shutdown():
    srv = make_server(message_ttl_days=7)
    await srv.start()
    try:
        assert srv._cleanup_task is not None
        assert not srv._cleanup_task.done()
    finally:
        await srv.stop()
    assert srv._cleanup_task is None


async def test_message_history_shared_across_instances_via_sqlite(tmp_path):
    shared_db = str(tmp_path / "shared-history.db")
    srv1, srv2 = await make_shared_instances(shared_database_url=shared_db)
    try:
        ws1 = await connect(srv1)
        ws2 = await connect(srv2)
        try:
            await recv_json(ws1)  # welcome
            await recv_json(ws2)  # welcome

            await ws1.send(json.dumps({"type": "broadcast", "payload": {"from": "srv1"}}))
            await recv_json(ws1)
            await recv_json(ws2)

            await ws2.send(json.dumps({"type": "broadcast", "payload": {"from": "srv2"}}))
            await recv_json(ws1)
            await recv_json(ws2)

            loop = asyncio.get_running_loop()
            status, body = await loop.run_in_executor(
                None, http_get, srv2.host, srv2.port, "/messages"
            )
            assert status == 200
            payloads = [m["payload"] for m in body["messages"]]
            assert {"from": "srv1"} in payloads
            assert {"from": "srv2"} in payloads
        finally:
            await ws1.close()
            await ws2.close()
    finally:
        await srv1.stop()
        await srv2.stop()
