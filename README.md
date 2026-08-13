# Notification Server

An asyncio notification service with WebSocket messaging and a SOAP health API.

## Run

Install `requirements.txt`, then start both listeners:

```bash
python3 app.py --websocket-port 8765 --soap-port 8080
```

Set `REDIS_URL` to the shared Redis broker (default `redis://127.0.0.1:6379/0`)
and `DATABASE_URL` to a SQLite URL or path (default `sqlite:///messages.db`).
Messages are persisted before being published to Redis, and each server instance
subscribes to Redis to deliver messages to its locally connected clients.
Set `RATE_LIMIT` to change the per-client inbound message limit (default 100 per
minute). Redis counters enforce the limit consistently across server instances.
Messages older than `MESSAGE_TTL_DAYS` (default 7) are removed by a background
task started with the server.

WebSocket clients connect to `ws://127.0.0.1:8765`. On connection, each client
receives a `system` message containing its unique `payload.client_id`.

Clients may send `broadcast` messages or `direct` messages. A direct message's
payload must include the destination as `client_id`. All outbound messages have
the shape `{type: str, payload: object, timestamp: str}`, with an additional
`channel` field for channel messages. The server creates the timestamp and adds
`sender_id` to client-originated messages.

Subscribe or unsubscribe by sending a message with type `subscribe` or
`unsubscribe`, an empty payload, and a top-level non-empty `channel` string.
Channel broadcasts are delivered only to current subscribers; broadcasts with
no channel continue to reach every connected client.

## Channel REST API

The HTTP service on port 8080 also provides `GET /channels`, which returns all
active channels and their subscriber counts, and
`GET /channels/{name}/subscribers`, which returns the channel's subscriber IDs.
Connection and subscription state is shared in Redis, so these endpoints include
clients attached to every server instance.

`GET /messages?limit=50&offset=0` returns persisted messages newest first. `limit`
may be between 1 and 1000, and `offset` must be non-negative.

`GET /history?channel=X&since=ISO_TIMESTAMP&limit=50` returns persisted messages
for one channel at or after the timezone-aware timestamp, in chronological order.
The response contains `messages` and a `has_more` pagination flag. `limit` defaults
to 50 and may be between 1 and 1000.

## SOAP health API

Send `POST /health` to port 8080 with a SOAP 1.1 envelope:

```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:ns="urn:notification-server">
  <soap:Body><ns:Health/></soap:Body>
</soap:Envelope>
```

The `HealthResponse` contains `connectedClientCount`. There is no REST health
endpoint.
