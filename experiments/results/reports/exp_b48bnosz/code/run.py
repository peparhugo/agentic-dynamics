"""Development entrypoint: `python run.py` or `flask --app run run`."""
import os

from app import create_app

app = create_app(os.environ.get("FLASK_CONFIG", "default"))

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
