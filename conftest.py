import importlib
import os

import pytest

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
