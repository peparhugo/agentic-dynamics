-- 0001_initial: create core schema
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(80) NOT NULL UNIQUE,
    color VARCHAR(20),
    created_at DATETIME NOT NULL
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'todo',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    due_date DATE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE INDEX ix_tasks_status ON tasks(status);
CREATE INDEX ix_tasks_priority ON tasks(priority);
CREATE INDEX ix_tasks_category_id ON tasks(category_id);
CREATE INDEX ix_tasks_assignee_id ON tasks(assignee_id);
CREATE INDEX ix_tasks_creator_id ON tasks(creator_id);
CREATE INDEX ix_tasks_due_date ON tasks(due_date);
