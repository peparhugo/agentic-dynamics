CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_categories_name ON categories (name);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'todo',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    due_date DATE,
    category_id INTEGER REFERENCES categories (id),
    assignee_id INTEGER REFERENCES users (id),
    created_by_id INTEGER NOT NULL REFERENCES users (id),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_tasks_title ON tasks (title);
CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS ix_tasks_priority ON tasks (priority);
CREATE INDEX IF NOT EXISTS ix_tasks_due_date ON tasks (due_date);
CREATE INDEX IF NOT EXISTS ix_tasks_category_id ON tasks (category_id);
CREATE INDEX IF NOT EXISTS ix_tasks_assignee_id ON tasks (assignee_id);
