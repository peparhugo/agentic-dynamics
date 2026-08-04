#!/usr/bin/env python3
"""Post-hoc analysis of experiment worktrees — generate Game Reports from existing sessions.

Problem: 95% of experiment sessions were run via batch/sweep scripts that only collected
raw cost/token data from the opencode DB. They never ran the analysis pipeline (solution
evaluation, basin escape, strategy classification, game reports).

This script fills that gap. It takes existing worktree directories, reads the generated
code, runs the full analysis stack, and produces GameReport markdown files.

Usage:
  python scripts/analyze_worktrees.py                    # analyze all experiment worktrees
  python scripts/analyze_worktrees.py --worktree /tmp/exp_xyz  # analyze one worktree
  python scripts/analyze_worktrees.py --limit 5           # analyze first 5
  python scripts/analyze_worktrees.py --dry-run            # show what would be analyzed
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from instrument import (
    evaluate_solution, compute_efficiency, measure_basin_escape,
    classify_strategy, GameReport, SolutionMetrics, EfficiencyMetrics, BasinMetrics,
    StrategyReport, analyze_ast,
)

OPENSCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"
REPORTS_DIR = RESULTS_DIR / "reports"
CONFIGS_DIR = PROJECT_ROOT / "experiments" / "configs"
TEST_VENV = Path("/tmp/pytest_venv")
PYTEST_DEPS = ["flask", "pytest", "sqlalchemy", "flask-jwt-extended", "flask-limiter",
               "flask-cors", "flask-migrate"]

run_tests_enabled = False
_test_venv_ready = False


def ensure_test_venv():
    """Create or reuse a shared venv for pytest across all worktrees."""
    global _test_venv_ready
    if _test_venv_ready:
        return
    if not TEST_VENV.exists():
        import venv as _venv
        _venv.create(str(TEST_VENV), with_pip=True)
    import subprocess as _sp
    pip = str(TEST_VENV / "bin" / "pip")
    _sp.run([pip, "install", "-q"] + PYTEST_DEPS, capture_output=True, timeout=60)
    _test_venv_ready = True


def run_pytest(worktree_path: str, timeout_sec: int = 15) -> dict:
    """Run pytest in a worktree using the shared venv."""
    import subprocess as _sp
    p = Path(worktree_path)
    if not p.exists():
        return {"ok": False, "error": "worktree missing"}

    test_dirs = list(p.rglob("tests"))
    test_files = list(p.rglob("test_*.py"))
    if not test_dirs and not test_files:
        return {"ok": False, "error": "no test files"}

    python = str(TEST_VENV / "bin" / "python")
    t0 = time.monotonic()
    try:
        r = _sp.run(
            [python, "-m", "pytest", "-q", "--tb=no"],
            cwd=str(p), capture_output=True, text=True,
            timeout=timeout_sec,
        )
        dur = time.monotonic() - t0
        out = r.stdout + r.stderr

        import re
        passed = int(re.search(r'(\d+)\s+passed', out).group(1)) if re.search(r'(\d+)\s+passed', out) else 0
        failed = int(re.search(r'(\d+)\s+failed', out).group(1)) if re.search(r'(\d+)\s+failed', out) else 0
        errors = int(re.search(r'(\d+)\s+error', out).group(1)) if re.search(r'(\d+)\s+error', out) else 0
        total = passed + failed

        return {
            "ok": total > 0,
            "passed": passed, "failed": failed, "errors": errors,
            "total": total, "duration_s": round(dur, 1),
            "pass_rate": round(passed / max(total, 1), 3) if total > 0 else 0,
        }
    except _sp.TimeoutExpired:
        return {"ok": False, "error": f"timeout {timeout_sec}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:60]}


# ── Utility ──────────────────────────────────────────────────────────────────

def _fmt_usd(v): return f"${v:,.4f}" if v is not None else "—"
def _fmt_int(v): return f"{v:,}" if v is not None else "—"


def _now(): return datetime.now(timezone.utc).isoformat()


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_db_sessions():
    """Load all sessions with cost data from the opencode DB."""
    if not OPENSCODE_DB.exists():
        print("Error: opencode DB not found at", OPENSCODE_DB)
        return []
    db = sqlite3.connect(str(OPENSCODE_DB))
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT id, directory, title, cost, tokens_input, tokens_output, tokens_reasoning,
               tokens_cache_read, tokens_cache_write,
               json_extract(model, '$.providerID') as provider,
               json_extract(model, '$.id') as model_id,
               time_created
        FROM session WHERE cost > 0 OR tokens_output > 0
        ORDER BY time_created
    """).fetchall()
    db.close()
    return {s["directory"]: dict(s) for s in rows if s["directory"]}


