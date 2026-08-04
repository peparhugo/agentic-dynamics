from flask import g, jsonify

from ...audit import audit
from ...auth import require_auth
from ...db import get_db
from ...errors import NotFoundError
from ...pagination import get_page_args, paginated_response
from ...validation import ITEM_CREATE_SCHEMA, ITEM_UPDATE_SCHEMA, validate_json
from . import bp


def _serialize(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_owned_item(item_id):
    row = get_db().execute(
        "SELECT * FROM items WHERE id = ? AND owner_id = ?",
        (item_id, g.current_user_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("Item not found.")
    return row


@bp.get("/items")
@require_auth
def list_items():
    page, per_page = get_page_args()
    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) AS c FROM items WHERE owner_id = ?",
        (g.current_user_id,),
    ).fetchone()["c"]
    rows = db.execute(
        "SELECT * FROM items WHERE owner_id = ? ORDER BY id LIMIT ? OFFSET ?",
        (g.current_user_id, per_page, (page - 1) * per_page),
    ).fetchall()
    return jsonify(paginated_response(
        [_serialize(r) for r in rows], page, per_page, total, "api_v1.list_items"))


@bp.post("/items")
@require_auth
def create_item():
    data = validate_json(ITEM_CREATE_SCHEMA)
    db = get_db()
    cur = db.execute(
        "INSERT INTO items (owner_id, name, description) VALUES (?, ?, ?)",
        (g.current_user_id, data["name"], data.get("description") or ""),
    )
    db.commit()
    row = _get_owned_item(cur.lastrowid)
    audit("item.create", resource=f"item:{row['id']}", detail={"name": row["name"]})
    return jsonify(_serialize(row)), 201


@bp.get("/items/<int:item_id>")
@require_auth
def get_item(item_id):
    return jsonify(_serialize(_get_owned_item(item_id)))


@bp.patch("/items/<int:item_id>")
@require_auth
def update_item(item_id):
    row = _get_owned_item(item_id)
    data = validate_json(ITEM_UPDATE_SCHEMA)
    if not data:
        return jsonify(_serialize(row))
    db = get_db()
    db.execute(
        "UPDATE items SET name = ?, description = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (data.get("name", row["name"]),
         data.get("description", row["description"]),
         item_id),
    )
    db.commit()
    updated = _get_owned_item(item_id)
    audit("item.update", resource=f"item:{item_id}", detail={"fields": sorted(data)})
    return jsonify(_serialize(updated))


@bp.delete("/items/<int:item_id>")
@require_auth
def delete_item(item_id):
    _get_owned_item(item_id)
    db = get_db()
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()
    audit("item.delete", resource=f"item:{item_id}")
    return "", 204
