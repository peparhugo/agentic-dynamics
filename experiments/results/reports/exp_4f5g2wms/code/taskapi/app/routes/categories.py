from flask import Blueprint, request, jsonify, g, current_app

from app.database import get_db
from app.auth import login_required
from app.utils import (
    validate_required_fields,
    validate_non_empty_string,
    build_pagination_meta,
    parse_pagination_args,
)

categories_bp = Blueprint("categories", __name__)


def _category_row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


@categories_bp.route("", methods=["GET"])
@login_required
def list_categories():
    db = get_db()

    page, per_page = parse_pagination_args(
        request.args,
        current_app.config.get("MAX_PAGE_SIZE", 100),
        current_app.config.get("DEFAULT_PAGE_SIZE", 20),
    )

    conditions = ["created_by = ?"]
    params = [g.current_user_id]

    search = request.args.get("q")
    if search and search.strip():
        conditions.append("name LIKE ?")
        params.append(f"%{search.strip()}%")

    where_clause = " WHERE " + " AND ".join(conditions)

    count_row = db.execute(
        f"SELECT COUNT(*) FROM categories {where_clause}", params
    ).fetchone()
    total = count_row[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM categories {where_clause} ORDER BY name ASC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    categories = [_category_row_to_dict(r) for r in rows]

    return jsonify(
        {
            "categories": categories,
            "pagination": build_pagination_meta(page, per_page, total),
        }
    )


@categories_bp.route("", methods=["POST"])
@login_required
def create_category():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    ok, msg = validate_required_fields(data, ["name"])
    if not ok:
        return jsonify({"error": msg}), 400

    name = data["name"].strip()
    ok, msg = validate_non_empty_string(name, "name")
    if not ok:
        return jsonify({"error": msg}), 400

    description = data.get("description", "").strip()

    db = get_db()

    existing = db.execute(
        "SELECT id FROM categories WHERE name = ? AND created_by = ?",
        (name, g.current_user_id),
    ).fetchone()
    if existing:
        return jsonify({"error": "A category with this name already exists"}), 409

    cursor = db.execute(
        "INSERT INTO categories (name, description, created_by) VALUES (?, ?, ?)",
        (name, description, g.current_user_id),
    )
    db.commit()

    category = db.execute(
        "SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify({"category": _category_row_to_dict(category)}), 201


@categories_bp.route("/<int:category_id>", methods=["GET"])
@login_required
def get_category(category_id):
    db = get_db()
    category = db.execute(
        "SELECT * FROM categories WHERE id = ? AND created_by = ?",
        (category_id, g.current_user_id),
    ).fetchone()
    if not category:
        return jsonify({"error": "Category not found"}), 404
    return jsonify({"category": _category_row_to_dict(category)})


@categories_bp.route("/<int:category_id>", methods=["PUT"])
@login_required
def update_category(category_id):
    db = get_db()
    category = db.execute(
        "SELECT * FROM categories WHERE id = ? AND created_by = ?",
        (category_id, g.current_user_id),
    ).fetchone()
    if not category:
        return jsonify({"error": "Category not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    fields = {}
    if "name" in data:
        name = data["name"].strip()
        ok, msg = validate_non_empty_string(name, "name")
        if not ok:
            return jsonify({"error": msg}), 400

        duplicate = db.execute(
            "SELECT id FROM categories WHERE name = ? AND created_by = ? AND id != ?",
            (name, g.current_user_id, category_id),
        ).fetchone()
        if duplicate:
            return jsonify({"error": "A category with this name already exists"}), 409

        fields["name"] = name

    if "description" in data:
        fields["description"] = data["description"].strip()

    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [category_id]
    db.execute(f"UPDATE categories SET {set_clause} WHERE id = ?", values)
    db.commit()

    updated = db.execute(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    return jsonify({"category": _category_row_to_dict(updated)})


@categories_bp.route("/<int:category_id>", methods=["DELETE"])
@login_required
def delete_category(category_id):
    db = get_db()
    category = db.execute(
        "SELECT * FROM categories WHERE id = ? AND created_by = ?",
        (category_id, g.current_user_id),
    ).fetchone()
    if not category:
        return jsonify({"error": "Category not found"}), 404

    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    return jsonify({"message": "Category deleted"}), 200
