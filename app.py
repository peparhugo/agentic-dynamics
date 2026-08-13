import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4
from xml.etree import ElementTree as ET

import jwt
from flask import Flask, Response, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NS = "urn:task-management"
ET.register_namespace("soap", SOAP_NS)
ET.register_namespace("task", TASK_NS)


def get_db():
    connection = sqlite3.connect(current_app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER NOT NULL REFERENCES users(id)
            )
            """
        )
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        if "owner_id" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )
            legacy_username = f"__legacy__{uuid4().hex}"
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (legacy_username, generate_password_hash(uuid4().hex)),
            )
            connection.execute(
                "UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL",
                (cursor.lastrowid,),
            )


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token.strip():
            return jsonify(error="valid bearer token required"), 401

        try:
            payload = jwt.decode(
                token.strip(),
                current_app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return jsonify(error="valid bearer token required"), 401

        with get_db() as connection:
            user = connection.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if user is None:
            return jsonify(error="valid bearer token required"), 401

        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def local_name(element):
    return element.tag.rsplit("}", 1)[-1]


def child_text(element, name):
    for child in element:
        if local_name(child) == name:
            return child.text or ""
    return None


def add_task(parent, task):
    task_element = ET.SubElement(parent, f"{{{TASK_NS}}}task")
    for field in ("id", "title", "status", "created_at"):
        ET.SubElement(task_element, f"{{{TASK_NS}}}{field}").text = str(task[field])


def soap_response(operation, tasks, status=200):
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    result = ET.SubElement(body, f"{{{TASK_NS}}}{operation}Response")
    if isinstance(tasks, sqlite3.Row):
        add_task(result, tasks)
    else:
        for task in tasks:
            add_task(result, task)
    return Response(
        ET.tostring(envelope, encoding="utf-8", xml_declaration=True),
        status=status,
        content_type="text/xml; charset=utf-8",
    )


def soap_fault(message, status):
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    fault = ET.SubElement(body, f"{{{SOAP_NS}}}Fault")
    ET.SubElement(fault, "faultcode").text = "soap:Client"
    ET.SubElement(fault, "faultstring").text = message
    return Response(
        ET.tostring(envelope, encoding="utf-8", xml_declaration=True),
        status=status,
        content_type="text/xml; charset=utf-8",
    )


def parse_operation():
    try:
        envelope = ET.fromstring(request.data)
    except ET.ParseError:
        return None, soap_fault("invalid SOAP XML", 400)

    body = envelope.find(f"{{{SOAP_NS}}}Body")
    if body is None or len(body) != 1:
        return None, soap_fault("SOAP body must contain one operation", 400)
    return body[0], None


def create_task(operation):
    title = (child_text(operation, "title") or "").strip()
    if not title:
        return soap_fault("title is required", 400)

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            """INSERT INTO tasks (title, status, created_at, owner_id)
               VALUES (?, 'pending', ?, ?)""",
            (title, created_at, g.user_id),
        )
        task = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (cursor.lastrowid, g.user_id),
        ).fetchone()
    return soap_response("CreateTask", task, 201)


def list_tasks():
    with get_db() as connection:
        tasks = connection.execute(
            """SELECT * FROM tasks WHERE owner_id = ?
               ORDER BY created_at DESC, id DESC""",
            (g.user_id,),
        ).fetchall()
    return soap_response("ListTasks", tasks)


def get_task(operation):
    task_id, error = parse_task_id(operation)
    if error:
        return error
    with get_db() as connection:
        task = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
    if task is None:
        return soap_fault("task not found", 404)
    return soap_response("GetTask", task)


def parse_task_id(operation):
    try:
        task_id = int(child_text(operation, "id"))
        if task_id < 1:
            raise ValueError
    except (TypeError, ValueError):
        return None, soap_fault("valid task id is required", 400)
    return task_id, None


def update_task(operation):
    task_id, error = parse_task_id(operation)
    if error:
        return error

    title = child_text(operation, "title")
    status = child_text(operation, "status")
    updates = []
    values = []
    if title is not None:
        title = title.strip()
        if not title:
            return soap_fault("title cannot be empty", 400)
        updates.append("title = ?")
        values.append(title)
    if status is not None:
        status = status.strip()
        if not status:
            return soap_fault("status cannot be empty", 400)
        updates.append("status = ?")
        values.append(status)
    if not updates:
        return soap_fault("title or status is required", 400)

    with get_db() as connection:
        existing = connection.execute(
            "SELECT id FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
        if existing is None:
            return soap_fault("task not found", 404)
        values.extend((task_id, g.user_id))
        connection.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
            values,
        )
        task = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
    return soap_response("UpdateTask", task)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.db")),
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-only-secret"),
        JWT_EXPIRATION_SECONDS=3600,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True)
        username = data.get("username") if isinstance(data, dict) else None
        password = data.get("password") if isinstance(data, dict) else None
        if not isinstance(username, str) or not username.strip():
            return jsonify(error="username is required"), 400
        if not isinstance(password, str) or not password:
            return jsonify(error="password is required"), 400

        try:
            with get_db() as connection:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username.strip(), generate_password_hash(password)),
                )
        except sqlite3.IntegrityError:
            return jsonify(error="username already exists"), 409
        return jsonify(id=cursor.lastrowid, username=username.strip()), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True)
        username = data.get("username") if isinstance(data, dict) else None
        password = data.get("password") if isinstance(data, dict) else None
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify(error="invalid username or password"), 401

        with get_db() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username.strip(),)
            ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify(error="invalid username or password"), 401

        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user["id"]),
                "iat": now,
                "exp": now + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"]),
            },
            app.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        return jsonify(token=token)

    @app.post("/soap")
    @token_required
    def soap_endpoint():
        operation, error = parse_operation()
        if error:
            return error
        handlers = {
            "CreateTask": create_task,
            "ListTasks": lambda _operation: list_tasks(),
            "GetTask": get_task,
            "UpdateTask": update_task,
        }
        handler = handlers.get(local_name(operation))
        if handler is None:
            return soap_fault("unknown operation", 400)
        return handler(operation)

    with app.app_context():
        init_db()
    return app


app = create_app()


if __name__ == "__main__":
    app.run()
