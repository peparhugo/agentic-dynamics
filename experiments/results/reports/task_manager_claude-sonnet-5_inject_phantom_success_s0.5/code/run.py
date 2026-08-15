from app import create_app
from app.extensions import db

app = create_app()


@app.shell_context_processor
def make_shell_context():
    from app.models import Category, Task, User

    return {"db": db, "User": User, "Task": Task, "Category": Category}


if __name__ == "__main__":
    app.run(debug=True)
