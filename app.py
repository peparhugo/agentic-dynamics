"""SOAP task-management API backed by SQLite."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from functools import wraps
from xml.etree import ElementTree as ET

from flask import Flask, Response, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


SOAP_NAMESPACE = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NAMESPACE = "urn:tasks"
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create current tables and safely upgrade databases from the task-only schema."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER REFERENCES users(id)
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")


def encode_jwt(user_id):
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {"sub": user_id, "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp())},
            separators=(",", ":"),
        ).encode()
    ).rstrip(b"=")
    signed = header + b"." + payload
    signature = base64.urlsafe_b64encode(hmac.new(JWT_SECRET.encode(), signed, hashlib.sha256).digest()).rstrip(b"=")
    return (signed + b"." + signature).decode()


def decode_jwt(token):
    try:
        header, payload, signature = token.encode().split(b".")
        signed = header + b"." + payload
        expected = base64.urlsafe_b64encode(hmac.new(JWT_SECRET.encode(), signed, hashlib.sha256).digest()).rstrip(b"=")
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + b"=" * (-len(payload) % 4)))
        user_id = claims.get("sub")
        if not isinstance(user_id, int) or claims.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return user_id
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def require_auth(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = decode_jwt(token) if scheme.lower() == "bearer" and token else None
        if user_id is None:
            return soap_fault("authentication required", 401)
        return handler(*args, owner_id=user_id, **kwargs)

    return wrapped


def local_name(element):
    return element.tag.rsplit("}", 1)[-1]


def child_text(element, name):
    child = next((node for node in element if local_name(node) == name), None)
    return child.text.strip() if child is not None and child.text else None


def task_element(parent, task):
    element = ET.SubElement(parent, "Task")
    for key in ("id", "title", "status", "created_at"):
        ET.SubElement(element, key).text = str(task[key])
    return element


def soap_response(operation, build_body, status=200):
    envelope = ET.Element(f"{{{SOAP_NAMESPACE}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NAMESPACE}}}Body")
    response = ET.SubElement(body, f"{{{TASK_NAMESPACE}}}{operation}Response")
    build_body(response)
    return Response(ET.tostring(envelope, encoding="utf-8", xml_declaration=True), status=status, content_type="text/xml; charset=utf-8")


def soap_fault(message, status):
    envelope = ET.Element(f"{{{SOAP_NAMESPACE}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NAMESPACE}}}Body")
    fault = ET.SubElement(body, f"{{{SOAP_NAMESPACE}}}Fault")
    ET.SubElement(fault, "faultcode").text = "Client" if status in (400, 401) else "Server"
    ET.SubElement(fault, "faultstring").text = message
    detail = ET.SubElement(fault, "detail")
    ET.SubElement(detail, "error").text = message
    return Response(ET.tostring(envelope, encoding="utf-8", xml_declaration=True), status=status, content_type="text/xml; charset=utf-8")


def create_task(operation, owner_id):
    title = child_text(operation, "title")
    if not title:
        return soap_fault("title is required", 400)
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute("INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)", (title, created_at, owner_id))
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return soap_response("CreateTask", lambda response: task_element(response, task), 201)


def list_tasks(_operation, owner_id):
    with get_db() as conn:
        tasks = conn.execute("SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)).fetchall()
    return soap_response("ListTasks", lambda response: [task_element(response, task) for task in tasks])


def task_id(operation):
    try:
        return int(child_text(operation, "id"))
    except (TypeError, ValueError):
        return None


def get_task(operation, owner_id):
    identifier = task_id(operation)
    if identifier is None:
        return soap_fault("valid task id is required", 400)
    with get_db() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (identifier, owner_id)).fetchone()
    if task is None:
        return soap_fault("task not found", 404)
    return soap_response("GetTask", lambda response: task_element(response, task))


def update_task(operation, owner_id):
    identifier = task_id(operation)
    if identifier is None:
        return soap_fault("valid task id is required", 400)
    title, status = child_text(operation, "title"), child_text(operation, "status")
    if title is None and status is None:
        return soap_fault("title or status is required", 400)
    if title == "":
        return soap_fault("title is required", 400)
    with get_db() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (identifier, owner_id)).fetchone()
        if task is None:
            return soap_fault("task not found", 404)
        conn.execute("UPDATE tasks SET title = ?, status = ? WHERE id = ?", (title if title is not None else task["title"], status if status is not None else task["status"], identifier))
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (identifier,)).fetchone()
    return soap_response("UpdateTask", lambda response: task_element(response, task))


OPERATIONS = {"CreateTask": create_task, "ListTasks": list_tasks, "GetTask": get_task, "UpdateTask": update_task}


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify(error="username and password are required"), 400
    try:
        with get_db() as conn:
            cursor = conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username.strip(), generate_password_hash(password)))
        return jsonify(id=cursor.lastrowid, username=username.strip()), 201
    except sqlite3.IntegrityError:
        return jsonify(error="username already exists"), 409


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="username and password are required"), 400
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="invalid credentials"), 401
    return jsonify(token=encode_jwt(user["id"]))


@app.post("/soap")
@require_auth
def soap(owner_id):
    if not request.data:
        return soap_fault("SOAP request body is required", 400)
    try:
        root = ET.fromstring(request.data)
    except ET.ParseError:
        return soap_fault("invalid SOAP XML", 400)
    if local_name(root) != "Envelope":
        return soap_fault("SOAP Envelope is required", 400)
    body = next((node for node in root if local_name(node) == "Body"), None)
    if body is None or len(body) != 1:
        return soap_fault("SOAP Body must contain exactly one operation", 400)
    operation = body[0]
    handler = OPERATIONS.get(local_name(operation))
    if handler is None:
        return soap_fault("unknown SOAP operation", 400)
    return handler(operation, owner_id)


init_db()


if __name__ == "__main__":
    app.run()
