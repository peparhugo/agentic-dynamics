import asyncio
import json
import threading
import urllib.request

import pytest
import websockets

import app

WS_URL = "ws://127.0.0.1"


@pytest.fixture
async def server():
    srv = await app.make_server()
    try:
        yield srv
    finally:
        await app.close_server(srv)


async def connect(port):
    return await websockets.connect(f"{WS_URL}:{port}")


async def recv_json(ws, timeout=5):
    raw = await asyncio.wait_for(ws.recv(), timeout)
    return json.loads(raw)


def http_health(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())


async def wait_for_count(registry, expected, timeout=5):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if registry.count == expected:
            return True
        await asyncio.sleep(0.05)
    return False


async def get_client_id(ws):
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    return msg["payload"]["client_id"]


# ── Message format ───────────────────────────────────────────────

def test_build_message_format():
    msg = app.build_message("broadcast", {"note": "hi"})
    assert set(msg) == {"type", "payload", "timestamp"}
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"note": "hi"}
    assert isinstance(msg["timestamp"], str)


def test_build_message_rejects_unknown_type():
    with pytest.raises(ValueError):
        app.build_message("nope", {})


def test_build_message_rejects_non_dict_payload():
    with pytest.raises(TypeError):
        app.build_message("system", ["not", "a", "dict"])


def test_registry_uses_threading_lock():
    registry = app.ClientRegistry()
    assert type(registry._lock) is type(threading.Lock())


# ── Connect / disconnect ─────────────────────────────────────────

async def test_connect_assigns_unique_id(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    a_id = await get_client_id(ws_a)
    b_id = await get_client_id(ws_b)
    assert a_id and b_id
    assert a_id != b_id
    await ws_a.close()
    await ws_b.close()


async def test_welcome_is_system_message(server):
    ws = await connect(server["ws_port"])
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert "client_id" in msg["payload"]
    assert "timestamp" in msg
    await ws.close()


async def test_disconnect_clean_removal(server):
    registry = server["registry"]
    ws = await connect(server["ws_port"])
    await get_client_id(ws)
    assert registry.count == 1
    await ws.close()
    assert await wait_for_count(registry, 0)


# ── Broadcast ────────────────────────────────────────────────────

async def test_broadcast_reaches_all_clients(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)

    await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    got_a = await recv_json(ws_a)
    got_b = await recv_json(ws_b)

    for got in (got_a, got_b):
        assert set(got) == {"type", "payload", "timestamp"}
        assert got["type"] == "broadcast"
        assert got["payload"] == {"text": "hello"}

    await ws_a.close()
    await ws_b.close()


async def test_broadcast_reaches_only_connected_after_disconnect(server):
    registry = server["registry"]
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)

    await ws_b.close()
    assert await wait_for_count(registry, 1)

    await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "still"}}))
    got_a = await recv_json(ws_a)
    assert got_a["type"] == "broadcast"
    assert got_a["payload"] == {"text": "still"}

    with pytest.raises((asyncio.TimeoutError, websockets.exceptions.ConnectionClosed)):
        await asyncio.wait_for(ws_a.recv(), 0.5)

    await ws_a.close()


# ── Direct ───────────────────────────────────────────────────────

