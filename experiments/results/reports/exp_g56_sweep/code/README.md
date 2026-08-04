# Versioned Flask REST API

An authenticated `/v1` REST API with JWT access tokens, rotating persisted refresh tokens, login rate limiting, validation, pagination, owner-scoped resources, and mutation audit logs.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 wsgi.py
```

Set `JWT_SECRET` and `DATABASE_URL` through an application config object when deploying. The built-in defaults are intended only for local development.

## Endpoints

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `POST /v1/auth/logout`
- `GET, POST /v1/items`
- `GET, PATCH, DELETE /v1/items/<id>`
- `GET /v1/audit-logs`
- `GET /v1/health`

Protected endpoints accept `Authorization: Bearer <access_token>`. List endpoints accept `page` and `per_page`; defaults are 1 and 20, with a maximum page size of 100.

## Test

```bash
python3 -m pytest
```
