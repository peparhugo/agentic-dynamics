# Notification Server Transport Layer Refactoring

## Overview

The notification server has been refactored to use a pluggable transport layer, enabling different communication mechanisms (WebSocket, SSE, polling, TCP) to be used interchangeably without modifying the core notification logic.

## Architecture

### BaseTransport (Abstract Base Class)

All transport implementations inherit from `BaseTransport` and implement these methods:

```python
class BaseTransport(ABC):
    async def on_connect(self, client_id: str) -> None:
        """Called when a client connects."""
        
    async def on_disconnect(self, client_id: str) -> None:
        """Called when a client disconnects."""
        
    async def send_message(self, client_id: str, message: str) -> None:
        """Send a message to a specific client."""
        
    async def broadcast(self, message: str, client_ids: Set[str] | None = None) -> None:
        """Broadcast a message to all clients or specific clients."""
        
    async def start(self, host: str, port: int) -> None:
        """Start the transport server."""
        
    async def shutdown(self) -> None:
        """Shutdown the transport server."""
```

### WebSocketTransport (Built-in Implementation)

The existing WebSocket logic has been extracted into `WebSocketTransport`, which:
- Manages WebSocket connections
- Handles client registration and unregistration
- Sends messages to individual clients or broadcasts to groups
- Provides the same functionality as the original implementation

### NotificationServer Integration

The `NotificationServer` class now:
- Accepts a `transport` parameter (defaults to `WebSocketTransport`)
- Delegates all client connection/message handling to the transport
- Remains independent of transport specifics
- Can work with any `BaseTransport` implementation

## Configuration

### Default (WebSocket)
```python
from notification_server import create_server

server = create_server()  # Uses WebSocketTransport by default
await server.start()
```

### Environment Variable
```bash
export TRANSPORT=websocket  # or any custom transport type
python notification_server.py
```

### Programmatic Selection
```python
from notification_server import create_server, WebSocketTransport

transport = WebSocketTransport()
server = create_server(transport=transport)
```

## Custom Transport Implementation

To add a new transport (e.g., SSE, polling), create a class that inherits from `BaseTransport`:

```python
from notification_server import BaseTransport, create_server

class CustomTransport(BaseTransport):
    async def on_connect(self, client_id: str) -> None:
        # Implementation
        
    async def on_disconnect(self, client_id: str) -> None:
        # Implementation
        
    async def send_message(self, client_id: str, message: str) -> None:
        # Implementation
        
    async def broadcast(self, message: str, client_ids=None) -> None:
        # Implementation
        
    async def start(self, host: str, port: int) -> None:
        # Implementation
        
    async def shutdown(self) -> None:
        # Implementation

# Use the custom transport
transport = CustomTransport()
server = create_server(transport=transport)
await server.start()
```

See `transport_examples.py` for example implementations of polling and SSE transports.

## API Compatibility

✅ **All existing APIs remain unchanged:**
- WebSocket client API (message format, connection flow)
- REST endpoints (/health, /messages, /channels, etc.)
- Message persistence and Redis pub/sub integration
- Client registry and subscription management
- All 57 existing tests pass without modification

## Benefits

1. **Flexibility**: Different transports can be added without modifying core logic
2. **Testability**: Transport layer can be mocked for testing
3. **Extensibility**: Custom transports for specific use cases (polling, SSE, TCP, gRPC, etc.)
4. **Separation of Concerns**: Transport logic is isolated from business logic
5. **Backward Compatibility**: Existing WebSocket behavior is preserved

## Files Modified

- `notification_server.py`:
  - Added `BaseTransport` abstract class
  - Added `WebSocketTransport` concrete implementation
  - Modified `NotificationServer.__init__()` to accept transport parameter
  - Modified `NotificationServer.handle_client()` to accept client_id parameter
  - Modified `NotificationServer.ws_server()` to use transport.start()
  - Modified `create_server()` factory to handle TRANSPORT env var

## Files Created

- `transport_examples.py`: Example implementations of alternative transports (Polling, SSE)
- `TRANSPORT_REFACTORING.md`: This documentation file

## Testing

All 57 existing tests pass without modification:
- Unit tests for BaseTransport and WebSocketTransport
- Integration tests with running server
- HTTP endpoint tests
- Message persistence and Redis integration tests

```bash
python3 -m pytest test_notification_server.py -v
# PASSED 57/57 tests
```

## Future Transport Examples

The pluggable architecture enables easy addition of:

- **Server-Sent Events (SSE)**: HTTP-based one-way server push
- **Polling**: HTTP-based client polling for messages
- **Raw TCP**: Direct TCP connections
- **gRPC**: Google's high-performance RPC framework
- **MQTT**: IoT-friendly publish/subscribe protocol
- **Apache Kafka**: Distributed streaming platform
- **Redis Pub/Sub**: Direct Redis connection for clients

Each requires a minimal implementation of `BaseTransport`.
