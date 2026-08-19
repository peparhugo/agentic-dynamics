# Task Management API

A Flask and SQLite task management service with JWT authentication.

## Run

```bash
python3 -m pip install -r requirements.txt
flask --app app run
```

Set `SECRET_KEY` and `DATABASE` in the environment for production use. The database is migrated automatically when the application starts.

## API

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET/POST /api/categories`
- `GET/POST /api/tasks`, `GET/PATCH/DELETE /api/tasks/<id>`

Task listing accepts `page`, `per_page`, `search`, `status`, `category`, `priority`, and `assigned_to` query parameters.
