# Task Management API

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app run run
```

Set `SECRET_KEY` and `DATABASE` in production. The database migration is applied automatically at startup; it can also be invoked with `app.init_db()`.

## API

Register at `POST /api/auth/register` with `username`, `email`, and an 8+ character `password`. Login at `POST /api/auth/login`; send the returned token as `Authorization: Bearer <token>`.

Authenticated task endpoints are `GET/POST /api/tasks` and `GET/PUT/PATCH/DELETE /api/tasks/<id>`. Task listing supports `page`, `per_page`, `search` (or `q`), `status`, `category`, and `priority`. Task status is `todo`, `in_progress`, or `completed`; priority is `low`, `medium`, `high`, or `urgent`.
