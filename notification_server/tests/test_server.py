import asyncio
import json
import urllib.error
import urllib.request

import pytest
import pytest_asyncio
import websockets

from notification_server.messages import now_iso
from notification_server.server import NotificationServer


@pytest_asyncio.fixture
async def running_server(tmp_path):
    server = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'messages.db'}",
    )
    await server.start()
    port = server._server.sockets[0].getsockname()[1]
    try:
        yield server, port
    finally:
        await server.stop()


@pytest_asyncio.fixture
async def rate_limited_server(tmp_path):
    server = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'messages.db'}",
        rate_limit=3,
    )
    await server.start()
    port = server._server.sockets[0].getsockname()[1]
    try:
        yield server, port
    finally:
        await server.stop()


async def connect(port):
    ws = await websockets.connect(f"ws://localhost:{port}")
    welcome = json.loads(await ws.recv())
    return ws, welcome


async def test_connect_assigns_unique_client_id(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, welcome2 = await connect(port)
    try:
        assert welcome1["type"] == "system"
        assert welcome1["payload"]["event"] == "connected"
        client_id1 = welcome1["payload"]["client_id"]
        client_id2 = welcome2["payload"]["client_id"]
        assert client_id1 != client_id2
        assert server.registry.count() == 2
    finally:
        await ws1.close()
        await ws2.close()


async def test_disconnect_removes_client(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    assert server.registry.count() == 1
    await ws.close()
    for _ in range(50):
        if server.registry.count() == 0:
            break
        await asyncio.sleep(0.05)
    assert server.registry.count() == 0


async def test_broadcast_reaches_all_connected_clients(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    try:
        await ws1.send(
            json.dumps({"type": "broadcast", "payload": {"text": "hello everyone"}})
        )
        msg1 = json.loads(await ws1.recv())
        msg2 = json.loads(await ws2.recv())
        assert msg1["type"] == "broadcast"
        assert msg1["payload"]["text"] == "hello everyone"
        assert msg2 == msg1
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_reaches_only_target(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, welcome2 = await connect(port)
    try:
        target_id = welcome2["payload"]["client_id"]
        await ws1.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": target_id, "content": {"text": "psst"}},
                }
            )
        )
        msg2 = json.loads(await ws2.recv())
        assert msg2["type"] == "direct"
        assert msg2["payload"]["content"] == {"text": "psst"}
        assert msg2["payload"]["sender_id"] == welcome1["payload"]["client_id"]

        # ws1 should not receive the direct message meant for ws2.
        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws1.recv(), timeout=0.2)
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_to_unknown_target_returns_error(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": "no-such-client", "content": {}},
                }
            )
        )
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_system_message_from_client_is_acknowledged(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "system", "payload": {"note": "ping"}}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "ack"
    finally:
        await ws.close()


async def test_invalid_json_returns_system_error(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send("not valid json")
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_health_endpoint_reports_connected_count(running_server):
    server, port = running_server

    def get_health():
        with urllib.request.urlopen(f"http://localhost:{port}/health") as resp:
            return resp.status, json.loads(resp.read())

    # urlopen is a blocking call; it must run off the event loop thread so
    # the server (running on that same loop) is free to accept and answer it.
    loop = asyncio.get_running_loop()

    status, body = await loop.run_in_executor(None, get_health)
    assert status == 200
    assert body == {"connected_clients": 0}

    ws, _ = await connect(port)
    try:
        status, body = await loop.run_in_executor(None, get_health)
        assert body == {"connected_clients": 1}
    finally:
        await ws.close()


async def test_events_are_persisted_to_flat_file(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "hi"}}))
    await ws.recv()
    await ws.close()
    for _ in range(50):
        events = server.storage.read_events()
        if any(e["event"] == "disconnect" for e in events):
            break
        await asyncio.sleep(0.05)

    events = server.storage.read_events()
    kinds = [e["event"] for e in events]
    assert "connect" in kinds
    assert "message" in kinds
    assert "disconnect" in kinds


