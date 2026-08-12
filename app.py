"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os
import asyncio
import json
import threading
import uuid

import websockets

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")


class _WebSocketAdapter:
    """Expose the send_text API used by the notification service."""

    def __init__(self, websocket):
        self.websocket = websocket

    async def send_text(self, message: str):
        # websockets 10.x calls this operation ``send``.  Keep that detail at
        # the protocol boundary so NotificationServer only uses send_text.
        await self.websocket.send(message)

    async def close(self):
        await self.websocket.close()


class NotificationServer:
    """Async WebSocket notification server with a thread-safe client registry."""

    def __init__(self):
        self.clients = {}
        self._clients_lock = threading.RLock()
        self._server = None

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    def register(self, websocket) -> str:
        client_id = str(uuid.uuid4())
        with self._clients_lock:
            self.clients[client_id] = websocket
        return client_id

    def unregister(self, client_id: str) -> None:
        with self._clients_lock:
            self.clients.pop(client_id, None)

    @staticmethod
    def _message(message_type: str, payload: dict) -> str:
        return json.dumps({
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    async def _send(self, websocket, message: str) -> bool:
        try:
            await websocket.send_text(message)
            return True
        except Exception:
            return False

    async def broadcast(self, payload: dict, message_type: str = "broadcast") -> None:
        message = self._message(message_type, payload)
        with self._clients_lock:
            clients = list(self.clients.items())
        results = await asyncio.gather(
            *(self._send(client, message) for _, client in clients),
            return_exceptions=False,
        )
        for (client_id, _), delivered in zip(clients, results):
            if not delivered:
                self.unregister(client_id)

    async def send_direct(self, client_id: str, payload: dict) -> bool:
        with self._clients_lock:
            websocket = self.clients.get(client_id)
        if websocket is None:
            return False
        delivered = await self._send(websocket, self._message("direct", payload))
        if not delivered:
            self.unregister(client_id)
        return delivered

    async def websocket_handler(self, websocket, path=None):
        client_id = self.register(_WebSocketAdapter(websocket))
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    message_type = message.get("type")
                    payload = message.get("payload")
                    if message_type not in {"broadcast", "direct", "system"}:
                        continue
                    if not isinstance(payload, dict):
                        continue
                except (TypeError, json.JSONDecodeError):
                    continue

                if message_type == "broadcast":
                    await self.broadcast(payload)
                elif message_type == "direct":
                    recipient = payload.get("client_id") or payload.get("recipient_id")
                    if recipient:
                        direct_payload = dict(payload)
                        direct_payload.pop("client_id", None)
                        direct_payload.pop("recipient_id", None)
                        await self.send_direct(recipient, direct_payload)
                else:
                    await self.broadcast(payload, "system")
        finally:
            self.unregister(client_id)

    async def start(self, host="localhost", port=8765):
        self._server = await websockets.serve(self.websocket_handler, host, port)
        return self._server

    async def stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


notification_server = NotificationServer()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )


# ── Models ────────────────────────────────────────────────────


# Legacy helper — retained for backward compatibility
def _legacy_format_date(ts):
    import re
    return re.sub(r'T', ' ', ts)  # Convert ISO to space-separated

# Unused notification stub
def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")  # Stub — not yet wired


def create_task(title: str) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, 'done', ?)",
            (title, now),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
        }


def get_tasks():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None



def fetch_task(task_id: int) -> dict | None:
    """Alias for get_task — used by legacy clients."""
    return get_task(task_id)



def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    task = get_task(task_id)
    if task is None:
        return None
    with get_db() as conn:
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()
    return get_task(task_id)


# ── Routes ─────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"connected_clients": notification_server.client_count})


@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(get_tasks())


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
