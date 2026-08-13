# Notification Server

An asyncio notification service with a WebSocket message channel and a SOAP
health API. The SOAP constraint supersedes the otherwise conflicting REST
health endpoint requirement.

## Run

```bash
python3 app.py --host 127.0.0.1 --websocket-port 8765 --soap-port 8080
```

Clients receive a `system` message containing their `client_id` immediately
after connecting. Every WebSocket message has this exact shape:

```json
{"type":"broadcast","payload":{"text":"hello"},"timestamp":"2026-08-13T12:00:00Z"}
```

Supported types are `broadcast`, `direct`, `subscribe`, `unsubscribe`, and
`system`. A direct message must
include the destination as `payload.client_id`. Clients cannot originate
`system` messages.

Add a top-level `channel` field to `subscribe` and `unsubscribe` messages to
change a connection's subscriptions. A `broadcast` or `direct` message with a
`channel` is delivered only to subscribers of that channel. Messages without a
channel retain their original behavior.

The HTTP port also exposes `GET /channels` and
`GET /channels/{name}/subscribers` as JSON endpoints.

## SOAP Health API

Send `POST /soap` to the SOAP port with a `GetHealth` envelope:

```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:ns="urn:notification-server">
  <soap:Body><ns:GetHealth/></soap:Body>
</soap:Envelope>
```

The response contains `ns:connectedClientCount`.

## Test

```bash
pytest
```
