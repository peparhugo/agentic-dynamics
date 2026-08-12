import sqlite3
import os
from abc import ABC, abstractmethod


class BaseRepository(ABC):
    def __init__(self, db_factory):
        self._db_factory = db_factory

    def _fetchone(self, query, params=()):
        with self._db_factory() as conn:
            return conn.execute(query, params).fetchone()

    def _fetchall(self, query, params=()):
        with self._db_factory() as conn:
            return conn.execute(query, params).fetchall()

    def _execute(self, query, params=()):
        with self._db_factory() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor

    @abstractmethod
    def create(self, **kwargs):
        pass

    @abstractmethod
    def find_by_id(self, *args, **kwargs):
        pass


class TaskRepository(BaseRepository):
    def create(self, title, status, created_at, owner_id):
        cursor = self._execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, status, created_at, owner_id),
        )
        return cursor.lastrowid

    def find_by_id(self, task_id, owner_id):
        return self._fetchone(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        )

    def find_all_by_owner(self, owner_id):
        return self._fetchall(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        )

    def find_paginated_by_owner(self, owner_id, cursor=None, limit=20):
        total_row = self._fetchone(
            "SELECT COUNT(*) FROM tasks WHERE owner_id = ?",
            (owner_id,),
        )
        total = total_row[0] if total_row else 0
        fetch_limit = limit + 1
        if cursor is not None:
            rows = self._fetchall(
                "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                (owner_id, cursor, fetch_limit),
            )
        else:
            rows = self._fetchall(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                (owner_id, fetch_limit),
            )
        return rows, total

    def update(self, task_id, owner_id, title, status):
        self._execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (title, status, task_id, owner_id),
        )


class UserRepository(BaseRepository):
    def create(self, username, password_hash, email):
        cursor = self._execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        return cursor.lastrowid

    def find_by_id(self, user_id):
        return self._fetchone(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        )

    def find_by_username(self, username):
        return self._fetchone(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        )

    def find_by_username_full(self, username):
        return self._fetchone(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        )
