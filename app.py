import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4
from xml.etree import ElementTree as ET

import jwt
from flask import Flask, Response, current_app, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import DuplicateRecordError, TaskRepository, UserRepository


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NS = "urn:task-management"
ET.register_namespace("soap", SOAP_NS)
ET.register_namespace("task", TASK_NS)


def rate_limit_key():
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and separator and token.strip():
        try:
            payload = jwt.decode(
                token.strip(),
                current_app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            return f"user:{int(payload['sub'])}"
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            pass
    return f"ip:{get_remote_address()}"


def get_user_repository():
    return UserRepository(current_app.config["DATABASE"])


def get_task_repository():
    return TaskRepository(current_app.config["DATABASE"])


def init_db():
    get_user_repository().initialize()
    get_task_repository().initialize(
        f"__legacy__{uuid4().hex}", generate_password_hash(uuid4().hex)
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

        user = get_user_repository().get_by_id(user_id)
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
    if isinstance(tasks, dict):
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
    task = get_task_repository().create_for_owner(title, created_at, g.user_id)
    return soap_response("CreateTask", task, 201)


def list_tasks():
    tasks = get_task_repository().list_for_owner(g.user_id)
    return soap_response("ListTasks", tasks)


def get_task(operation):
    task_id, error = parse_task_id(operation)
    if error:
        return error
    task = get_task_repository().get_for_owner(task_id, g.user_id)
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


def queue_completion_notification(user_email, task_title):
    try:
        send_notification_email.delay(user_email, task_title)
    except Exception:
        current_app.logger.exception("Could not queue task completion notification")


def update_task(operation):
    task_id, error = parse_task_id(operation)
    if error:
        return error

    title = child_text(operation, "title")
    status = child_text(operation, "status")
    updates = {}
    if title is not None:
        title = title.strip()
        if not title:
            return soap_fault("title cannot be empty", 400)
        updates["title"] = title
    if status is not None:
        status = status.strip()
        if not status:
            return soap_fault("status cannot be empty", 400)
        updates["status"] = status
    if not updates:
        return soap_fault("title or status is required", 400)

    existing, task = get_task_repository().update_for_owner(
        task_id, g.user_id, updates
    )
    if existing is None:
        return soap_fault("task not found", 404)
    if existing["status"] != "completed" and task["status"] == "completed":
        queue_completion_notification(existing["owner_email"], task["title"])
    return soap_response("UpdateTask", task)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.db")),
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-only-secret"),
        JWT_EXPIRATION_SECONDS=3600,
        RATELIMIT_STORAGE_URI=os.environ.get(
            "RATELIMIT_STORAGE_URI", "redis://localhost:6379/2"
        ),
        RATELIMIT_HEADERS_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)
    if app.testing and not (test_config or {}).get("RATELIMIT_STORAGE_URI"):
        app.config["RATELIMIT_STORAGE_URI"] = "memory://"

    Limiter(
        key_func=rate_limit_key,
        app=app,
        default_limits=["100 per minute"],
    )

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
            user = get_user_repository().register(
                username.strip(), generate_password_hash(password)
            )
        except DuplicateRecordError:
            return jsonify(error="username already exists"), 409
        return jsonify(id=user["id"], username=username.strip()), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True)
        username = data.get("username") if isinstance(data, dict) else None
        password = data.get("password") if isinstance(data, dict) else None
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify(error="invalid username or password"), 401

        user = get_user_repository().get_by_username(username.strip())
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

    @app.put("/tasks/<int:task_id>")
    @token_required
    def update_task_rest(task_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="JSON body is required"), 400

        updates = {}
        for field in ("title", "status"):
            if field not in data:
                continue
            value = data[field]
            if not isinstance(value, str) or not value.strip():
                return jsonify(error=f"{field} cannot be empty"), 400
            updates[field] = value.strip()
        if not updates:
            return jsonify(error="title or status is required"), 400

        existing, task = get_task_repository().update_for_owner(
            task_id, g.user_id, updates
        )
        if existing is None:
            return jsonify(error="task not found"), 404

        if existing["status"] != "completed" and task["status"] == "completed":
            queue_completion_notification(existing["owner_email"], task["title"])
        return jsonify({key: task[key] for key in ("id", "title", "status", "created_at")})

    @app.get("/tasks")
    @token_required
    def get_tasks_rest():
        cursor_value = request.args.get("cursor")
        limit_value = request.args.get("limit", "20")
        try:
            cursor = int(cursor_value) if cursor_value is not None else None
            limit = int(limit_value)
            if (cursor is not None and cursor < 1) or limit < 1:
                raise ValueError
        except ValueError:
            return jsonify(error="cursor and limit must be positive integers"), 400

        limit = min(limit, 100)
        page, next_cursor, total = get_task_repository().paginate_for_owner(
            g.user_id, cursor, limit
        )
        data = [
            {key: task[key] for key in ("id", "title", "status", "created_at")}
            for task in page
        ]
        return jsonify(data=data, next_cursor=next_cursor, total=total)

    with app.app_context():
        init_db()
    return app


app = create_app()


if __name__ == "__main__":
    app.run()
