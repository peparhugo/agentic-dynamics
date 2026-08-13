# Empty conftest so pytest adds the repository root to sys.path,
# making `server` importable from the tests.

import os
import tempfile

# Isolate message-history persistence to a temporary SQLite file so tests
# never create or pollute a database inside the repository.
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.path.join(
        tempfile.gettempdir(), f"test_messages_{os.getpid()}.db"
    )