def get_json(port, path):
    with urllib.request.urlopen(f"http://localhost:{port}{path}") as resp:
        return resp.status, json.loads(resp.read())


async def test_subscribe_acknowledges_and_registers_client(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"] == {"event": "subscribed", "channel": "alerts"}
        assert server.channels.subscribers("alerts") != set()
    finally:
        await ws.close()


async def test_subscribe_without_channel_returns_error(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
    finally:
        await ws.close()


async def test_unsubscribe_removes_client_from_channel(running_server):
    server, port = running_server
    ws, welcome = await connect(port)
    try:
        client_id = welcome["payload"]["client_id"]
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws.recv()
        await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        reply = json.loads(await ws.recv())
        assert reply["payload"] == {"event": "unsubscribed", "channel": "alerts"}
        assert client_id not in server.channels.subscribers("alerts")
    finally:
        await ws.close()


async def test_channel_message_delivered_only_to_subscribers(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    ws3, _ = await connect(port)
    try:
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await ws2.recv()

        await ws1.send(
            json.dumps(
                {"type": "broadcast", "payload": {"channel": "alerts", "text": "fire!"}}
            )
        )
        msg1 = json.loads(await ws1.recv())
        assert msg1["type"] == "broadcast"
        assert msg1["payload"]["text"] == "fire!"
        assert msg1["payload"]["channel"] == "alerts"

        # ws2 (subscribed to a different channel) and ws3 (subscribed to
        # nothing) must not receive the channel-scoped message.
        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws2.recv(), timeout=0.2)
        with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
            await asyncio.wait_for(ws3.recv(), timeout=0.2)
    finally:
        await ws1.close()
        await ws2.close()
        await ws3.close()


async def test_message_without_channel_still_broadcasts_to_all(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    try:
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()

        await ws2.send(json.dumps({"type": "broadcast", "payload": {"text": "hi all"}}))
        msg1 = json.loads(await ws1.recv())
        msg2 = json.loads(await ws2.recv())
        assert msg1["payload"]["text"] == "hi all"
        assert msg2 == msg1
    finally:
        await ws1.close()
        await ws2.close()


async def test_client_can_subscribe_to_multiple_channels(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, _ = await connect(port)
    try:
        client_id = welcome1["payload"]["client_id"]
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await ws1.recv()

        await ws2.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "chat", "text": "hey"}})
        )
        msg = json.loads(await ws1.recv())
        assert msg["payload"]["text"] == "hey"
        assert client_id in server.channels.subscribers("alerts")
        assert client_id in server.channels.subscribers("chat")
    finally:
        await ws1.close()
        await ws2.close()


async def test_disconnect_removes_client_from_all_channels(running_server):
    server, port = running_server
    ws, welcome = await connect(port)
    client_id = welcome["payload"]["client_id"]
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await ws.recv()
    assert client_id in server.channels.subscribers("alerts")

    await ws.close()
    for _ in range(50):
        if client_id not in server.channels.subscribers("alerts"):
            break
        await asyncio.sleep(0.05)
    assert client_id not in server.channels.subscribers("alerts")
    assert server.channels.channels() == {}


async def test_channels_endpoint_lists_active_channels_and_counts(running_server):
    server, port = running_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    try:
        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(None, get_json, port, "/channels")
        assert status == 200
        assert body == {"channels": []}

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws2.recv()
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await ws2.recv()

        status, body = await loop.run_in_executor(None, get_json, port, "/channels")
        assert status == 200
        assert body == {
            "channels": [
                {"name": "alerts", "subscriber_count": 2},
                {"name": "chat", "subscriber_count": 1},
            ]
        }
    finally:
        await ws1.close()
        await ws2.close()


