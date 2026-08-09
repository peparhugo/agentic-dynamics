import sqlite3
import threading
from contextlib import contextmanager
from flask import g, current_app


class DatabasePool:
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._local = threading.local()

    @property
    def connection(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA mmap_size=268435456")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None


db_pool = None


def init_db(db_path):
    global db_pool
    db_pool = DatabasePool(db_path)


def get_pool():
    return db_pool


@contextmanager
def get_db():
    pool = get_pool()
    conn = pool.connection
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise


def query_one(sql, params=()):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchone()


def query_all(sql, params=()):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def execute(sql, params=()):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def execute_returning(sql, params=()):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
