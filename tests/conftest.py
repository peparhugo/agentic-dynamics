import asyncio

import pytest_asyncio
import websockets

import app


async def recv_message(websocket, timeout: float = 5.0) -> dict:
    raw = await asyncio.wait_for(websocket.recv(), timeout)
    return _decode(raw)


async def recv_message_with_id(websocket, client_id: str, timeout: float = 5.0) -> dict:
    while True:
        message = await recv_message(websocket, timeout)
        if message.get("payload", {}).get("client_id") != client_id:
            raise AssertionError("unexpected message while waiting for welcome")
        return message


def _decode(raw) -> dict:
    import json

    return json.loads(raw)


async def wait_for_count(registry, expected: int, timeout: float = 5.0) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while registry.count() != expected:
        if loop.time() >= deadline:
            raise AssertionError(
                f"registry count is {registry.count()}, expected {expected}"
            )
        await asyncio.sleep(0.01)


@pytest_asyncio.fixture
async def running_server():
    server = app.NotificationServer()
    await server.start(
        ws_host="127.0.0.1", ws_port=0,
        http_host="127.0.0.1", http_port=0,
    )
    try:
        yield server
    finally:
        await server.stop()


@pytest_asyncio.fixture
async def ws_url(running_server):
    return f"ws://127.0.0.1:{running_server.ws_port}"


@pytest_asyncio.fixture
async def http_url(running_server):
    return f"http://127.0.0.1:{running_server.http_port}"
