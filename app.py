"""Flask API for authenticated task management."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import hmac
import json
import os
import sqlite3
from xml.etree import ElementTree as ET

from flask import Flask, Response, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NS = "urn:task-service"
DATABASE = os.environ.get("DATABASE", "tasks.db")

ET.register_namespace("soap", SOAP_ENV)
ET.register_namespace("tns", TASK_NS)

app = Flask(__name__)
app.config.update(
    JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-secret-change-me"),
    JWT_EXPIRES_SECONDS=3600,
)


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    """Create the schema and migrate databases made by earlier versions."""
    with get_db() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "username TEXT NOT NULL UNIQUE, "
            "password_hash TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending', "
            "created_at TEXT NOT NULL, "
            "owner_id INTEGER REFERENCES users(id))"
        )
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        if "owner_id" not in columns:
            # Nullable ownership preserves legacy rows without exposing them to users.
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
        )


def _b64encode(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64encode(
        json.dumps(
            {
                "sub": str(user_id),
                "iat": int(now.timestamp()),
                "exp": int(
                    (now + timedelta(seconds=app.config["JWT_EXPIRES_SECONDS"])).timestamp()
                ),
            }
        ).encode()
    )
    unsigned = f"{header}.{payload}"
    signature = hmac.new(
        app.config["JWT_SECRET_KEY"].encode(), unsigned.encode(), hashlib.sha256
    ).digest()
    return f"{unsigned}.{_b64encode(signature)}"


def decode_token(token: str) -> int | None:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}"
        expected = hmac.new(
            app.config["JWT_SECRET_KEY"].encode(), unsigned.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            return None
        header_data = json.loads(_b64decode(header))
        payload_data = json.loads(_b64decode(payload))
        if header_data.get("alg") != "HS256":
            return None
        if payload_data["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        return int(payload_data["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _unauthorized():
    if request.path == "/soap":
        return _fault("authentication required", 401)
    return jsonify(error="authentication required"), 401


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = decode_token(token) if scheme.lower() == "bearer" and token else None
        if user_id is None:
            return _unauthorized()
        with get_db() as connection:
            user = connection.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if user is None:
            return _unauthorized()
        g.user = dict(user)
        return view(*args, **kwargs)

    return wrapped


def create_task(title: str, owner_id: int) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) "
            "VALUES (?, 'pending', ?, ?)",
            (title, created_at, owner_id),
        )
        task_id = cursor.lastrowid
    return {
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": created_at,
        "owner_id": owner_id,
    }


def get_tasks(owner_id: int) -> list[dict]:
    with get_db() as connection:
        rows = connection.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
    return dict(row) if row else None


def update_task(
    task_id: int,
    owner_id: int,
    title: str | None = None,
    status: str | None = None,
) -> dict | None:
    if get_task(task_id, owner_id) is None:
        return None

    updates = []
    values = []
    if title is not None:
        updates.append("title = ?")
        values.append(title)
    if status is not None:
        updates.append("status = ?")
        values.append(status)
    if updates:
        with get_db() as connection:
            connection.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                (*values, task_id, owner_id),
            )
    return get_task(task_id, owner_id)


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return jsonify(error="username is required"), 400
    if not isinstance(password, str) or not password:
        return jsonify(error="password is required"), 400
    username = username.strip()
    try:
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify(error="username already exists"), 409
    return jsonify(id=user_id, username=username), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="invalid username or password"), 401
    with get_db() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="invalid username or password"), 401
    return jsonify(token=create_token(user["id"]))


@app.route("/tasks", methods=["GET", "POST"])
@require_auth
def tasks_collection():
    if request.method == "GET":
        return jsonify(get_tasks(g.user["id"]))
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="title is required"), 400
    return jsonify(create_task(title.strip(), g.user["id"])), 201


@app.route("/tasks/<int:task_id>", methods=["GET", "PATCH", "PUT"])
@require_auth
def task_item(task_id: int):
    if request.method == "GET":
        task = get_task(task_id, g.user["id"])
    else:
        data = request.get_json(silent=True) or {}
        task = update_task(
            task_id, g.user["id"], title=data.get("title"), status=data.get("status")
        )
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


def _name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _name(child) == name:
            return child.text
    return None


def _task_element(parent: ET.Element, task: dict) -> None:
    node = ET.SubElement(parent, f"{{{TASK_NS}}}task")
    for field in ("id", "title", "status", "created_at"):
        ET.SubElement(node, f"{{{TASK_NS}}}{field}").text = str(task[field])


def _response(operation: str, tasks: list[dict] | dict, status: int = 200) -> Response:
    envelope = ET.Element(f"{{{SOAP_ENV}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_ENV}}}Body")
    result = ET.SubElement(body, f"{{{TASK_NS}}}{operation}Response")
    if isinstance(tasks, list):
        for task in tasks:
            _task_element(result, task)
    else:
        _task_element(result, tasks)
    return Response(
        ET.tostring(envelope, encoding="utf-8", xml_declaration=True),
        status=status,
        content_type="text/xml; charset=utf-8",
    )


def _fault(message: str, status: int) -> Response:
    envelope = ET.Element(f"{{{SOAP_ENV}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_ENV}}}Body")
    fault = ET.SubElement(body, f"{{{SOAP_ENV}}}Fault")
    ET.SubElement(fault, "faultcode").text = "soap:Client"
    ET.SubElement(fault, "faultstring").text = message
    detail = ET.SubElement(fault, "detail")
    ET.SubElement(detail, f"{{{TASK_NS}}}error").text = message
    return Response(
        ET.tostring(envelope, encoding="utf-8", xml_declaration=True),
        status=status,
        content_type="text/xml; charset=utf-8",
    )


def _required_id(operation: ET.Element) -> int | Response:
    value = _child_text(operation, "id")
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _fault("id must be an integer", 400)


@app.route("/soap", methods=["POST"])
@require_auth
def soap_service():
    try:
        envelope = ET.fromstring(request.get_data())
    except ET.ParseError:
        return _fault("invalid SOAP XML", 400)

    body = envelope.find(f"{{{SOAP_ENV}}}Body")
    if body is None or len(body) != 1:
        return _fault("SOAP body must contain one operation", 400)
    operation = body[0]
    operation_name = _name(operation)

    if operation_name == "CreateTask":
        title = (_child_text(operation, "title") or "").strip()
        if not title:
            return _fault("title is required", 400)
        return _response(operation_name, create_task(title, g.user["id"]), 201)

    if operation_name == "ListTasks":
        return _response(operation_name, get_tasks(g.user["id"]))

    if operation_name in {"GetTask", "UpdateTask"}:
        task_id = _required_id(operation)
        if isinstance(task_id, Response):
            return task_id

        if operation_name == "GetTask":
            task = get_task(task_id, g.user["id"])
        else:
            task = update_task(
                task_id,
                g.user["id"],
                title=_child_text(operation, "title"),
                status=_child_text(operation, "status"),
            )
        if task is None:
            return _fault("task not found", 404)
        return _response(operation_name, task)

    return _fault("unknown operation", 400)


@app.route("/soap", methods=["GET"])
def wsdl():
    if "wsdl" not in request.args:
        return _fault("send SOAP requests using POST", 405)
    location = request.url_root.rstrip("/") + "/soap"
    document = f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
 xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
 xmlns:tns="{TASK_NS}" targetNamespace="{TASK_NS}">
 <service name="TaskService"><port name="TaskServicePort" binding="tns:TaskServiceBinding">
  <soap:address location="{location}"/>
 </port></service>
</definitions>"""
    return Response(document, content_type="text/xml; charset=utf-8")


init_db()


if __name__ == "__main__":
    app.run(debug=True)
