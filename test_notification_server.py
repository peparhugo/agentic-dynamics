import asyncio
import json

import pytest
import pytest_asyncio
import websockets
from websockets.asyncio.client import connect

import notification_server as ns


@pytest_asyncio.fixture(autouse=True)
async def clean_registry():
    ns.registry = ns.ClientRegistry()
    ns.channels = ns.ChannelRegistry()
    yield
    ns.registry = ns.ClientRegistry()
    ns.channels = ns.ChannelRegistry()


@pytest_asyncio.fixture
async def server():
    async with ns.serve(ns.handler, "localhost", 0, process_request=ns.process_request) as srv:
        port = srv.sockets[0].getsockname()[1]
        yield f"ws://localhost:{port}"


async def recv_json(ws, msg_type=None):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(raw)
        if msg_type is None or data["type"] == msg_type:
            return data


async def http_get(server, path):
    host_port = server.split("://", 1)[1]
    reader, writer = await asyncio.open_connection(*host_port.split(":"))
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    raw = await reader.read()
    writer.close()
    header_blob, _, body = raw.partition(b"\r\n\r\n")
    status_line = header_blob.splitlines()[0].decode()
    return status_line, json.loads(body.decode())


@pytest.mark.asyncio
async def test_connect_assigns_unique_id(server):
    async with connect(server) as ws1, connect(server) as ws2:
        welcome1 = await recv_json(ws1, "system")
        welcome2 = await recv_json(ws2, "system")
        id1 = welcome1["payload"]["client_id"]
        id2 = welcome2["payload"]["client_id"]
        assert id1 != id2
        assert welcome1["type"] == "system"
        assert "timestamp" in welcome1


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(server):
    async with connect(server) as ws1, connect(server) as ws2, connect(server) as ws3:
        await recv_json(ws1, "system")
        await recv_json(ws2, "system")
        await recv_json(ws3, "system")

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello everyone"},
            "timestamp": "ignored-client-side",
        }))

        msg1 = await recv_json(ws1, "broadcast")
        msg2 = await recv_json(ws2, "broadcast")
        msg3 = await recv_json(ws3, "broadcast")

        for msg in (msg1, msg2, msg3):
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello everyone"
            assert "timestamp" in msg


@pytest.mark.asyncio
async def test_direct_message_reaches_only_target(server):
    async with connect(server) as ws1, connect(server) as ws2, connect(server) as ws3:
        welcome1 = await recv_json(ws1, "system")
        await recv_json(ws2, "system")
        welcome3 = await recv_json(ws3, "system")
        target_id = welcome3["payload"]["client_id"]

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": target_id, "text": "just for you"},
        }))

        msg3 = await recv_json(ws3, "direct")
        assert msg3["payload"]["text"] == "just for you"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_direct_message_unknown_target_gets_error(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target": "does-not-exist", "text": "hi"},
        }))
        err = await recv_json(ws1, "system")
        assert "not connected" in err["payload"]["error"]


@pytest.mark.asyncio
async def test_unsupported_type_gets_error(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({"type": "bogus", "payload": {}}))
        err = await recv_json(ws1, "system")
        assert "unsupported type" in err["payload"]["error"]


