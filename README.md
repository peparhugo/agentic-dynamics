# WebSocket Notification Server

A production-ready async WebSocket notification server in Python with broadcast and direct messaging capabilities.

## Features

✓ **WebSocket Connections**: Accept client connections with unique UUIDs  
✓ **Broadcast Messaging**: Send messages to all connected clients  
✓ **Direct Messaging**: Send messages to specific clients  
✓ **Health Endpoint**: REST API to check server status and client count  
✓ **Graceful Disconnection**: Automatic cleanup and broadcast of disconnection events  
✓ **Thread-Safe**: asyncio.Lock-based client registry  

## Message Format

All messages follow this JSON format:
```json
{
  "type": "broadcast|direct|system",
  "payload": {"key": "value", ...},
  "timestamp": "2024-08-13T12:00:00.000000"
}
```

## Architecture

- **websockets**: WebSocket server library
- **aiohttp**: REST API for health endpoint
- **asyncio**: Async/await event loop
- **asyncio.Lock**: Thread-safe client registry

## Running the Server

```bash
python3 app.py
```

- WebSocket server: `ws://localhost:8765`
- REST health endpoint: `http://localhost:8080/health`

## API Endpoints

### WebSocket (ws://localhost:8765)
Connect to receive and send messages in JSON format.

**Broadcast Message**:
```json
{"type": "broadcast", "payload": {"message": "hello everyone"}}
```

**Direct Message**:
```json
{"type": "direct", "payload": {"to_client": "client-id", "message": "private"}}
```

### REST: GET /health
Returns server status and connected client count.

**Response**:
```json
{
  "status": "ok",
  "connected_clients": 5,
  "timestamp": "2024-08-13T12:00:00.000000"
}
```

## Testing

Run the comprehensive test suite:
```bash
python3 -m pytest test_app.py -v
```

**20 tests covering**:
- Client registration/unregistration
- Broadcasting and direct messaging
- Disconnection handling
- Message format validation
- Concurrent operations
- Edge cases

## Implementation Details

### ClientRegistry
Thread-safe registry using `asyncio.Lock`:
- `register(client_id, websocket)`: Add new client
- `unregister(client_id)`: Remove client
- `get_client_count()`: Current connected clients
- `broadcast(message)`: Send to all clients

### Event Loop
- WebSocket server: port 8765
- REST server: port 8080
- Both run concurrently via asyncio tasks

### Error Handling
- Automatic removal of disconnected clients
- Invalid JSON rejection
- Connection closure handling
- Broadcast failure recovery