def load_config_constraints(config_name: str) -> list[str]:
    """Load constraints from a YAML config file."""
    config_path = CONFIGS_DIR / config_name
    if not config_path.exists():
        return []
    try:
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return data.get("constraints", [])
    except Exception:
        return []


def read_worktree_code(worktree_path: str) -> str:
    """Concatenate project code files in a worktree.
    
    Reads .py files first. If none found, falls back to .html/.js/.css for frontend worktrees.
    """
    p = Path(worktree_path)
    if not p.exists():
        return ""
    code_parts = []
    skip_dirs = {"__pycache__", ".git", "venv", ".venv", "env", "site-packages",
                 "node_modules", ".mypy_cache", ".pytest_cache", "dist", "build",
                 "Lib", "lib", "include"}
    for f in sorted(p.rglob("*.py")):
        parts = set(f.parts)
        if parts & skip_dirs:
            continue
        try:
            content = f.read_text(errors="replace")
            if content.strip() and len(content) > 20:
                rel = f.relative_to(p)
                code_parts.append(f"# {rel}\n{content}")
        except Exception:
            pass
        if len(code_parts) > 200:  # safety cap: don't read 1000+ files
            break
    return "\n\n".join(code_parts)


DEFAULT_CONSTRAINTS = [
    "JWT auth with refresh tokens",
    "Rate limiting on login endpoint",
    "Input validation on all endpoints",
    "Paginated list responses",
    "Error handling with proper HTTP status codes",
    "Audit logging of mutations",
    "API versioning via URL prefix",
]


def infer_constraints(worktree_path: str, title: str = "") -> list[str]:
    """Infer constraints from worktree contents or session title."""
    constraints = DEFAULT_CONSTRAINTS.copy()

    t = (title or worktree_path).lower()
    if "url_shortener" in t or "url shortener" in t:
        constraints = [
            "REST API with CRUD endpoints",
            "URL shortening with hash generation",
            "Redirect handling",
            "Analytics/stats tracking",
            "Rate limiting",
            "Input validation",
        ]
    elif "data_table" in t or "data table" in t:
        constraints = [
            "Sortable data table component",
            "Pagination with page/limit controls",
            "Filter/search functionality",
            "Responsive design",
        ]
    elif "collaborat" in t or "editor" in t:
        constraints = [
            "Real-time collaborative editing",
            "Conflict resolution / OT",
            "User presence tracking",
            "Auto-save and persistence",
        ]

    return constraints


def parse_session_title_info(title: str) -> dict:
    """Extract experiment and model metadata from session title.
    
    Returns: {experiment, operator, silent_mode, model_short}
    """
    info = {"experiment": "", "operator": "baseline", "silent_mode": "natural",
            "model_short": ""}
    t = title or ""

    bracket_tags = re.findall(r'\[([^\]]+)\]', t)
    if bracket_tags:
        first_tag = bracket_tags[0]
        parts = first_tag.split(":")

        if len(parts) == 1:
            tag = parts[0]
            if "baseline" in tag:
                info["operator"] = "baseline"
            elif any(k in tag for k in ["inject_", "remove_", "invert_", "shift_",
                                          "alien_", "false_", "competing", "phantom",
                                          "force_", "reverse_", "probe", "std_",
                                          "standardized", "perturbed"]):
                info["operator"] = "perturbed"
                info["experiment"] = tag
        elif len(parts) >= 2:
            info["experiment"] = parts[1]
            if len(parts) >= 3:
                info["operator"] = parts[2] if parts[2] in ("baseline", "perturbed") else "baseline"
            if "forced" in first_tag:
                info["silent_mode"] = "forced-silent"
            elif "natural" in first_tag:
                info["silent_mode"] = "natural"

    after_brackets = re.sub(r'\[[^\]]+\]\s*', '', t).strip()
    info["model_short"] = after_brackets

    if not info["experiment"]:
        for pattern, exp_name in [
            ("task_manage", "task_manager"), ("task manager", "task_manager"),
            ("task api", "task_manager"), ("collaborative", "collaborative_editor"),
            ("data_table", "data_table"), ("data table", "data_table"),
            ("url_shortener", "url_shortener"), ("url shortener", "url_shortener"),
            ("silent_sweep", "silent_sweep"),
        ]:
            if pattern in t.lower():
                info["experiment"] = exp_name
                break

    return info


