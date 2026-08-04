"""Development entry point: `python run.py`."""
import os

from app import create_app

app = create_app(os.environ.get("APP_ENV", "dev"))

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
