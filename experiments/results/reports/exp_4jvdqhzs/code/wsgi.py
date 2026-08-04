import os

from app import create_app


app = create_app({"JWT_SECRET": os.environ.get("JWT_SECRET", "change-me-in-production")})
