# WebSocket Notification Server

An asyncio notification server using `websockets`, with a WebSocket endpoint and
HTTP status endpoints on the same port. Current client state is stored in
`clients.json`; delivered messages and connection events are appended to
`messages.jsonl`.

```bash
python -m pip install -r requirements.txt
python app.py --host 127.0.0.1 --port 8765 --data-dir data
```

Connect to `ws://127.0.0.1:8765`. Messages use this shape:

```json
{"type":"broadcast","payload":{"text":"hello"},"timestamp":"ignored for input"}
```

The server generates authoritative UTC timestamps. `broadcast` and `system`
messages go to every client. A `direct` payload must include the target client's
`client_id`:

```json
{"type":"direct","payload":{"client_id":"...","text":"private"}}
```

Clients can dynamically subscribe to multiple named channels. Subscription
control messages are silent:

```json
{"type":"subscribe","channel":"alerts"}
{"type":"unsubscribe","channel":"alerts"}
```

Adding a top-level `channel` to a `broadcast` or `system` message delivers it
only to subscribers. A channeled `direct` message is delivered only when its
target subscribes to that channel. Messages without a channel retain their
original broadcast or direct behavior.

`GET /health` reports the connected client count. `GET /channels` lists active
channels and subscriber counts, while `GET /channels/{name}/subscribers` lists
the subscriber IDs for a channel.
