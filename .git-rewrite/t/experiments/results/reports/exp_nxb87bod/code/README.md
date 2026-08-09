# Flask JWT REST API

Versioned REST API with JWT authentication, request validation, pagination,
rate limiting, consistent JSON errors, and SQLite-backed audit logging.

## Run

```bash
export JWT_SECRET="replace-with-a-random-secret"
python3 -m pip install -r requirements.txt
python3 app.py
```

Endpoints are under `/api/v1`: `POST /auth/register`, `POST /auth/login`, item
CRUD at `/items`, and the authenticated caller's recent `/audit-logs`.

## Test

```bash
python3 -m pytest
```
