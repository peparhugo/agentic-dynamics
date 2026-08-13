"""SOAP task-management API backed by SQLite."""

from datetime import datetime, timezone
import os
import sqlite3
from xml.etree import ElementTree as ET

from flask import Flask, Response, request


SOAP_NAMESPACE = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NAMESPACE = "urn:tasks"
DATABASE = os.environ.get("DATABASE", "tasks.db")

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the task table before the service accepts requests."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )


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
    return Response(
        ET.tostring(envelope, encoding="utf-8", xml_declaration=True),
        status=status,
        content_type="text/xml; charset=utf-8",
    )


def soap_fault(message, status):
    envelope = ET.Element(f"{{{SOAP_NAMESPACE}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NAMESPACE}}}Body")
    fault = ET.SubElement(body, f"{{{SOAP_NAMESPACE}}}Fault")
    ET.SubElement(fault, "faultcode").text = "Client" if status == 400 else "Server"
    ET.SubElement(fault, "faultstring").text = message
    detail = ET.SubElement(fault, "detail")
    ET.SubElement(detail, "error").text = message
    return Response(
        ET.tostring(envelope, encoding="utf-8", xml_declaration=True),
        status=status,
        content_type="text/xml; charset=utf-8",
    )


def create_task(operation):
    title = child_text(operation, "title")
    if not title:
        return soap_fault("title is required", 400)
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
            (title, created_at),
        )
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return soap_response("CreateTask", lambda response: task_element(response, task), 201)


def list_tasks(_operation):
    with get_db() as conn:
        tasks = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    return soap_response("ListTasks", lambda response: [task_element(response, task) for task in tasks])


def task_id(operation):
    value = child_text(operation, "id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_task(operation):
    identifier = task_id(operation)
    if identifier is None:
        return soap_fault("valid task id is required", 400)
    with get_db() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (identifier,)).fetchone()
    if task is None:
        return soap_fault("task not found", 404)
    return soap_response("GetTask", lambda response: task_element(response, task))


def update_task(operation):
    identifier = task_id(operation)
    if identifier is None:
        return soap_fault("valid task id is required", 400)
    title = child_text(operation, "title")
    status = child_text(operation, "status")
    if title is None and status is None:
        return soap_fault("title or status is required", 400)
    if title == "":
        return soap_fault("title is required", 400)
    with get_db() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (identifier,)).fetchone()
        if task is None:
            return soap_fault("task not found", 404)
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title if title is not None else task["title"], status if status is not None else task["status"], identifier),
        )
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (identifier,)).fetchone()
    return soap_response("UpdateTask", lambda response: task_element(response, task))


OPERATIONS = {
    "CreateTask": create_task,
    "ListTasks": list_tasks,
    "GetTask": get_task,
    "UpdateTask": update_task,
}


@app.post("/soap")
def soap():
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
    return handler(operation)


init_db()


if __name__ == "__main__":
    app.run()
