# Flask URL Shortener

A SQLite-backed URL shortener with a REST API, collision-free seven-character
codes, persistent fixed-window rate limiting, and click analytics.

## Run

```bash
python -m pip install -r requirements.txt
flask --app app run
```

The default database is `instance/shortener.sqlite3`. Relevant configuration
keys are `DATABASE`, `RATE_LIMIT` (default 60), `RATE_LIMIT_WINDOW` in seconds
(default 60), and `TRUST_PROXY` (enable only behind a trusted reverse proxy).

## API

Create a short URL:

```bash
curl -X POST http://localhost:5000/api/urls \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/article"}'
```

`GET /<code>` records a click and redirects. `GET /api/urls/<code>` returns
the total click count, unique visitor count, latest click time, and 20 most
recent click records. `GET /health` is an unthrottled health check.

## Test

```bash
pytest
```
