"""HTTP API routes for the task management service."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from . import models

bp = Blueprint("api", __name__, url_prefix="/api")


def _error(message: str, status: int):
    response = jsonify({"error": message})
    response.status_code = status
    return response


@bp.get("/tasks")
def list_tasks():
    status = request.args.get("status")
    priority = request.args.get("priority")
    sort = request.args.get("sort", "id")
    order = request.args.get("order", "asc")

    try:
        tasks = models.list_tasks(
            status=status, priority=priority, sort=sort, order=order
        )
    except ValueError as exc:
        return _error(str(exc), 400)

    return jsonify(tasks)


@bp.post("/tasks")
def create_task():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("request body must be a JSON object", 400)

    try:
        task = models.create_task(data)
    except ValueError as exc:
        return _error(str(exc), 400)

    return jsonify(task), 201


@bp.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    task = models.get_task(task_id)
    if task is None:
        return _error("task not found", 404)
    return jsonify(task)


@bp.put("/tasks/<int:task_id>")
def update_task(task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("request body must be a JSON object", 400)

    try:
        task = models.update_task(task_id, data)
    except ValueError as exc:
        return _error(str(exc), 400)

    if task is None:
        return _error("task not found", 404)
    return jsonify(task)


@bp.patch("/tasks/<int:task_id>")
def patch_task(task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("request body must be a JSON object", 400)

    try:
        task = models.update_task(task_id, data)
    except ValueError as exc:
        return _error(str(exc), 400)

    if task is None:
        return _error("task not found", 404)
    return jsonify(task)


@bp.delete("/tasks/<int:task_id>")
def delete_task(task_id: int):
    if not models.delete_task(task_id):
        return _error("task not found", 404)
    return "", 204


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})