# ── Analysis ─────────────────────────────────────────────────────────────────

def analyze_worktree(worktree_path: str, session: dict = None, baseline_code: str = "",
                     config_name: str = ""):
    """Run the full analysis pipeline on a single worktree.

    Returns:
        (GameReport, dict of metrics) or (None, error_dict)
    """
    global run_tests_enabled
    wt = Path(worktree_path)
    if not wt.exists():
        return None, {"error": "worktree not found"}

    # Read code
    code = read_worktree_code(worktree_path)
    if not code:
        return None, {"error": "no Python files found",
                        "narration_failure": True}

    # Session metadata
    title = session.get("title", "") if session else ""
    info = parse_session_title_info(title)

    # Constraints
    constraints = infer_constraints(worktree_path, title)
    if config_name:
        config_constraints = load_config_constraints(config_name)
        if config_constraints:
            constraints = config_constraints

    # ── Solution Evaluation ──
    solution = evaluate_solution(code, constraints, baseline_code=baseline_code)

    # ── Code Density Check — detect narration without code ──
    import ast
    real_code_lines = 0
    has_functions = False
    total_code_files = 0
    non_python_files = 0
    for f in Path(worktree_path).rglob("*"):
        if f.is_dir() or "__pycache__" in str(f) or ".git" in f.parts:
            continue
        if f.suffix in (".html", ".js", ".jsx", ".css", ".ts", ".tsx", ".json"):
            non_python_files += 1
            try:
                content = f.read_text(errors="replace")
                lines = [l for l in content.split("\n") if l.strip()]
                real_code_lines += len(lines)
            except: pass
        elif f.suffix == ".py":
            total_code_files += 1
            try:
                content = f.read_text(errors="replace")
                lines = [l for l in content.split("\n") if l.strip() 
                        and not l.strip().startswith("#")]
                real_code_lines += len(lines)
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
                        has_functions = True
            except Exception:
                pass

    output_tok = session.get("tokens_output", 0) or 0 if session else 0
    code_density = real_code_lines / max(output_tok, 1)
    narration_penalty = 0.0
    narration_failure = False
    is_frontend = False

    if total_code_files == 0 and non_python_files == 0:
        # Codeless: zero files of any kind = pure narration failure
        narration_failure = True
        narration_penalty = 1.0
    elif total_code_files == 0 and non_python_files > 0:
        # Frontend/browser worktree: HTML/JS but no Python
        is_frontend = True
    elif output_tok > 200 and not has_functions and total_code_files > 0:
        narration_failure = True
        narration_penalty = 0.5
    elif output_tok > 500 and code_density < 0.05:
        narration_penalty = 0.3
    elif output_tok > 1000 and code_density < 0.03:
        narration_penalty = 0.2

    if narration_penalty > 0:
        solution.correctness_score = max(0, solution.correctness_score - narration_penalty)
        solution.composite_score = (
            0.35 * solution.correctness_score
            + 0.30 * solution.constraint_score
            + 0.20 * solution.code_quality_score
            + 0.15 * solution.novelty_score
        )
        solution.constraints_met = 0
        solution.constraint_score = 0.0

    # ── Efficiency ──
    prompt_tok = session.get("tokens_input", 0) or 0 if session else 0
    completion_tok = session.get("tokens_output", 0) or 0 if session else 0
    reasoning_tok = session.get("tokens_reasoning", 0) or 0 if session else 0
    total_tok = prompt_tok + completion_tok + reasoning_tok

    # Use DB cost if available, otherwise estimate
    db_cost = session.get("cost", 0) or 0 if session else 0
    efficiency = compute_efficiency(
        prompt_tokens=prompt_tok, completion_tokens=completion_tok,
        reasoning_tokens=reasoning_tok, total_tokens=total_tok,
        solution=solution,
    )
    if db_cost > 0:
        efficiency.total_cost_usd = db_cost

    # ── Basin Escape ──
    pert_class = "manifold" if any(k in info.get("operator", "") for k in
                                   ["alien_vocab", "shift_framing", "reverse_causality",
                                    "force_abandonment"]) else "semantic"
    basin = measure_basin_escape(
        baseline_code=baseline_code or code,  # self-comparison if no baseline
        perturbed_code=code,
        baseline_correctness=solution.correctness_score,
        perturbed_correctness=solution.correctness_score,
        baseline_constraints_met=solution.constraints_met,
        perturbed_constraints_met=solution.constraints_met,
        baseline_loc=solution.lines_of_code,
        perturbed_loc=solution.lines_of_code,
        prompt_tokens=prompt_tok,
        completion_tokens=completion_tok,
        reasoning_tokens=reasoning_tok,
        perturbation_operator=info.get("operator", "baseline"),
        perturbation_class=pert_class,
        perturbation_strength=0.5,
        model=session.get("model_id", "") if session else "",
    )

    # ── Strategy ──
    strategy = classify_strategy(basin, solution, efficiency, pert_class)

    # ── AST Profiling ──
    ast_profile = ast_profile_worktree(worktree_path)
    ast_comparison = None
    if baseline_code and code:
        ast_comparison = analyze_ast(baseline_code, code,
                                     operator=info.get("operator", ""),
                                     perturbation_class=pert_class)

    # ── Test Results (if --run-tests) ──
    test_results = None
    if run_tests_enabled:
        test_results = run_pytest(worktree_path)
        if test_results.get("ok") and test_results.get("total", 0) > 0:
            solution.tests_passed = test_results["passed"]
            solution.tests_total = test_results["total"]
            solution.correctness_score = test_results["pass_rate"]

    # ── Game Report ──
    experiment_id = info.get("experiment", wt.name) or wt.name
    report = GameReport(
        experiment_id=f"{experiment_id}-{info.get('operator', '?')}",
        model=str(session.get("provider", "") or "") + "/" + str(session.get("model_id", "") or "")
               if session and (session.get("provider") or session.get("model_id")) else wt.name,
        task=title[:200] if title else str(wt.name),
        operator=info.get("operator", "baseline"),
        perturbation_class=pert_class,
        reasoning=basin, solution=solution, efficiency=efficiency,
        strategy=strategy,
    )

    return report, {
        "experiment": experiment_id,
        "operator": info["operator"],
        "silent_mode": info["silent_mode"],
        "code_lines": solution.lines_of_code,
        "cost": efficiency.total_cost_usd,
        "tokens": total_tok,
        "thinking_ratio": efficiency.thinking_ratio,
        "correctness": solution.correctness_score,
        "constraints": f"{solution.constraints_met}/{solution.constraints_total}",
        "escape": basin.escape_score,
        "strategy": strategy.strategy.value if strategy else "?",
        "ast": ast_profile,
        "narration_penalty": narration_penalty,
        "code_density": round(code_density, 4),
        "narration_failure": narration_failure,
        "is_frontend": is_frontend,
        "non_python_files": non_python_files,
        "has_tests": ast_profile.get("has_tests", False),
        "test_results": test_results,
    }


