# URL Shortener

A Flask and SQLite URL shortener with cryptographically random short codes, per-IP creation rate limiting, and click analytics.

## Run

```bash
python3 -m pip install -r requirements.txt
flask --app app run
```

Set `DATABASE` to choose the SQLite file and `PORT` when running `python3 app.py`.

## API

- `POST /api/urls` with JSON `{"url": "https://example.com"}` creates a short URL.
- `GET /api/urls/<code>` returns its metadata.
- `GET /api/urls/<code>/analytics` returns the click count and events.
- `DELETE /api/urls/<code>` deletes it and its analytics.
- `GET /<code>` records a click and redirects to the target.

Creation is limited to 10 requests per client IP per minute by default. Codes contain 48 bits of cryptographic randomness, and database uniqueness is retried on collision.

## Test

```bash
pytest
```
