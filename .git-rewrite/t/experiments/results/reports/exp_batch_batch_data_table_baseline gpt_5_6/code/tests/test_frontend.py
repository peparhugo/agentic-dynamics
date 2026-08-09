from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_production_build_succeeds():
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_virtualization_is_bounded_to_visible_window():
    source = read("src/DataGrid.tsx")
    assert "OVERSCAN" in source
    assert "rows.slice(startIndex, endIndex)" in source
    assert "rows.length * ROW_HEIGHT" in source


def test_grid_has_accessible_semantics_and_keyboard_navigation():
    source = read("src/DataGrid.tsx")
    for contract in (
        'role="grid"',
        'role="columnheader"',
        'role="gridcell"',
        "aria-rowcount",
        "aria-multiselectable",
        "ArrowDown",
        "ArrowRight",
        "Home",
        "End",
    ):
        assert contract in source


def test_full_scale_demo_and_column_count():
    app = read("src/App.tsx")
    data = read("src/data.ts")
    assert "makeRows(100_000)" in app
    assert "length: 42" in data
    assert "...Array.from" in data


def test_sort_filter_selection_and_editing_are_implemented():
    grid = read("src/DataGrid.tsx")
    app = read("src/App.tsx")
    assert "sortRules" in grid and "event.shiftKey" in grid
    assert "selectionMode" in grid and "setSelected" in grid
    assert "commitEdit" in grid and "cell-editor" in grid
    assert "filterMode === 'server'" in app and "useDeferredValue" in app


def test_csv_and_excel_exports_are_available():
    source = read("src/export.ts")
    assert "exportCsv" in source
    assert "exportExcel" in source
    assert "text/csv" in source
    assert "application/vnd.ms-excel" in source
