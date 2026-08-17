-- 001_initial.sql
-- Initial schema for the Task Manager API.

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at DATETIME NOT NULL
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(80) NOT NULL UNIQUE,
    description TEXT,
    created_at DATETIME NOT NULL
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'todo',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    due_date DATE,
    created_by_id INTEGER NOT NULL REFERENCES users(id),
    assignee_id INTEGER REFERENCES users(id),
    category_id INTEGER REFERENCES categories(id),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE INDEX ix_users_username ON users (username);
CREATE INDEX ix_users_email ON users (email);
CREATE INDEX ix_categories_name ON categories (name);
CREATE INDEX ix_tasks_title ON tasks (title);
CREATE INDEX ix_tasks_status ON tasks (status);
CREATE INDEX ix_tasks_priority ON tasks (priority);
CREATE INDEX ix_tasks_due_date ON tasks (due_date);
CREATE INDEX ix_tasks_created_by_id ON tasks (created_by_id);
CREATE INDEX ix_tasks_assignee_id ON tasks (assignee_id);
CREATE INDEX ix_tasks_category_id ON tasks (category_id);
