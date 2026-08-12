"""Tests for the WebSocket-based notification server."""

import asyncio
import json
import threading

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

from notifications.messages import make_message, parse_message
from notifications.registry import ClientRegistry
from notifications.server import NotificationServer

HOST = "127.0.0.1"


@pytest_asyncio.fixture
async def server():
    srv = NotificationServer(host=HOST, port=0, path="/ws")
    await srv.start()
    yield srv
    await srv.close()


async def connect_client(port, path="/ws"):
    ws = await connect(f"ws://{HOST}:{port}{path}")
    welcome = json.loads(await ws.recv())
    return ws, welcome


async def http_get(port, path="/health"):
    reader, writer = await asyncio.open_connection(HOST, port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    data = (await reader.read()).decode("utf-8", errors="replace")
    writer.close()
    await writer.wait_closed()
    head, _, body = data.partition("\r\n\r\n")
    status_line = head.split("\r\n")[0]
    return int(status_line.split()[1]), body


async def wait_for(predicate, timeout=2.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return False


# ── core connection handling ────────────────────────────────────────────


async def test_connect_assigns_unique_ids(server):
    ws1, welcome1 = await connect_client(server.bound_port)
    ws2, welcome2 = await connect_client(server.bound_port)

    assert welcome1["type"] == "system"
    assert welcome2["type"] == "system"
    assert "client_id" in welcome1["payload"]
    assert "client_id" in welcome2["payload"]
    assert welcome1["payload"]["client_id"] != welcome2["payload"]["client_id"]
    assert len(server.registry) == 2

    await ws1.close()
    await ws2.close()


async def test_system_message_on_connect_has_valid_envelope(server):
    ws, welcome = await connect_client(server.bound_port)
    assert set(welcome) == {"type", "payload", "timestamp"}
    assert welcome["type"] == "system"
    assert welcome["payload"]["event"] == "connected"
    assert isinstance(welcome["timestamp"], str)

    await ws.close()


# ── REST /health endpoint ───────────────────────────────────────────────


async def test_health_returns_zero_when_empty(server):
    status, body = await http_get(server.bound_port, "/health")
    assert status == 200
    assert json.loads(body) == {"clients": 0}


async def test_health_counts_connected_clients(server):
    ws1, _ = await connect_client(server.bound_port)
    ws2, _ = await connect_client(server.bound_port)

    _, body = await http_get(server.bound_port, "/health")
    assert json.loads(body) == {"clients": 2}

    await ws1.close()
    assert await wait_for(lambda: len(server.registry) == 1)
    _, body = await http_get(server.bound_port, "/health")
    assert json.loads(body) == {"clients": 1}

    await ws2.close()


async def test_unknown_path_returns_not_found(server):
    status, _ = await http_get(server.bound_port, "/nope")
    assert status == 404


# ── broadcasting ────────────────────────────────────────────────────────


async def test_server_broadcast_reaches_all_clients(server):
    clients = [await connect_client(server.bound_port) for _ in range(3)]

    sent = await server.broadcast({"text": "hello everyone"})
    assert sent == 3

    for ws, _ in clients:
        msg = json.loads(await ws.recv())
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "hello everyone"}
        assert isinstance(msg["timestamp"], str)

    for ws, _ in clients:
        await ws.close()


async def test_client_broadcast_relayed_to_all(server):
    ws_a, welcome_a = await connect_client(server.bound_port)
    ws_b, _ = await connect_client(server.bound_port)
    ws_c, _ = await connect_client(server.bound_port)

    await ws_a.send(
        make_message("broadcast", {"text": "hi"}, timestamp="t1")
    )

    for ws in (ws_b, ws_c):
        msg = json.loads(await ws.recv())
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "hi", "from": welcome_a["payload"]["client_id"]}
        assert msg["timestamp"] == "t1"

    for ws in (ws_a, ws_b, ws_c):
        await ws.close()


async def test_broadcast_type_survives_timestamp(server):
    ws_a, _ = await connect_client(server.bound_port)
    ws_b, _ = await connect_client(server.bound_port)

    await ws_a.send(make_message("broadcast", {"n": 1}, timestamp="2026-01-01T00:00:00+00:00"))
    msg = json.loads(await ws_b.recv())
    assert msg["timestamp"] == "2026-01-01T00:00:00+00:00"

    await ws_a.close()
    await ws_b.close()


# ── direct messaging ────────────────────────────────────────────────────


