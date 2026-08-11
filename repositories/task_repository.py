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

    def update(self, task_id, owner_id, title, status):
        self.db.execute(
            "UPDATE task SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (title, status, task_id, owner_id),
        )
        self.db.commit()
