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
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from _constants import WORKTREE_GLOB

from instrument import (
    evaluate_solution, compute_efficiency, measure_basin_escape,
    classify_strategy, GameReport, SolutionMetrics, EfficiencyMetrics, BasinMetrics,
    StrategyReport, analyze_ast,
    run_sonar_analysis, compute_sonar_diff, sonar_quality_score,
    build_operators, perturbation_class_for,
)

from _constants import EXPERIMENT_SESSION_PATTERNS, bootstrap_ci

OPENCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"
REPORTS_DIR = RESULTS_DIR / "reports"
CONFIGS_DIR = PROJECT_ROOT / "experiments" / "configs"
TEST_VENV = Path("/tmp/pytest_venv")
PYTEST_DEPS = ["flask", "pytest", "sqlalchemy", "flask-jwt-extended", "flask-limiter",
               "flask-cors", "flask-migrate"]

run_tests_enabled = True
sonar_enabled = True
_sonar_url = "http://localhost:9000"
_sonar_user = "admin"
_sonar_password = "admin"
_sonar_timeout = 120
_test_timeout = 120
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
    _sp.run([pip, "install", "-q"] + PYTEST_DEPS, capture_output=True, timeout=120)
    _test_venv_ready = True


def run_pytest(worktree_path: str, timeout_sec: int = 120) -> dict:
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
            "ok": r.returncode == 0 and total > 0,
            "passed": passed, "failed": failed, "errors": errors,
            "total": total, "duration_s": round(dur, 1),
            "pass_rate": round(passed / max(total, 1), 3) if total > 0 else 0,
        }
    except _sp.TimeoutExpired:
        return {"ok": False, "error": f"timeout {timeout_sec}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:60]}


def run_ts_tests(worktree_path: str, timeout_sec: int = 30) -> dict:
    """Run TypeScript tests in a worktree using vitest or jest."""
    import subprocess as _sp
    p = Path(worktree_path)
    if not p.exists():
        return {"ok": False, "error": "worktree missing"}

    configs = list(p.glob("jest.config.*")) + list(p.glob("vitest.config.*"))
    test_files = list(p.rglob("*.test.ts")) + list(p.rglob("*.spec.ts"))
    if not test_files and not configs and not (p / "package.json").exists():
        return {"ok": False, "error": "no TypeScript test infrastructure"}

    has_package_json = (p / "package.json").exists()

    # Detect vitest vs jest
    has_vitest = any(f.name.startswith("vitest.config") for f in configs)
    has_jest = any(f.name.startswith("jest.config") for f in configs)

    t0 = time.monotonic()
    try:
        if has_vitest and has_package_json:
            r = _sp.run(
                ["npx", "vitest", "run", "--reporter=verbose"],
                cwd=str(p), capture_output=True, text=True,
                timeout=timeout_sec, env={**os.environ, "CI": "true"},
            )
            runner = "vitest"
        elif has_jest and has_package_json:
            r = _sp.run(
                ["npx", "jest", "--passWithNoTests", "--no-coverage", "-q"],
                cwd=str(p), capture_output=True, text=True,
                timeout=timeout_sec, env={**os.environ, "CI": "true"},
            )
            runner = "jest"
        elif has_package_json:
            r = _sp.run(
                ["npx", "vitest", "run", "--reporter=verbose"],
                cwd=str(p), capture_output=True, text=True,
                timeout=timeout_sec, env={**os.environ, "CI": "true"},
            )
            runner = "vitest"
        else:
            r = _sp.run(
                ["npx", "tsc", "--noEmit"],
                cwd=str(p), capture_output=True, text=True,
                timeout=timeout_sec,
            )
            runner = "tsc"
        dur = time.monotonic() - t0
        out = r.stdout + r.stderr
        import re
        passed = int(re.search(r'(\d+)\s+passed', out).group(1)) if re.search(r'(\d+)\s+passed', out) else 0
        failed = int(re.search(r'(\d+)\s+failed', out).group(1)) if re.search(r'(\d+)\s+failed', out) else 0
        total = passed + failed
        if total == 0 and r.returncode == 0:
            return {
                "ok": False, "passed": 0, "failed": 0, "total": 0,
                "duration_s": round(dur, 1),
                "pass_rate": 0,
                "note": "No test counts parsed from output — likely no tests executed",
                "runner": runner,
            }
        if total == 0:
            return None
        return {
            "ok": r.returncode == 0,
            "passed": passed, "failed": failed,
            "errors": 0, "total": total,
            "duration_s": round(dur, 1),
            "pass_rate": round(passed / max(total, 1), 3),
            "runner": runner,
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
    if not OPENCODE_DB.exists():
        print("Error: opencode DB not found at", OPENCODE_DB)
        return []
    db = sqlite3.connect(str(OPENCODE_DB))
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
    
    Reads .py files first. Falls back to .ts/.tsx if no Python found.
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
        if len(code_parts) > 200:
            break
    if not code_parts:
        for ext in [".ts", ".tsx", ".js", ".jsx"]:
            comment = "//" if ext in (".ts", ".tsx", ".js", ".jsx") else "#"
            for f in sorted(p.rglob(f"*{ext}")):
                parts = set(f.parts)
                if parts & skip_dirs:
                    continue
                try:
                    content = f.read_text(errors="replace")
                    if content.strip() and len(content) > 20:
                        rel = f.relative_to(p)
                        code_parts.append(f"{comment} {rel}\n{content}")
                except Exception:
                    pass
                if len(code_parts) > 200:
                    break
            if code_parts:
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
                     config_name: str = "", run_sonar: bool = False,
                     baseline_path: str = ""):
    """Run the full analysis pipeline on a single worktree.

    Returns:
        (GameReport, dict of metrics) or (None, error_dict)
    """
    global run_tests_enabled, sonar_enabled, _sonar_url, _sonar_user, _sonar_password, _sonar_timeout
    wt = Path(worktree_path)
    if not wt.exists():
        return None, {"error": "worktree not found"}

    # Read code
    code = read_worktree_code(worktree_path)
    if not code:
        # Check if TypeScript/frontend worktree with files but no Python
        has_other_files = False
        for ext in [".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".json"]:
            if list(Path(worktree_path).rglob(f"*{ext}")):
                has_other_files = True
                break
        if not has_other_files:
            return None, {"error": "no source files found",
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
    solution.evaluator_source = "heuristic"

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

    # ── SonarQube Analysis ──
    baseline_sm = None
    if run_sonar and sonar_enabled:
        sm = run_sonar_analysis(
            worktree_path, sonar_url=_sonar_url,
            sonar_user=_sonar_user, sonar_password=_sonar_password,
            timeout_sec=_sonar_timeout,
        )
        if sm.analyzed:
            solution.sonar_analyzed = True
            solution.sonar_bugs = sm.bugs
            solution.sonar_vulnerabilities = sm.vulnerabilities
            solution.sonar_code_smells = sm.code_smells
            solution.sonar_cognitive_complexity = sm.cognitive_complexity
            solution.sonar_duplicated_lines_density = sm.duplicated_lines_density
            solution.sonar_ncloc = sm.ncloc
            solution.sonar_maintainability_rating = sm.maintainability_rating
            solution.sonar_reliability_rating = sm.reliability_rating
            solution.sonar_security_rating = sm.security_rating
            solution.sonar_quality_gate = sm.quality_gate
            solution.sonar_quality_score = sonar_quality_score(sm)
        if baseline_path and baseline_path != worktree_path:
            baseline_sm = run_sonar_analysis(
                baseline_path, sonar_url=_sonar_url,
                sonar_user=_sonar_user, sonar_password=_sonar_password,
                timeout_sec=_sonar_timeout,
            )

    # ── Efficiency ──
    prompt_tok = session.get("tokens_input", 0) or 0 if session else 0
    completion_tok = session.get("tokens_output", 0) or 0 if session else 0
    reasoning_tok = session.get("tokens_reasoning", 0) or 0 if session else 0
    cache_read = session.get("tokens_cache_read", 0) or 0 if session else 0
    cache_write = session.get("tokens_cache_write", 0) or 0 if session else 0
    total_tok = prompt_tok + completion_tok + reasoning_tok
    provider = str(session.get("provider", "") or "") if session else ""
    model_id = str(session.get("model_id", "") or "") if session else ""

    db_cost = session.get("cost", 0) or 0 if session else 0
    efficiency = compute_efficiency(
        prompt_tokens=prompt_tok, completion_tokens=completion_tok,
        reasoning_tokens=reasoning_tok, total_tokens=total_tok,
        cache_read_tokens=cache_read, cache_write_tokens=cache_write,
        provider=provider, model=model_id,
        solution=solution,
    )
    if db_cost > 0:
        est_total = efficiency.total_cost_usd
        if est_total > 0:
            scale = db_cost / est_total
            efficiency.cost_input_usd *= scale
            efficiency.cost_output_usd *= scale
            efficiency.cost_reasoning_usd *= scale
            efficiency.cost_cache_usd *= scale
        efficiency.total_cost_usd = db_cost
        efficiency.cost_is_estimated = False

    # ── Perturbation class detection ──
    exp_name = info.get("experiment", "") or ""
    op_name = ""
    for name in build_operators():
        if name in exp_name:
            op_name = name
            break
    if op_name:
        pert_class = perturbation_class_for(op_name)
    elif info.get("operator") == "baseline":
        pert_class = "baseline"
    else:
        pert_class = "unknown"

    # ── AST Profiling ──
    ast_profile = ast_profile_worktree(worktree_path)
    ast_comparison = None
    if baseline_code and code:
        ast_comparison = analyze_ast(baseline_code, code,
                                     operator=info.get("operator", ""),
                                     perturbation_class=pert_class)

    # ── Test Results (run before basin/strategy so they consume canonical correctness) ──
    test_results = None
    if run_tests_enabled:
        if ast_profile.get("py_files", 0) > 0:
            test_results = run_pytest(worktree_path, timeout_sec=_test_timeout)
        elif ast_profile.get("ts_files", 0) + ast_profile.get("tsx_files", 0) > 0:
            test_results = run_ts_tests(worktree_path, timeout_sec=_test_timeout)
        if test_results and test_results.get("total", 0) > 0:
            solution.tests_passed = test_results["passed"]
            solution.tests_total = test_results["total"]
            solution.correctness_score = test_results["pass_rate"]
            solution.evaluator_source = "agent_authored_test"
            solution.evaluator_independent = False

    # ── Recompute composite score after canonical correctness is established ──
    if solution.sonar_analyzed:
        solution.composite_score = (
            0.30 * solution.correctness_score
            + 0.25 * solution.constraint_score
            + 0.20 * solution.sonar_quality_score
            + 0.15 * solution.code_quality_score
            + 0.10 * solution.novelty_score
        )
    else:
        solution.composite_score = (
            0.35 * solution.correctness_score
            + 0.30 * solution.constraint_score
            + 0.20 * solution.code_quality_score
            + 0.15 * solution.novelty_score
        )

    # ── Basin Escape ──
    strength_match = re.search(r'_s(\d+\.\d+)', worktree_path)
    actual_strength = float(strength_match.group(1)) if strength_match else 0.5
    no_baseline = not baseline_code
    self_comparison = bool(baseline_code) and baseline_code == code
    if no_baseline or self_comparison:
        from instrument.basin import BasinMetrics as _BM
        basin = _BM(
            perturbation_operator=info.get("operator", "baseline"),
            perturbation_class=pert_class,
            perturbation_strength=actual_strength,
            model=session.get("model_id", "") if session else "",
            cost_usd=db_cost if db_cost > 0 else None,
            correctness=solution.correctness_score,
            constraints_met=solution.constraints_met,
            constraints_total=solution.constraints_total,
            lines_of_code=solution.lines_of_code,
            total_tokens=total_tok,
            reasoning_tokens=reasoning_tok,
            thinking_ratio=reasoning_tok / max(total_tok, 1),
            estimated_energy_j=efficiency.total_energy_j,
            escape_score=float('nan'),
            architecture_divergence=float('nan'),
            structure_divergence=float('nan'),
            novelty_score=float('nan'),
            quality_per_dollar=float('nan'),
            quality_per_joule=float('nan'),
            converged_back=None,
            verdict="self-comparison" if self_comparison else "no baseline",
        )
    else:
        sonar_diff_data = None
        if baseline_sm and baseline_sm.analyzed and solution.sonar_analyzed:
            from instrument.sonar import SonarMetrics as _SM
            perturbed_sm = _SM(
                analyzed=True, bugs=solution.sonar_bugs,
                vulnerabilities=solution.sonar_vulnerabilities,
                code_smells=solution.sonar_code_smells,
                cognitive_complexity=solution.sonar_cognitive_complexity,
                complexity=0, duplicated_lines_density=solution.sonar_duplicated_lines_density,
                maintainability_rating=solution.sonar_maintainability_rating,
                reliability_rating=solution.sonar_reliability_rating,
                security_rating=solution.sonar_security_rating,
            )
            sonar_diff_data = compute_sonar_diff(baseline_sm, perturbed_sm)
        baseline_solution = evaluate_solution(baseline_code, constraints)
        basin = measure_basin_escape(
            baseline_code=baseline_code,
            perturbed_code=code,
            baseline_correctness=baseline_solution.correctness_score,
            perturbed_correctness=solution.correctness_score,
            baseline_constraints_met=baseline_solution.constraints_met,
            perturbed_constraints_met=solution.constraints_met,
            baseline_loc=baseline_solution.lines_of_code,
            perturbed_loc=solution.lines_of_code,
        prompt_tokens=prompt_tok,
        completion_tokens=completion_tok,
        reasoning_tokens=reasoning_tok,
        perturbation_operator=info.get("operator", "baseline"),
        perturbation_class=pert_class,
        perturbation_strength=actual_strength,
        model=session.get("model_id", "") if session else "",
        cost_usd=db_cost if db_cost > 0 else None,
        sonar_diff=sonar_diff_data,
        constraint_count=solution.constraints_total,
    )

    # ── Strategy ──
    strategy = classify_strategy(basin, solution, efficiency, pert_class)

    # ── Game Report ──
    experiment_id = info.get("experiment", wt.name) or wt.name
    model_str = ""
    if session:
        prov = str(session.get("provider", "") or "").strip()
        mid = str(session.get("model_id", "") or "").strip()
        if prov and mid:
            model_str = f"{prov}/{mid}"
    if not model_str:
        # Fallback: try to detect from worktree name patterns
        model_str = f"unknown ({wt.name})"
    report = GameReport(
        experiment_id=f"{experiment_id}-{info.get('operator', '?')}",
        model=model_str,
        task=title[:200] if title else str(wt.name),
        operator=info.get("operator", "baseline"),
        perturbation_class=pert_class,
        reasoning=basin, solution=solution, efficiency=efficiency,
        strategy=strategy,
    )

    return report, {
        "experiment": experiment_id,
        "model": model_str,
        "operator": info["operator"],
        "perturbation_class": pert_class,
        "silent_mode": info["silent_mode"],
        "code_lines": solution.lines_of_code,
        "cost": efficiency.total_cost_usd,
        "cost_input_usd": efficiency.cost_input_usd,
        "cost_output_usd": efficiency.cost_output_usd,
        "cost_reasoning_usd": efficiency.cost_reasoning_usd,
        "cost_cache_usd": efficiency.cost_cache_usd,
        "tokens": total_tok,
        "tokens_input": prompt_tok,
        "tokens_output": completion_tok,
        "tokens_reasoning": reasoning_tok,
        "tokens_cache_read": cache_read,
        "tokens_cache_write": cache_write,
        "energy_total_j": efficiency.total_energy_j,
        "energy_input_j": efficiency.energy_input_j,
        "energy_output_j": efficiency.energy_output_j,
        "energy_reasoning_j": efficiency.energy_reasoning_j,
        "thinking_ratio": efficiency.thinking_ratio,
        "output_efficiency": efficiency.output_efficiency,
        "solution_density": efficiency.solution_density,
        "correctness_per_dollar": efficiency.correctness_per_dollar,
        "quality_per_joule": efficiency.quality_per_joule,
        "correctness": solution.correctness_score,
        "constraints": f"{solution.constraints_met}/{solution.constraints_total}",
        "constraints_met": solution.constraints_met,
        "constraints_total": solution.constraints_total,
        "cyclomatic_complexity": solution.cyclomatic_complexity,
        "comment_ratio": solution.comment_ratio,
        "code_quality_score": solution.code_quality_score,
        "novelty_score": solution.novelty_score,
        "composite_score": solution.composite_score,
        "escape": basin.escape_score,
        "architecture_divergence": basin.architecture_divergence,
        "structure_divergence": basin.structure_divergence,
        "basin_novelty": basin.novelty_score,
        "basin_verdict": basin.verdict,
        "converged_back": basin.converged_back,
        "no_baseline": no_baseline,
        "strategy": strategy.strategy.value if strategy else "?",
        "strategy_score": strategy.strategy_score if strategy else 0,
        "exploration_premium": strategy.exploration_premium if strategy else 0,
        "thermal_efficiency": strategy.thermal_efficiency if strategy else 0,
        "strategy_verdict": strategy.verdict if strategy else "",
        "ast": ast_profile,
        "narration_penalty": narration_penalty,
        "code_density": round(code_density, 4),
        "narration_failure": narration_failure,
        "is_frontend": is_frontend,
        "non_python_files": non_python_files,
        "has_tests": ast_profile.get("has_tests", False),
        "evaluator_source": solution.evaluator_source,
        "evaluator_independent": solution.evaluator_independent,
        "test_results": test_results,
        "sonar_analyzed": solution.sonar_analyzed,
        "sonar_bugs": solution.sonar_bugs,
        "sonar_vulnerabilities": solution.sonar_vulnerabilities,
        "sonar_code_smells": solution.sonar_code_smells,
        "sonar_cognitive_complexity": solution.sonar_cognitive_complexity,
        "sonar_duplicated_lines_density": solution.sonar_duplicated_lines_density,
        "sonar_ncloc": solution.sonar_ncloc,
        "sonar_maintainability_rating": solution.sonar_maintainability_rating,
        "sonar_reliability_rating": solution.sonar_reliability_rating,
        "sonar_security_rating": solution.sonar_security_rating,
        "sonar_quality_gate": solution.sonar_quality_gate,
        "sonar_quality_score": solution.sonar_quality_score,
        "sonar_bugs_delta": basin.sonar_bugs_delta if hasattr(basin, 'sonar_bugs_delta') else 0,
        "sonar_vulnerabilities_delta": basin.sonar_vulnerabilities_delta if hasattr(basin, 'sonar_vulnerabilities_delta') else 0,
        "sonar_code_smells_delta": basin.sonar_code_smells_delta if hasattr(basin, 'sonar_code_smells_delta') else 0,
        "sonar_cognitive_complexity_delta": basin.sonar_cognitive_complexity_delta if hasattr(basin, 'sonar_cognitive_complexity_delta') else 0,
        "sonar_complexity_delta": basin.sonar_complexity_delta if hasattr(basin, 'sonar_complexity_delta') else 0,
        "sonar_duplication_delta": basin.sonar_duplication_delta if hasattr(basin, 'sonar_duplication_delta') else 0.0,
        "sonar_maintainability_delta": basin.sonar_maintainability_delta if hasattr(basin, 'sonar_maintainability_delta') else 0,
        "sonar_security_delta": basin.sonar_security_delta if hasattr(basin, 'sonar_security_delta') else 0,
        "sonar_baseline_bugs": basin.sonar_baseline_bugs if hasattr(basin, 'sonar_baseline_bugs') else 0,
        "sonar_perturbed_bugs": basin.sonar_perturbed_bugs if hasattr(basin, 'sonar_perturbed_bugs') else 0,
    }


# ── Worktree Discovery ───────────────────────────────────────────────────────

def discover_worktrees(sessions_by_dir: dict) -> list[dict]:
    """Discover experiment worktrees and match to DB sessions."""
    import glob
    worktrees = []
    for path in sorted(glob.glob(str(WORKTREE_GLOB))):
        wt = {"path": path, "name": Path(path).name}
        if path in sessions_by_dir:
            wt["session"] = sessions_by_dir[path]
        worktrees.append(wt)
    return worktrees


def ast_profile_worktree(worktree_path: str) -> dict:
    """Comprehensive analysis of a worktree's generated code.
    
    Analyzes Python files with AST. Counts TypeScript/JS files for multi-language worktrees.
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
        "ts_files": 0, "tsx_files": 0, "js_files": 0, "ts_total_lines": 0,
    }
    
    py_files = [f for f in sorted(p.rglob("*.py")) if not (skip & set(f.parts))]
    metrics["py_files"] = len(py_files)
    
    # Count TypeScript and JavaScript files
    for ext, key in [(".ts", "ts_files"), (".tsx", "tsx_files"), (".js", "js_files")]:
        ts_list = [f for f in sorted(p.rglob(f"*{ext}")) if not (skip & set(f.parts))]
        metrics[key] = len(ts_list)
        for f in ts_list:
            try:
                content = f.read_text(errors="replace")
                lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith("//")]
                metrics["ts_total_lines"] += len(lines)
            except Exception:
                pass
    
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
    ap.add_argument("--no-tests", action="store_true", help="Skip pytest in worktrees (faster)")
    ap.add_argument("--no-sonar", action="store_true", help="Skip SonarQube analysis")
    ap.add_argument("--sonar-url", default="http://localhost:9000", help="SonarQube server URL")
    ap.add_argument("--sonar-user", default="admin", help="SonarQube login user")
    ap.add_argument("--sonar-password", default="admin", help="SonarQube login password")
    ap.add_argument("--sonar-timeout", type=int, default=120, help="Sonar scanner timeout in seconds")
    ap.add_argument("--tests", action="store_true", default=True, help="Run tests (default)")
    ap.add_argument("--timeout", type=int, default=120, help="Test timeout in seconds (default 120)")
    args = ap.parse_args()

    global run_tests_enabled, sonar_enabled, _sonar_url, _sonar_user, _sonar_password, _sonar_timeout, _test_timeout
    if args.no_tests:
        run_tests_enabled = False
    if args.no_sonar:
        sonar_enabled = False
    _sonar_url = args.sonar_url
    _sonar_user = args.sonar_user
    _sonar_password = args.sonar_password
    _sonar_timeout = args.sonar_timeout
    _test_timeout = args.timeout
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
    analyzed = [wt for wt in exp_wts if any(
        p in (wt.get("session", {}).get("title", "") or "").lower()
        for p in EXPERIMENT_SESSION_PATTERNS
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
        baseline_path = ""
        if baseline_code:
            info = parse_session_title_info(title)
            exp = info.get("experiment", "")
            ms = info.get("model_short", "")
            prov = s.get("provider", "")
            mid = s.get("model_id", "")
            for key in [f"{exp}|{ms}", f"{exp}|{prov}/{mid}"]:
                entry = baseline_index.get(key)
                if entry:
                    baseline_path = entry.get("path", "")
                    break
        if args.baseline and not baseline_code:
            baseline_code = read_worktree_code(args.baseline)
            baseline_path = args.baseline

        report, metrics = analyze_worktree(
            wt["path"], s, baseline_code=baseline_code,
            run_sonar=sonar_enabled, baseline_path=baseline_path,
        )

        safe_name = wt["name"].replace("/", "_")[:60]

        # Compute model string for tracking (used in both success and failure branches)
        fallback_model = ""
        if s:
            prov = str(s.get("provider", "") or "").strip()
            mid = str(s.get("model_id", "") or "").strip()
            if prov and mid:
                fallback_model = f"{prov}/{mid}"

        if report:
            md_path = REPORTS_DIR / f"{safe_name}.md"

            # Artifact bundling — copy code + session transcript for independent verification
            artifact_path = REPORTS_DIR / safe_name
            has_code = False
            has_session = False
            worktree_dir = wt["path"]
            if worktree_dir and os.path.isdir(worktree_dir):
                code_dest = artifact_path / "code"
                skip_dirs = {"__pycache__", ".git", "venv", ".venv", "env",
                             "site-packages", "node_modules", ".mypy_cache",
                             ".pytest_cache", "dist", "build", "Lib", "lib",
                             "include", ".instrument"}
                file_count = 0
                for item in Path(worktree_dir).rglob("*"):
                    if item.is_file() and not (skip_dirs & set(item.parts)) \
                            and not item.name.startswith("."):
                        rel = item.relative_to(worktree_dir)
                        dest = code_dest / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.copy2(item, dest)
                            file_count += 1
                        except Exception:
                            pass

                if file_count > 0:
                    has_code = True

                # Look for session transcript saved by the instrument
                session_jsonl = Path(worktree_dir) / ".instrument" / "session.jsonl"
                if session_jsonl.exists():
                    try:
                        if not has_code:
                            code_dest.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(session_jsonl, artifact_path / "session.jsonl")
                        has_session = True
                    except Exception:
                        pass

                if has_code or has_session:
                    report.artifact_dir = safe_name
                    report.has_code = has_code
                    report.has_session = has_session

            # Build markdown with AST section
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
                    # Skip zero-value rows for irrelevant metrics
                    if val == 0 and key in ("ts_files", "tsx_files", "js_files", "ts_total_lines"):
                        continue
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

            metrics["worktree_name"] = wt["name"]
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
                results.append({"experiment": wt["name"], "worktree_name": wt["name"],
                               "model": fallback_model, "narration_failure": True,
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

        # ── Build enriched summary with operator-level aggregation ──
        by_model = {}
        by_operator = {}
        by_operator_model = {}
        for r in results:
            m = r.get("model", "unknown")
            o = r.get("operator", "unknown")
            pc = r.get("perturbation_class", "unknown")

            if m not in by_model:
                by_model[m] = []
            by_model[m].append(r)

            if o not in by_operator:
                by_operator[o] = []
            by_operator[o].append(r)

            key = f"{o}|{pc}|{m}"
            if key not in by_operator_model:
                by_operator_model[key] = []
            by_operator_model[key].append(r)

        def _agg(entries, fields):
            agg = {"n": len(entries)}
            for f in fields:
                vals = [e.get(f, 0) for e in entries if isinstance(e.get(f), (int, float))]
                if vals:
                    avg = round(sum(vals) / len(vals), 4)
                    agg[f"{f}_avg"] = avg
                    agg[f"{f}_sum"] = round(sum(vals), 4)
                    agg[f"{f}_min"] = round(min(vals), 4)
                    agg[f"{f}_max"] = round(max(vals), 4)
                    result = bootstrap_ci(vals)
                    if result is not None:
                        agg[f"{f}_ci95_lo"] = result[0]
                        agg[f"{f}_ci95_hi"] = result[1]
                    agg[f"{f}_n"] = len(vals)
            return agg

        NUM_FIELDS = ["cost", "cost_input_usd", "cost_output_usd", "cost_reasoning_usd",
                      "cost_cache_usd", "code_lines", "tokens", "tokens_input", "tokens_output",
                      "tokens_reasoning", "tokens_cache_read", "tokens_cache_write",
                      "energy_total_j", "thinking_ratio", "correctness", "escape",
                      "narration_penalty", "code_density", "architecture_divergence",
                      "structure_divergence", "strategy_score", "exploration_premium",
                      "thermal_efficiency", "composite_score", "novelty_score",
                      "code_quality_score", "solution_density", "correctness_per_dollar",
                      "quality_per_joule", "sonar_bugs", "sonar_vulnerabilities",
                      "sonar_code_smells", "sonar_cognitive_complexity",
                      "sonar_duplicated_lines_density", "sonar_quality_score",
                      "sonar_bugs_delta", "sonar_code_smells_delta",
                      "sonar_cognitive_complexity_delta", "sonar_duplication_delta",]

        strategy_counts = {}
        for r in results:
            s = r.get("strategy", "?")
            strategy_counts[s] = strategy_counts.get(s, 0) + 1

        narrated = sum(1 for r in results if r.get("narration_failure"))

        summary_data = {
            "_meta": {
                "generated_at": _now(),
                "total_entries": len(results),
                "narrated": narrated,
                "valid_entries": len(results) - narrated,
            },
            "strategy_distribution": strategy_counts,
            "entries": results,
            "by_model": {m: _agg(entries, NUM_FIELDS) for m, entries in by_model.items()},
            "by_operator": {o: _agg(entries, NUM_FIELDS) for o, entries in by_operator.items()},
            "by_operator_model": {
                k: _agg(entries, NUM_FIELDS) for k, entries in by_operator_model.items()
            },
        }

        summary_path = REPORTS_DIR.parent / "_results_summary.json"
        summary_path.write_text(json.dumps(summary_data, indent=2, default=str))
        print(f"  Summary saved to: {summary_path}")

    else:
        print("\nNo worktrees analyzed.")


if __name__ == "__main__":
    main()