async def test_direct_reaches_only_target(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    a_id = await get_client_id(ws_a)
    b_id = await get_client_id(ws_b)

    await ws_a.send(
        json.dumps({"type": "direct", "payload": {"to": b_id, "text": "psst"}})
    )
    got_b = await recv_json(ws_b)
    assert got_b["type"] == "direct"
    assert got_b["payload"]["to"] == b_id
    assert got_b["payload"]["text"] == "psst"

    with pytest.raises((asyncio.TimeoutError, websockets.exceptions.ConnectionClosed)):
        await asyncio.wait_for(ws_a.recv(), 0.5)

    await ws_a.close()
    await ws_b.close()


async def test_direct_unknown_target_reports_error(server):
    ws = await connect(server["ws_port"])
    await get_client_id(ws)

    await ws.send(
        json.dumps({"type": "direct", "payload": {"to": "does-not-exist", "text": "x"}})
    )
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert "no client" in msg["payload"]["error"]
    await ws.close()


# ── Malformed input ──────────────────────────────────────────────

async def test_unsupported_type_gets_error(server):
    ws = await connect(server["ws_port"])
    await get_client_id(ws)
    await ws.send(json.dumps({"type": "teleport", "payload": {}}))
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert "unsupported" in msg["payload"]["error"]
    await ws.close()


async def test_invalid_json_gets_error(server):
    ws = await connect(server["ws_port"])
    await get_client_id(ws)
    await ws.send("this is not json")
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert msg["payload"]["error"] == "invalid JSON"
    await ws.close()


# ── /health ──────────────────────────────────────────────────────

async def test_health_returns_connected_client_count(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)

    status, body = http_health(server["http_port"])
    assert status == 200
    assert body["status"] == "ok"
    assert body["clients"] == 2

    await ws_b.close()
    assert await wait_for_count(server["registry"], 1)
    _, body = http_health(server["http_port"])
    assert body["clients"] == 1

    await ws_a.close()
    assert await wait_for_count(server["registry"], 0)
    _, body = http_health(server["http_port"])
    assert body["clients"] == 0


# ── Channels ─────────────────────────────────────────────────────

def http_get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())


async def subscribe(ws, channel):
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": channel}}))


async def unsubscribe(ws, channel):
    await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": channel}}))


async def test_subscribe_confirms_and_delivers_channel_messages(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)

    await subscribe(ws_a, "alerts")
    msg = await recv_json(ws_a)
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "subscribed"
    assert msg["payload"]["channel"] == "alerts"

    await ws_a.send(
        json.dumps({"type": "broadcast", "payload": {"text": "fire"}, "channel": "alerts"})
    )
    got_a = await recv_json(ws_a)
    assert got_a["type"] == "broadcast"
    assert got_a["payload"] == {"text": "fire"}
    assert got_a["channel"] == "alerts"

    with pytest.raises((asyncio.TimeoutError, websockets.exceptions.ConnectionClosed)):
        await asyncio.wait_for(ws_b.recv(), 0.5)

    await ws_a.close()
    await ws_b.close()


async def test_channel_message_ignores_non_subscribers(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)
    await subscribe(ws_a, "chat")
    await recv_json(ws_a)

    await ws_a.send(
        json.dumps({"type": "broadcast", "payload": {"text": "hi"}, "channel": "chat"})
    )
    got_a = await recv_json(ws_a)
    assert got_a["payload"] == {"text": "hi"}
    with pytest.raises((asyncio.TimeoutError, websockets.exceptions.ConnectionClosed)):
        await asyncio.wait_for(ws_b.recv(), 0.5)

    await ws_b.send(json.dumps({"type": "broadcast", "payload": {"text": "open"}}))
    got_a = await recv_json(ws_a)
    got_b = await recv_json(ws_b)
    assert got_a["payload"] == {"text": "open"}
    assert got_b["payload"] == {"text": "open"}

    await ws_a.close()
    await ws_b.close()


async def test_unsubscribe_stops_delivery(server):
    registry = server["registry"]
    ws = await connect(server["ws_port"])
    cid = await get_client_id(ws)
    await subscribe(ws, "system")
    await recv_json(ws)
    assert registry.channel_subscribers("system") == {cid}

    await unsubscribe(ws, "system")
    msg = await recv_json(ws)
    assert msg["payload"]["event"] == "unsubscribed"
    assert registry.channel_subscribers("system") == set()

    await ws.send(
        json.dumps({"type": "broadcast", "payload": {"text": "gone"}, "channel": "system"})
    )
    with pytest.raises((asyncio.TimeoutError, websockets.exceptions.ConnectionClosed)):
        await asyncio.wait_for(ws.recv(), 0.5)
    await ws.close()


async def test_client_can_subscribe_to_multiple_channels(server):
    registry = server["registry"]
    ws = await connect(server["ws_port"])
    cid = await get_client_id(ws)
    await subscribe(ws, "alerts")
    await recv_json(ws)
    await subscribe(ws, "chat")
    await recv_json(ws)

    channels = registry.channels()
    assert set(channels) == {"alerts", "chat"}
    assert channels["alerts"] == {cid}
    assert channels["chat"] == {cid}

    await ws.send(
        json.dumps({"type": "broadcast", "payload": {"n": 1}, "channel": "chat"})
    )
    got = await recv_json(ws)
    assert got["payload"] == {"n": 1}
    await ws.close()


