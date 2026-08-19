from app import create_app
from app.models import Category, Task, User

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {"db": __import__("app.extensions", fromlist=["db"]).db,
            "User": User, "Category": Category, "Task": Task}


if __name__ == "__main__":
    app.run(debug=True)
