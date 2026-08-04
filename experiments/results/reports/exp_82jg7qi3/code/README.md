# Flask JWT API

Versioned REST API with JWT authentication, per-client rate limiting, strict JSON validation, paginated resources, consistent JSON errors, and persisted audit logs.

## Run

```bash
python3 -m pip install -r requirements.txt
export JWT_SECRET="a-long-random-production-secret"
flask --app app:create_app run
```

The API is rooted at `/api/v1`. Main endpoints are `/auth/register`, `/auth/login`, `/items`, and `/audit-logs`.

## Test

```bash
python3 -m pytest
```