# ── Worktree Discovery ───────────────────────────────────────────────────────

def discover_worktrees(sessions_by_dir: dict) -> list[dict]:
    """Discover experiment worktrees and match to DB sessions."""
    import glob
    worktrees = []
    for path in sorted(glob.glob("/tmp/exp_*")):
        wt = {"path": path, "name": Path(path).name}
        if path in sessions_by_dir:
            wt["session"] = sessions_by_dir[path]
        worktrees.append(wt)
    return worktrees


def ast_profile_worktree(worktree_path: str) -> dict:
    """Comprehensive AST analysis of a worktree's generated code.
    
    Returns the same metrics shown on the evidence page: files, functions,
    classes, type hints, docstrings, error handlers, imports, decorators.
    """
    import ast
    p = Path(worktree_path)
    skip = {"__pycache__", ".git", "venv", ".venv", "site-packages",
            "node_modules", ".mypy_cache", ".pytest_cache", "Lib", "lib"}
    
    metrics = {
        "py_files": 0, "total_lines": 0, "total_functions": 0,
        "total_classes": 0, "type_hints": 0, "docstrings": 0,
        "error_handlers": 0, "imports": 0, "decorators": 0,
        "test_files": 0, "parse_errors": 0, "has_tests": False,
    }
    
    py_files = [f for f in sorted(p.rglob("*.py")) if not (skip & set(f.parts))]
    metrics["py_files"] = len(py_files)
    
    for f in py_files:
        rel = str(f.name)
        if "test" in rel.lower():
            metrics["test_files"] += 1
        try:
            code = f.read_text(errors="replace")
            lines = [l for l in code.split("\n") if l.strip() and not l.strip().startswith("#")]
            metrics["total_lines"] += len(lines)
            
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    metrics["total_functions"] += 1
                    if node.returns: metrics["type_hints"] += 1
                    if (node.body and isinstance(node.body[0], ast.Expr)
                            and isinstance(node.body[0].value, ast.Constant)):
                        metrics["docstrings"] += 1
                    for arg in node.args.args:
                        if arg.annotation: metrics["type_hints"] += 1
                    # Check for error handler patterns
                    for dec in node.decorator_list:
                        metrics["decorators"] += 1
                        dec_str = ast.unparse(dec) if hasattr(ast, 'unparse') else str(dec)
                        if "error" in dec_str.lower():
                            metrics["error_handlers"] += 1
                
                if isinstance(node, ast.ClassDef):
                    metrics["total_classes"] += 1
                
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    metrics["imports"] += 1
                
                if isinstance(node, ast.Try):
                    metrics["error_handlers"] += 1
        except Exception:
            metrics["parse_errors"] += 1
    
    metrics["has_tests"] = metrics["test_files"] > 0
    if metrics["py_files"] > 0:
        metrics["functions_per_file"] = round(metrics["total_functions"] / metrics["py_files"], 1)
        metrics["classes_per_file"] = round(metrics["total_classes"] / metrics["py_files"], 1)
        metrics["avg_lines_per_file"] = round(metrics["total_lines"] / metrics["py_files"])
        metrics["type_hint_pct"] = round(metrics["type_hints"] / max(metrics["total_functions"] * 2, 1) * 100)
        metrics["docstring_pct"] = round(metrics["docstrings"] / max(metrics["total_functions"], 1) * 100)
        metrics["test_rate"] = round(metrics["test_files"] / metrics["py_files"] * 100)
    else:
        metrics.update({"functions_per_file": 0, "classes_per_file": 0,
                        "avg_lines_per_file": 0, "type_hint_pct": 0,
                        "docstring_pct": 0, "test_rate": 0})
    
    return metrics
    """Extract structural fingerprint from generated code: modules, routes, classes.
    
    Two worktrees with similar fingerprints were given the same instructions.
    """
    import ast
    p = Path(workdir)
    if not p.exists():
        return {}
    skip_dirs = {"__pycache__", ".git", "venv", ".venv", "site-packages",
                 "node_modules", ".mypy_cache", ".pytest_cache", "Lib", "lib"}
    py_files = []
    for f in sorted(p.rglob("*.py")):
        if skip_dirs & set(f.parts):
            continue
        try:
            code = f.read_text(errors="replace")
            if len(code) > 20:
                py_files.append((f.relative_to(p), code))
        except Exception:
            pass
        if len(py_files) > 30:
            break
    if not py_files:
        return {}

    modules = sorted(set(str(f).replace("/", ".").replace(".py", "") for f, _ in py_files))
    routes = set()
    classes = set()
    for _, code in py_files:
        for m in re.findall(r'@.*\.route\(["\']([^"\']+)', code):
            routes.add(m)
        try:
            for node in ast.walk(ast.parse(code)):
                if isinstance(node, ast.ClassDef) and not node.name.startswith("Test"):
                    classes.add(node.name)
        except Exception:
            pass

    return {"modules": sorted(modules), "routes": sorted(routes), "classes": sorted(classes)}