async def test_direct_message_routed_to_target_only(server):
    ws_a, _ = await connect_client(server.bound_port)
    ws_b, welcome_b = await connect_client(server.bound_port)

    target = welcome_b["payload"]["client_id"]
    await ws_a.send(
        make_message(
            "direct",
            {"target": target, "text": "psst"},
            timestamp="t2",
        )
    )

    msg = json.loads(await ws_b.recv())
    assert msg["type"] == "direct"
    assert msg["payload"]["text"] == "psst"
    assert "target" not in msg["payload"]
    assert "from" in msg["payload"]

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws_a.recv(), timeout=0.2)

    await ws_a.close()
    await ws_b.close()


async def test_direct_to_unknown_client_yields_error(server):
    ws_a, _ = await connect_client(server.bound_port)

    await ws_a.send(
        make_message("direct", {"target": "client-9999", "text": "hi"})
    )
    msg = json.loads(await ws_a.recv())
    assert msg["type"] == "system"
    assert "error" in msg["payload"]

    await ws_a.close()


# ── disconnect handling ─────────────────────────────────────────────────


async def test_disconnect_removes_client_cleanly(server):
    ws1, _ = await connect_client(server.bound_port)
    ws2, _ = await connect_client(server.bound_port)
    assert len(server.registry) == 2

    await ws1.close()
    assert await wait_for(lambda: len(server.registry) == 1)

    # the remaining client still works
    await ws2.send(make_message("broadcast", {"text": "still here"}))
    await asyncio.sleep(0.05)
    assert len(server.registry) == 1

    await ws2.close()
    assert await wait_for(lambda: len(server.registry) == 0)


# ── message helpers ─────────────────────────────────────────────────────


def test_make_message_creates_envelope():
    raw = make_message("system", {"event": "ping"})
    data = json.loads(raw)
    assert set(data) == {"type", "payload", "timestamp"}
    assert data["type"] == "system"
    assert data["payload"] == {"event": "ping"}
    assert isinstance(data["timestamp"], str)


@pytest.mark.parametrize("bad_type", ["unknown", "", None, 42])
def test_make_message_rejects_unknown_type(bad_type):
    with pytest.raises(ValueError):
        make_message(bad_type, {})


def test_make_message_rejects_non_dict_payload():
    with pytest.raises(ValueError):
        make_message("broadcast", "nope")


def test_parse_message_accepts_valid_envelope():
    raw = json.dumps(
        {"type": "direct", "payload": {"target": "x"}, "timestamp": "2026-01-01"}
    )
    data = parse_message(raw)
    assert data["type"] == "direct"


@pytest.mark.parametrize(
    "bad",
    [
        "not json at all",
        "[]",
        json.dumps({"payload": {}, "timestamp": "t"}),
        json.dumps({"type": "broadcast", "timestamp": "t"}),
        json.dumps({"type": "broadcast", "payload": "str", "timestamp": "t"}),
        json.dumps({"type": "broadcast", "payload": {}, "timestamp": 5}),
    ],
)
def test_parse_message_rejects_invalid(bad):
    with pytest.raises(ValueError):
        parse_message(bad)


# ── registry thread safety ──────────────────────────────────────────────


def test_registry_is_thread_safe():
    registry = ClientRegistry()

    results = []

    def worker(n):
        ids = [registry.register(None) for _ in range(n)]
        results.append(len(ids))

    threads = [threading.Thread(target=worker, args=(50,)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(registry) == 200
    assert sum(results) == 200

    ids = [client_id for client_id, _ in registry]
    assert len(set(ids)) == 200


# ── channel subscriptions ────────────────────────────────────────────────


async def test_subscribe_and_channel_routing(server):
    ws_a, welcome_a = await connect_client(server.bound_port)
    ws_b, welcome_b = await connect_client(server.bound_port)
    ws_c, welcome_c = await connect_client(server.bound_port)

    await ws_a.send(make_message("subscribe", {"channel": "alerts"}))
    await ws_b.send(make_message("subscribe", {"channel": "alerts"}))
    await ws_c.send(make_message("subscribe", {"channel": "system"}))

    assert await wait_for(
        lambda: server.registry.is_subscribed(
            welcome_a["payload"]["client_id"], "alerts"
        )
    )
    assert await wait_for(
        lambda: server.registry.is_subscribed(
            welcome_b["payload"]["client_id"], "alerts"
        )
    )
    assert await wait_for(
        lambda: server.registry.is_subscribed(
            welcome_c["payload"]["client_id"], "system"
        )
    )
    assert not server.registry.is_subscribed(
        welcome_c["payload"]["client_id"], "alerts"
    )

    await ws_a.send(
        make_message("broadcast", {"text": "alert!"}, channel="alerts")
    )

    for ws in (ws_b,):
        msg = json.loads(await ws.recv())
        assert msg["type"] == "broadcast"
        assert msg["channel"] == "alerts"
        assert msg["payload"]["text"] == "alert!"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws_c.recv(), timeout=0.2)

    await ws_a.close()
    await ws_b.close()
    await ws_c.close()


async def test_unsubscribe_stops_delivery(server):
    ws_a, welcome_a = await connect_client(server.bound_port)
    ws_b, _ = await connect_client(server.bound_port)

    await ws_b.send(make_message("subscribe", {"channel": "chat"}))
    await ws_a.send(
        make_message("broadcast", {"text": "one"}, channel="chat")
    )
    msg = json.loads(await ws_b.recv())
    assert msg["payload"]["text"] == "one"

    await ws_b.send(make_message("unsubscribe", {"channel": "chat"}))
    await ws_a.send(
        make_message("broadcast", {"text": "two"}, channel="chat")
    )

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws_b.recv(), timeout=0.2)

    await ws_a.close()
    await ws_b.close()


