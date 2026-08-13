"""Integration tests for the Redis pub/sub backbone: multiple
NotificationServer instances sharing one Redis backend must behave like one
logical cluster (messages cross instances, connection state is shared and
outlives an individual process), and every routed message must be
persisted to SQLite and queryable via GET /messages.
"""
import asyncio
import json
import os

import aiohttp
import pytest
import websockets
from websockets.asyncio.server import serve


async def recv_json(ws, timeout=2):
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


async def connect_and_get_id(uri):
    ws = await websockets.connect(uri)
    welcome = await recv_json(ws)
    assert welcome["payload"]["event"] == "connected"
    return ws, welcome["payload"]["client_id"]


class RunningInstance:
    """A NotificationServer bound to a real localhost port, for tests that
    need multiple independent server processes-in-miniature sharing one
    Redis backend."""

    def __init__(self, notification_server, server, db_path):
        self.notification_server = notification_server
        self.server = server
        self.db_path = db_path
        port = server.sockets[0].getsockname()[1]
        self.uri = f"ws://localhost:{port}"
        self.http_base = f"http://localhost:{port}"

    async def close(self):
        self.server.close()
        await self.server.wait_closed()
        await self.notification_server.close()
        os.remove(self.db_path)


async def start_instance(factory, shared_fake_server=None):
    notification_server, fake_server, db_path = factory(shared_fake_server)
    await notification_server.start()
    server = await serve(
        notification_server.handler,
        "localhost",
        0,
        process_request=notification_server.process_request,
    )
    return RunningInstance(notification_server, server, db_path), fake_server


async def test_broadcast_from_one_instance_reaches_client_on_another(notification_server_factory):
    instance_a, fake_server = await start_instance(notification_server_factory)
    instance_b, _ = await start_instance(notification_server_factory, fake_server)
    try:
        ws_a, id_a = await connect_and_get_id(instance_a.uri)
        ws_b, id_b = await connect_and_get_id(instance_b.uri)
        try:
            await ws_a.send(json.dumps({"type": "broadcast", "payload": {"text": "hello from A"}}))

            msg = await recv_json(ws_b)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello from A"
            assert msg["payload"]["from"] == id_a

            # the sender's own instance also delivers it locally.
            own_echo = await recv_json(ws_a)
            assert own_echo["payload"]["text"] == "hello from A"
        finally:
            await ws_a.close()
            await ws_b.close()
    finally:
        await instance_a.close()
        await instance_b.close()


async def test_channel_scoped_broadcast_crosses_instances(notification_server_factory):
    instance_a, fake_server = await start_instance(notification_server_factory)
    instance_b, _ = await start_instance(notification_server_factory, fake_server)
    try:
        ws_a, id_a = await connect_and_get_id(instance_a.uri)
        ws_b, id_b = await connect_and_get_id(instance_b.uri)
        try:
            await ws_b.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
            ack = await recv_json(ws_b)
            assert ack["payload"]["event"] == "subscribed"

            await ws_a.send(json.dumps({
                "type": "broadcast",
                "channel": "alerts",
                "payload": {"text": "cluster-wide alert"},
            }))

            msg = await recv_json(ws_b)
            assert msg["channel"] == "alerts"
            assert msg["payload"]["text"] == "cluster-wide alert"

            # ws_a never subscribed, so it should not receive this one.
            with pytest.raises(asyncio.TimeoutError):
                await recv_json(ws_a, timeout=0.3)
        finally:
            await ws_a.close()
            await ws_b.close()
    finally:
        await instance_a.close()
        await instance_b.close()


async def test_direct_message_delivered_across_instances(notification_server_factory):
    instance_a, fake_server = await start_instance(notification_server_factory)
    instance_b, _ = await start_instance(notification_server_factory, fake_server)
    try:
        ws_a, id_a = await connect_and_get_id(instance_a.uri)
        ws_b, id_b = await connect_and_get_id(instance_b.uri)
        try:
            await ws_a.send(json.dumps({"type": "direct", "payload": {"target": id_b, "text": "psst, cross-node"}}))

            msg = await recv_json(ws_b)
            assert msg["type"] == "direct"
            assert msg["payload"]["from"] == id_a
            assert msg["payload"]["text"] == "psst, cross-node"

            with pytest.raises(asyncio.TimeoutError):
                await recv_json(ws_a, timeout=0.3)
        finally:
            await ws_a.close()
            await ws_b.close()
    finally:
        await instance_a.close()
        await instance_b.close()