def code_fingerprint(workdir: str) -> dict:
    """Extract structural fingerprint: modules, routes, classes.
    
    Two worktrees with similar fingerprints were given the same instructions.
    """
    import ast
    p = Path(workdir)
    if not p.exists():
        return {}
    skip = {"__pycache__", ".git", "venv", ".venv", "site-packages",
            "node_modules", ".mypy_cache", ".pytest_cache", "Lib", "lib"}
    py_files = []
    for f in sorted(p.rglob("*.py")):
        if skip & set(f.parts): continue
        try:
            code = f.read_text(errors="replace")
            if len(code) > 20:
                py_files.append((f.relative_to(p), code))
        except: pass
        if len(py_files) > 30: break
    if not py_files: return {}
    modules = sorted(set(str(f).replace("/", ".").replace(".py", "") for f, _ in py_files))
    routes = set()
    classes = set()
    for _, code in py_files:
        for m in re.findall(r'@.*\.route\(["\']([^"\']+)', code):
            routes.add(m)
        try:
            for node in ast.walk(ast.parse(code)):
                if isinstance(node, ast.ClassDef) and not node.name.startswith("Test"):
                    classes.add(node.name)
        except: pass
    return {"modules": sorted(modules), "routes": sorted(routes), "classes": sorted(classes)}