async def test_channel_subscribers_endpoint_lists_subscriber_ids(running_server):
    server, port = running_server
    ws1, welcome1 = await connect(port)
    ws2, welcome2 = await connect(port)
    try:
        client_id1 = welcome1["payload"]["client_id"]
        client_id2 = welcome2["payload"]["client_id"]
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws1.recv()
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws2.recv()

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, get_json, port, "/channels/alerts/subscribers"
        )
        assert status == 200
        assert body["channel"] == "alerts"
        assert sorted(body["subscribers"]) == sorted([client_id1, client_id2])
    finally:
        await ws1.close()
        await ws2.close()


async def test_channel_subscribers_endpoint_empty_for_unknown_channel(running_server):
    server, port = running_server
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, get_json, port, "/channels/does-not-exist/subscribers"
    )
    assert status == 200
    assert body == {"channel": "does-not-exist", "subscribers": []}


# ── rate limiting ────────────────────────────────────────────────


async def test_messages_within_rate_limit_are_processed(rate_limited_server):
    server, port = rate_limited_server
    ws, _ = await connect(port)
    try:
        for i in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
            reply = json.loads(await ws.recv())
            assert reply["type"] == "broadcast"
            assert reply["payload"]["n"] == i
    finally:
        await ws.close()


async def test_messages_over_rate_limit_get_error_not_dropped(rate_limited_server):
    server, port = rate_limited_server
    ws, _ = await connect(port)
    try:
        for i in range(3):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
            await ws.recv()

        await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 99}}))
        reply = json.loads(await ws.recv())
        assert reply["type"] == "system"
        assert reply["payload"]["event"] == "error"
        assert reply["payload"]["detail"] == "rate_limit_exceeded"
    finally:
        await ws.close()


async def test_rate_limit_is_tracked_per_client(rate_limited_server):
    server, port = rate_limited_server
    ws1, _ = await connect(port)
    ws2, _ = await connect(port)
    try:
        for i in range(3):
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
            await ws1.recv()

        # ws1 is now at its limit; ws2 (a different client) is unaffected.
        await ws2.send(json.dumps({"type": "broadcast", "payload": {"n": 0}}))
        reply = json.loads(await ws2.recv())
        assert reply["type"] == "broadcast"
    finally:
        await ws1.close()
        await ws2.close()


async def test_default_rate_limit_matches_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT", "2")
    server = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'messages.db'}",
    )
    await server.start()
    port = server._server.sockets[0].getsockname()[1]
    try:
        ws, _ = await connect(port)
        try:
            for i in range(2):
                await ws.send(json.dumps({"type": "broadcast", "payload": {"n": i}}))
                await ws.recv()
            await ws.send(json.dumps({"type": "broadcast", "payload": {"n": 99}}))
            reply = json.loads(await ws.recv())
            assert reply["payload"]["detail"] == "rate_limit_exceeded"
        finally:
            await ws.close()
    finally:
        await server.stop()


# ── GET /history ─────────────────────────────────────────────────


async def test_history_returns_channel_messages_in_chronological_order(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws.recv()

        for i in range(3):
            await ws.send(
                json.dumps(
                    {"type": "broadcast", "payload": {"channel": "alerts", "n": i}}
                )
            )
            await ws.recv()

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, get_json, port, "/history?channel=alerts"
        )
        assert status == 200
        assert [m["payload"]["n"] for m in body["messages"]] == [0, 1, 2]
        assert body["has_more"] is False
    finally:
        await ws.close()


async def test_history_excludes_other_channels(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws.recv()
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await ws.recv()

        await ws.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "a"}})
        )
        await ws.recv()
        await ws.send(
            json.dumps({"type": "broadcast", "payload": {"channel": "chat", "text": "b"}})
        )
        await ws.recv()

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, get_json, port, "/history?channel=alerts"
        )
        assert status == 200
        assert len(body["messages"]) == 1
        assert body["messages"][0]["payload"]["text"] == "a"
    finally:
        await ws.close()


