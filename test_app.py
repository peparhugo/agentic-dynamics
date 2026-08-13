import json

import pytest
import pytest_asyncio
from websockets.asyncio.client import connect

import app


@pytest_asyncio.fixture
async def ws_server():
    server = app.NotificationServer()
    ws = await app.start_ws_server(server)
    httpd = app.start_health_server(server.registry)
    ws_port = ws.sockets[0].getsockname()[1]
    health_port = httpd.server_address[1]
    yield {
        "server": server,
        "ws": ws,
        "httpd": httpd,
        "ws_url": f"ws://127.0.0.1:{ws_port}",
        "health_url": f"http://127.0.0.1:{health_port}",
    }
    ws.close()
    app.stop_health_server(httpd)


@pytest_asyncio.fixture
async def client(ws_server):
    ws = await connect(ws_server["ws_url"])
    greeting = json.loads(await ws.recv())
    yield ws, greeting["payload"]["client_id"]
    await ws.close()


async def recv_message(ws):
    return json.loads(await ws.recv())


async def test_connect_assigns_unique_ids(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    g1 = await recv_message(ws1)
    g2 = await recv_message(ws2)
    assert g1["type"] == "system"
    assert g2["type"] == "system"
    id1 = g1["payload"]["client_id"]
    id2 = g2["payload"]["client_id"]
    assert id1 != id2
    assert len(ws_server["server"].registry) == 2
    await ws1.close()
    await ws2.close()


async def test_broadcast_reaches_all_connected_clients(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    await recv_message(ws1)
    await recv_message(ws2)

    await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))
    m1 = await recv_message(ws1)
    m2 = await recv_message(ws2)
    assert m1["type"] == "broadcast"
    assert m1["payload"] == {"text": "hello"}
    assert m2["type"] == "broadcast"
    assert m2["payload"] == {"text": "hello"}
    assert "timestamp" in m1
    await ws1.close()
    await ws2.close()


async def test_direct_message_routes_to_target_client(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    g1 = await recv_message(ws1)
    g2 = await recv_message(ws2)
    id2 = g2["payload"]["client_id"]

    await ws1.send(
        json.dumps({"type": "direct", "payload": {"client_id": id2, "text": "psst"}})
    )
    m2 = await recv_message(ws2)
    assert m2["type"] == "direct"
    assert m2["payload"] == {"client_id": id2, "text": "psst"}
    await ws1.close()
    await ws2.close()


async def test_direct_message_to_unknown_client_reports_error(ws_server, client):
    ws, _ = client
    await ws.send(
        json.dumps({"type": "direct", "payload": {"client_id": "nope", "text": "hi"}})
    )
    err = await recv_message(ws)
    assert err["type"] == "system"
    assert err["payload"]["action"] == "error"


async def test_system_health_returns_client_count(ws_server, client):
    ws, _ = client
    await ws.send(json.dumps({"type": "system", "payload": {"action": "health"}}))
    resp = await recv_message(ws)
    assert resp["type"] == "system"
    assert resp["payload"]["action"] == "health"
    assert resp["payload"]["client_count"] == 1


async def test_disconnect_removes_client_cleanly(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    await recv_message(ws1)
    ws2 = await connect(ws_server["ws_url"])
    await recv_message(ws2)
    assert len(ws_server["server"].registry) == 2

    await ws1.close()
    await asyncio_gather_till_count(ws_server["server"].registry, 1)
    assert len(ws_server["server"].registry) == 1
    await ws2.close()


async def asyncio_gather_till_count(registry, expected):
    import asyncio

    for _ in range(50):
        if len(registry) == expected:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"registry did not reach {expected} clients")


def test_http_health_endpoint_returns_client_count(ws_server):
    import urllib.request

    with urllib.request.urlopen(ws_server["health_url"] + "/health") as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
        assert body == {"client_count": 0}


async def test_subscribe_acknowledges_subscription(ws_server, client):
    ws, _ = client
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    ack = await recv_message(ws)
    assert ack["type"] == "system"
    assert ack["payload"]["action"] == "subscribed"
    assert ack["payload"]["channel"] == "alerts"


async def test_subscribe_without_channel_reports_error(ws_server, client):
    ws, _ = client
    await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
    err = await recv_message(ws)
    assert err["type"] == "system"
    assert err["payload"]["action"] == "error"


async def test_channel_message_delivered_only_to_subscribers(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    ws3 = await connect(ws_server["ws_url"])
    await recv_message(ws1)
    await recv_message(ws2)
    await recv_message(ws3)

    await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws1)
    await recv_message(ws2)

    await ws1.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "hi"}}))
    m1 = await recv_message(ws1)
    m2 = await recv_message(ws2)
    assert m1["type"] == "broadcast"
    assert m1["payload"] == {"channel": "alerts", "text": "hi"}
    assert m2["type"] == "broadcast"
    assert m2["payload"] == {"channel": "alerts", "text": "hi"}
    await ws1.close()
    await ws2.close()
    await ws3.close()


