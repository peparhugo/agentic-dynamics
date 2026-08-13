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
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import DuplicateUserError, TaskRepository, UserRepository


SOAP_NAMESPACE = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NAMESPACE = "urn:tasks"
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24
RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")

app = Flask(__name__)


def rate_limit_key():
    """Use the authenticated identity when available; auth routes fall back to the client."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    user_id = decode_jwt(token) if scheme.lower() == "bearer" and token else None
    return f"user:{user_id}" if user_id is not None else request.remote_addr


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=RATELIMIT_STORAGE_URI,
    headers_enabled=True,
)


@app.errorhandler(RateLimitExceeded)
def rate_limit_exceeded(error):
    response = jsonify(error="rate limit exceeded")
    response.status_code = 429
    retry_after = error.retry_after
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create current tables and safely upgrade databases from the task-only schema."""
    UserRepository(get_db).initialize()
    TaskRepository(get_db).initialize()


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
    task = TaskRepository(get_db).create_task(title, created_at, owner_id)
    return soap_response("CreateTask", lambda response: task_element(response, task), 201)


def list_tasks(_operation, owner_id):
    tasks = TaskRepository(get_db).list_for_owner(owner_id)
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
    task = TaskRepository(get_db).get_for_owner(identifier, owner_id)
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
    previous_task, task = TaskRepository(get_db).update_for_owner(identifier, owner_id, title, status)
    if previous_task is None:
        return soap_fault("task not found", 404)
    user = UserRepository(get_db).get(owner_id)
    previous_status = previous_task["status"]
    if status == "completed" and previous_status != "completed" and user["email"]:
        send_notification_email.delay(user["email"], task["title"])
    return soap_response("UpdateTask", lambda response: task_element(response, task))


OPERATIONS = {"CreateTask": create_task, "ListTasks": list_tasks, "GetTask": get_task, "UpdateTask": update_task}


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username, password, email = data.get("username"), data.get("password"), data.get("email")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify(error="username and password are required"), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify(error="email must be a non-empty string"), 400
    try:
        user = UserRepository(get_db).create_user(
            username.strip(), email.strip() if email else None, generate_password_hash(password)
        )
        return jsonify(id=user["id"], username=username.strip()), 201
    except DuplicateUserError:
        return jsonify(error="username already exists"), 409


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="username and password are required"), 400
    user = UserRepository(get_db).get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="invalid credentials"), 401
    return jsonify(token=encode_jwt(user["id"]))


@app.get("/tasks")
@require_auth
def get_tasks(owner_id):
    cursor_value = request.args.get("cursor")
    limit_value = request.args.get("limit", "20")
    try:
        cursor = int(cursor_value) if cursor_value is not None else None
        limit = int(limit_value)
    except ValueError:
        return jsonify(error="cursor and limit must be integers"), 400
    if cursor is not None and cursor < 1:
        return jsonify(error="cursor must be a positive integer"), 400
    if limit < 1:
        return jsonify(error="limit must be a positive integer"), 400

    tasks, total = TaskRepository(get_db).list_page_for_owner(owner_id, cursor, min(limit, 100))
    return jsonify(
        data=[dict(task) for task in tasks],
        next_cursor=str(tasks[-1]["id"]) if len(tasks) == min(limit, 100) else None,
        total=total,
    )


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
