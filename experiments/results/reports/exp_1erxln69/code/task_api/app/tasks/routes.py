from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.task import Task, task_dependencies, task_tags
from app.models.category import Category
from app.models.user import User
from sqlalchemy import or_

tasks_bp = Blueprint("tasks", __name__)


def _get_user():
    user_id = int(get_jwt_identity())
    return db.session.get(User, user_id)


def _task_or_404(task_id, user):
    task = db.session.get(Task, task_id)
    if not task:
        return None, (jsonify({"error": "Task not found"}), 404)
    if task.creator_id != user.id:
        return None, (jsonify({"error": "Forbidden"}), 403)
    return task, None


def _build_filter_query(user, args):
    query = Task.query

    status = args.get("status")
    if status:
        if status not in Task.VALID_STATUSES:
            return None, (jsonify({"error": f"Invalid status. Must be one of: {sorted(Task.VALID_STATUSES)}"}), 400)
        query = query.filter(Task.status == status)

    priority = args.get("priority")
    if priority:
        if priority not in Task.VALID_PRIORITIES:
            return None, (jsonify({"error": f"Invalid priority. Must be one of: {sorted(Task.VALID_PRIORITIES)}"}), 400)
        query = query.filter(Task.priority == priority)

    category_id = args.get("category_id", type=int)
    if category_id:
        query = query.filter(Task.category_id == category_id)

    assignee_id = args.get("assignee_id", type=int)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)

    creator_id = args.get("creator_id", type=int)
    if creator_id:
        query = query.filter(Task.creator_id == creator_id)

    due_before = args.get("due_before")
    if due_before:
        query = query.filter(Task.due_date <= due_before)

    due_after = args.get("due_after")
    if due_after:
        query = query.filter(Task.due_date >= due_after)

    parent_id = args.get("parent_id")
    if parent_id is not None:
        pid = int(parent_id) if parent_id != "" else None
        query = query.filter(Task.parent_id == pid)

    search = args.get("search")
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Task.title.ilike(pattern),
                Task.description.ilike(pattern),
            )
        )

    tags = args.get("tags")
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            query = query.filter(
                Task.id.in_(
                    db.select(task_tags.c.task_id).where(task_tags.c.tag.in_(tag_list))
                )
            )

    sort_by = args.get("sort_by", "created_at")
    sort_dir = args.get("sort_dir", "desc")
    sort_columns = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "status": Task.status,
        "title": Task.title,
    }
    column = sort_columns.get(sort_by)
    if column is None:
        return None, (jsonify({"error": f"Invalid sort_by. Must be one of: {sorted(sort_columns.keys())}"}), 400)
    if sort_dir not in ("asc", "desc"):
        return None, (jsonify({"error": "sort_dir must be 'asc' or 'desc'"}), 400)
    query = query.order_by(column.asc() if sort_dir == "asc" else column.desc())

    return query, None


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    query, error = _build_filter_query(user, request.args)
    if error:
        return error

    query = query.filter(Task.creator_id == user.id)

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "tasks": [t.to_dict() for t in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }), 200


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    if len(title) > 200:
        return jsonify({"error": "title must be 200 characters or fewer"}), 400

    status = data.get("status", "pending")
    priority = data.get("priority", "medium")
    if status not in Task.VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {sorted(Task.VALID_STATUSES)}"}), 400
    if priority not in Task.VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {sorted(Task.VALID_PRIORITIES)}"}), 400

    category_id = data.get("category_id")
    if category_id:
        cat = db.session.get(Category, category_id)
        if not cat or cat.user_id != user.id:
            return jsonify({"error": "Category not found"}), 404

    assignee_id = data.get("assignee_id")
    if assignee_id:
        if not db.session.get(User, assignee_id):
            return jsonify({"error": "Assignee not found"}), 404

    parent_id = data.get("parent_id")
    if parent_id:
        parent = db.session.get(Task, parent_id)
        if not parent or parent.creator_id != user.id:
            return jsonify({"error": "Parent task not found"}), 404

    due_date = data.get("due_date")
    if due_date:
        from datetime import date
        try:
            due_date = date.fromisoformat(due_date)
        except (ValueError, TypeError):
            return jsonify({"error": "due_date must be in YYYY-MM-DD format"}), 400

    effort_estimate = data.get("effort_estimate")
    if effort_estimate is not None:
        effort_estimate = int(effort_estimate)
        if effort_estimate < 1:
            return jsonify({"error": "effort_estimate must be positive"}), 400

    dependency_ids = data.get("dependency_ids", [])
    tag_list = data.get("tags", [])

    task = Task(
        title=title,
        description=data.get("description", ""),
        status=status,
        priority=priority,
        due_date=due_date,
        effort_estimate=effort_estimate,
        category_id=category_id,
        creator_id=user.id,
        assignee_id=assignee_id or None,
        parent_id=parent_id,
    )
    db.session.add(task)
    db.session.flush()

    for dep_id in dependency_ids:
        dep = db.session.get(Task, dep_id)
        if dep:
            task.dependencies.append(dep)

    for tag in tag_list:
        tag = str(tag).strip().lower()
        if tag and len(tag) <= 50:
            db.session.execute(task_tags.insert().values(task_id=task.id, tag=tag))

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    task, error = _task_or_404(task_id, user)
    if error:
        return error
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    task, error = _task_or_404(task_id, user)
    if error:
        return error

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "title must not be empty"}), 400
        if len(title) > 200:
            return jsonify({"error": "title must be 200 characters or fewer"}), 400
        task.title = title

    if "description" in data:
        task.description = data["description"]

    if "status" in data:
        s = data["status"]
        if s not in Task.VALID_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {sorted(Task.VALID_STATUSES)}"}), 400
        task.status = s

    if "priority" in data:
        p = data["priority"]
        if p not in Task.VALID_PRIORITIES:
            return jsonify({"error": f"Invalid priority. Must be one of: {sorted(Task.VALID_PRIORITIES)}"}), 400
        task.priority = p

    if "category_id" in data:
        cid = data["category_id"]
        if cid is not None:
            cat = db.session.get(Category, cid)
            if not cat or cat.user_id != user.id:
                return jsonify({"error": "Category not found"}), 404
        task.category_id = cid

    if "assignee_id" in data:
        aid = data["assignee_id"]
        if aid is not None and not db.session.get(User, aid):
            return jsonify({"error": "Assignee not found"}), 404
        task.assignee_id = aid

    if "parent_id" in data:
        pid = data["parent_id"]
        if pid is not None:
            parent = db.session.get(Task, pid)
            if not parent or parent.creator_id != user.id:
                return jsonify({"error": "Parent task not found"}), 404
        task.parent_id = pid

    if "due_date" in data:
        dd = data["due_date"]
        if dd is not None:
            from datetime import date
            try:
                task.due_date = date.fromisoformat(dd)
            except (ValueError, TypeError):
                return jsonify({"error": "due_date must be in YYYY-MM-DD format"}), 400
        else:
            task.due_date = None

    if "effort_estimate" in data:
        ee = data["effort_estimate"]
        if ee is not None:
            ee = int(ee)
            if ee < 1:
                return jsonify({"error": "effort_estimate must be positive"}), 400
        task.effort_estimate = ee

    if "dependency_ids" in data:
        task.dependencies = []
        for dep_id in data["dependency_ids"]:
            dep = db.session.get(Task, dep_id)
            if dep:
                task.dependencies.append(dep)

    if "tags" in data:
        db.session.execute(
            db.delete(task_tags).where(task_tags.c.task_id == task.id)
        )
        for tag in data["tags"]:
            tag = str(tag).strip().lower()
            if tag and len(tag) <= 50:
                db.session.execute(task_tags.insert().values(task_id=task.id, tag=tag))

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    task, error = _task_or_404(task_id, user)
    if error:
        return error
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200


