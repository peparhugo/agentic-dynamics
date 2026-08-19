import os

from url_shortener import create_app


app = create_app(
    {
        "DATABASE": os.environ.get("DATABASE", "instance/shortener.sqlite3"),
        "BASE_URL": os.environ.get("BASE_URL"),
    }
)


if __name__ == "__main__":
    app.run()
