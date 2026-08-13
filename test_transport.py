"""Tests for the pluggable transport layer."""

import asyncio
import json

import pytest
import websockets

import app


# ── Configuration ─────────────────────────────────────────────────

def test_transport_default_is_websocket():
    assert app.TRANSPORT_DEFAULT == "websocket"


def test_resolve_transport_default():
    assert app.resolve_transport() == "websocket"


def test_resolve_transport_from_env(monkeypatch):
    monkeypatch.setenv("TRANSPORT", "sse")
    assert app.resolve_transport() == "sse"
    assert app.resolve_transport("polling") == "polling"
    monkeypatch.delenv("TRANSPORT")
    assert app.resolve_transport() == "websocket"


def test_get_transport_default_is_websocket():
    transport = app.get_transport()
    assert isinstance(transport, app.WebSocketTransport)


def test_get_transport_by_name():
    transport = app.get_transport("ws")
    assert isinstance(transport, app.WebSocketTransport)


def test_get_transport_unknown_raises():
    with pytest.raises(ValueError):
        app.get_transport("carrier-pigeon")


# ── Interface ────────────────────────────────────────────────────

def test_base_transport_is_abstract():
    with pytest.raises(TypeError):
        app.BaseTransport()


def test_websocket_transport_is_concrete():
    registry = app.ClientRegistry()
    transport = app.WebSocketTransport(registry=registry)
    assert transport.registry is registry


# ── Custom transport is pluggable ────────────────────────────────

class _EchoTransport(app.BaseTransport):
    """Minimal in-memory transport used to prove pluggability."""

    def __init__(self, registry=None):
        super().__init__(registry=registry)
        self.sent = []

    def on_connect(self, connection):
        return self.registry.add(connection)

    def on_disconnect(self, client_id):
        self.registry.remove(client_id)

    async def send_message(self, client_id, message):
        connection = self.registry.get(client_id)
        if connection is None:
            return False
        self.sent.append((client_id, message))
        return True

    async def broadcast(self, message):
        count = 0
        for client_id in list(self.registry.snapshot()):
            if await self.send_message(client_id, message):
                count += 1
        return count

    async def receive(self, connection):
        return None

    async def serve(self, host, port, handler):
        return object()

    async def close(self, server):
        return None


def test_custom_transport_connects_and_disconnects():
    registry = app.ClientRegistry()
    transport = _EchoTransport(registry=registry)
    registry.set_transport(transport)
    client_id = transport.on_connect("stub")
    assert registry.get(client_id) == "stub"
    assert registry.count == 1
    transport.on_disconnect(client_id)
    assert registry.count == 0


async def test_registry_delivers_through_custom_transport():
    registry = app.ClientRegistry()
    transport = _EchoTransport(registry=registry)
    registry.set_transport(transport)
    cid_a = registry.add("a")
    cid_b = registry.add("b")

    assert await registry.send_to(cid_a, {"type": "system", "payload": {}}) is True
    assert await registry.send_to("missing", {"type": "system", "payload": {}}) is False

    registry.subscribe(cid_a, "alerts")
    delivered = await registry.broadcast_to_channel("alerts", {"n": 1})
    assert delivered == 1

    broadcasted = await registry.broadcast({"n": 2})
    assert broadcasted == 2

    delivered_ids = {cid for cid, _ in transport.sent}
    assert delivered_ids == {cid_a, cid_b}
    assert len(transport.sent) == 4


@pytest.fixture
async def server():
    srv = await app.make_server()
    try:
        yield srv
    finally:
        await app.close_server(srv)


async def test_websocket_transport_default_selection(server):
    assert isinstance(server["transport"], app.WebSocketTransport)


async def test_websocket_transport_full_roundtrip(server):
    uri = f"ws://127.0.0.1:{server['ws_port']}"
    ws = await asyncio.wait_for(websockets.connect(uri), 5)
    try:
        welcome = json.loads(await asyncio.wait_for(ws.recv(), 5))
        assert welcome["type"] == "system"
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "hi"}}))
        echo = json.loads(await asyncio.wait_for(ws.recv(), 5))
        assert echo["type"] == "broadcast"
        assert echo["payload"] == {"text": "hi"}
    finally:
        await ws.close()
