from flask import g, jsonify, request

from .auth import auth_required
from .db import get_db


def register_routes(app):
    @app.get("/api/categories")
    @auth_required
    def list_categories():
        rows = get_db().execute(
            "SELECT c.id, c.name, c.created_at, COUNT(t.id) AS task_count "
            "FROM categories c LEFT JOIN tasks t ON t.category_id = c.id "
            "GROUP BY c.id ORDER BY c.name COLLATE NOCASE"
        ).fetchall()
        return jsonify(categories=[dict(row) for row in rows])

    @app.post("/api/categories")
    @auth_required
    def create_category():
        name = str((request.get_json(silent=True) or {}).get("name", "")).strip()
        if not name or len(name) > 80:
            return jsonify(error="Category name must be between 1 and 80 characters"), 400
        db = get_db()
        try:
            cursor = db.execute("INSERT INTO categories(name) VALUES (?)", (name,))
            db.commit()
        except Exception as error:
            if "UNIQUE constraint failed" not in str(error):
                raise
            return jsonify(error="Category already exists"), 409
        category = db.execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(category=dict(category)), 201

    @app.patch("/api/categories/<int:category_id>")
    @auth_required
    def update_category(category_id):
        name = str((request.get_json(silent=True) or {}).get("name", "")).strip()
        if not name or len(name) > 80:
            return jsonify(error="Category name must be between 1 and 80 characters"), 400
        db = get_db()
        if db.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone() is None:
            return jsonify(error="Category not found"), 404
        try:
            db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
            db.commit()
        except Exception as error:
            if "UNIQUE constraint failed" not in str(error):
                raise
            return jsonify(error="Category already exists"), 409
        return jsonify(category=dict(db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()))

    @app.delete("/api/categories/<int:category_id>")
    @auth_required
    def delete_category(category_id):
        db = get_db()
        cursor = db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit()
        if cursor.rowcount == 0:
            return jsonify(error="Category not found"), 404
        return "", 204
