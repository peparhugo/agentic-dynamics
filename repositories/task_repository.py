"""
TaskRepository — all SQL for the `tasks` table.
"""

from datetime import datetime

from .base import BaseRepository


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create_schema(self, conn):
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )

    def migrate_schema(self, conn):
        """Add owner_id to a pre-existing tasks table without dropping data."""
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
            conn.commit()

    def create(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        task_id = self.insert(title=title, status="pending", created_at=now, owner_id=owner_id)
        return {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }

    def list_for_owner(self, owner_id: int):
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get(self, task_id: int, owner_id: int) -> dict | None:
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
            ).fetchone()
            return dict(row) if row else None

    def update(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        task = self.get(task_id, owner_id)
        if task is None:
            return None
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            params.append(owner_id)
            with self.get_db() as conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", params
                )
                conn.commit()
        return self.get(task_id, owner_id)
