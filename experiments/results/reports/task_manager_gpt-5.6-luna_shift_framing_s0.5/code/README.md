# Task Management API

## Run

```bash
pip install -r requirements.txt
flask --app run:app init-db  # or run `python run.py`
```

The API uses SQLite and stores the database at `task_manager.sqlite3` by default. Set `DATABASE` and `SECRET_KEY` in the environment for deployment.

Endpoints are rooted at `/api`: register/login under `/auth`, and authenticated task CRUD under `/tasks`. Send `Authorization: Bearer <token>`. List tasks supports `page`, `per_page`, `search`, `status`, `category`, and `priority`.
