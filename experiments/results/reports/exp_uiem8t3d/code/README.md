# Flask JWT REST API

An API-versioned Flask service with JWT authentication, validation, pagination,
rate limiting, consistent JSON errors, and structured audit logging.

## Run

```bash
python3 -m pip install -r requirements.txt
flask --app app run
```

Endpoints are under `/api/v1`: register and log in through `/auth/register` and
`/auth/login`, then use the returned Bearer token with the `/items` CRUD routes.
Set `JWT_SECRET` through application configuration to a strong secret in deployed
environments.

## Test

```bash
pytest
```
