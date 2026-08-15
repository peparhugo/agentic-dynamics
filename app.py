"""
Task management API — SOAP web service (Flask + SQLite).

The service exposes a single SOAP endpoint at ``/tasks``. Operations are
dispatched from the SOAP body's root element (with the ``SOAPAction`` header
ignored — the body is authoritative):

    CreateTask(title)          -> task
    ListTasks()                -> task[]
    GetTask(id)                -> task
    UpdateTask(id, title?, status?) -> task

Error handling returns SOAP Faults with the appropriate HTTP status codes.
"""

from datetime import datetime
import os
import sqlite3
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from flask import Flask, Response, request

SOAP_11 = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_12 = "http://www.w3.org/2003/05/soap-envelope"
SERVICE_NS = "urn:tasks"

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")


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

def create_task(title: str) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, 'pending', ?)",
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


def get_task(task_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def update_task(task_id: int, title=None, status=None):
    task = get_task(task_id)
    if task is None:
        return None
    with get_db() as conn:
        updates, params = [], []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
    return get_task(task_id)


# ── SOAP helpers ───────────────────────────────────────────────

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_child(elem, name: str):
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


def _child_text(elem, name: str):
    c = _find_child(elem, name)
    return (c.text or "").strip() if c is not None else None


def _task_xml(tag: str, task: dict) -> str:
    return (
        f'<{tag} xmlns="{SERVICE_NS}">'
        f"<id>{task['id']}</id>"
        f"<title>{escape(str(task['title']))}</title>"
        f"<status>{escape(str(task['status']))}</status>"
        f"<created_at>{escape(str(task['created_at']))}</created_at>"
        f"</{tag}>"
    )


def _envelope(soap_ns: str, body_xml: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<soap:Envelope xmlns:soap="{soap_ns}">'
        f"<soap:Body>{body_xml}</soap:Body>"
        "</soap:Envelope>"
    ).encode("utf-8")


def _soap_response(soap_ns: str, body_xml: str, status: int = 200):
    return Response(
        _envelope(soap_ns, body_xml),
        status=status,
        content_type="text/xml; charset=utf-8",
    )


def _fault_response(soap_ns: str, message: str, status: int):
    body = (
        "<soap:Fault>"
        "<faultcode>soap:Client</faultcode>"
        f"<faultstring>{escape(message)}</faultstring>"
        "</soap:Fault>"
    )
    return _soap_response(soap_ns, body, status)


def _parse_id(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ── SOAP handlers ──────────────────────────────────────────────

def _handle_create(soap_ns, op_elem):
    title = _child_text(op_elem, "title")
    if not title:
        return _fault_response(soap_ns, "title is required", 400)
    return _soap_response(soap_ns, _task_xml("CreateTaskResponse", create_task(title)))


def _handle_list(soap_ns, op_elem):
    items = "".join(_task_xml("task", t) for t in get_tasks())
    return _soap_response(
        soap_ns, f'<ListTasksResponse xmlns="{SERVICE_NS}">{items}</ListTasksResponse>'
    )


def _handle_get(soap_ns, op_elem):
    task_id = _parse_id(_child_text(op_elem, "id"))
    if task_id is None:
        return _fault_response(soap_ns, "invalid or missing id", 400)
    task = get_task(task_id)
    if task is None:
        return _fault_response(soap_ns, "task not found", 404)
    return _soap_response(soap_ns, _task_xml("GetTaskResponse", task))


def _handle_update(soap_ns, op_elem):
    task_id = _parse_id(_child_text(op_elem, "id"))
    if task_id is None:
        return _fault_response(soap_ns, "invalid or missing id", 400)
    title = _child_text(op_elem, "title")
    status = _child_text(op_elem, "status")
    if title == "":
        title = None
    if status == "":
        status = None
    task = update_task(task_id, title=title, status=status)
    if task is None:
        return _fault_response(soap_ns, "task not found", 404)
    return _soap_response(soap_ns, _task_xml("UpdateTaskResponse", task))


# ── Routes ─────────────────────────────────────────────────────

@app.route("/tasks", methods=["POST"])
def soap_handler():
    raw = request.get_data(as_text=True)
    if not raw or not raw.strip():
        return _fault_response(SOAP_11, "empty request body", 400)

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return _fault_response(SOAP_11, f"invalid XML: {exc}", 400)

    soap_ns = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else SOAP_11
    if soap_ns not in (SOAP_11, SOAP_12):
        soap_ns = SOAP_11

    body = _find_child(root, "Body")
    if body is None:
        return _fault_response(soap_ns, "missing SOAP body", 400)

    children = list(body)
    if not children:
        return _fault_response(soap_ns, "missing operation", 400)

    op_elem = children[0]
    op = _local(op_elem.tag)

    handlers = {
        "CreateTask": _handle_create,
        "ListTasks": _handle_list,
        "GetTask": _handle_get,
        "UpdateTask": _handle_update,
    }
    handler = handlers.get(op)
    if handler is None:
        return _fault_response(soap_ns, f"unknown operation: {op}", 400)

    return handler(soap_ns, op_elem)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
