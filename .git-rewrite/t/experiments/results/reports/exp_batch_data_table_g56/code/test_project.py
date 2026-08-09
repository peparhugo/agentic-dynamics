from pathlib import Path


ROOT = Path(__file__).parent
COMPONENT = (ROOT / "src" / "DataTable.tsx").read_text()


def test_react_typescript_project_is_complete():
    for path in ["package.json", "tsconfig.json", "index.html", "src/main.tsx", "src/index.ts"]:
        assert (ROOT / path).is_file()


def test_virtualizes_rows():
    assert "visibleRows = processedRows.slice" in COMPONENT
    assert "firstVisible" in COMPONENT and "overscan" in COMPONENT


def test_sorting_and_filter_modes_exist():
    assert 'sortMode?: "client" | "server"' in COMPONENT
    assert 'filterMode?: "client" | "server"' in COMPONENT
    assert "deferredFilters" in COMPONENT


def test_selection_modes_and_ranges_exist():
    assert 'selectionMode?: "none" | "single" | "multi"' in COMPONENT
    assert "selectionAnchor" in COMPONENT


def test_edit_resize_and_reorder_exist():
    assert "commitEdit" in COMPONENT
    assert "beginResize" in COMPONENT
    assert "reorderColumn" in COMPONENT


def test_exports_csv_and_excel():
    assert 'exportRows("csv")' in COMPONENT
    assert 'exportRows("excel")' in COMPONENT


def test_keyboard_navigation_exists():
    for key in ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"]:
        assert key in COMPONENT


def test_accessibility_semantics_exist():
    for token in ['role="grid"', 'role="row"', 'role="columnheader"', 'aria-live="polite"']:
        assert token in COMPONENT