async def test_history_respects_limit_and_reports_has_more(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws.recv()

        for i in range(5):
            await ws.send(
                json.dumps(
                    {"type": "broadcast", "payload": {"channel": "alerts", "n": i}}
                )
            )
            await ws.recv()

        loop = asyncio.get_running_loop()
        status, body = await loop.run_in_executor(
            None, get_json, port, "/history?channel=alerts&limit=2"
        )
        assert status == 200
        assert [m["payload"]["n"] for m in body["messages"]] == [0, 1]
        assert body["has_more"] is True
        assert body["limit"] == 2
    finally:
        await ws.close()


async def test_history_since_filters_out_earlier_messages(running_server):
    server, port = running_server
    ws, _ = await connect(port)
    try:
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await ws.recv()

        for i in range(3):
            await ws.send(
                json.dumps(
                    {"type": "broadcast", "payload": {"channel": "alerts", "n": i}}
                )
            )
            await ws.recv()

        loop = asyncio.get_running_loop()
        status, first_page = await loop.run_in_executor(
            None, get_json, port, "/history?channel=alerts&limit=1"
        )
        since = first_page["messages"][0]["timestamp"]

        status, body = await loop.run_in_executor(
            None, get_json, port, f"/history?channel=alerts&since={since}"
        )
        assert status == 200
        assert [m["payload"]["n"] for m in body["messages"]] == [1, 2]
    finally:
        await ws.close()


async def test_history_without_channel_returns_400(running_server):
    server, port = running_server
    loop = asyncio.get_running_loop()

    def get_error():
        try:
            urllib.request.urlopen(f"http://localhost:{port}/history")
            raise AssertionError("expected HTTPError")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    status, body = await loop.run_in_executor(None, get_error)
    assert status == 400
    assert "channel" in body["error"]


async def test_history_empty_for_unknown_channel(running_server):
    server, port = running_server
    loop = asyncio.get_running_loop()
    status, body = await loop.run_in_executor(
        None, get_json, port, "/history?channel=does-not-exist"
    )
    assert status == 200
    assert body == {"messages": [], "has_more": False, "limit": 50}


# ── message expiry ──────────────────────────────────────────────


async def test_cleanup_expired_messages_purges_only_old_messages(running_server):
    server, port = running_server
    server.message_ttl_days = 1
    server.messages.save_message(
        "broadcast", {"n": "old"}, "2000-01-01T00:00:00+00:00", channel="alerts"
    )
    server.messages.save_message(
        "broadcast", {"n": "new"}, now_iso(), channel="alerts"
    )

    removed = await server.cleanup_expired_messages()
    assert removed == 1

    remaining, _ = server.messages.list_by_channel("alerts")
    assert [m["payload"]["n"] for m in remaining] == ["new"]


async def test_cleanup_task_is_running_after_server_start(running_server):
    server, port = running_server
    assert server._cleanup_task is not None
    assert not server._cleanup_task.done()


async def test_cleanup_task_stops_when_server_stops(tmp_path):
    server = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'messages.db'}",
    )
    await server.start()
    task = server._cleanup_task
    await server.stop()
    assert task.cancelled() or task.done()
    assert server._cleanup_task is None


async def test_cleanup_worker_loop_purges_expired_messages_on_startup(tmp_path):
    server = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'messages.db'}",
        message_ttl_days=1,
        cleanup_interval_seconds=0.05,
    )
    server.messages.save_message(
        "broadcast", {"n": "old"}, "2000-01-01T00:00:00+00:00", channel="alerts"
    )
    await server.start()
    try:
        for _ in range(50):
            remaining, _ = server.messages.list_by_channel("alerts")
            if not remaining:
                break
            await asyncio.sleep(0.05)
        remaining, _ = server.messages.list_by_channel("alerts")
        assert remaining == []
    finally:
        await server.stop()


async def test_message_ttl_days_configurable_via_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MESSAGE_TTL_DAYS", "30")
    server = NotificationServer(
        host="localhost",
        port=0,
        storage_path=tmp_path / "events.jsonl",
        database_url=f"sqlite:///{tmp_path / 'messages.db'}",
    )
    assert server.message_ttl_days == 30
