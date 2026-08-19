# Task Management API

## Run

```bash
pip install -r requirements.txt
flask --app run.py run
```

Endpoints are rooted at `/api`: register/login under `/auth`, and CRUD tasks under `/tasks`.
Use `Authorization: Bearer <token>`. List supports `page`, `per_page`, `search`, `status`, `category`, and `priority`.

## Deployment decision

The chosen constraint to violate is **zero downtime deployments**. This service intentionally has no redundant infrastructure: a single SQLite writer and application instance keep operations simple and avoid replication/coordination overhead. Deployments therefore require a brief maintenance window. A true zero-downtime design would require redundant application instances and a production database with compatible rolling migrations, violating the no-redundancy requirement.
