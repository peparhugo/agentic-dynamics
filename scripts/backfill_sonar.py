#!/usr/bin/env python3
r"""Non-destructive SonarQube backfill — enriches existing results with code quality metrics.

Runs sonar-scanner (via Docker) against existing worktree code directories,
fetches quality metrics from the SonarQube API, and writes enriched data
to a NEW file: _results_summary_sonar.json (never overwrites the original).

Usage:
  python scripts/backfill_sonar.py --limit 1           # test single worktree
  python scripts/backfill_sonar.py --limit 20           # backfill 20
  python scripts/backfill_sonar.py                       # all worktrees
  python scripts/backfill_sonar.py --dry-run             # show what would run
"""

import json
import subprocess
import sys
import time
import urllib.request
from base64 import b64encode
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "_results_summary_sonar.json"
REPORTS_DIR = ROOT / "experiments" / "results" / "reports"

SONAR_URL = "http://localhost:9000"
SONAR_USER = "admin"
SONAR_PASSWORD = "admin"
SONAR_NETWORK = "infrastructure_sonar-net"


def _auth_header():
    creds = b64encode(f"{SONAR_USER}:{SONAR_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


def _sonar_api(path: str) -> dict:
    url = f"{SONAR_URL}{path}"
    req = urllib.request.Request(url, headers=_auth_header())
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _wait_for_analysis(project_key: str, timeout: int = 120) -> dict:
    deadline = time.monotonic() + timeout
    metric_keys = (
        "bugs,vulnerabilities,code_smells,cognitive_complexity,complexity,"
        "duplicated_lines_density,ncloc,comment_lines_density,classes,"
        "functions,files,sqale_rating,reliability_rating,security_rating,"
        "alert_status,sqale_index,sqale_debt_ratio"
    )
    path = f"/api/measures/component?component={project_key}&metricKeys={metric_keys}"
    while time.monotonic() < deadline:
        data = _sonar_api(path)
        measures = data.get("component", {}).get("measures", [])
        if measures:
            return {m["metric"]: m["value"] for m in measures}
        time.sleep(2)
    return {}


_RATING_MAP = {"1.0": "A", "2.0": "B", "3.0": "C", "4.0": "D", "5.0": "E"}


def _sonar_quality_score(metrics: dict) -> float:
    if not metrics or metrics.get("ncloc", "0") == "0":
        return 0.5
    rating_scores = {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4, "E": 0.2, "": 0.5}
    mt = _RATING_MAP.get(metrics.get("sqale_rating", ""), "")
    rl = _RATING_MAP.get(metrics.get("reliability_rating", ""), "")
    sc = _RATING_MAP.get(metrics.get("security_rating", ""), "")
    qg = 1.0 if metrics.get("alert_status", "").upper() == "OK" else 0.0
    ratings = (0.35 * rating_scores.get(mt, 0.5)
               + 0.25 * rating_scores.get(rl, 0.5)
               + 0.25 * rating_scores.get(sc, 0.5)
               + 0.15 * qg)
    ncloc = max(int(metrics.get("ncloc", "1")), 1)
    bugs_kloc = int(metrics.get("bugs", "0")) / ncloc * 1000
    smells_kloc = int(metrics.get("code_smells", "0")) / ncloc * 1000
    dup = float(metrics.get("duplicated_lines_density", "0"))
    density = ((max(0, 1 - bugs_kloc / 10) + max(0, 1 - smells_kloc / 50) + max(0, 1 - dup / 20)) / 3)
    return 0.6 * ratings + 0.4 * density


def _find_project_root(code_dir: Path) -> Path:
    """Find the actual project root if code is nested inside a subdirectory."""
    top_has_src = any(code_dir.glob("*.py")) or any(code_dir.glob("*.ts")) or (code_dir / "src").exists() or (code_dir / "app").exists()
    if top_has_src:
        return code_dir
    # Look for a subdirectory that looks like a project
    for child in sorted(code_dir.iterdir()):
        if child.is_dir() and not child.name.startswith(".") and child.name not in ("node_modules",):
            if any(child.glob("*.py")) or any(child.glob("*.ts")) or (child / "src").exists():
                return child
    return code_dir


def run_sonar_docker(project_key: str, code_dir: Path) -> bool:
    """Run sonar-scanner via Docker against a code directory."""
    code_dir = _find_project_root(code_dir.resolve())
    if not code_dir.exists() or not list(code_dir.iterdir()):
        return False

    cmd = [
        "docker", "run", "--rm",
        "--network", SONAR_NETWORK,
        "-v", f"{code_dir}:/usr/src",
        "-w", "/usr/src",
        "sonarsource/sonar-scanner-cli:latest",
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.projectName={project_key}",
        "-Dsonar.sources=.",
        "-Dsonar.host.url=http://sonarqube:9000",
        f"-Dsonar.login={SONAR_USER}",
        f"-Dsonar.password={SONAR_PASSWORD}",
        "-Dsonar.exclusions=**/node_modules/**,**/__pycache__/**,**/.git/**,**/venv/**,**/.venv/**",
        "-Dsonar.scanner.skipJreProvisioning=true",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output = result.stdout + result.stderr
        return "SUCCESS" in output or "ANALYSIS SUCCESSFUL" in output
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def backfill(limit: int = 0, dry_run: bool = False):
    input_path = OUTPUT_PATH if OUTPUT_PATH.exists() else SUMMARY_PATH
    if input_path == OUTPUT_PATH:
        print(f"Resuming from existing: {OUTPUT_PATH}")
    summary = json.loads(input_path.read_text())
    entries = summary.get("entries", [])

    code_dirs_found = 0
    analyzed = 0
    skipped = 0

    for i, entry in enumerate(entries):
        wt = entry.get("worktree_name", "")
        if not wt:
            continue

        code_dir = REPORTS_DIR / wt / "code"
        if not code_dir.exists():
            continue

        code_dirs_found += 1

        if entry.get("sonar_analyzed"):
            continue

        if limit and analyzed >= limit:
            break

        if dry_run:
            print(f"[DRY] {wt}: {code_dir}")
            analyzed += 1
            continue

        print(f"\n[{analyzed+1}/{limit if limit else '∞'}] {wt}...", end=" ", flush=True)

        success = run_sonar_docker(wt, code_dir)
        if not success:
            print("SCANNER FAILED")
            skipped += 1
            continue

        metrics = _wait_for_analysis(wt, timeout=60)
        if not metrics:
            print("NO METRICS (timeout)")
            skipped += 1
            continue

        score = round(_sonar_quality_score(metrics), 4)

        entry["sonar_analyzed"] = True
        entry["sonar_bugs"] = int(metrics.get("bugs", 0))
        entry["sonar_vulnerabilities"] = int(metrics.get("vulnerabilities", 0))
        entry["sonar_code_smells"] = int(metrics.get("code_smells", 0))
        entry["sonar_cognitive_complexity"] = int(metrics.get("cognitive_complexity", 0))
        entry["sonar_duplicated_lines_density"] = float(metrics.get("duplicated_lines_density", 0))
        entry["sonar_ncloc"] = int(metrics.get("ncloc", 0))
        entry["sonar_comment_lines_density"] = float(metrics.get("comment_lines_density", 0))
        entry["sonar_classes"] = int(metrics.get("classes", 0))
        entry["sonar_functions"] = int(metrics.get("functions", 0))
        entry["sonar_files"] = int(metrics.get("files", 0))
        entry["sonar_maintainability_rating"] = _RATING_MAP.get(metrics.get("sqale_rating", ""), "")
        entry["sonar_reliability_rating"] = _RATING_MAP.get(metrics.get("reliability_rating", ""), "")
        entry["sonar_security_rating"] = _RATING_MAP.get(metrics.get("security_rating", ""), "")
        entry["sonar_quality_gate"] = metrics.get("alert_status", "")
        entry["sonar_quality_score"] = score
        entry["sonar_sqale_index"] = int(metrics.get("sqale_index", 0))
        entry["sonar_sqale_debt_ratio"] = float(metrics.get("sqale_debt_ratio", 0))

        analyzed += 1
        bugs = entry["sonar_bugs"]
        smells = entry["sonar_code_smells"]
        ncloc = entry["sonar_ncloc"]
        gate = entry["sonar_quality_gate"]
        print(f"{bugs}b {smells}s {ncloc}loc gate={gate} score={score:.3f}")

    # Write to NEW file — never overwrites the original
    total_enriched = sum(1 for e in entries if e.get("sonar_analyzed"))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary["_meta"]["sonar_backfilled"] = total_enriched
    summary["_meta"]["sonar_backfilled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    if dry_run:
        print(f"\n[DRY RUN] Would enrich {analyzed} entries with sonar data → {OUTPUT_PATH}")
    else:
        OUTPUT_PATH.write_text(json.dumps(summary, indent=2, default=str))
        print(f"\nEnriched {analyzed} new entries ({skipped} skipped, {total_enriched} total, {code_dirs_found} code dirs found)")
        print(f"Wrote: {OUTPUT_PATH}")

    print(f"\nOriginal file UNCHANGED: {SUMMARY_PATH}")
    print(f"Backup exists: {SUMMARY_PATH}.bak")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Non-destructive SonarQube backfill")
    parser.add_argument("--limit", type=int, default=0, help="Max worktrees to analyze")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    args = parser.parse_args()
    backfill(limit=args.limit, dry_run=args.dry_run)
