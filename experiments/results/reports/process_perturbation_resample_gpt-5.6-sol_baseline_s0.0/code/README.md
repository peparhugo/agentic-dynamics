# Flask URL Shortener

Install and run:

```sh
python -m pip install -e '.[test]'
flask --app app run
```

`POST /api/urls` accepts `{"url": "https://example.com"}` and an optional
`custom_code`. `GET /<code>` redirects and records a click. Analytics are
available from `GET /api/urls/<code>`, and `DELETE /api/urls/<code>` removes a
URL and its click history.

Storage defaults to `shortener.sqlite3`. Configure it with
`URL_SHORTENER_DATABASE`; configure request limits with
`URL_SHORTENER_RATE_LIMIT` and `URL_SHORTENER_RATE_WINDOW` (seconds).
