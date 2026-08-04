# Flask JWT API

Versioned REST API with JWT authentication, owner-scoped item CRUD, validation,
pagination, fixed-window rate limiting, JSON errors, and structured audit logs.

## Run

```bash
python3 -m pip install -r requirements.txt
JWT_SECRET='replace-with-a-random-secret' flask --app run run
```

Routes are under `/api/v1`. Register at `/api/v1/auth/register`, log in at
`/api/v1/auth/login`, and send the returned token as `Authorization: Bearer TOKEN`.

## Test

```bash
python3 -m pytest
```
