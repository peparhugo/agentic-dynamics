"""Examples showing how to use different transport implementations."""

import asyncio
from notification_server import NotificationServer
from websocket_transport import WebSocketTransport
from polling_transport import PollingTransport


async def example_websocket():
    """Example: Using WebSocket transport (default)."""
    print("Example 1: WebSocket Transport (Default)")
    print("-" * 50)

    server = NotificationServer(
        ws_host='localhost',
        ws_port=8765,
        rest_port=8080
    )
    # Transport is automatically WebSocketTransport

    print(f"Transport type: {type(server.transport).__name__}")
    print(f"WebSocket endpoint: ws://localhost:8765")
    print()


async def example_websocket_explicit():
    """Example: Explicitly passing WebSocket transport."""
    print("Example 2: WebSocket Transport (Explicit)")
    print("-" * 50)

    transport = WebSocketTransport(
        host='localhost',
        port=8765,
        on_client_connect=lambda cid: print(f"Connected: {cid}"),
        on_client_disconnect=lambda cid: print(f"Disconnected: {cid}"),
    )

    server = NotificationServer(
        ws_host='localhost',
        ws_port=8765,
        rest_port=8080,
        transport=transport
    )

    print(f"Transport type: {type(server.transport).__name__}")
    print(f"WebSocket endpoint: ws://localhost:8765")
    print()


async def example_polling():
    """Example: Using HTTP polling transport."""
    print("Example 3: HTTP Polling Transport")
    print("-" * 50)

    transport = PollingTransport(
        host='localhost',
        port=8766,
        on_client_connect=lambda cid: print(f"Connected: {cid}"),
        on_client_disconnect=lambda cid: print(f"Disconnected: {cid}"),
    )

    server = NotificationServer(
        ws_host='localhost',
        ws_port=8765,
        rest_port=8080,
        transport=transport
    )

    print(f"Transport type: {type(server.transport).__name__}")
    print(f"HTTP polling endpoints:")
    print(f"  POST   /poll/connect")
    print(f"  GET    /poll/{{client_id}}/messages")
    print(f"  POST   /poll/{{client_id}}/send")
    print(f"  POST   /poll/{{client_id}}/disconnect")
    print()


def example_env_config():
    """Example: Using environment variable to select transport."""
    print("Example 4: Transport Selection via Environment Variable")
    print("-" * 50)

    import os
    print("To use WebSocket (default):")
    print("  export TRANSPORT=websocket")
    print("  python notification_server.py")
    print()

    print("To use HTTP polling:")
    print("  export TRANSPORT=polling")
    print("  python notification_server.py")
    print()


def main():
    """Run all examples."""
    print("=" * 50)
    print("NOTIFICATION SERVER TRANSPORT EXAMPLES")
    print("=" * 50)
    print()

    asyncio.run(example_websocket())
    asyncio.run(example_websocket_explicit())
    asyncio.run(example_polling())
    example_env_config()

    print("=" * 50)
    print("Adding New Transports")
    print("=" * 50)
    print("""
To add a new transport mechanism (e.g., SSE, raw TCP):

1. Create a new file (e.g., sse_transport.py)
2. Inherit from BaseTransport
3. Implement required methods:
   - on_connect(client_id)
   - on_disconnect(client_id)
   - send_message(client_id, message)
   - broadcast(message, channel=None)
   - run()
   - stop()
4. Update NotificationServer._create_transport() to support it
5. All existing code continues to work unchanged!

Example transports to implement:
  - SSE (Server-Sent Events) transport
  - Raw TCP transport
  - gRPC transport
  - Message queue transport (RabbitMQ, Kafka)
    """)


if __name__ == '__main__':
    main()
