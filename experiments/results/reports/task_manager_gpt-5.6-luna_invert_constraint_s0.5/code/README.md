# Task Management API

## Run

```sh
python3 -m pip install -r requirements.txt
flask --app run run
```

The SQLite database is created in `instance/tasks.sqlite` and migrations in `migrations/` are applied automatically.

## API

Register with `POST /api/auth/register` using `username`, `email`, and an eight-character minimum `password`. Login is `POST /api/auth/login`. Send the returned token as `Authorization: Bearer <token>`.

Authenticated endpoints are `GET/POST /api/categories`, `GET/POST /api/tasks`, `GET/PATCH/PUT/DELETE /api/tasks/<id>`. Task list supports `page`, `per_page`, `q`, `status`, `category`, and `priority` query parameters. Task status is `pending`, `in_progress`, `completed`, or `cancelled`; priorities are `low`, `medium`, `high`, or `urgent`.
