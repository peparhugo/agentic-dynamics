CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(80) NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME NOT NULL,
    UNIQUE (name, user_id)
);

CREATE INDEX IF NOT EXISTS ix_categories_user_id ON categories (user_id);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'todo',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    due_date DATETIME,
    category_id INTEGER REFERENCES categories(id),
    assignee_id INTEGER REFERENCES users(id),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS ix_tasks_priority ON tasks (priority);
CREATE INDEX IF NOT EXISTS ix_tasks_created_by ON tasks (created_by);
CREATE INDEX IF NOT EXISTS ix_tasks_created_at ON tasks (created_at);
