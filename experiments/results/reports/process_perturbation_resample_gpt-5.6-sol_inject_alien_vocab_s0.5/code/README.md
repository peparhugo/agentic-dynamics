# Flask URL Shortener

A SQLite-backed URL shortener with a versioned REST API, custom or randomly generated collision-resistant codes, sliding-window rate limiting, expiration, and click analytics.

## Run

```bash
python3 -m pip install -e '.[test]'
flask --app app run
```

Set `DATABASE` to select the SQLite file and `PORT` when running `python3 app.py`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/urls` | Create a link (`url`, optional `custom_code`, optional `expires_at`) |
| `GET` | `/api/v1/urls?limit=20&offset=0` | List links |
| `GET` | `/api/v1/urls/{code}` | Retrieve a link |
| `PATCH` | `/api/v1/urls/{code}` | Change `url`, `expires_at`, or `active` |
| `DELETE` | `/api/v1/urls/{code}` | Delete a link and its analytics |
| `GET` | `/api/v1/urls/{code}/analytics` | Click totals, daily counts, and referrers |
| `GET` | `/{code}` | Record a click and redirect |
| `GET` | `/health` | Health check |

All failures are JSON objects under `error`. Rate-limit state is exposed through `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and, for `429` responses, `Retry-After`.
