from flask import Flask, g, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from auth import generate_token, token_required
from models import (
    VALID_PRIORITIES,
    VALID_ROLES,
    VALID_STATUSES,
    Attachment,
    Comment,
    Project,
    ProjectMember,
    Task,
    User,
    db,
)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///collab.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


def paginate(query, page=None, per_page=None):
    page = max(1, int(request.args.get("page", page or 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", per_page or 20))))
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [item.to_dict() for item in paginated.items],
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    }


def get_project_member(project_id, user_id):
    return ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()


def require_project_role(project_id, *roles):
    member = get_project_member(project_id, g.current_user.id)
    if not member:
        return jsonify({"error": "Access denied: not a project member"}), 403
    if member.role not in roles:
        return jsonify({"error": "Access denied: insufficient permissions"}), 403
    return member


# ─── Auth routes ───


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    errors = {}
    if not username:
        errors["username"] = "Username is required"
    if not email:
        errors["email"] = "Email is required"
    if not password:
        errors["password"] = "Password is required"
    if len(password) < 3:
        errors["password"] = "Password must be at least 3 characters"
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({"message": "User registered", "user": user.to_dict(), "token": token}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = generate_token(user.id)
    return jsonify({"message": "Login successful", "user": user.to_dict(), "token": token}), 200


# ─── Project routes ───


@app.route("/projects", methods=["GET"])
@token_required
def list_projects():
    query = Project.query

    search = request.args.get("search", "").strip()
    if search:
        term = f"%{search}%"
        query = query.filter(
            db.or_(Project.name.ilike(term), Project.description.ilike(term))
        )

    sort = request.args.get("sort", "created_at_desc")
    if sort == "name_asc":
        query = query.order_by(Project.name.asc())
    elif sort == "name_desc":
        query = query.order_by(Project.name.desc())
    elif sort == "created_at_asc":
        query = query.order_by(Project.created_at.asc())
    else:
        query = query.order_by(Project.created_at.desc())

    return jsonify(paginate(query)), 200


@app.route("/projects", methods=["POST"])
@token_required
def create_project():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    if not name:
        return jsonify({"error": "Project name is required"}), 400

    project = Project(name=name, description=description, created_by=g.current_user.id)
    db.session.add(project)
    db.session.flush()

    member = ProjectMember(
        project_id=project.id, user_id=g.current_user.id, role="admin"
    )
    db.session.add(member)
    db.session.commit()

    return jsonify({"message": "Project created", "project": project.to_dict()}), 201


@app.route("/projects/<int:project_id>", methods=["GET"])
@token_required
def get_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project.to_dict()), 200


@app.route("/projects/<int:project_id>", methods=["PUT"])
@token_required
def update_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    result = require_project_role(project_id, "admin")
    if isinstance(result, tuple):
        return result

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if name:
        project.name = name
    if "description" in data:
        project.description = data.get("description", "").strip()
    db.session.commit()
    return jsonify({"message": "Project updated", "project": project.to_dict()}), 200


@app.route("/projects/<int:project_id>", methods=["DELETE"])
@token_required
def delete_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    result = require_project_role(project_id, "admin")
    if isinstance(result, tuple):
        return result

    db.session.delete(project)
    db.session.commit()
    return jsonify({"message": "Project deleted"}), 200


# ─── Member routes ───


@app.route("/projects/<int:project_id>/members", methods=["GET"])
@token_required
def list_members(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    members = (
        ProjectMember.query.filter_by(project_id=project_id)
        .order_by(ProjectMember.joined_at.asc())
        .all()
    )
    return jsonify({"members": [m.to_dict() for m in members]}), 200


@app.route("/projects/<int:project_id>/members", methods=["POST"])
@token_required
def add_member(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    result = require_project_role(project_id, "admin")
    if isinstance(result, tuple):
        return result

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    role = data.get("role", "member")
    if role not in VALID_ROLES:
        return jsonify({"error": f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}"}), 400

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({"error": "User not found"}), 404

    existing = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if existing:
        return jsonify({"error": "User is already a member of this project"}), 409

    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.session.add(member)
    db.session.commit()
    return jsonify({"message": "Member added", "member": member.to_dict()}), 201


@app.route("/projects/<int:project_id>/members/<int:member_id>", methods=["PUT"])
@token_required
def update_member(project_id, member_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    result = require_project_role(project_id, "admin")
    if isinstance(result, tuple):
        return result

    member = ProjectMember.query.filter_by(id=member_id, project_id=project_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404

    data = request.get_json(silent=True) or {}
    role = data.get("role")
    if not role or role not in VALID_ROLES:
        return jsonify({"error": f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}"}), 400

    member.role = role
    db.session.commit()
    return jsonify({"message": "Member role updated", "member": member.to_dict()}), 200


@app.route("/projects/<int:project_id>/members/<int:member_id>", methods=["DELETE"])
@token_required
def remove_member(project_id, member_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    result = require_project_role(project_id, "admin")
    if isinstance(result, tuple):
        return result

    member = ProjectMember.query.filter_by(id=member_id, project_id=project_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404

    if member.user_id == g.current_user.id:
        return jsonify({"error": "Cannot remove yourself from the project"}), 400

    db.session.delete(member)
    db.session.commit()
    return jsonify({"message": "Member removed"}), 200


# ─── Task routes ───


@app.route("/projects/<int:project_id>/tasks", methods=["GET"])
@token_required
def list_tasks(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    result = require_project_role(project_id, "admin", "member", "viewer")
    if isinstance(result, tuple):
        return result

    query = Task.query.filter_by(project_id=project_id)

    search = request.args.get("search", "").strip()
    if search:
        term = f"%{search}%"
        query = query.filter(
            db.or_(Task.title.ilike(term), Task.description.ilike(term))
        )

    status = request.args.get("status", "").strip()
    if status and status in VALID_STATUSES:
        query = query.filter_by(status=status)

    priority = request.args.get("priority", "").strip()
    if priority and priority in VALID_PRIORITIES:
        query = query.filter_by(priority=priority)

    assigned_to = request.args.get("assigned_to", "").strip()
    if assigned_to:
        try:
            aid = int(assigned_to)
            query = query.filter_by(assigned_to=aid)
        except (ValueError, TypeError):
            return jsonify({"error": "assigned_to must be a valid user ID"}), 400

    sort = request.args.get("sort", "created_at_desc")
    if sort == "priority_asc":
        query = query.order_by(Task.priority.asc(), Task.created_at.desc())
    elif sort == "priority_desc":
        query = query.order_by(Task.priority.desc(), Task.created_at.desc())
    elif sort == "status_asc":
        query = query.order_by(Task.status.asc(), Task.created_at.desc())
    elif sort == "created_at_asc":
        query = query.order_by(Task.created_at.asc())
    else:
        query = query.order_by(Task.created_at.desc())

    return jsonify(paginate(query)), 200


@app.route("/projects/<int:project_id>/tasks", methods=["POST"])
@token_required
def create_task(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    result = require_project_role(project_id, "admin", "member")
    if isinstance(result, tuple):
        return result

    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    status = data.get("status", "todo")
    priority = data.get("priority", "medium")
    assigned_to = data.get("assigned_to")

    if not title:
        return jsonify({"error": "Task title is required"}), 400
    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}), 400
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"}), 400
    if assigned_to is not None:
        if not isinstance(assigned_to, int):
            return jsonify({"error": "assigned_to must be a valid user ID"}), 400
        if not User.query.get(assigned_to):
            return jsonify({"error": "Assigned user not found"}), 404

    task = Task(
        project_id=project_id,
        title=title,
        description=description,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        created_by=g.current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"message": "Task created", "task": task.to_dict()}), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    result = require_project_role(task.project_id, "admin", "member", "viewer")
    if isinstance(result, tuple):
        return result

    return jsonify(task.to_dict()), 200


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    result = require_project_role(task.project_id, "admin", "member")
    if isinstance(result, tuple):
        return result

    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = data["title"].strip()
        if not title:
            return jsonify({"error": "Task title cannot be empty"}), 400
        task.title = title
    if "description" in data:
        task.description = data["description"].strip()
    if "status" in data:
        status = data["status"]
        if status not in VALID_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}), 400
        task.status = status
    if "priority" in data:
        priority = data["priority"]
        if priority not in VALID_PRIORITIES:
            return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"}), 400
        task.priority = priority
    if "assigned_to" in data:
        aid = data["assigned_to"]
        if aid is not None:
            if not isinstance(aid, int):
                return jsonify({"error": "assigned_to must be a valid user ID"}), 400
            if not User.query.get(aid):
                return jsonify({"error": "Assigned user not found"}), 404
        task.assigned_to = aid

    db.session.commit()
    return jsonify({"message": "Task updated", "task": task.to_dict()}), 200


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
@token_required
def delete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    result = require_project_role(task.project_id, "admin")
    if isinstance(result, tuple):
        return result

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200


# ─── Comment routes ───


@app.route("/tasks/<int:task_id>/comments", methods=["GET"])
@token_required
def list_comments(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    result = require_project_role(task.project_id, "admin", "member", "viewer")
    if isinstance(result, tuple):
        return result

    comments = (
        Comment.query.filter_by(task_id=task_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return jsonify({"comments": [c.to_dict() for c in comments]}), 200


@app.route("/tasks/<int:task_id>/comments", methods=["POST"])
@token_required
def create_comment(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    result = require_project_role(task.project_id, "admin", "member")
    if isinstance(result, tuple):
        return result

    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Comment content is required"}), 400

    comment = Comment(task_id=task_id, user_id=g.current_user.id, content=content)
    db.session.add(comment)
    db.session.commit()
    return jsonify({"message": "Comment created", "comment": comment.to_dict()}), 201


@app.route("/comments/<int:comment_id>", methods=["PUT"])
@token_required
def update_comment(comment_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    if comment.user_id != g.current_user.id:
        return jsonify({"error": "You can only edit your own comments"}), 403

    data = request.get_json(silent=True) or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Comment content is required"}), 400

    comment.content = content
    db.session.commit()
    return jsonify({"message": "Comment updated", "comment": comment.to_dict()}), 200


@app.route("/comments/<int:comment_id>", methods=["DELETE"])
@token_required
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    member = get_project_member(comment.task.project_id, g.current_user.id)
    is_admin = member and member.role == "admin"
    is_owner = comment.user_id == g.current_user.id

    if not is_owner and not is_admin:
        return jsonify({"error": "You can only delete your own comments unless you are an admin"}), 403

    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": "Comment deleted"}), 200


# ─── Attachment routes ───


@app.route("/attachments", methods=["POST"])
@token_required
def create_attachment():
    data = request.get_json(silent=True) or {}

    task_id = data.get("task_id")
    comment_id = data.get("comment_id")
    filename = data.get("filename", "").strip()
    file_path = data.get("file_path", "").strip()

    if not filename:
        return jsonify({"error": "filename is required"}), 400
    if not file_path:
        return jsonify({"error": "file_path is required"}), 400
    if not task_id and not comment_id:
        return jsonify({"error": "Either task_id or comment_id is required"}), 400

    project_id = None
    if task_id:
        task = Task.query.get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        result = require_project_role(task.project_id, "admin", "member")
        if isinstance(result, tuple):
            return result
        project_id = task.project_id
    if comment_id:
        comment = Comment.query.get(comment_id)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404
        result = require_project_role(comment.task.project_id, "admin", "member")
        if isinstance(result, tuple):
            return result
        project_id = comment.task.project_id

    attachment = Attachment(
        task_id=task_id,
        comment_id=comment_id,
        filename=filename,
        file_path=file_path,
        uploaded_by=g.current_user.id,
    )
    db.session.add(attachment)
    db.session.commit()
    return jsonify({"message": "Attachment created", "attachment": attachment.to_dict()}), 201


@app.route("/attachments/<int:attachment_id>", methods=["GET"])
@token_required
def get_attachment(attachment_id):
    attachment = Attachment.query.get(attachment_id)
    if not attachment:
        return jsonify({"error": "Attachment not found"}), 404

    project_id = None
    if attachment.task_id:
        project_id = attachment.task.project_id
    elif attachment.comment_id:
        project_id = attachment.comment.task.project_id

    if project_id:
        result = require_project_role(project_id, "admin", "member", "viewer")
        if isinstance(result, tuple):
            return result

    return jsonify(attachment.to_dict()), 200


@app.route("/attachments/<int:attachment_id>", methods=["DELETE"])
@token_required
def delete_attachment(attachment_id):
    attachment = Attachment.query.get(attachment_id)
    if not attachment:
        return jsonify({"error": "Attachment not found"}), 404

    project_id = None
    if attachment.task_id:
        project_id = attachment.task.project_id
    elif attachment.comment_id:
        project_id = attachment.comment.task.project_id

    if project_id:
        member = get_project_member(project_id, g.current_user.id)
        is_admin = member and member.role == "admin"
        is_owner = attachment.uploaded_by == g.current_user.id
        if not is_owner and not is_admin:
            return jsonify({"error": "You can only delete your own attachments unless you are an admin"}), 403

    db.session.delete(attachment)
    db.session.commit()
    return jsonify({"message": "Attachment deleted"}), 200


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
