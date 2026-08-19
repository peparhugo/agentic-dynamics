"""WSGI entrypoint for production servers (e.g. gunicorn shortener.wsgi:app)."""

from shortener import create_app

app = create_app()
