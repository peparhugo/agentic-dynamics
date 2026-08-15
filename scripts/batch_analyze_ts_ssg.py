#!/usr/bin/env python3
"""Run analyze_worktrees on just the typescript_ssg worktrees."""
import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import shutil

from analyze_worktrees import (
    REPORTS_DIR,
    analyze_worktree,
    build_baseline_index,
    find_baseline_code,
    load_db_sessions,
    parse_session_title_info,
)

DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")


def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    sessions = db.execute("""
        SELECT id, directory, title, model, cost, tokens_input, tokens_output, tokens_reasoning
        FROM session
        WHERE title LIKE '%typescript_ssg%' AND cost > 0 AND directory LIKE '/tmp/%'
        ORDER BY time_created
    """).fetchall()
    db.close()

    # Only sessions whose worktree exists
    existing = [(s, Path(s["directory"])) for s in sessions if Path(s["directory"]).exists()]
    print(f"Found {len(existing)} existing typescript_ssg worktrees\n")

    # Load all sessions for baseline index
    print("Loading all sessions for baseline index...")
    sessions_by_dir = load_db_sessions()
    worktrees_for_baseline = [{"path": d, "name": Path(d).name, "session": s}
                              for d, s in sessions_by_dir.items()]
    baseline_index = build_baseline_index(worktrees_for_baseline)
    print(f"  {len(baseline_index)} baselines indexed\n")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    failed = []

    for i, (s, wt_path) in enumerate(existing):
        title = s["title"] or ""
        json.loads(s["model"]) if s["model"] else {}
        parse_session_title_info(title)

        baseline_code = find_baseline_code(title, dict(s), baseline_index,
                                           worktree_path=str(wt_path))

        print(f"  [{i+1:2d}/{len(existing)}] {wt_path.name} {title[:60]}")

        try:
            report, metrics = analyze_worktree(
                str(wt_path), dict(s), baseline_code=baseline_code
            )
        except Exception as e:
            print(f"    ERROR: {e}")
            failed.append({"name": wt_path.name, "error": str(e)})
            continue

        if report:
            safe_name = wt_path.name.replace("/", "_")[:60]
            md_path = REPORTS_DIR / f"{safe_name}.md"

            # Build markdown with code quality + narration sections
            md = report.to_markdown()
            ast = metrics.get("ast", {})
            if ast:
                md += "\n\n---\n\n## Code Quality\n\n"
                md += "| Metric | Value |\n|--------|-------|\n"
                for label, key in [
                    ("Python files", "py_files"), ("TS files", "ts_files"),
                    ("TSX files", "tsx_files"), ("JS files", "js_files"),
                    ("Total lines (Py)", "total_lines"), ("Total lines (TS/TSX)", "ts_total_lines"),
                    ("Functions", "total_functions"), ("Classes", "total_classes"),
                    ("Functions/file", "functions_per_file"), ("Classes/file", "classes_per_file"),
                    ("Avg lines/file", "avg_lines_per_file"),
                    ("Type hints", "type_hint_pct"), ("Docstrings", "docstring_pct"),
                    ("Error handlers", "error_handlers"), ("Imports", "imports"),
                    ("Decorators", "decorators"), ("Test files", "test_files"),
                    ("Test file rate", "test_rate"), ("Parse errors", "parse_errors"),
                ]:
                    val = ast.get(key, 0)
                    if isinstance(val, float):
                        val_str = f"{val:.1f}" if key.endswith("_pct") or key.endswith("_rate") else f"{val:.1f}"
                    else:
                        val_str = str(val)
                    if key.endswith("_pct") or key.endswith("_rate"):
                        val_str += "%"
                    if val == 0 and key in ("ts_files", "tsx_files", "js_files", "ts_total_lines"):
                        continue
                    md += f"| {label} | {val_str} |\n"

            if metrics.get("narration_penalty", 0) > 0:
                md += "\n## Narration Assessment\n\n"
                md += f"**Narration penalty:** {metrics['narration_penalty']:.0%}\n\n"
                md += "| Metric | Value |\n|--------|-------|\n"
                md += f"| Output tokens | {s.get('tokens_output', 0):,} |\n"
                md += f"| Python files | {ast.get('py_files', 0)} |\n"
                md += f"| Non-Python files | {metrics.get('non_python_files', 0)} |\n"
                md += f"| Code density | {metrics.get('code_density', 0):.4f} LOC/tok |\n"
                if metrics.get("narration_failure"):
                    md += "| **Verdict** | **NARRATION FAILURE** |\n"
                elif metrics.get("is_frontend"):
                    md += "| **Verdict** | **FRONTEND WORKTREE** |\n"
                else:
                    md += "| **Assessment** | Low code density |\n"
                md += "\n"

            md_path.write_text(md)

            # Copy artifacts
            artifact_path = REPORTS_DIR / safe_name
            skip_dirs = {"__pycache__", ".git", "venv", ".venv", "env",
                         "site-packages", "node_modules", ".mypy_cache",
                         ".pytest_cache", "dist", "build", "Lib", "lib",
                         "include", ".instrument"}
            file_count = 0
            for item in wt_path.rglob("*"):
                if item.is_file() and not (skip_dirs & set(item.parts)) \
                        and not item.name.startswith("."):
                    rel = item.relative_to(wt_path)
                    dest = artifact_path / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(item, dest)
                        file_count += 1
                    except Exception:
                        pass

            results.append(metrics)
            strat = metrics.get("strategy", "?")
            print(f"    -> {safe_name}.md  cor={metrics.get('correctness',0):.0%} "
                  f"esc={metrics.get('escape',0):.2f} strat={strat} cost=${metrics.get('cost',0):.4f}")
        else:
            err = metrics.get("error", "unknown") if metrics else "unknown"
            failed.append({"name": wt_path.name, "error": err})
            print(f"    FAILED: {err}")

    print(f"\n{'='*60}")
    print("COMPLETE")
    print(f"  Generated:  {len(results)} game reports")
    print(f"  Failed:     {len(failed)}")
    print(f"  Reports dir: {REPORTS_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
