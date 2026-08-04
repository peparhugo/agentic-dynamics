import os

from app import create_app


app = create_app(
    {
        "JWT_SECRET": os.environ.get("JWT_SECRET", "change-this-secret-in-production"),
    }
)


if __name__ == "__main__":
    app.run()
