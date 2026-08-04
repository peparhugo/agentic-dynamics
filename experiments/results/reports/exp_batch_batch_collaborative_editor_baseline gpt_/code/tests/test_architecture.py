from pathlib import Path


ROOT = Path(__file__).parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_all_required_frontend_entrypoints_exist():
    required = [
        "package.json",
        "index.html",
        "src/main.tsx",
        "src/App.tsx",
        "src/styles.css",
        "ARCHITECTURE.md",
    ]
    assert all((ROOT / path).is_file() for path in required)


def test_crdt_realtime_and_offline_layers_are_configured():
    session = read("src/collaboration/session.ts")
    assert "new Y.Doc()" in session
    assert "WebsocketProvider" in session
    assert "IndexeddbPersistence" in session
    assert "awareness" in session
    assert "provider.connect()" in session


def test_editor_uses_collaborative_cursor_and_local_origin_undo():
    editor = read("src/hooks/useCollaborativeEditor.ts")
    architecture = read("ARCHITECTURE.md")
    assert "CollaborationCursor" in editor
    assert "history: false" in editor
    assert "Collaboration.configure" in editor
    assert "scoped to the local client origin" in architecture


def test_comments_use_crdt_relative_positions():
    comments = read("src/collaboration/comments.ts")
    assert "absolutePositionToRelativePosition" in comments
    assert "relativePositionToAbsolutePosition" in comments
    assert "Y.encodeRelativePosition" in comments
    assert "session.comments.push" in comments


def test_required_ui_surfaces_are_present():
    app = read("src/App.tsx")
    assert "Toolbar" in app
    assert "CommentsPanel" in app
    assert "VersionPanel" in app
    assert "Presence" in app
