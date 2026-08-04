# Versioned Flask API

An authenticated REST API with HS256 JWT authentication, input validation,
pagination, rate limiting, structured errors, and audit logging.

## Run

Set secure production values for `JWT_SECRET` and `USERS` in the app config.

```bash
flask --app 'app:create_app()' run
pytest
```

Create a token with `POST /api/v1/auth/token`, then send it as
`Authorization: Bearer <token>` when using `/api/v1/items`.
