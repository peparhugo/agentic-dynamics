from .base_repository import BaseRepository


class TaskRepository(BaseRepository):
    def create(self, owner_id, title, status, created_at):
        cursor = self.db.execute(
            "INSERT INTO task (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, status, created_at, owner_id),
        )
        self.db.commit()
        task_id = cursor.lastrowid
        row = self.db.execute(
            "SELECT * FROM task WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
        return self._row_to_dict(row)

    def find_by_id(self, task_id, owner_id):
        row = self.db.execute(
            "SELECT * FROM task WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
        return self._row_to_dict(row)

    def find_all_by_owner(self, owner_id):
        rows = self.db.execute(
            "SELECT * FROM task WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        return self._rows_to_dicts(rows)

    def find_all_by_owner_paginated(self, owner_id, cursor, limit):
        if cursor is not None:
            rows = self.db.execute(
                "SELECT * FROM task WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                (owner_id, cursor, limit + 1),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM task WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                (owner_id, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        data = self._rows_to_dicts(rows)
        next_cursor = str(data[-1]["id"]) if (data and has_more) else None
        return data, next_cursor

    def count_by_owner(self, owner_id):
        row = self.db.execute(
            "SELECT COUNT(*) as cnt FROM task WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()
        return row["cnt"]

    def update(self, task_id, owner_id, title, status):
        self.db.execute(
            "UPDATE task SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (title, status, task_id, owner_id),
        )
        self.db.commit()
