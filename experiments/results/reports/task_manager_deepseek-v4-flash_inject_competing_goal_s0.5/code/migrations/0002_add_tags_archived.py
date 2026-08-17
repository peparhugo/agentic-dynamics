def _column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in rows)


def migrate(conn):
    if not _column_exists(conn, "tasks", "tags"):
        conn.execute("ALTER TABLE tasks ADD COLUMN tags VARCHAR(500)")
    if not _column_exists(conn, "tasks", "archived"):
        conn.execute("ALTER TABLE tasks ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_tasks_archived ON tasks (archived)")
