# URL Shortener

A Flask REST API backed by SQLite. Short codes use 48 bits of cryptographic randomness by default, with database uniqueness enforcement and collision retries.

## Run

```bash
python3 -m pip install -r requirements.txt
flask --app app run
```

## API

- `POST /api/urls` with `{"url":"https://example.com"}` creates a short URL.
- `GET /<code>` records a click and redirects.
- `GET /api/urls/<code>` returns URL metadata and the click count.
- `GET /api/urls/<code>/analytics` returns click events and unique visitor totals.
- `DELETE /api/urls/<code>` deletes the URL and its analytics.

Creation is rate-limited per client IP. Configure the database, code length, and rate limit through the Flask app factory configuration.

## Test

```bash
pytest
```