@tasks_bp.route("/categories", methods=["GET"])
@jwt_required()
def list_categories():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    cats = Category.query.filter_by(user_id=user.id).order_by(Category.name).all()
    return jsonify({"categories": [c.to_dict() for c in cats]}), 200


@tasks_bp.route("/categories", methods=["POST"])
@jwt_required()
def create_category():
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    existing = Category.query.filter_by(name=name, user_id=user.id).first()
    if existing:
        return jsonify({"error": "Category with this name already exists"}), 409

    cat = Category(
        name=name,
        description=data.get("description", ""),
        color=data.get("color", "#6b7280"),
        user_id=user.id,
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify({"category": cat.to_dict()}), 201


@tasks_bp.route("/categories/<int:cat_id>", methods=["DELETE"])
@jwt_required()
def delete_category(cat_id):
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    cat = db.session.get(Category, cat_id)
    if not cat or cat.user_id != user.id:
        return jsonify({"error": "Category not found"}), 404
    db.session.delete(cat)
    db.session.commit()
    return jsonify({"message": "Category deleted"}), 200


@tasks_bp.route("/<int:task_id>/dependencies", methods=["POST"])
@jwt_required()
def add_dependency(task_id):
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    task, error = _task_or_404(task_id, user)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    dep_id = data.get("depends_on_id")
    if not dep_id:
        return jsonify({"error": "depends_on_id is required"}), 400
    dep = db.session.get(Task, dep_id)
    if not dep or dep.creator_id != user.id:
        return jsonify({"error": "Dependency task not found"}), 404
    if dep_id == task_id:
        return jsonify({"error": "Task cannot depend on itself"}), 400
    if dep not in task.dependencies:
        task.dependencies.append(dep)
        db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>/dependencies/<int:dep_id>", methods=["DELETE"])
@jwt_required()
def remove_dependency(task_id, dep_id):
    user = _get_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    task, error = _task_or_404(task_id, user)
    if error:
        return error
    dep = db.session.get(Task, dep_id)
    if dep and dep in task.dependencies:
        task.dependencies.remove(dep)
        db.session.commit()
    return jsonify({"task": task.to_dict()}), 200