@pytest.mark.asyncio
async def test_invalid_json_gets_error(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send("not json")
        err = await recv_json(ws1, "system")
        assert "invalid JSON" in err["payload"]["error"]


@pytest.mark.asyncio
async def test_disconnect_removes_client(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        assert ns.registry.count() == 1

    for _ in range(50):
        if ns.registry.count() == 0:
            break
        await asyncio.sleep(0.05)
    assert ns.registry.count() == 0


@pytest.mark.asyncio
async def test_health_endpoint_reports_connected_count(server):
    ws_url = server
    http_url = "http://" + ws_url.split("://", 1)[1]

    async with connect(ws_url) as ws1:
        await recv_json(ws1, "system")
        async with connect(ws_url) as ws2:
            await recv_json(ws2, "system")

            reader, writer = await asyncio.open_connection(
                *ws_url.split("://", 1)[1].split(":")
            )
            writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            await writer.drain()
            raw = await reader.read()
            writer.close()

            header_blob, _, body = raw.partition(b"\r\n\r\n")
            assert b"200" in header_blob.splitlines()[0]
            data = json.loads(body.decode())
            assert data["connected_clients"] == 2


@pytest.mark.asyncio
async def test_registry_add_remove_and_snapshot():
    registry = ns.ClientRegistry()

    class FakeConn:
        pass

    c1, c2 = FakeConn(), FakeConn()
    id1 = registry.add(c1)
    id2 = registry.add(c2)
    assert id1 != id2
    assert registry.count() == 2
    assert dict(registry.snapshot()) == {id1: c1, id2: c2}

    registry.remove(id1)
    assert registry.count() == 1
    assert registry.get(id1) is None
    assert registry.get(id2) is c2


@pytest.mark.asyncio
async def test_subscribe_gets_ack(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        ack = await recv_json(ws1, "system")
        assert ack["payload"] == {"event": "subscribed", "channel": "alerts"}


@pytest.mark.asyncio
async def test_subscribe_without_channel_gets_error(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({"type": "subscribe", "payload": {}}))
        err = await recv_json(ws1, "system")
        assert "requires 'channel'" in err["payload"]["error"]


@pytest.mark.asyncio
async def test_channel_message_reaches_only_subscribers(server):
    async with connect(server) as ws1, connect(server) as ws2, connect(server) as ws3:
        await recv_json(ws1, "system")
        await recv_json(ws2, "system")
        await recv_json(ws3, "system")

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1, "system")
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws2, "system")
        # ws3 does not subscribe to "alerts"

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "fire!"},
        }))

        msg1 = await recv_json(ws1, "broadcast")
        msg2 = await recv_json(ws2, "broadcast")
        assert msg1["payload"]["text"] == "fire!"
        assert msg2["payload"]["text"] == "fire!"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws3.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_broadcast_without_channel_still_reaches_all(server):
    async with connect(server) as ws1, connect(server) as ws2:
        await recv_json(ws1, "system")
        await recv_json(ws2, "system")

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1, "system")
        # ws2 is subscribed to nothing

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "no channel here"},
        }))

        msg1 = await recv_json(ws1, "broadcast")
        msg2 = await recv_json(ws2, "broadcast")
        assert msg1["payload"]["text"] == "no channel here"
        assert msg2["payload"]["text"] == "no channel here"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery(server):
    async with connect(server) as ws1, connect(server) as ws2:
        await recv_json(ws1, "system")
        await recv_json(ws2, "system")

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await recv_json(ws1, "system")
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await recv_json(ws2, "system")

        await ws2.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "chat"}}))
        unsub_ack = await recv_json(ws2, "system")
        assert unsub_ack["payload"] == {"event": "unsubscribed", "channel": "chat"}

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "chat", "text": "hi"},
        }))
        msg1 = await recv_json(ws1, "broadcast")
        assert msg1["payload"]["text"] == "hi"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_disconnect_removes_client_from_channels(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1, "system")
        assert ns.channels.subscribers("alerts") != []

    for _ in range(50):
        if not ns.channels.subscribers("alerts"):
            break
        await asyncio.sleep(0.05)
    assert ns.channels.subscribers("alerts") == []


@pytest.mark.asyncio
async def test_channels_endpoint_lists_active_channels_and_counts(server):
    async with connect(server) as ws1, connect(server) as ws2:
        await recv_json(ws1, "system")
        await recv_json(ws2, "system")

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1, "system")
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws2, "system")
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await recv_json(ws1, "system")

        status_line, data = await http_get(server, "/channels")
        assert "200" in status_line
        by_name = {c["name"]: c["subscribers"] for c in data["channels"]}
        assert by_name == {"alerts": 2, "chat": 1}


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_lists_subscriber_ids(server):
    async with connect(server) as ws1, connect(server) as ws2:
        welcome1 = await recv_json(ws1, "system")
        welcome2 = await recv_json(ws2, "system")
        id1 = welcome1["payload"]["client_id"]
        id2 = welcome2["payload"]["client_id"]

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws1, "system")
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws2, "system")

        status_line, data = await http_get(server, "/channels/alerts/subscribers")
        assert "200" in status_line
        assert data["channel"] == "alerts"
        assert sorted(data["subscribers"]) == sorted([id1, id2])


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_empty_for_unknown_channel(server):
    async with connect(server) as ws1:
        await recv_json(ws1, "system")
        status_line, data = await http_get(server, "/channels/does-not-exist/subscribers")
        assert "200" in status_line
        assert data == {"channel": "does-not-exist", "subscribers": []}