async def test_client_can_subscribe_to_multiple_channels(server):
    ws, _ = await connect_client(server.bound_port)
    await ws.send(make_message("subscribe", {"channel": "alerts"}))
    await ws.send(make_message("subscribe", {"channel": "system"}))
    await ws.send(make_message("subscribe", {"channel": "chat"}))

    assert await wait_for(
        lambda: server.registry.channels()
        == {"alerts": 1, "system": 1, "chat": 1}
    )

    await ws.close()


async def test_message_without_channel_still_broadcasts_to_all(server):
    ws_a, _ = await connect_client(server.bound_port)
    ws_b, _ = await connect_client(server.bound_port)

    await ws_a.send(make_message("broadcast", {"text": "everyone"}))

    for ws in (ws_a, ws_b):
        msg = json.loads(await ws.recv())
        assert msg["payload"]["text"] == "everyone"
        assert "channel" not in msg

    await ws_a.close()
    await ws_b.close()


async def test_rest_channels_endpoint(server):
    ws_a, _ = await connect_client(server.bound_port)
    ws_b, _ = await connect_client(server.bound_port)

    await ws_a.send(make_message("subscribe", {"channel": "alerts"}))
    await ws_b.send(make_message("subscribe", {"channel": "alerts"}))
    await ws_b.send(make_message("subscribe", {"channel": "chat"}))

    assert await wait_for(
        lambda: server.registry.channels() == {"alerts": 2, "chat": 1}
    )

    status, body = await http_get(server.bound_port, "/channels")
    assert status == 200
    assert json.loads(body) == {"alerts": 2, "chat": 1}

    await ws_a.close()
    await ws_b.close()


async def test_rest_channel_subscribers_endpoint(server):
    ws_a, welcome_a = await connect_client(server.bound_port)
    ws_b, welcome_b = await connect_client(server.bound_port)

    await ws_a.send(make_message("subscribe", {"channel": "alerts"}))
    await ws_b.send(make_message("subscribe", {"channel": "alerts"}))

    status, body = await http_get(
        server.bound_port, "/channels/alerts/subscribers"
    )
    assert status == 200
    data = json.loads(body)
    assert data["channel"] == "alerts"
    assert sorted(data["subscribers"]) == sorted(
        [
            welcome_a["payload"]["client_id"],
            welcome_b["payload"]["client_id"],
        ]
    )

    await ws_a.close()
    await ws_b.close()


async def test_disconnect_cleans_up_channels(server):
    ws, welcome = await connect_client(server.bound_port)
    await ws.send(make_message("subscribe", {"channel": "alerts"}))
    assert await wait_for(
        lambda: server.registry.channels() == {"alerts": 1}
    )

    client_id = welcome["payload"]["client_id"]
    await ws.close()
    assert await wait_for(lambda: client_id not in server.registry)
    assert server.registry.channels() == {}


async def test_subscribe_without_channel_yields_error(server):
    ws, _ = await connect_client(server.bound_port)
    await ws.send(make_message("subscribe", {}))
    msg = json.loads(await ws.recv())
    assert msg["type"] == "system"
    assert "error" in msg["payload"]
    await ws.close()
