# WebSocket Notification Server

A Python-based WebSocket notification server with broadcast and direct messaging capabilities, built with async/await and thread-safe client management.

## Features

- ✅ WebSocket server accepting client connections
- ✅ Unique client ID assignment on connect
- ✅ Broadcast messages to ALL connected clients
- ✅ Direct messaging between specific clients
- ✅ Automatic cleanup on client disconnect
- ✅ REST health endpoint returning connected client count
- ✅ Thread-safe client registry
- ✅ JSON message format with timestamps
- ✅ Comprehensive test coverage (20 tests, 100% pass rate)

## Tech Stack

- **Framework**: Python 3.10+
- **WebSocket Library**: `websockets` (async, not Flask-SocketIO)
- **HTTP Server**: `aiohttp` (for REST endpoints)
- **Async Runtime**: `asyncio`
- **Testing**: `pytest` with `pytest-asyncio`
- **Thread Safety**: `threading.Lock` for client registry

## Installation

```bash
pip install -r requirements.txt
```

## Running the Server

```bash
python3 websocket_server.py
```

The server will start on:
- **WebSocket**: `ws://0.0.0.0:8765`
- **Health Endpoint**: `http://0.0.0.0:9765/health`

## API Reference

### Message Format

All messages are JSON with the following structure:

```json
{
  "type": "broadcast|direct|system",
  "payload": {
    "key": "value"
  },
  "timestamp": "2025-08-13T10:15:30.123456"
}
```

### Message Types

#### Broadcast Message
Send a message to all connected clients:

```json
{
  "type": "broadcast",
  "payload": {
    "text": "Hello everyone!",
    "sender_id": "user123"
  }
}
```

#### Direct Message
Send a message to a specific client:

```json
{
  "type": "direct",
  "payload": {
    "target_id": "recipient-uuid",
    "text": "Private message"
  }
}
```

#### System Message
Sent by the server to acknowledge connection:

```json
{
  "type": "system",
  "payload": {
    "message": "Connected to notification server",
    "client_id": "unique-uuid"
  },
  "timestamp": "2025-08-13T10:15:30.123456"
}
```

### REST Endpoints

#### Health Check
```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "connected_clients": 5
}
```

## Usage Examples

### Python Client Example

```python
import asyncio
import json
import websockets

async def send_broadcast():
    async with websockets.connect("ws://localhost:8765") as ws:
        # Receive connection greeting
        greeting = await ws.recv()
        data = json.loads(greeting)
        client_id = data["payload"]["client_id"]
        
        # Send broadcast
        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "Hello all!"}
        }))

asyncio.run(send_broadcast())
```

### Health Check Example

```bash
curl http://localhost:9765/health
```

## Client Registry

The server uses a **thread-safe `ClientRegistry`** class that:
- Stores connected WebSocket connections with unique UUIDs
- Uses `threading.Lock` for thread-safe operations
- Automatically removes disconnected clients
- Provides methods for getting all clients or a specific client

## Testing

Run all tests:
```bash
pytest test_websocket_server.py -v
```

Test coverage includes:
- **Client Registry Tests** (6 tests): Add, remove, retrieve clients
- **Server Tests** (14 tests): Connection, broadcasting, health endpoint, error handling

All 20 tests pass ✅

## Architecture

### ClientRegistry
Thread-safe registry for managing connected WebSocket clients:
- `add(client_id, websocket)`: Add a new client
- `remove(client_id)`: Remove a client
- `get(client_id)`: Get a specific client
- `get_all()`: Get all clients
- `get_count()`: Get number of connected clients

### NotificationServer
Main server class:
- `start()`: Start both WebSocket and HTTP servers
- `stop()`: Gracefully shutdown servers
- `broadcast(payload)`: Send message to all clients
- `send_direct(target_id, payload)`: Send message to specific client
- `handle_client(websocket, path)`: Handle new connections
- `health_handler()`: REST endpoint handler

## Connection Lifecycle

1. **Connect**: Client connects → Server assigns unique UUID → Sends system message
2. **Operate**: Client can send broadcast/direct messages
3. **Disconnect**: Client disconnects → Server removes from registry
4. **Automatic Cleanup**: Failed sends automatically clean up dead connections

## Design Decisions

- **No external database**: Client registry is in-memory (suitable for notification use cases)
- **Thread-safe with Lock**: Ensures concurrent access safety
- **Async-first**: Uses Python asyncio for scalability
- **JSON only**: All messages are JSON for simplicity and interoperability
- **Separate HTTP server**: Health endpoint on separate port to keep concerns separate
- **UUID for client IDs**: Ensures uniqueness without collisions
