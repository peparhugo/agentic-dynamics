from abc import ABC


class BaseRepository(ABC):
    def __init__(self, conn):
        self.conn = conn

    def _execute(self, query, params=None):
        return self.conn.execute(query, params or ())

    def _fetchone(self, query, params=None):
        return self._execute(query, params).fetchone()

    def _fetchall(self, query, params=None):
        return self._execute(query, params).fetchall()


class UserRepository(BaseRepository):
    def find_by_username(self, username):
        return self._fetchone(
            "SELECT * FROM users WHERE username = ?", (username,)
        )

    def create_user(self, username, password_hash, created_at):
        self._execute(
            "INSERT INTO users (username, password_hash, role, created_at) "
            "VALUES (?, ?, 'user', ?)",
            (username, password_hash, created_at),
        )

    def get_all_users(self):
        return self._fetchall(
            "SELECT id, username, role, created_at FROM users ORDER BY created_at"
        )


class TaskRepository(BaseRepository):
    def create_task(self, title, owner_id, created_at):
        cursor = self._execute(
            "INSERT INTO tasks (title, status, owner_id, created_at) "
            "VALUES (?, 'pending', ?, ?)",
            (title, owner_id, created_at),
        )
        return cursor.lastrowid

    def find_tasks_by_owner(self, owner_id):
        return self._fetchall(
            "SELECT id, title, status, owner_id, created_at FROM tasks "
            "WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        )

    def find_task_by_id_and_owner(self, task_id, owner_id):
        return self._fetchone(
            "SELECT id, title, status, owner_id, created_at FROM tasks "
            "WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        )

    def find_task_by_id(self, task_id):
        return self._fetchone(
            "SELECT id, title, status, owner_id, created_at FROM tasks "
            "WHERE id = ?",
            (task_id,),
        )

    def update_task_title(self, task_id, title):
        self._execute(
            "UPDATE tasks SET title = ? WHERE id = ?", (title, task_id)
        )

    def update_task_status(self, task_id, status):
        self._execute(
            "UPDATE tasks SET status = ? WHERE id = ?", (status, task_id)
        )


class ItemsRepository(BaseRepository):
    def find_items_by_user(self, user_id):
        return self._fetchall(
            "SELECT * FROM items WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )

    def create_item(self, user_id, name, description, created_at):
        cursor = self._execute(
            "INSERT INTO items (user_id, name, description, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, name, description, created_at),
        )
        return cursor.lastrowid

    def find_item_by_id_and_user(self, item_id, user_id):
        return self._fetchone(
            "SELECT * FROM items WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        )

    def item_exists(self, item_id, user_id):
        return self._fetchone(
            "SELECT id FROM items WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        )

    def delete_item_by_id(self, item_id):
        self._execute("DELETE FROM items WHERE id = ?", (item_id,))
