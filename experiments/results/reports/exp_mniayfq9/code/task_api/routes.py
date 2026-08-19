from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import Category, Task, User


api = Blueprint("api", __name__)
VALID_STATUSES = {"pending", "in_progress", "completed"}
VALID_PRIORITIES = {"low", "medium", "high"}


def error(message, status=400):
    return jsonify(error=message), status


def payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def current_user_id():
    return int(get_jwt_identity())


def clean_text(value, field, maximum, required=False):
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters")
    return value


def validate_choice(value, field, choices):
    if value not in choices:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(choices))}")
    return value


def parse_due_date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("due_date must use YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("due_date must use YYYY-MM-DD format") from exc


def get_owned_category(category_id, user_id):
    if category_id is None:
        return None
    if isinstance(category_id, bool) or not isinstance(category_id, int):
        raise ValueError("category_id must be an integer or null")
    category = db.session.get(Category, category_id)
    if not category or category.owner_id != user_id:
        raise ValueError("category not found")
    return category


def get_assignee(assignee_id):
    if assignee_id is None:
        return None
    if isinstance(assignee_id, bool) or not isinstance(assignee_id, int):
        raise ValueError("assignee_id must be an integer or null")
    user = db.session.get(User, assignee_id)
    if not user:
        raise ValueError("assignee not found")
    return user


@api.post("/auth/register")
def register():
    data = payload()
    if data is None:
        return error("A JSON object is required")
    try:
        username = clean_text(data.get("username"), "username", 80, required=True)
        email = clean_text(data.get("email"), "email", 255, required=True).lower()
        password = data.get("password")
        if not isinstance(password, str) or len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("email is invalid")
    except ValueError as exc:
        return error(str(exc))

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error("Username or email is already registered", 409)
    return jsonify(user=user.to_dict()), 201


@api.post("/auth/login")
def login():
    data = payload()
    if data is None:
        return error("A JSON object is required")
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return error("email and password are required")
    user = db.session.scalar(db.select(User).where(User.email == email.strip().lower()))
    if not user or not user.check_password(password):
        return error("Invalid email or password", 401)
    token = create_access_token(identity=str(user.id))
    return jsonify(access_token=token, user=user.to_dict())


@api.get("/users")
@jwt_required()
def list_users():
    users = db.session.scalars(db.select(User).order_by(User.username)).all()
    return jsonify(users=[user.to_dict() for user in users])


@api.post("/categories")
@jwt_required()
def create_category():
    data = payload()
    if data is None:
        return error("A JSON object is required")
    try:
        name = clean_text(data.get("name"), "name", 80, required=True)
    except ValueError as exc:
        return error(str(exc))
    category = Category(name=name, owner_id=current_user_id())
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error("A category with this name already exists", 409)
    return jsonify(category=category.to_dict()), 201


@api.get("/categories")
@jwt_required()
def list_categories():
    categories = db.session.scalars(
        db.select(Category).where(Category.owner_id == current_user_id()).order_by(Category.name)
    ).all()
    return jsonify(categories=[category.to_dict() for category in categories])


@api.patch("/categories/<int:category_id>")
@jwt_required()
def update_category(category_id):
    category = db.session.get(Category, category_id)
    if not category or category.owner_id != current_user_id():
        return error("Category not found", 404)
    data = payload()
    if data is None:
        return error("A JSON object is required")
    try:
        category.name = clean_text(data.get("name"), "name", 80, required=True)
    except ValueError as exc:
        return error(str(exc))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error("A category with this name already exists", 409)
    return jsonify(category=category.to_dict())


@api.delete("/categories/<int:category_id>")
@jwt_required()
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if not category or category.owner_id != current_user_id():
        return error("Category not found", 404)
    for task in category.tasks:
        task.category = None
    db.session.delete(category)
    db.session.commit()
    return "", 204


@api.post("/tasks")
@jwt_required()
def create_task():
    data = payload()
    if data is None:
        return error("A JSON object is required")
    user_id = current_user_id()
    try:
        title = clean_text(data.get("title"), "title", 200, required=True)
        description = clean_text(data.get("description", ""), "description", 10000) or ""
        status = validate_choice(data.get("status", "pending"), "status", VALID_STATUSES)
        priority = validate_choice(data.get("priority", "medium"), "priority", VALID_PRIORITIES)
        due_date = parse_due_date(data.get("due_date"))
        category = get_owned_category(data.get("category_id"), user_id)
        assignee = get_assignee(data.get("assignee_id"))
    except ValueError as exc:
        return error(str(exc))

    task = Task(
        title=title,
        description=description,
        status=status,
        priority=priority,
        due_date=due_date,
        creator_id=user_id,
        category=category,
        assignee=assignee,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task=task.to_dict()), 201


def visible_task(task_id, user_id):
    task = db.session.get(Task, task_id)
    if not task or user_id not in (task.creator_id, task.assignee_id):
        return None
    return task


@api.get("/tasks/<int:task_id>")
@jwt_required()
def get_task(task_id):
    task = visible_task(task_id, current_user_id())
    if not task:
        return error("Task not found", 404)
    return jsonify(task=task.to_dict())


def positive_int_arg(name, default, maximum=None):
    raw = request.args.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1 or (maximum and value > maximum):
        suffix = f" between 1 and {maximum}" if maximum else " a positive integer"
        raise ValueError(f"{name} must be{suffix}")
    return value


@api.get("/tasks")
@jwt_required()
def list_tasks():
    user_id = current_user_id()
    try:
        page = positive_int_arg("page", 1)
        per_page = positive_int_arg("per_page", 20, 100)
        status = request.args.get("status")
        priority = request.args.get("priority")
        if status:
            validate_choice(status, "status", VALID_STATUSES)
        if priority:
            validate_choice(priority, "priority", VALID_PRIORITIES)
        category_id = request.args.get("category_id")
        if category_id is not None:
            category_id = int(category_id)
            if category_id < 1:
                raise ValueError
    except (ValueError, TypeError) as exc:
        message = str(exc) or "category_id must be a positive integer"
        return error(message)

    query = db.select(Task).where(or_(Task.creator_id == user_id, Task.assignee_id == user_id))
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if category_id is not None:
        query = query.where(Task.category_id == category_id)
    search = request.args.get("search", "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    query = query.order_by(Task.created_at.desc(), Task.id.desc())
    result = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return jsonify(
        tasks=[task.to_dict() for task in result.items],
        pagination={
            "page": result.page,
            "per_page": result.per_page,
            "total": result.total,
            "pages": result.pages,
            "has_next": result.has_next,
            "has_prev": result.has_prev,
        },
    )


@api.patch("/tasks/<int:task_id>")
@jwt_required()
def update_task(task_id):
    user_id = current_user_id()
    task = visible_task(task_id, user_id)
    if not task:
        return error("Task not found", 404)
    data = payload()
    if data is None:
        return error("A JSON object is required")
    if task.creator_id != user_id and set(data) - {"status"}:
        return error("Assignees may only update task status", 403)
    allowed = {"title", "description", "status", "priority", "due_date", "category_id", "assignee_id"}
    unknown = set(data) - allowed
    if unknown:
        return error(f"Unknown fields: {', '.join(sorted(unknown))}")
    try:
        if "title" in data:
            task.title = clean_text(data["title"], "title", 200, required=True)
        if "description" in data:
            task.description = clean_text(data["description"], "description", 10000) or ""
        if "status" in data:
            task.status = validate_choice(data["status"], "status", VALID_STATUSES)
        if "priority" in data:
            task.priority = validate_choice(data["priority"], "priority", VALID_PRIORITIES)
        if "due_date" in data:
            task.due_date = parse_due_date(data["due_date"])
        if "category_id" in data:
            task.category = get_owned_category(data["category_id"], task.creator_id)
        if "assignee_id" in data:
            task.assignee = get_assignee(data["assignee_id"])
    except ValueError as exc:
        return error(str(exc))
    db.session.commit()
    return jsonify(task=task.to_dict())


@api.delete("/tasks/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    task = visible_task(task_id, current_user_id())
    if not task:
        return error("Task not found", 404)
    if task.creator_id != current_user_id():
        return error("Only the task creator may delete this task", 403)
    db.session.delete(task)
    db.session.commit()
    return "", 204
