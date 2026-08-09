"""Development entry point.

Usage:
    python run.py            # runs migrations, then serves on :5000
"""
from app import create_app
from app.config import Config
from app.db import run_migrations

if __name__ == "__main__":
    run_migrations(Config.DATABASE)
    create_app().run(debug=True)
