# Flask JWT API

Versioned REST API with JWT authentication, validation, pagination, rate limiting, JSON error responses, and SQLite audit logging.

```bash
python3 -m pip install -r requirements.txt
export JWT_SECRET="a-long-random-production-secret"
python3 app.py
python3 -m pytest
```

Routes are under `/api/v1`: `POST /auth/register`, `POST /auth/login`, and authenticated CRUD at `/items`. Send JWTs as `Authorization: Bearer <token>`.
