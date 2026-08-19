# Flask URL Shortener

A persistent URL shortener with random Base62 codes, SQLite-backed fixed-window
rate limiting, redirects, and click analytics.

## Run

```bash
python -m pip install -r requirements.txt
flask --app app run
```

The database defaults to `instance/shortener.sqlite`.

## API

Create a short URL (limited to 10 requests per client IP per minute):

```bash
curl -X POST http://localhost:5000/api/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/article"}'
```

The response has status `201` and includes `code`, `short_url`, `url`, and
`created_at`. Visit `GET /<code>` to record a click and receive a `302`
redirect. Read aggregate and the 20 most recent click records with
`GET /api/urls/<code>/stats`.

Errors use the shape `{"error":{"message":"...","status":400}}`. A `429`
response also includes `Retry-After` and `X-RateLimit-*` headers.
