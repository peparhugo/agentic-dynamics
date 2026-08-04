# Flask JWT API

A versioned REST API with JWT authentication, request validation, pagination,
fixed-window IP rate limiting, structured JSON errors, and in-memory audit logging.

## Run

```bash
python3 -m pip install -r requirements.txt
export JWT_SECRET="a-long-random-production-secret"
flask --app wsgi run
```

Run tests with `python3 -m pytest`.

## Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET|POST /api/v1/items`
- `GET|DELETE /api/v1/items/<id>`
- `GET /api/v1/audit-logs`

Protected endpoints require `Authorization: Bearer <token>`. The application uses
in-memory storage by design; use durable shared stores for data, audit records,
and distributed rate limits in production.
