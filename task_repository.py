"""Repository for the tasks table.

SQLite's INTEGER PRIMARY KEY without AUTOINCREMENT can still reuse ids after
deletes, so task ids are assigned manually from a counter persisted in a
dedicated `counters` table rather than relying on SQLite's rowid behavior.
That id allocation is owned by this repository, alongside task creation.
"""

from base_repository import BaseRepository


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def _next_id(self):
        self.db.execute("BEGIN IMMEDIATE")
        row = self.db.execute("SELECT value FROM counters WHERE name = 'task_id'").fetchone()
        next_id = row["value"]
        self.db.execute("UPDATE counters SET value = ? WHERE name = 'task_id'", (next_id + 1,))
        return next_id

    def create(self, title, status, created_at, owner_id):
        task_id = self._next_id()
        self.db.execute(
            "INSERT INTO tasks (id, title, status, created_at, owner_id) VALUES (?, ?, ?, ?, ?)",
            (task_id, title, status, created_at, owner_id),
        )
        self.db.commit()
        return self.get_by_id(task_id)

    def list_by_owner(self, owner_id):
        return self.db.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()

    def get_by_id_and_owner(self, task_id, owner_id):
        return self.db.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()

    def update(self, task_id, owner_id, title, status):
        self.db.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (title, status, task_id, owner_id),
        )
        self.db.commit()
        return self.get_by_id(task_id)