def fingerprint_score(fp_a: dict, fp_b: dict) -> float:
    """Structural similarity 0-1 based on modules, routes, classes."""
    if not fp_a or not fp_b:
        return 0.0
    splits = []
    for key in ["modules", "routes", "classes"]:
        sa = set(fp_a.get(key, []))
        sb = set(fp_b.get(key, []))
        if not sa and not sb:
            continue
        inter = len(sa & sb)
        union = len(sa | sb) or 1
        splits.append(inter / union)
    return sum(splits) / len(splits) if splits else 0.0


def build_baseline_index(worktrees: list[dict]) -> dict:
    """Index baselines by key -> {code, fingerprint, path}.
    
    Keys: experiment|model_short and experiment|provider/model_id
    """
    index = {}
    for wt in worktrees:
        s = wt.get("session", {})
        title = s.get("title", "") or ""
        info = parse_session_title_info(title)
        if info["operator"] != "baseline":
            continue
        exp = info["experiment"]; ms = info["model_short"]
        prov = s.get("provider", ""); mid = s.get("model_id", "")
        keys = []
        if exp and ms: keys.append(f"{exp}|{ms}")
        if exp and prov and mid: keys.append(f"{exp}|{prov}/{mid}")
        for key in keys:
            if key not in index:
                code = read_worktree_code(wt["path"])
                if code:
                    index[key] = {"code": code, "fp": code_fingerprint(wt["path"]),
                                  "path": wt["path"], "prov": prov, "mid": mid}
    return index


def find_baseline_code(worktree_title: str, session: dict,
                       baseline_index: dict, worktree_path: str = "") -> str:
    """Find matching baseline code, preferring instruction-level fingerprint matches.
    
    Priority:
      1. Fingerprint match (same instructions → same code structure)
      2. Experiment+model exact match
      3. Same-model fallback
    """
    info = parse_session_title_info(worktree_title)
    if info["operator"] == "baseline":
        return ""

    ms = info["model_short"]; exp = info["experiment"]
    prov = session.get("provider", ""); mid = session.get("model_id", "")

    # ── Priority 1: fingerprint match ──
    if worktree_path:
        pert_fp = code_fingerprint(worktree_path)
        if pert_fp:
            best_score = 0.0
            best_code = ""
            for key, entry in baseline_index.items():
                base_fp = entry.get("fp")
                if not base_fp:
                    continue
                s = fingerprint_score(pert_fp, base_fp)
                # Boost score for same-model matches
                if prov and mid and entry.get("prov") == prov and entry.get("mid") == mid:
                    s = min(s + 0.1, 1.0)
                if s > best_score and s > 0.25:
                    best_score = s
                    best_code = entry["code"]
            if best_code:
                return best_code

    # ── Priority 2: exact experiment+model match ──
    if exp and ms:
        entry = baseline_index.get(f"{exp}|{ms}")
        if entry: return entry["code"]
    if exp and prov and mid:
        entry = baseline_index.get(f"{exp}|{prov}/{mid}")
        if entry: return entry["code"]

    # ── Priority 3: fuzzy model_short within same experiment ──
    if exp and ms:
        ms_words = set(ms.lower().replace("_", " ").split())
        for key, entry in baseline_index.items():
            key_exp, key_ms = key.split("|", 1)
            if key_exp == exp:
                kw = set(key_ms.lower().replace("_", " ").split())
                if ms_words & kw or ms.lower() in key_ms.lower() or key_ms.lower() in ms.lower():
                    return entry["code"]

    # ── Priority 4: any baseline for same model ──
    if prov and mid:
        target = f"{prov}/{mid}"
        for bk, entry in baseline_index.items():
            if target in bk:
                return entry["code"]
    if prov:
        for bk, entry in baseline_index.items():
            if prov in bk:
                return entry["code"]

    return ""


