# Versioned Flask API

Authenticated REST API with JWT authentication, validation, pagination, rate limiting, structured errors, and audit logging.

Set `JWT_SECRET`, `API_USERNAME`, and `API_PASSWORD` before production use. Optional settings are `JWT_TTL_SECONDS`, `RATE_LIMIT`, and `RATE_WINDOW_SECONDS`.

```bash
python3 -m pip install -r requirements-dev.txt
flask --app app run
pytest
```

Create a token with `POST /api/v1/auth/token`, then pass it as `Authorization: Bearer <token>` to `/api/v1/items` routes.