async def test_disconnect_cleans_channel_membership(server):
    registry = server["registry"]
    ws = await connect(server["ws_port"])
    cid = await get_client_id(ws)
    await subscribe(ws, "system")
    await recv_json(ws)
    await ws.close()
    assert await wait_for_count(registry, 0)
    assert registry.channel_subscribers("system") == set()
    assert registry.channels() == {}


async def test_subscribe_requires_channel(server):
    ws = await connect(server["ws_port"])
    await get_client_id(ws)
    await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert "channel" in msg["payload"]["error"]
    await ws.close()


async def test_rest_channels_lists_subscriber_counts(server):
    ws_a = await connect(server["ws_port"])
    ws_b = await connect(server["ws_port"])
    await get_client_id(ws_a)
    await get_client_id(ws_b)
    await subscribe(ws_a, "alerts")
    await recv_json(ws_a)
    await subscribe(ws_b, "alerts")
    await recv_json(ws_b)
    await subscribe(ws_a, "chat")
    await recv_json(ws_a)

    status, body = http_get(server["http_port"], "/channels")
    assert status == 200
    by_name = {c["name"]: c["subscribers"] for c in body["channels"]}
    assert by_name == {"alerts": 2, "chat": 1}

    await ws_a.close()
    await ws_b.close()


async def test_rest_channel_subscribers_lists_ids(server):
    ws = await connect(server["ws_port"])
    cid = await get_client_id(ws)
    await subscribe(ws, "system")
    await recv_json(ws)

    status, body = http_get(server["http_port"], "/channels/system/subscribers")
    assert status == 200
    assert body["channel"] == "system"
    assert body["subscribers"] == [cid]

    status, body = http_get(server["http_port"], "/channels/nope/subscribers")
    assert status == 200
    assert body["subscribers"] == []

    await ws.close()


def test_health_unknown_path_returns_404(server):
    # Uses a plain HTTP request against the health server via urllib.
    port = server["http_port"]
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
        raise AssertionError("expected HTTP 404")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404


# ── Thread safety ────────────────────────────────────────────────

def test_registry_thread_safety():
    registry = app.ClientRegistry()
    errors = []

    def worker():
        try:
            for _ in range(300):
                cid = registry.add("ws-stub")
                assert registry.get(cid) == "ws-stub"
                assert registry.count >= 1
                registry.remove(cid)
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert registry.count == 0


# ── Redis pub/sub backbone ───────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def clean_redis_state():
    state = app.ClientStateStore()
    state.connect()
    if state.available:
        state.clear()
    limiter = app.RateLimiter(limit=app.RATE_LIMIT_DEFAULT)
    limiter.connect()
    if limiter.available:
        limiter.reset()
    limiter.close()
    yield
    if state.available:
        state.clear()
    limiter = app.RateLimiter(limit=app.RATE_LIMIT_DEFAULT)
    limiter.connect()
    if limiter.available:
        limiter.reset()
    limiter.close()


@pytest.fixture
def redis_available():
    state = app.ClientStateStore()
    state.connect()
    if not state.available:
        pytest.skip("Redis is not available")
    state.clear()
    yield
    state.clear()


def redis_url():
    return app.resolve_redis_url()


async def wait_for_state(state, client_id, expected, timeout=5):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if state.has_client(client_id) == expected:
            return True
        await asyncio.sleep(0.05)
    return False


async def test_broker_publishes_to_redis_channel(redis_available):
    import redis.asyncio as _aioredis

    broker = app.RedisBroker(redis_url=redis_url())
    await broker.connect()
    assert broker.available

    listener = _aioredis.from_url(redis_url())
    pubsub = listener.pubsub()
    await pubsub.subscribe(app.NOTIFICATIONS_CHANNEL)
    try:
        message = app.build_message("broadcast", {"text": "via-redis"})
        await broker.publish(message)

        async def _listen():
            async for m in pubsub.listen():
                if m.get("type") == "message":
                    return m

        raw = await asyncio.wait_for(_listen(), 5)
        assert raw is not None
        assert json.loads(raw["data"]) == message
    finally:
        await pubsub.close()
        await listener.close()
        await broker.close()