def find_baseline_worktree(worktrees: list[dict], experiment: str) -> str:
    """Find a baseline worktree for the given experiment name."""
    baselines = [wt for wt in worktrees
                 if experiment in (wt.get("session", {}).get("title", "") or "").lower()
                 and "baseline" in (wt.get("session", {}).get("title", "") or "").lower()]
    if baselines:
        return read_worktree_code(baselines[0]["path"])
    return ""


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Post-hoc analysis of experiment worktrees")
    ap.add_argument("--worktree", help="Analyze a single worktree path")
    ap.add_argument("--limit", type=int, default=0, help="Max worktrees to analyze")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be analyzed")
    ap.add_argument("--baseline", help="Baseline worktree path for comparison")
    ap.add_argument("--run-tests", action="store_true", help="Run pytest in each worktree")
    args = ap.parse_args()

    global run_tests_enabled
    run_tests_enabled = args.run_tests
    if run_tests_enabled:
        ensure_test_venv()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load sessions from DB
    print("Loading session data from opencode DB...")
    sessions_by_dir = load_db_sessions()
    print(f"  {len(sessions_by_dir)} sessions with directory paths")

    if args.worktree:
        worktrees = [{"path": args.worktree, "name": Path(args.worktree).name,
                       "session": sessions_by_dir.get(args.worktree)}]
    else:
        print("Discovering worktrees...")
        worktrees = discover_worktrees(sessions_by_dir)
        print(f"  {len(worktrees)} worktrees found")

    # Filter to only ones with sessions and experiment-like titles
    exp_wts = [wt for wt in worktrees if wt.get("session")]
    EXP_PATTERNS = ["flask", "api", "rest", "task", "url", "sweep", "batch", "config",
                     "silent", "constraint", "recovery", "baseline", "perturb", "inject",
                     "phantom", "remove_critical", "invert", "shift_framing", "alien",
                     "false_premise", "competing", "data_table", "collaborat"]

    analyzed = [wt for wt in exp_wts if any(
        p in (wt.get("session", {}).get("title", "") or "").lower()
        for p in EXP_PATTERNS
    ) or ((wt.get("session", {}).get("title", "") or "").startswith("["))]
    print(f"  {len(analyzed)} experiment worktrees")

    if args.limit:
        analyzed = analyzed[:args.limit]
        print(f"  limited to {args.limit}")

    if args.dry_run:
        print("\n=== DRY RUN — would analyze these worktrees ===\n")
        for i, wt in enumerate(analyzed):
            s = wt.get("session", {})
            title = (s.get("title", "") or "?")[:70]
            cost = s.get("cost", 0) or 0
            print(f"  {i+1:3d}. {wt['name']:<20} ${cost:>7.4f}  {title}")
        print(f"\n  Total: {len(analyzed)} worktrees")
        return

    # Build baseline index from ALL worktrees (not just the limited subset)
    print("Building baseline index...")
    all_worktrees = discover_worktrees(sessions_by_dir)
    all_with_sessions = [wt for wt in all_worktrees if wt.get("session")]
    baseline_index = build_baseline_index(all_with_sessions)
    print(f"  {len(baseline_index)} baselines indexed")

    # Analyze each worktree
    results = []

    print(f"\n{'='*100}")
    print(f"ANALYZING {len(analyzed)} WORKTREES")
    print(f"{'='*100}\n")

    for i, wt in enumerate(analyzed):
        s = wt.get("session", {})
        title = (s.get("title", "") or "")[:60]

        # Find matching baseline via smart index
        baseline_code = find_baseline_code(title, s, baseline_index, worktree_path=wt["path"])
        if args.baseline and not baseline_code:
            baseline_code = read_worktree_code(args.baseline)

        report, metrics = analyze_worktree(wt["path"], s, baseline_code=baseline_code)

        if report:
            safe_name = wt["name"].replace("/", "_")[:60]
            md_path = REPORTS_DIR / f"{safe_name}.md"

            # Build markdown with AST section
            md = report.to_markdown()
            ast = metrics.get("ast", {})
            if ast:
                md += "\n\n---\n\n## AST Code Quality\n\n"
                md += "| Metric | Value |\n|--------|-------|\n"
                for label, key in [
                    ("Python files", "py_files"), ("Total lines", "total_lines"),
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
                    md += f"| {label} | {val_str} |\n"

            if metrics.get("narration_penalty", 0) > 0:
                md += f"\n## Narration Assessment\n\n"
                md += f"**Narration penalty:** {metrics['narration_penalty']:.0%}\n\n"
                md += f"| Metric | Value |\n|--------|-------|\n"
                md += f"| Output tokens | {s.get('tokens_output', 0):,} |\n"
                md += f"| Python files | {ast.get('py_files', 0)} |\n"
                md += f"| Non-Python files | {metrics.get('non_python_files', 0)} |\n"
                md += f"| Code density | {metrics.get('code_density', 0):.4f} LOC/tok |\n"
                if metrics.get("narration_failure"):
                    md += f"| **Verdict** | **NARRATION FAILURE — {s.get('tokens_output',0):,} tokens burned, zero code output** |\n"
                elif metrics.get("is_frontend"):
                    md += f"| **Verdict** | **FRONTEND WORKTREE — {metrics.get('non_python_files',0)} HTML/JS files, no Python** |\n"
                else:
                    md += f"| **Assessment** | Low code density — narration exceeded code output |\n"
                md += "\n"

            # Test results section
            tr = metrics.get("test_results")
            if tr and tr.get("ok"):
                md += "\n\n---\n\n## Pytest Results\n\n"
                md += f"| Metric | Value |\n|--------|-------|\n"
                md += f"| Passed | {tr['passed']} |\n"
                md += f"| Failed | {tr['failed']} |\n"
                md += f"| Errors | {tr['errors']} |\n"
                md += f"| Total | {tr['total']} |\n"
                md += f"| Pass rate | {tr['pass_rate']:.0%} |\n"
                md += f"| Duration | {tr['duration_s']}s |\n"

            md_path.write_text(md)

            results.append(metrics)

            strat_icon = {"conservative": "C", "exploratory": "E",
                          "wasteful": "W", "efficient": "✓"}.get(
                (metrics.get("strategy") or "").lower()[:1], "?")
            test_str = ""
            if tr and tr.get("ok"):
                test_str = f" T:{tr['passed']}/{tr['total']}"
            elif metrics.get("narration_failure"):
                test_str = " ❌ NARRATION"
            elif metrics.get("is_frontend"):
                test_str = " 🖥 FRONTEND"
            print(f"  {i+1:3d}/{len(analyzed)} {strat_icon} {wt['name']:<18} "
                  f"${metrics['cost']:>7.4f} cor={metrics['correctness']:.0%} "
                  f"esc={metrics['escape']:.2f} [{metrics['constraints']}]{test_str} "
                  f"→ {safe_name}.md")
        else:
            err = metrics.get("error", "unknown")
            if metrics.get("narration_failure"):
                cost = (s.get("cost") or 0) if s else 0
                results.append({"experiment": wt["name"], "narration_failure": True,
                               "cost": cost,
                               "output_tokens": (s.get("tokens_output") or 0) if s else 0})
                print(f"  {i+1:3d}/{len(analyzed)} ❌ {wt['name']:<18} "
                      f"${cost:>7.4f} NARRATION FAIL ({s.get('tokens_output',0) if s else 0} tok)"
                      f" → skipped")
            elif args.worktree:
                print(f"  Error: {err}")

    # Summary
    if results:
        narrated = sum(1 for r in results if r.get("narration_failure"))
        valid = [r for r in results if not r.get("narration_failure") and "correctness" in r]

        print(f"\n{'='*100}")
        print(f"SUMMARY — {len(results)} entries ({len(valid)} analyzed, {narrated} narration failures)")
        print(f"{'='*100}")

        total_cost = sum(r.get("cost", 0) for r in results)
        narr_cost = sum(r.get("cost", 0) for r in results if r.get("narration_failure"))

        if valid:
            avg_correct = sum(r["correctness"] for r in valid) / len(valid)
            avg_escape = sum(r["escape"] for r in valid) / len(valid)
            strategies = {}
            for r in valid:
                s = r.get("strategy", "?")
                strategies[s] = strategies.get(s, 0) + 1

            print(f"  Total cost analyzed:  {_fmt_usd(total_cost)}")
            print(f"  Narration waste:      {_fmt_usd(narr_cost)} ({narrated} worktrees)")
            print(f"  Avg correctness:      {avg_correct:.1%}")
            print(f"  Avg escape score:     {avg_escape:.2f}")
            print(f"  Strategy breakdown:   {strategies}")
        else:
            print(f"  Total cost (all narr): {_fmt_usd(total_cost)}")
        print(f"\n  Reports saved to: {REPORTS_DIR}/")
    else:
        print("\nNo worktrees analyzed.")


if __name__ == "__main__":
    main()
