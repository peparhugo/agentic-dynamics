# Task Manager API

A complete task management REST API built with Python/Flask and SQLite.

## Features

- User registration and login with JWT authentication
- Role-based authorization (`user` / `admin`)
- Task CRUD (create / read / update / delete)
- Task categories and priorities (`low` / `medium` / `high`)
- Due dates
- Task assignment to users
- Pagination
- Search and filtering by status / category / priority / assignee / due date / overdue
- Sorting by title, due date, priority, status, created_at
- Comprehensive pytest test suite

## Layout

```
task_manager/
  __init__.py            app factory
  config.py              configuration classes
  extensions.py          db + migrate instances
  models.py              User, Category, Task models
  auth.py                register / login / me routes
  tasks.py               task CRUD, filters, pagination, assignment
  categories.py          category CRUD
  utils.py               JWT encode/decode + auth decorators
  run.py                 development entry point
  migrations/            SQL + Flask-Migrate migrations
  tests/                 pytest suite
```

## Quickstart

```bash
cd task_manager
pip install -r requirements.txt
python run.py
```

The API is served at `http://localhost:5000`.

## Endpoints

| Method | Path                        | Description                              |
| ------ | --------------------------- | ---------------------------------------- |
| POST   | /api/auth/register          | Register a new user                      |
| POST   | /api/auth/login             | Login, returns a JWT access token        |
| GET    | /api/auth/me                | Current user profile                     |
| GET    | /api/tasks                  | List tasks (filters + pagination)        |
| POST   | /api/tasks                  | Create a task                            |
| GET    | /api/tasks/<id>             | Get a task                               |
| PUT    | /api/tasks/<id>             | Update a task                            |
| PATCH  | /api/tasks/<id>             | Partially update a task                  |
| DELETE | /api/tasks/<id>             | Delete a task                            |
| POST   | /api/tasks/<id>/assign      | Assign a task to a user                  |
| DELETE | /api/tasks/<id>/assignee    | Unassign a task                          |
| GET    | /api/categories             | List categories                          |
| POST   | /api/categories             | Create a category                        |
| GET    | /api/categories/<id>        | Get a category                           |
| PUT    | /api/categories/<id>        | Update a category (admin)                |
| DELETE | /api/categories/<id>        | Delete a category (admin)                |
| GET    | /health                     | Health check                             |

All routes except `register`, `login`, and `/health` require a `Authorization: Bearer <token>` header.

### Task list query parameters

| Param        | Description                                   |
| ------------ | --------------------------------------------- |
| status       | `todo`, `in_progress`, `done`                 |
| priority     | `low`, `medium`, `high`                       |
| category     | category id or name (partial, case-insensitive)|
| assignee_id  | filter by assigned user id                    |
| created_by   | filter by creator id                          |
| search       | substring match on title/description          |
| due_before   | `YYYY-MM-DD`                                  |
| due_after    | `YYYY-MM-DD`                                  |
| overdue      | `true` filters tasks past due and not done    |
| sort         | `created_at`, `due_date`, `title`, `priority`, `status`, `id` |
| order        | `asc` or `desc` (default `desc`)              |
| page         | page number (default `1`)                     |
| per_page     | page size (default `10`, max `100`)           |

## Running tests

```bash
cd task_manager
pytest
```
