# WebSocket Notification Server

An asyncio notification server using `websockets`, with a WebSocket endpoint and
an HTTP `GET /health` endpoint on the same port. Current client state is stored in
`clients.json`; all accepted messages and connection events are appended to
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
