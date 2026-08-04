from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.models import db, Task, Category, User
from app.schemas import TaskCreateSchema, TaskUpdateSchema, PaginationSchema
from app.utils import get_current_user, paginate_query, apply_task_filters, parse_date

task_bp = Blueprint("tasks", __name__)


@task_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    current_user = get_current_user()
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "Request body must be JSON."}), 400

    try:
        data = TaskCreateSchema().load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed.", "details": err.messages}), 400

    if data.get("category_id"):
        cat = db.session.get(Category, data["category_id"])
        if not cat:
            return jsonify({"error": "Category not found."}), 404

    if data.get("assigned_to_id"):
        assignee = db.session.get(User, data["assigned_to_id"])
        if not assignee:
            return jsonify({"error": "Assigned user not found."}), 404

    task = Task(
        title=data["title"],
        description=data.get("description"),
        status=data.get("status", Task.STATUS_PENDING),
        priority=data.get("priority", Task.PRIORITY_MEDIUM),
        due_date=parse_date(data.get("due_date")),
        category_id=data.get("category_id"),
        created_by_id=current_user.id,
        assigned_to_id=data.get("assigned_to_id"),
    )
    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@task_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    try:
        params = PaginationSchema().load(request.args)
    except ValidationError as err:
        return jsonify({"error": "Validation failed.", "details": err.messages}), 400

    query = Task.query
    query = apply_task_filters(
        query,
        status=params.get("status"),
        priority=params.get("priority"),
        category_id=params.get("category_id"),
        assigned_to_id=params.get("assigned_to_id"),
        search=params.get("search"),
        sort_by=params.get("sort_by"),
        sort_order=params.get("sort_order"),
    )

    result = paginate_query(query, page=params["page"], per_page=params["per_page"])
    return jsonify(result), 200


@task_bp.route("/<task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404
    return jsonify(task.to_dict()), 200


@task_bp.route("/<task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "Request body must be JSON."}), 400

    try:
        data = TaskUpdateSchema().load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed.", "details": err.messages}), 400

    if data.get("category_id"):
        cat = db.session.get(Category, data["category_id"])
        if not cat:
            return jsonify({"error": "Category not found."}), 404

    if data.get("assigned_to_id"):
        assignee = db.session.get(User, data["assigned_to_id"])
        if not assignee:
            return jsonify({"error": "Assigned user not found."}), 404

    for field in ("title", "description", "status", "priority", "due_date",
                  "category_id", "assigned_to_id"):
        if field in data:
            val = parse_date(data[field]) if field == "due_date" else data[field]
            setattr(task, field, val)

    db.session.commit()
    return jsonify(task.to_dict()), 200


@task_bp.route("/<task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted."}), 200
