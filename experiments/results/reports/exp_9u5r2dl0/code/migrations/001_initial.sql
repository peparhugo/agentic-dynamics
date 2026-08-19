CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL COLLATE NOCASE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'in_progress', 'completed')),
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
    due_date TEXT,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tasks_creator ON tasks(creator_id, created_at DESC);
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id, created_at DESC);
CREATE INDEX idx_tasks_filters ON tasks(status, priority, category_id);
