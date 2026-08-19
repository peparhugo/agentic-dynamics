import os

from urlshortener import create_app


app = create_app({"DATABASE": os.environ.get("DATABASE", "shortener.sqlite3")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
