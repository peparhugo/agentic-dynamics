from ..database import get_db


def create_category(name, color="#3B82F6"):
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO categories (name, color) VALUES (?, ?)",
            (name, color),
        )
        db.commit()
        return cursor.lastrowid
    except db.IntegrityError:
        return None


def get_category_by_id(category_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    ).fetchone()


def get_category_by_name(name):
    db = get_db()
    return db.execute(
        "SELECT * FROM categories WHERE name = ?", (name,)
    ).fetchone()


def get_all_categories():
    db = get_db()
    return db.execute("SELECT * FROM categories ORDER BY name").fetchall()


def update_category(category_id, name=None, color=None):
    db = get_db()
    fields = []
    values = []

    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if color is not None:
        fields.append("color = ?")
        values.append(color)

    if not fields:
        return False

    values.append(category_id)
    db.execute(
        f"UPDATE categories SET {', '.join(fields)} WHERE id = ?", values
    )
    db.commit()
    return True


def delete_category(category_id):
    db = get_db()
    db.execute("UPDATE tasks SET category_id = NULL WHERE category_id = ?", (category_id,))
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    return True


def category_to_dict(category):
    return {
        "id": category["id"],
        "name": category["name"],
        "color": category["color"],
        "created_at": category["created_at"],
    }
