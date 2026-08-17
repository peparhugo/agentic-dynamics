from task_api import create_app
from task_api.db import migrate


app = create_app()
with app.app_context():
    migrate()
    print("Database migrations are up to date.")
