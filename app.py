"""Flask-based SOAP service for task management."""

from datetime import datetime, timezone
import os
import sqlite3
from xml.etree import ElementTree as ET

from flask import Flask, Response, request


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NS = "urn:task-service"
DATABASE = os.environ.get("DATABASE", "tasks.db")

ET.register_namespace("soap", SOAP_ENV)
ET.register_namespace("tns", TASK_NS)

app = Flask(__name__)


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending', "
            "created_at TEXT NOT NULL)"
        )


def create_task(title: str) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, 'pending', ?)",
            (title, created_at),
        )
        task_id = cursor.lastrowid
    return {
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": created_at,
    }


def get_tasks() -> list[dict]:
    with get_db() as connection:
        rows = connection.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_task(task_id: int) -> dict | None:
    with get_db() as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return dict(row) if row else None


def update_task(
    task_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    if get_task(task_id) is None:
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
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                (*values, task_id),
            )
    return get_task(task_id)


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
        return _response(operation_name, create_task(title), 201)

    if operation_name == "ListTasks":
        return _response(operation_name, get_tasks())

    if operation_name in {"GetTask", "UpdateTask"}:
        task_id = _required_id(operation)
        if isinstance(task_id, Response):
            return task_id

        if operation_name == "GetTask":
            task = get_task(task_id)
        else:
            title_node = _child_text(operation, "title")
            status_node = _child_text(operation, "status")
            task = update_task(task_id, title=title_node, status=status_node)
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
