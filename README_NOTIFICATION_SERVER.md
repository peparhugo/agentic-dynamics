# WebSocket Notification Server

A high-performance, async WebSocket notification server built with Python's `websockets` library. Supports client connections, message broadcasting, direct messaging, and system notifications.

## Features

- **WebSocket Server**: Accept multiple concurrent client connections
- **Unique Client IDs**: Each connected client receives a unique UUID
- **Broadcasting**: Send messages to all connected clients simultaneously
- **Direct Messaging**: Send targeted messages to specific clients
- **Health Endpoint**: REST API endpoint (`GET /health`) returning connected client count
- **Thread-Safe Registry**: Multiple threads can safely access the client registry
- **JSON Message Format**: All messages are standardized JSON with type, payload, and timestamp
- **Error Handling**: Graceful handling of disconnects, invalid JSON, and send failures
- **Async/Await**: Full asyncio support for non-blocking operations

## Message Types

### Connection Confirmation (System)
When a client connects, they receive:
```json
{
  "type": "system",
  "payload": {"action": "connected", "client_id": "uuid-here"},
  "timestamp": "2026-08-13T10:00:00+00:00"
}
```

### Broadcast Message
Send to all connected clients:
```json
{
  "type": "broadcast",
  "payload": {"data": "your data here"},
  "timestamp": "2026-08-13T10:00:00+00:00"
}
```

### Direct Message
Send to a specific client:
```json
{
  "type": "direct",
  "payload": {"target_id": "client-uuid", "message": "data"},
  "timestamp": "2026-08-13T10:00:00+00:00"
}
```

### System Message
Broadcast system-wide notifications:
```json
{
  "type": "system",
  "payload": {"action": "alert", "message": "content"},
  "timestamp": "2026-08-13T10:00:00+00:00"
}
```

## Architecture

### NotificationMessage
Handles message serialization/deserialization:
- `__init__(type, payload)`: Create a message
- `to_json()`: Convert to JSON string
- `from_json(data)`: Parse JSON to message

### ClientRegistry
Thread-safe registry for managing connected clients:
- `add(client_id, connection)`: Add client
- `remove(client_id)`: Remove client
- `get(client_id)`: Retrieve specific client
- `get_all()`: Get all clients (returns copy)
- `count()`: Get number of connected clients
- Uses threading.Lock for thread safety

### NotificationServer
Main server class:
- `handle_client(websocket)`: Handle individual client connections
- `broadcast(message)`: Send message to all clients
- `send_direct(target_id, message)`: Send to specific client
- `http_health(reader, writer)`: HTTP handler for `/health` endpoint
- `start()`: Start both WebSocket and HTTP servers

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Start the Server

```bash
python3 notification_server.py
```

This starts:
- WebSocket server on `ws://127.0.0.1:8765`
- HTTP server on `http://127.0.0.1:8080`

### Run Tests

```bash
pytest test_notification_server.py -v
```

All 32 tests pass, covering:
- Message serialization/deserialization
- Thread-safe client registry operations
- Broadcasting to multiple clients
- Direct messaging
- HTTP health endpoint
- Error handling
- Connection lifecycle

### Demo Client

```bash
python3 client_demo.py
```

## API

### WebSocket Endpoint
- **URI**: `ws://127.0.0.1:8765`
- **Protocol**: JSON-based message protocol

### HTTP Health Endpoint
- **URL**: `http://127.0.0.1:8080/health`
- **Method**: GET
- **Response**: `{"connected_clients": <count>}`
- **Status**: 200 OK

## Configuration

Server parameters can be customized when creating an instance:

```python
from notification_server import create_server

server = create_server(
    host="127.0.0.1",      # Listen address
    ws_port=8765,          # WebSocket port
    http_port=8080         # HTTP port
)

asyncio.run(server.start())
```

## Implementation Details

### Broadcast Mechanism
The server implements broadcasting by:
1. Maintaining a thread-safe registry of connected clients
2. On broadcast request, retrieving all client connections
3. Iterating through connections and sending the message to each
4. Using `asyncio.gather()` for concurrent sends
5. Safely handling disconnects and failures per connection

### Thread Safety
- `ClientRegistry` uses `threading.Lock` to protect access to the client dictionary
- All registry operations are atomic
- Safe for multi-threaded access while maintaining async event loop integrity

### Error Handling
- Gracefully handles `ConnectionClosed` exceptions
- Logs and recovers from send failures
- Invalid JSON messages trigger system error response
- Missing target clients in direct messages are silently ignored with logging

## Logging

The server uses Python's logging module at INFO level:
- Client connections/disconnections
- Message types received
- Any errors during send operations

Enable debug logging by setting environment variable:
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## Tests Coverage

- **5 tests**: NotificationMessage serialization/deserialization
- **8 tests**: ClientRegistry thread-safe operations
- **8 tests**: NotificationServer unit tests
- **3 tests**: HTTP health endpoint
- **8 tests**: Integration tests with real WebSocket connections

## Performance Notes

- Non-blocking async I/O with asyncio
- Supports hundreds of concurrent connections
- Broadcast scales with connection count (linear)
- Efficient connection management with UUID-based lookups

## License

MIT