async def test_direct_message_to_client_known_only_via_shared_state(notification_server_factory):
    """The sender is on instance A and the target is connected only to
    instance B. Instance A has never seen that client locally, yet it must
    still resolve it as a valid target because presence is shared via
    Redis, not kept in the sender's local in-process registry."""
    instance_a, fake_server = await start_instance(notification_server_factory)
    instance_b, _ = await start_instance(notification_server_factory, fake_server)
    try:
        ws_b, id_b = await connect_and_get_id(instance_b.uri)
        ws_a, id_a = await connect_and_get_id(instance_a.uri)
        try:
            assert id_b not in instance_a.notification_server.registry.all_ids()

            await ws_a.send(json.dumps({"type": "direct", "payload": {"target": id_b, "text": "found you"}}))
            msg = await recv_json(ws_b)
            assert msg["payload"]["text"] == "found you"
        finally:
            await ws_a.close()
            await ws_b.close()
    finally:
        await instance_a.close()
        await instance_b.close()


async def test_client_state_is_shared_and_outlives_the_connecting_instance(notification_server_factory):
    """Connection state lives in Redis, not just in the process that
    accepted the connection: a brand new NotificationServer instance
    pointed at the same Redis backend (standing in for "the server
    restarted") immediately sees the same connected-client count -- state
    that would be lost if it were only an in-process dict."""
    instance_a, fake_server = await start_instance(notification_server_factory)
    try:
        ws_a, id_a = await connect_and_get_id(instance_a.uri)
        try:
            fresh_notification_server, _, fresh_db_path = notification_server_factory(fake_server)
            try:
                assert await fresh_notification_server.state.is_connected(id_a)
                assert await fresh_notification_server.state.count() == 1
            finally:
                await fresh_notification_server.close()
                os.remove(fresh_db_path)
        finally:
            await ws_a.close()
    finally:
        await instance_a.close()


async def test_messages_are_persisted_and_queryable_via_rest_endpoint(running_server):
    notification_server, uri, health_url = running_server
    messages_url = health_url.replace("/health", "/messages")

    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        for i in range(3):
            await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": f"msg-{i}"}}))
            await recv_json(ws1)
            await recv_json(ws2)

        async with aiohttp.ClientSession() as session:
            async with session.get(messages_url) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert len(data) == 3
                # most recent first
                assert [m["payload"]["text"] for m in data] == ["msg-2", "msg-1", "msg-0"]
                assert all(m["type"] == "broadcast" for m in data)
                assert all(m["payload"]["from"] == id1 for m in data)

        # a fresh session, since this websockets version doesn't reliably
        # keep a plain-HTTP connection alive across back-to-back requests.
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{messages_url}?limit=1&offset=1") as resp:
                data = await resp.json()
                assert len(data) == 1
                assert data[0]["payload"]["text"] == "msg-1"
    finally:
        await ws1.close()
        await ws2.close()


async def test_messages_endpoint_persists_channel_and_direct_messages(running_server):
    notification_server, uri, health_url = running_server
    messages_url = health_url.replace("/health", "/messages")

    ws1, id1 = await connect_and_get_id(uri)
    ws2, id2 = await connect_and_get_id(uri)
    try:
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws2)

        await ws1.send(json.dumps({"type": "broadcast", "channel": "alerts", "payload": {"text": "chan msg"}}))
        await recv_json(ws2)

        await ws1.send(json.dumps({"type": "direct", "payload": {"target": id2, "text": "direct msg"}}))
        await recv_json(ws2)

        async with aiohttp.ClientSession() as session:
            async with session.get(messages_url) as resp:
                data = await resp.json()

        assert len(data) == 2
        by_type = {m["type"]: m for m in data}
        assert by_type["broadcast"]["channel"] == "alerts"
        assert by_type["broadcast"]["payload"]["text"] == "chan msg"
        assert by_type["direct"]["channel"] is None
        assert by_type["direct"]["payload"]["text"] == "direct msg"
    finally:
        await ws1.close()
        await ws2.close()


async def test_messages_endpoint_empty_when_no_messages_sent(running_server):
    _, _, health_url = running_server
    messages_url = health_url.replace("/health", "/messages")

    async with aiohttp.ClientSession() as session:
        async with session.get(messages_url) as resp:
            assert resp.status == 200
            assert await resp.json() == []


async def test_messages_endpoint_ignores_invalid_query_params(running_server):
    notification_server, uri, health_url = running_server
    messages_url = health_url.replace("/health", "/messages")

    ws1, _ = await connect_and_get_id(uri)
    try:
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "only message"}}))
        await recv_json(ws1)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{messages_url}?limit=not-a-number&offset=-5") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert len(data) == 1
    finally:
        await ws1.close()
