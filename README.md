# WebSocket Notification Server

A thread-safe, async WebSocket notification server built with Python, featuring broadcast messaging, direct messaging, and a REST health endpoint.

## Features

- **WebSocket Connections**: Accept client connections and assign unique IDs
- **Broadcast Messaging**: Send messages to all connected clients
- **Direct Messaging**: Send messages to specific clients
- **System Messages**: Handle connection/disconnection events
- **REST Health Endpoint**: Monitor connected client count via HTTP
- **Thread-Safe Registry**: Concurrent client management with thread safety
- **Async/Await**: Built on asyncio for high performance
- **JSON Message Format**: All messages follow a consistent JSON schema

## Architecture

### NotificationServer Class

Thread-safe client registry with methods:
- `add_client(client_id, websocket)`: Register a new client
- `remove_client(client_id)`: Unregister a client
- `get_client_count()`: Get number of connected clients
- `broadcast(message)`: Send message to all clients
- `send_direct(client_id, message)`: Send message to specific client

### WebSocket Handler

Handles incoming connections and messages:
- Assigns UUID to each client on connect
- Processes broadcast and direct messages
- Handles JSON parsing errors gracefully
- Cleans up disconnected clients

### REST Endpoint

- `GET /health`: Returns server status and connected client count

## Message Format

All messages are JSON with the following structure:

```json
{
  "type": "broadcast|direct|system",
  "payload": {},
  "timestamp": "2023-01-01T00:00:00.000000"
}
```

### Message Types

- **broadcast**: Sent to all connected clients
- **direct**: Sent to a specific client (requires `client_id` in payload)
- **system**: Internal messages (connections, disconnections, errors)

## Usage

### Start the Server

```python
import asyncio
from server import main

asyncio.run(main())
```

Servers run on:
- WebSocket: `ws://localhost:8765`
- REST: `http://localhost:8080`

### Send a Broadcast Message

```json
{
  "type": "broadcast",
  "payload": {
    "text": "Hello everyone",
    "data": {...}
  }
}
```

### Send a Direct Message

```json
{
  "type": "direct",
  "payload": {
    "client_id": "uuid-of-target",
    "message": {
      "text": "Personal message"
    }
  }
}
```

## Testing

Run all tests:

```bash
python3 -m pytest test_server.py -v
```

Test coverage includes:
- Client registration and cleanup
- Broadcast functionality
- Direct messaging
- Message format validation
- Thread safety
- Connection error handling
- Edge cases (empty payloads, large messages, closed connections)

## Dependencies

- `websockets`: WebSocket protocol implementation
- `aiohttp`: REST server and HTTP client
- `pytest`: Testing framework
- `pytest-asyncio`: Async test support

## Design Notes

- Uses `threading.Lock` for thread-safe client registry operations
- Broadcast uses `asyncio.gather()` for concurrent message delivery
- Failed sends are silently skipped to avoid cascade failures
- Timestamps are automatically added if not present in messages
- Unique client IDs are generated using Python's `uuid.uuid4()`