async def test_unsubscribed_client_does_not_receive_channel_message(ws_server):
    ws_sub = await connect(ws_server["ws_url"])
    ws_not = await connect(ws_server["ws_url"])
    await recv_message(ws_sub)
    await recv_message(ws_not)

    await ws_sub.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws_sub)

    await ws_sub.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "hi"}}))
    m = await recv_message(ws_sub)
    assert m["payload"]["text"] == "hi"
    assert not await _poll_no_message(ws_not)
    await ws_sub.close()
    await ws_not.close()


async def test_unsubscribe_stops_channel_delivery(ws_server):
    ws1 = await connect(ws_server["ws_url"])
    ws2 = await connect(ws_server["ws_url"])
    await recv_message(ws1)
    await recv_message(ws2)

    await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws1)
    await recv_message(ws2)

    await ws2.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
    ack = await recv_message(ws2)
    assert ack["payload"]["action"] == "unsubscribed"

    await ws1.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "hi"}}))
    m1 = await recv_message(ws1)
    assert m1["payload"]["text"] == "hi"
    assert not await _poll_no_message(ws2)
    await ws1.close()
    await ws2.close()


async def test_client_can_subscribe_to_multiple_channels(ws_server):
    ws = await connect(ws_server["ws_url"])
    await recv_message(ws)
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws)
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
    await recv_message(ws)

    await ws.send(json.dumps({"type": "broadcast", "payload": {"channel": "alerts", "text": "a"}}))
    await ws.send(json.dumps({"type": "broadcast", "payload": {"channel": "chat", "text": "c"}}))
    assert (await recv_message(ws))["payload"]["text"] == "a"
    assert (await recv_message(ws))["payload"]["text"] == "c"
    await ws.close()


async def test_broadcast_without_channel_reaches_everyone(ws_server):
    ws_sub = await connect(ws_server["ws_url"])
    ws_not = await connect(ws_server["ws_url"])
    await recv_message(ws_sub)
    await recv_message(ws_not)

    await ws_sub.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws_sub)

    await ws_sub.send(json.dumps({"type": "broadcast", "payload": {"text": "all"}}))
    m1 = await recv_message(ws_sub)
    m2 = await recv_message(ws_not)
    assert m1["payload"] == {"text": "all"}
    assert m2["payload"] == {"text": "all"}
    await ws_sub.close()
    await ws_not.close()


async def _poll_no_message(ws):
    import asyncio

    for _ in range(10):
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.05)
            return True
        except asyncio.TimeoutError:
            continue
    return False


def test_http_channels_endpoint_empty(ws_server):
    import urllib.request

    with urllib.request.urlopen(ws_server["health_url"] + "/channels") as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
        assert body == {"channels": {}}


async def test_http_channels_lists_subscriber_counts(ws_server):
    import urllib.request

    ws = await connect(ws_server["ws_url"])
    await recv_message(ws)
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws)

    with urllib.request.urlopen(ws_server["health_url"] + "/channels") as resp:
        body = json.loads(resp.read())
    assert body["channels"]["alerts"] == 1
    await ws.close()


async def test_http_channels_subscribers_endpoint(ws_server):
    import urllib.request

    ws = await connect(ws_server["ws_url"])
    greeting = await recv_message(ws)
    client_id = greeting["payload"]["client_id"]
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await recv_message(ws)

    with urllib.request.urlopen(ws_server["health_url"] + "/channels/alerts/subscribers") as resp:
        assert resp.status == 200
        body = json.loads(resp.read())
    assert body["channel"] == "alerts"
    assert body["subscribers"] == [client_id]
    await ws.close()
