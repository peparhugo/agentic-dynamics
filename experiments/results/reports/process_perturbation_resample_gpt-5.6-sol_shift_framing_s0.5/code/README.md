# Flask URL Shortener

A small URL shortener with SQLite persistence, cryptographically random 72-bit
codes, database-backed fixed-window rate limiting, and click analytics.

## Run

```bash
python -m pip install -r requirements.txt
flask --app app run
```

Set `DATABASE` to choose the SQLite file and `BASE_URL` to the public origin used
in API responses.

## API

Create a short URL:

```bash
curl -X POST http://localhost:5000/api/urls \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/page"}'
```

`GET /<code>` redirects and records a click. `GET /api/urls/<code>` returns the
destination, total click count, last click time, and the 20 most recent clicks.
Rate-limit metadata is returned in `X-RateLimit-*` headers.

## Test

```bash
pytest
```
