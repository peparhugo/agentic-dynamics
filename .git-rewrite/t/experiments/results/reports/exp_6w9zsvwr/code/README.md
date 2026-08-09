# URL Shortener

A Flask and SQLite URL shortener with collision-resistant eight-character codes,
per-IP creation rate limits, and redirect analytics.

## Run

```bash
python3 -m pip install -r requirements.txt
flask --app run run
```

The database is created at `instance/shortener.sqlite3` by default.

## API

- `POST /api/urls` with `{"url": "https://example.com"}` creates a short URL.
- `GET /api/urls/<code>` returns URL metadata and its click count.
- `DELETE /api/urls/<code>` deletes the URL and its analytics.
- `GET /api/urls/<code>/analytics?limit=50` returns click analytics.
- `GET /<code>` records a click and redirects to the original URL.

Run tests with `pytest`.