async def test_redis_pubsub_distributes_between_servers(redis_available, tmp_path):
    srv_a = await app.make_server(redis_url=redis_url(), db_path=str(tmp_path / "a.db"))
    srv_b = await app.make_server(redis_url=redis_url(), db_path=str(tmp_path / "b.db"))
    try:
        ws_a = await connect(srv_a["ws_port"])
        ws_b = await connect(srv_b["ws_port"])
        await get_client_id(ws_a)
        await get_client_id(ws_b)

        await subscribe(ws_a, "alerts")
        await recv_json(ws_a)
        await subscribe(ws_b, "alerts")
        await recv_json(ws_b)

        await ws_a.send(
            json.dumps(
                {"type": "broadcast", "payload": {"text": "cross"}, "channel": "alerts"}
            )
        )
        got_a = await recv_json(ws_a)
        got_b = await recv_json(ws_b)
        assert got_a["payload"] == {"text": "cross"}
        assert got_b["payload"] == {"text": "cross"}
        assert got_a["channel"] == "alerts"
        assert got_b["channel"] == "alerts"

        await ws_a.send(
            json.dumps({"type": "broadcast", "payload": {"text": "global"}})
        )
        got_b = await recv_json(ws_b)
        assert got_b["payload"] == {"text": "global"}

        await ws_a.close()
        await ws_b.close()
    finally:
        await app.close_server(srv_a)
        await app.close_server(srv_b)


async def test_direct_message_reaches_client_on_other_server(redis_available, tmp_path):
    srv_a = await app.make_server(redis_url=redis_url(), db_path=str(tmp_path / "a.db"))
    srv_b = await app.make_server(redis_url=redis_url(), db_path=str(tmp_path / "b.db"))
    try:
        ws_a = await connect(srv_a["ws_port"])
        ws_b = await connect(srv_b["ws_port"])
        b_id = await get_client_id(ws_b)
        await get_client_id(ws_a)

        await ws_a.send(
            json.dumps({"type": "direct", "payload": {"to": b_id, "text": "psst"}})
        )
        got_b = await recv_json(ws_b)
        assert got_b["type"] == "direct"
        assert got_b["payload"] == {"to": b_id, "text": "psst"}

        with pytest.raises((asyncio.TimeoutError, websockets.exceptions.ConnectionClosed)):
            await asyncio.wait_for(ws_a.recv(), 0.5)

        await ws_a.close()
        await ws_b.close()
    finally:
        await app.close_server(srv_a)
        await app.close_server(srv_b)


# ── Client state in Redis ────────────────────────────────────────

async def test_client_state_mirrored_to_redis(redis_available, tmp_path):
    srv = await app.make_server(redis_url=redis_url(), db_path=str(tmp_path / "s.db"))
    try:
        ws = await connect(srv["ws_port"])
        cid = await get_client_id(ws)
        await subscribe(ws, "alerts")
        await recv_json(ws)
        await subscribe(ws, "chat")
        await recv_json(ws)

        state = srv["state_store"]
        assert state.available
        assert state.has_client(cid) is True
        assert state.client_channels(cid) == {"alerts", "chat"}

        restored = app.ClientRegistry(state_store=srv["state_store"])
        restored.restore_state()
        assert restored.channel_subscribers("alerts") == {cid}
        assert restored.channel_subscribers("chat") == {cid}

        await unsubscribe(ws, "alerts")
        await recv_json(ws)
        assert state.client_channels(cid) == {"chat"}

        await ws.close()
        assert await wait_for_state(state, cid, False)
    finally:
        await app.close_server(srv)


async def test_client_state_survives_restart(redis_available, tmp_path):
    db = str(tmp_path / "restart.db")
    srv = await app.make_server(redis_url=redis_url(), db_path=db)
    ws = await connect(srv["ws_port"])
    cid = await get_client_id(ws)
    await subscribe(ws, "alerts")
    await recv_json(ws)
    await subscribe(ws, "chat")
    await recv_json(ws)

    assert srv["state_store"].has_client(cid) is True

    # A fresh process (new state store + registry) restores the persisted state
    # from Redis even though the original server instance is gone.
    state = app.ClientStateStore(redis_url=redis_url())
    state.connect()
    assert state.has_client(cid) is True
    registry = app.ClientRegistry(state_store=state)
    registry.restore_state()
    assert registry.channel_subscribers("alerts") == {cid}
    assert registry.channel_subscribers("chat") == {cid}
    assert registry.channels() == {"alerts": {cid}, "chat": {cid}}

    await ws.close()
    assert await wait_for_state(srv["state_store"], cid, False)
    await app.close_server(srv)


