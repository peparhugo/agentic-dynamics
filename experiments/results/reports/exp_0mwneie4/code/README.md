# Flask JWT REST API

Versioned REST API providing JWT authentication, owner-scoped item CRUD, pagination,
input validation, rate limiting, consistent JSON errors, and SQLite audit logging.

## Run

```bash
pip install -r requirements.txt
flask --app 'app:create_app()' run
```

Set a strong `SECRET_KEY` and production database path through the application config
before deployment.

## Test

```bash
pytest
```
