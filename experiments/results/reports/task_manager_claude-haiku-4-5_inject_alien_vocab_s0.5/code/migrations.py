"""
Database migrations and initialization script for Task Management System.

This script initializes the database schema with all required tables.
Run this after first deployment or when setting up a new environment.
"""

from app import create_app
from models import db, User, Category, Priority, Task
from datetime import datetime

def init_db():
    """Initialize database with all tables and default data."""
    app = create_app()
    with app.app_context():
        db.create_all()
        print("✓ All tables created successfully")

        seed_db()

def seed_db():
    """Add default categories and priorities."""
    app = create_app()
    with app.app_context():
        existing_categories = Category.query.first()
        existing_priorities = Priority.query.first()

        if not existing_categories:
            default_categories = [
                Category(name='Work', description='Work-related tasks'),
                Category(name='Personal', description='Personal tasks'),
                Category(name='Shopping', description='Shopping and errands'),
                Category(name='Health', description='Health and fitness related'),
                Category(name='Learning', description='Educational and learning tasks'),
            ]
            db.session.add_all(default_categories)
            print("✓ Default categories added")

        if not existing_priorities:
            default_priorities = [
                Priority(name='Critical', level=1),
                Priority(name='High', level=2),
                Priority(name='Medium', level=3),
                Priority(name='Low', level=4),
            ]
            db.session.add_all(default_priorities)
            print("✓ Default priorities added")

        db.session.commit()

def reset_db():
    """Drop all tables and reinitialize."""
    app = create_app()
    with app.app_context():
        db.drop_all()
        print("✓ All tables dropped")
        init_db()

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'reset':
        reset_db()
    else:
        init_db()
