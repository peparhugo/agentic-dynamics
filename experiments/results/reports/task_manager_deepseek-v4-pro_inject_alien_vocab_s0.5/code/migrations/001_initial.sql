-- 001_initial.sql
-- Create the base schema for the task management application.

PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_users_username ON users (username);
CREATE INDEX ix_users_email ON users (email);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(80) NOT NULL UNIQUE,
    color VARCHAR(20),
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_categories_name ON categories (name);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    due_date DATE,
    category_id INTEGER,
    assignee_id INTEGER,
    creator_id INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL,
    FOREIGN KEY (assignee_id) REFERENCES users (id) ON DELETE SET NULL,
    FOREIGN KEY (creator_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_tasks_title ON tasks (title);
CREATE INDEX ix_tasks_status ON tasks (status);
CREATE INDEX ix_tasks_priority ON tasks (priority);
CREATE INDEX ix_tasks_due_date ON tasks (due_date);
