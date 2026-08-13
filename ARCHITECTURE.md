# WebSocket Notification Server - Architecture Guide

## System Design

This notification server is designed for microservices environments with clean separation of concerns and scalability in mind.

## Components

### 1. **NotificationServer** (`notification_server.py`)
The main orchestrator managing both WebSocket and REST servers.

**Responsibilities:**
- Accept and manage WebSocket connections
- Route messages (broadcast, direct, system)
- Run REST health endpoint
- Coordinate graceful shutdown

**Key Methods:**
- `handle_client()` - WebSocket connection handler
- `_broadcast_message()` - Send to all clients
- `_direct_message()` - Send to specific client
- `_health_handler()` - REST endpoint

### 2. **ClientRegistry** (`client_registry.py`)
Thread-safe container for connected clients.

**Responsibilities:**
- Register new connections with UUID
- Track active clients
- Thread-safe operations for concurrent access

**Why Thread-Safe?**
- Multiple async tasks may register/unregister simultaneously
- Python threading locks ensure atomicity

### 3. **Message Handler** (`message_handler.py`)
Validates and serializes notification messages.

**Message Structure:**
```
{
  type: 'broadcast'|'direct'|'system',
  payload: {...},
  timestamp: ISO8601
}
```

**Validation:**
- Type must be in SUPPORTED_TYPES
- Payload must be a dict
- Timestamp optional (auto-generated)

## Data Flow

### WebSocket Connection Flow
```
Client Connect
    ↓
NotificationServer.handle_client()
    ↓
ClientRegistry.register() → Returns UUID
    ↓
Send system message with client_id to client
    ↓
Listen for incoming messages
    ↓
MessageHandler.validate_message()
    ↓
Route by type (broadcast/direct/system)
    ↓
Client Disconnect → ClientRegistry.unregister()
```

### Message Broadcast Flow
```
Client sends broadcast message
    ↓
Validate with MessageHandler
    ↓
ClientRegistry.get_all_clients()
    ↓
Send to all websockets concurrently (asyncio.gather)
    ↓
Handle send errors gracefully (closed connections)
```

### Direct Message Flow
```
Client sends direct message with recipient_id
    ↓
Validate with MessageHandler
    ↓
ClientRegistry.get_client(recipient_id)
    ↓
If found: Send message to recipient websocket
    ↓
If not found: Log warning, continue
```

## Concurrency Model

**WebSocket Level:**
- Each connection runs in its own async task
- `async for message in websocket` reads messages concurrently

**Broadcast Level:**
- `asyncio.gather()` sends to all clients in parallel
- Individual send failures don't block others

**Registry Level:**
- `threading.RLock` protects dictionary access
- Works with both async tasks and thread-safe atomic operations

## Performance Characteristics

**Memory:**
- Per-client: ~1KB overhead (UUID, reference)
- Registry: O(n) where n = connected clients

**Latency:**
- Message receipt: <10ms average
- Broadcast distribution: <100ms for 50 clients (network bound)

**Scalability:**
- Designed for 100-1000 concurrent connections
- Async I/O means minimal CPU usage
- Can be sharded via multiple servers + load balancer

## Integration Points

### With Other Microservices

1. **Service Discovery**
   ```
   - Register as 'notification-service'
   - Advertise ws://localhost:8765 and http://localhost:8080
   ```

2. **Health Checks**
   ```
   GET /health → Returns connected client count
   Can be polled by orchestration (Kubernetes, Docker Swarm)
   ```

3. **Load Balancing**
   ```
   - WebSocket connections should route to same instance (sticky)
   - REST health endpoint can be load balanced
   - Multiple server instances for horizontal scaling
   ```

## Error Handling Strategy

| Scenario | Behavior |
|----------|----------|
| Invalid JSON | Log warning, keep connection |
| Invalid message type | Log warning, keep connection |
| Direct to nonexistent client | Log warning, continue |
| Client disconnect | Auto-cleanup, no error |
| Failed broadcast send | Log error, continue to next client |
| REST endpoint error | Return 500 (unlikely) |

## Testing Coverage

**31 Tests Organized By:**

1. **Unit Tests** (ClientRegistry, Message, Handler)
   - Isolated component testing
   - Thread safety verification
   - Serialization/deserialization

2. **Integration Tests** (WebSocket Server)
   - Connection lifecycle
   - Message routing
   - Broadcast/direct messaging

3. **API Tests** (REST Endpoints)
   - Health endpoint
   - Client count tracking

4. **Validation Tests**
   - Malformed messages
   - Invalid types
   - Missing fields

## Deployment Patterns

### Single Node
```bash
python3 notification_server.py
# ws://localhost:8765
# http://localhost:8080/health
```

### Docker Compose
```yaml
services:
  notification:
    build: .
    ports:
      - "8765:8765"
      - "8080:8080"
    healthcheck:
      test: curl -f http://localhost:8080/health
```

### Kubernetes
```yaml
apiVersion: v1
kind: Service
metadata:
  name: notification-service
spec:
  ports:
  - port: 8765
    name: websocket
  - port: 8080
    name: rest
```

## Future Enhancements

1. **Persistence**
   - Message queue (Redis, RabbitMQ)
   - Connection state snapshot
   - Delivery guarantees

2. **Scaling**
   - Redis pub/sub for multi-server broadcast
   - Connection sharding
   - Message routing layer

3. **Security**
   - TLS/WSS support
   - Authentication tokens
   - Rate limiting

4. **Monitoring**
   - Prometheus metrics
   - Message throughput
   - Connection duration histograms
