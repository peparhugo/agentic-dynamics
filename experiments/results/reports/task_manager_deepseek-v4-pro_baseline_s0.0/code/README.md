# Task Management API

A RESTful task management API built with Python, Flask, and SQLite.

## Features

- User registration and login with JWT authentication
- Task CRUD (create, read, update, delete)
- Task categories and priorities
- Due dates
- Task assignment to users
- Pagination
- Search and filtering by status, category, priority, and assignee

## Tech Stack

- Flask 3.x
- Flask-SQLAlchemy 3.x (SQLite)
- Flask-Migrate (Alembic migrations)
- Flask-JWT-Extended (JWT auth)

## Setup

```bash
pip install -r requirements.txt
export FLASK_APP=run.py
flask db upgrade          # apply migrations
python run.py             # or: flask run
```

## API Endpoints

### Auth

| Method | Path             | Description           |
|--------|------------------|-----------------------|
| POST   | `/auth/register` | Register a new user   |
| POST   | `/auth/login`    | Log in, get JWT token |
| GET    | `/auth/me`       | Current user info     |

Register/login body: `{"username", "email", "password"}` (login only needs
`username`/`password`). Responses include `access_token` and `user`.

### Tasks (all require `Authorization: Bearer <token>`)

| Method | Path                     | Description                       |
|--------|--------------------------|-----------------------------------|
| GET    | `/tasks`                 | List (paginated, filterable)      |
| POST   | `/tasks`                 | Create a task                     |
| GET    | `/tasks/<id>`            | Get a single task                 |
| PUT    | `/tasks/<id>`            | Update a task                     |
| DELETE | `/tasks/<id>`            | Delete a task                     |
| POST   | `/tasks/<id>/assign`     | Assign a task to a user           |

Task fields: `title` (required), `description`, `status`
(`pending`/`in_progress`/`completed`), `priority`
(`low`/`medium`/`high`/`urgent`), `category`, `due_date` (`YYYY-MM-DD`),
`assignee_id`.

### Query parameters for `GET /tasks`

| Param         | Description                    |
|---------------|--------------------------------|
| `page`        | Page number (default 1)        |
| `per_page`    | Items per page (default 10)    |
| `status`      | Filter by status               |
| `priority`    | Filter by priority             |
| `category`    | Filter by category             |
| `assignee_id` | Filter by assignee             |
| `q`/`search`  | Full-text search on title/desc |

## Testing

```bash
pytest
```