# ── Message persistence ──────────────────────────────────────────

async def test_messages_persisted_and_queryable(redis_available, tmp_path):
    db = str(tmp_path / "hist.db")
    srv = await app.make_server(redis_url=redis_url(), db_path=db)
    try:
        ws = await connect(srv["ws_port"])
        cid = await get_client_id(ws)
        await subscribe(ws, "alerts")
        await recv_json(ws)

        await ws.send(
            json.dumps(
                {"type": "broadcast", "payload": {"n": 1}, "channel": "alerts"}
            )
        )
        await recv_json(ws)

        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
        await recv_json(ws)

        await ws.send(
            json.dumps({"type": "direct", "payload": {"to": cid, "n": 3}})
        )
        await recv_json(ws)

        status, body = http_get(srv["http_port"], "/messages")
        assert status == 200
        messages = body["messages"]
        assert len(messages) == 3
        by_n = {m["payload"]["n"]: m for m in messages}
        assert set(by_n) == {1, 2, 3}
        for n, msg in by_n.items():
            assert set(msg) == {"id", "channel", "type", "payload", "timestamp"}
            assert isinstance(msg["id"], int)
            assert isinstance(msg["timestamp"], str)
        assert by_n[1]["channel"] == "alerts"
        assert by_n[1]["type"] == "broadcast"
        assert by_n[2]["channel"] is None
        assert by_n[2]["type"] == "broadcast"
        assert by_n[3]["type"] == "direct"
        assert body["limit"] == 50
        assert body["offset"] == 0

        status, body = http_get(srv["http_port"], "/messages?limit=2&offset=0")
        assert status == 200
        assert len(body["messages"]) == 2

        status, body = http_get(srv["http_port"], "/messages?limit=2&offset=2")
        assert status == 200
        assert len(body["messages"]) == 1

        assert srv["store"].count() == 3
        await ws.close()
    finally:
        await app.close_server(srv)


async def test_history_survives_server_restart(redis_available, tmp_path):
    db = str(tmp_path / "hist2.db")
    srv = await app.make_server(redis_url=redis_url(), db_path=db)
    ws = await connect(srv["ws_port"])
    await get_client_id(ws)
    await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 1}}))
    await recv_json(ws)
    await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 2}}))
    await recv_json(ws)
    await ws.close()
    await app.close_server(srv)

    srv2 = await app.make_server(redis_url=redis_url(), db_path=db)
    try:
        status, body = http_get(srv2["http_port"], "/messages")
        assert status == 200
        assert len(body["messages"]) == 2
        assert {m["payload"]["n"] for m in body["messages"]} == {1, 2}
    finally:
        await app.close_server(srv2)


def test_message_store_record_and_list(tmp_path):
    store = app.MessageStore(str(tmp_path / "direct.db"))
    try:
        msg = app.build_message("broadcast", {"x": 1})
        store.record(dict(msg, channel="alerts"))
        rows = store.list_messages()
        assert len(rows) == 1
        assert rows[0]["id"] == 1
        assert rows[0]["type"] == "broadcast"
        assert rows[0]["channel"] == "alerts"
        assert rows[0]["payload"] == {"x": 1}
        assert rows[0]["timestamp"] == msg["timestamp"]
        assert store.count() == 1
    finally:
        store.close()


# ── Configuration ────────────────────────────────────────────────

def test_config_resolve_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example.test:9999/3")
    assert app.resolve_redis_url() == "redis://example.test:9999/3"
    assert app.resolve_redis_url("redis://other:1/0") == "redis://other:1/0"


def test_config_resolve_db_path(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///var/data/notes.db")
    assert app.resolve_db_path() == "var/data/notes.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:////var/data/notes.db")
    assert app.resolve_db_path() == "/var/data/notes.db"
    assert app.resolve_db_path("custom.db") == "custom.db"
    monkeypatch.delenv("DATABASE_URL")
    assert app.resolve_db_path() == "notifications.db"
