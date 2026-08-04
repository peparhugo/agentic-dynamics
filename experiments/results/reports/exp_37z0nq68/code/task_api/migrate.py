"""Database migration script — creates all tables for SQLite."""

import os
import sys

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from config import Config
from flask import Flask

app = Flask(__name__)
app.config.from_object(Config)

from models import db

db.init_app(app)


def migrate():
    with app.app_context():
        db.create_all()
        print("All tables created successfully.")


if __name__ == "__main__":
    migrate()
