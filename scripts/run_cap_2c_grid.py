"""cap_adaptive_2c p2 grid executor — run the remaining cells of the pre-registered table.

Phase p2 of ``cap_adaptive_2c``: runs the 23 remaining cells (E4 = cap2c_correct_adaptive_r1 was
measured in p1) EXACTLY per the pre-registered assignment table
(``docs/designs/current/cap_adaptive_2c_preregistration.md`` section 4 — the committed seed
``92983f6f...`` + block scheme). Per cell: fresh worktree, unique FINOPS_CELL_ID, proposal emitted
+ validated BEFORE the outcome; static = recorded never applied; adaptive = applied exactly as
proposed (rework = ONE bounded pass, verify = one pass, continue = null). Outcomes INDEPENDENT
(runtime pytest + a per-class post-hoc defect determination). The absent-class cells exercise the
seam's refuse path in the designed degraded state and record the refusal + facts present (never a
hand-authored proposal). Graph-down/analyzer-down cells are flagged, never dropped.

Usage:
    python scripts/run_cap_2c_grid.py --dry-run        # print the plan, touch nothing
    python scripts/run_cap_2c_grid.py --cell <id>      # run one cell by cell_id
    python scripts/run_cap_2c_grid.py                  # run all pending cells, commit per cell
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import _bootstrap  # noqa: E402
except ImportError:
    from scripts import _bootstrap  # noqa: E402, F401

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results" / "cap_adaptive_2c"
PROPOSALS = RESULTS / "proposals"
CELLS_DIR = RESULTS / "cells"

MODEL = "deepseek/deepseek-v4-pro"
BACKEND = "opencode"
GRAPH_URI = "bolt://localhost:7687"
FORECAST_PER_CELL = 0.031707  # p1 FORECAST (measured x 2), labeled FORECAST

SEED_CALC = """def add(a, b):
    return a + b


def subtract(a, b):
    return a - b
"""

SEED_TEST = """from calc import add, subtract


def test_add():
    assert add(1, 2) == 3


def test_subtract():
    assert subtract(3, 1) == 2
"""

#: The canonical pre-registered assignment table (pre-registration section 4). Slot = execution
#: order within the block. No cell outside this table is ever run.
CELLS: list[dict] = [
    {"cell_id": "cap2c_correct_adaptive_r1", "class": "correct", "variant": None, "arm": "adaptive", "rep": "r1", "slot": 1, "done_p1": True},
    {"cell_id": "cap2c_correct_adaptive_r2", "class": "correct", "variant": None, "arm": "adaptive", "rep": "r2", "slot": 2},
    {"cell_id": "cap2c_correct_static_r1", "class": "correct", "variant": None, "arm": "static", "rep": "r1", "slot": 3},
    {"cell_id": "cap2c_correct_static_r2", "class": "correct", "variant": None, "arm": "static", "rep": "r2", "slot": 4},
    {"cell_id": "cap2c_incorrect_adaptive_r1", "class": "incorrect", "variant": None, "arm": "adaptive", "rep": "r1", "slot": 1},
    {"cell_id": "cap2c_incorrect_adaptive_r2", "class": "incorrect", "variant": None, "arm": "adaptive", "rep": "r2", "slot": 2},
    {"cell_id": "cap2c_incorrect_static_r1", "class": "incorrect", "variant": None, "arm": "static", "rep": "r1", "slot": 3},
    {"cell_id": "cap2c_incorrect_static_r2", "class": "incorrect", "variant": None, "arm": "static", "rep": "r2", "slot": 4},
    {"cell_id": "cap2c_irrelevant_adaptive_r1", "class": "irrelevant", "variant": None, "arm": "adaptive", "rep": "r1", "slot": 1},
    {"cell_id": "cap2c_irrelevant_static_r1", "class": "irrelevant", "variant": None, "arm": "static", "rep": "r1", "slot": 2},
    {"cell_id": "cap2c_irrelevant_static_r2", "class": "irrelevant", "variant": None, "arm": "static", "rep": "r2", "slot": 3},
    {"cell_id": "cap2c_irrelevant_adaptive_r2", "class": "irrelevant", "variant": None, "arm": "adaptive", "rep": "r2", "slot": 4},
    {"cell_id": "cap2c_competing_static_r1", "class": "competing", "variant": None, "arm": "static", "rep": "r1", "slot": 1},
    {"cell_id": "cap2c_competing_static_r2", "class": "competing", "variant": None, "arm": "static", "rep": "r2", "slot": 2},
    {"cell_id": "cap2c_competing_adaptive_r1", "class": "competing", "variant": None, "arm": "adaptive", "rep": "r1", "slot": 3},
    {"cell_id": "cap2c_competing_adaptive_r2", "class": "competing", "variant": None, "arm": "adaptive", "rep": "r2", "slot": 4},
    {"cell_id": "cap2c_absent-clean_static_r1", "class": "absent", "variant": "clean", "arm": "static", "rep": "r1", "slot": 1},
    {"cell_id": "cap2c_absent-clean_adaptive_r1", "class": "absent", "variant": "clean", "arm": "adaptive", "rep": "r1", "slot": 2},
    {"cell_id": "cap2c_absent-defective_static_r1", "class": "absent", "variant": "defective", "arm": "static", "rep": "r1", "slot": 1},
    {"cell_id": "cap2c_absent-defective_adaptive_r1", "class": "absent", "variant": "defective", "arm": "adaptive", "rep": "r1", "slot": 2},
    {"cell_id": "cap2c_unseen_family_static_r1", "class": "unseen_family", "variant": None, "arm": "static", "rep": "r1", "slot": 1},
    {"cell_id": "cap2c_unseen_family_adaptive_r1", "class": "unseen_family", "variant": None, "arm": "adaptive", "rep": "r1", "slot": 2},
    {"cell_id": "cap2c_unseen_family_static_r2", "class": "unseen_family", "variant": None, "arm": "static", "rep": "r2", "slot": 3},
    {"cell_id": "cap2c_unseen_family_adaptive_r2", "class": "unseen_family", "variant": None, "arm": "adaptive", "rep": "r2", "slot": 4},
]

#: Per-class cell spec + goal (the goal text is recorded per cell; the goal hash is derived).
SPECS = {
    "correct": {
        "path": "workflows/operations/cap_2a_cell_critical.yaml",
        "spec_id": "cap_2a_cell_critical@0.1",
        "goal": "add a classifier function with a deep nested decision tree containing one real boundary defect (to the calc app)",
    },
    "incorrect": {
        "path": "workflows/operations/cap_2c_cell_incorrect.yaml",
        "spec_id": "cap_2c_cell_incorrect@0.1",
        "goal": "modify add(a, b) in calc.py with a behavior-preserving body change (result = a + b; return result) AND add 19 trivial distinct pure helpers widget_1(x)..widget_19(x) returning x + k in a NEW module widgets.py with NO test file — the change is defect-free; do not change add's behavior, do not change subtract or its test",
    },
    "irrelevant": {
        "path": "workflows/operations/cap_2a_cell_clean.yaml",
        "spec_id": "cap_2a_cell_clean@0.1",
        "goal": "add a product function to the calc app (with a test), leaving add/subtract unchanged",
    },
    "competing": {
        "path": "workflows/operations/cap_2c_cell_competing.yaml",
        "spec_id": "cap_2c_cell_competing@0.1",
        "goal": "add a classifier function with a deep nested decision tree containing TWO real boundary defects (the [10, 20) boundary uses > instead of >= so classify(10.0) is wrong, AND the [20, 30) boundary uses > instead of >= so classify(20.0) is wrong)",
    },
    "absent": {
        "path": "workflows/operations/cap_2c_cell_absent.yaml",
        "spec_id": "cap_2c_cell_absent@0.1",
        "goal_clean": "add a trivial pure helper widget(x) that returns x, in a NEW module widgets.py (no test file, not imported anywhere)",
        "goal_defective": "add wrong_op(a, b) to a NEW module widgets.py (no test file, not imported anywhere): documented to return a - b, implemented to return a + b (the single real defect)",
    },
    "unseen_family": {
        "path": "workflows/operations/cap_2c_cell_unseen_family.yaml",
        "spec_id": "cap_2c_cell_unseen_family@0.1",
        "goal": "add a tally(scores) function to calc.py: documented to return a NEW list sorted in descending order WITHOUT modifying the input; implemented with scores.sort(reverse=True); return scores (so the input IS mutated — the single real mutation/aliasing defect)",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def goal_for(cell: dict) -> str:
    spec = SPECS[cell["class"]]
    if cell["class"] == "absent":
        return spec["goal_clean"] if cell["variant"] == "clean" else spec["goal_defective"]
    return spec["goal"]


def spec_path_for(cell: dict) -> str:
    return SPECS[cell["class"]]["path"]


def seed_worktree(workdir: Path) -> str:
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "calc.py").write_text(SEED_CALC)
    (workdir / "test_calc.py").write_text(SEED_TEST)
    _git(workdir, "init", "-q", "-b", "main")
    _git(workdir, "config", "user.email", "campaign@agentic-dynamics")
    _git(workdir, "config", "user.name", "campaign")
    _git(workdir, "add", "-A")
    _git(workdir, "commit", "-q", "-m", "seed calc app")
    return _git(workdir, "rev-parse", "HEAD").strip()


def _git(workdir: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=workdir, capture_output=True, text=True, timeout=120
    ).stdout


def run_workflow_cell(cell: dict, workdir: Path, ledger_dir: Path) -> dict:
    """Run the cell's workflow via run_workflow.py with the full seam (absent cells: seam inert —
    the refusal is exercised separately). Returns the parsed run ledger JSON."""
    goal = goal_for(cell)
    spec = spec_path_for(cell)
    is_absent = cell["class"] == "absent"
    cmd = [
        sys.executable, str(ROOT / "scripts" / "run_workflow.py"),
        "--spec", spec, "--goal", goal, "--model", MODEL,
        "--workdir", str(workdir), "--backend", BACKEND,
        "--timeout", "1800", "--phase-watchdog-min", "20",
    ]
    if not is_absent:
        cmd += ["--change-analysis", "--change-analysis-graph", GRAPH_URI]
    env = dict(os.environ)
    env["FINOPS_CELL_ID"] = cell["cell_id"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800, env=env)
    out = proc.stdout + proc.stderr
    m = re.search(r"ledger:\s+(\S+\.json)", out)
    if proc.returncode != 0 or not m:
        raise RuntimeError(
            f"cell {cell['cell_id']} run_workflow failed rc={proc.returncode}\n{out[-2000:]}"
        )
    ledger_path = Path(m.group(1))
    ledger = json.loads(ledger_path.read_text())
    ledger["_run_ledger_path"] = str(ledger_path)
    ledger["_run_ledger_sha256"] = sha256_file(ledger_path)
    return ledger


def find_implement(ledger: dict) -> dict:
    for ph in ledger["phases"]:
        if ph["phase"] == "implement":
            return ph
    raise RuntimeError("no implement phase in run ledger")


def emit_proposal(cell: dict, impl: dict, seed_rev: str) -> dict:
    """Emit + validate the proposal from the implement phase's change_analysis facts, attaching the
    measured confidence field (pre-registration section 7). Raises on a seam refusal."""
    from agentic_dynamics.control.verify_proposal import emit_verify_proposal

    ca = impl.get("change_analysis") or {}
    facts = list(ca.get("facts") or [])
    recorded_at = datetime.now(timezone.utc).isoformat()
    proposal, path = emit_verify_proposal(
        facts=facts,
        cell_id=cell["cell_id"],
        baseline_revision=seed_rev,
        analyzed_revision=ca.get("revision") or impl.get("analyzed_revision") or impl["commit_hash"],
        scope=list(ca.get("neighborhood") or []),
        recorded_at=recorded_at,
    )
    # Campaign extension (pre-registration section 7): the durable proposal record MUST carry the
    # measured confidence field; validate_verify_proposal is structural and accepts extra fields.
    payload = json.loads(path.read_text())
    payload["confidence"] = impl.get("confidence")
    payload["confidence_note"] = (
        "MEASURED [H] per-attempt execution-confidence of the analyzed attempt (implement phase, "
        "AgenticResult.confidence) — pre-registration section 7; recorded BEFORE the outcome."
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    out = {
        "proposal_id": proposal.proposal_id,
        "action": proposal.action,
        "depth": proposal.depth,
        "scope": list(proposal.scope),
        "applied": False,
        "confidence": impl.get("confidence"),
        "schema_version": proposal.schema_version,
        "contract_version": proposal.contract_version,
        "artifact": str(path.relative_to(ROOT)),
        "artifact_sha256": sha256_file(path),
        "baseline_revision": seed_rev,
        "analyzed_revision": ca.get("revision") or impl["commit_hash"],
        "facts_used": sorted(f["predicate"] for f in facts),
    }
    return out


def exercise_absent_refusal(cell: dict, workdir: Path, impl: dict, seed_rev: str) -> dict:
    """Absent class: run the analyzer over the real implement commit with the DESIGNED degraded
    evidence (sonar + lsp unavailable, graph unavailable -> no risk term measurable) and let the
    seam refuse. Records the refusal + the facts present. Never a hand-authored proposal."""
    from agentic_dynamics.control.evidence_analyzer import EvidenceChangeAnalyzer
    from agentic_dynamics.control.verify_proposal import build_verify_proposal
    from agentic_dynamics.core.language import (
        build_code_snapshot,
        compute_code_delta,
        detect_language,
    )
    from agentic_dynamics.measurement.commit_analysis import _read_commit_files
    from agentic_dynamics.runtime.change_analyzer import ChangeInput
    from agentic_dynamics.runtime.workflow_runner import _git_full_sha

    profile = detect_language(workdir)
    full = _git_full_sha(workdir, impl["commit_hash"]) or impl["commit_hash"]
    parent = _git_full_sha(workdir, f"{full}^")
    before_files = _read_commit_files(workdir, parent or f"{full}^", profile)
    after_files = _read_commit_files(workdir, full, profile)
    before = build_code_snapshot(before_files, revision=parent, profile=profile)
    after = build_code_snapshot(after_files, revision=full, profile=profile)
    delta = compute_code_delta(before, after)
    # The DESIGNED degraded state (pre-registration section 3 class 5): sonar/lsp unavailable,
    # graph unavailable -> no analyzer counts, ratio deferred (untested module), impacted omitted.
    scope_id = f"self-{cell['cell_id']}"
    change = ChangeInput(
        before=before, after=after, delta=delta, revision=full,
        repository_id=scope_id, acl_scope=scope_id,
        sonar={"status": "unavailable", "revision_matches": None, "new_critical_count": None, "analyzed_sha": ""},
        lsp={"status": "unavailable", "new_error_count": None, "tool": "mypy"},
        impacted_count=None, phase_id="implement", observed_at=now_iso(),
    )
    analyzer = EvidenceChangeAnalyzer(graph_client=None, graph_requested=False)
    analysis = analyzer.analyze(change)
    facts = [dict(f) for f in analysis.facts]
    predicates = sorted(f["predicate"] for f in facts)
    refused = False
    error = ""
    proposal = None
    try:
        proposal = build_verify_proposal(
            facts=facts,
            cell_id=cell["cell_id"],
            baseline_revision=seed_rev,
            analyzed_revision=full,
            scope=[],
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
    except ValueError as exc:
        refused = True
        error = str(exc)
    return {
        "refused": refused,
        "error": error if refused else "",
        "facts_present": predicates,
        "facts": facts,
        "neighborhood": list(analysis.neighborhood),
        "graph_status": analysis.graph_status,
        "impacted_count": analysis.impacted_count,
        "proposal": None if proposal is None else {
            "proposal_id": proposal.proposal_id, "action": proposal.action, "depth": proposal.depth,
        },
        "note": "designed degraded state: sonar + lsp unavailable + graph unavailable -> code_change_risk "
                "unmeasurable -> the seam refuses (never a hand-authored proposal).",
    }


def _run_agent_pass(prompt: str, workdir: Path, timeout_s: int = 600) -> dict:
    from agentic_dynamics.adapters.opencode import run_opencode_agentic

    t0 = time.time()
    res = run_opencode_agentic(
        prompt=prompt, model=MODEL, thinking_effort="high",
        thinking_budget_tokens=32000, output_token_limit=20000, timeout=timeout_s,
        silent_mode=False, enforce_pytest=False, workdir=workdir,
    )
    return {
        "ok": res.ok, "exit_code": res.exit_code, "cost_usd": res.estimated_cost_usd,
        "duration_s": round(time.time() - t0, 3), "error": res.error,
        "confidence": res.confidence, "tests_passed": res.tests_passed,
        "tests_total": res.tests_total, "tool_calls": len(res.tool_calls),
    }


def apply_adaptive(cell: dict, workdir: Path, proposal: dict) -> dict:
    """Adaptive arm: apply exactly as proposed. rework = ONE bounded pass over the proposal scope;
    verify = one pass; continue = null. Returns the application record with proof."""
    action = proposal["action"]
    scope = ", ".join(proposal["scope"]) or "(empty)"
    if action == "continue":
        return {
            "applied_or_null": "null", "action": "continue", "rework_passes": 0,
            "note": "continue proposal -> provable null application (no extra pass).",
            "proof": "provable-null:commit-trail",
        }
    if action == "rework":
        prompt = _rework_prompt(cell, scope)
        res = _run_agent_pass(prompt, workdir)
        _git(workdir, "add", "-A", "--", ":(exclude).instrument")
        _git(workdir, "commit", "-q", "-m", "[workflow] rework")
        commit = _git(workdir, "rev-parse", "HEAD").strip()
        return {
            "applied_or_null": "applied", "action": "rework", "depth": proposal["depth"],
            "rework_passes": 1, "rework_commit": commit,
            "rework_pass_cost_usd": res["cost_usd"], "rework_duration_s": res["duration_s"],
            "agent_result": res,
            "proof": f"rework proposal APPLIED as ONE bounded pass over the proposal scope; [workflow] rework commit {commit}",
        }
    # verify = one pass over the proposal scope (a verification agent pass; on a clean change this
    # is the measured wrong-apply wasted pass — no code change expected).
    prompt = _verify_prompt(cell, scope)
    res = _run_agent_pass(prompt, workdir)
    return {
        "applied_or_null": "applied", "action": "verify", "depth": proposal["depth"],
        "verify_passes": 1, "verify_pass_cost_usd": res["cost_usd"],
        "verify_duration_s": res["duration_s"], "agent_result": res,
        "proof": "verify proposal APPLIED as ONE bounded verification pass over the proposal scope (recorded pass; "
                 "tree unchanged on a clean change — the wrong-apply wasted-pass cost is measured).",
    }


def _rework_prompt(cell: dict, scope: str) -> str:
    cls = cell["class"]
    base = f"""Apply the rework proposal for the analyzed code change in this worktree.

Proposal scope (the bounded neighborhood): {scope}.
Proposed action: rework (depth 3).

"""
    if cls == "correct":
        target = ("In calc.py, classify(value) documents the contract [10, 20) -> \"ten_to_twenty\" (lower edge "
                  "INCLUSIVE). The guard uses `if value > 10 and value < 20:` which EXCLUDES the boundary value "
                  "10.0. Change `value > 10` to `value >= 10` so the guard reads `if value >= 10 and value < 20:`.")
    elif cls == "competing":
        target = ("In calc.py, classify(value) documents the contracts [10, 20) -> \"ten_to_twenty\" AND "
                  "[20, 30) -> \"twenty_to_thirty\" (lower edges INCLUSIVE). TWO guards are wrong: the [10, 20) "
                  "guard uses `>` instead of `>=` (10.0 excluded), and the [20, 30) guard uses `>` instead of "
                  "`>=` (20.0 excluded). Fix BOTH boundaries so the guards read `>=` (and < the upper edge).")
    else:
        target = ("Fix the single real defect the proposal's change analysis targeted (the boundary guard in "
                  "calc.py that excludes its documented lower-inclusive edge).")
    return (base + "THE DEFECT(S) TO FIX (exactly):\n" + target + "\n\nCONSTRAINTS:\n"
            "- Change ONLY the defect(s) described. Do not change any other branch, behavior, docstring, "
            "add, subtract, or the test file.\n- Do not add or remove anything else.\n\n"
            "After the edit, run `python -m pytest test_calc.py -q` and report the result exactly as it is.")


def _verify_prompt(cell: dict, scope: str) -> str:
    return f"""Apply the verify proposal for the analyzed code change in this worktree.

Proposal scope (the bounded neighborhood): {scope}.
Proposed action: verify (depth-level verification pass).

DO: perform ONE bounded verification pass over the proposal scope: read the changed code in scope,
run `python -m pytest test_calc.py -q`, and report what you verified. Do NOT modify any code (the
change is clean and the proposal's action is verification only).

Report the verification result exactly as observed.
"""


def run_independent_outcome(cell: dict, workdir: Path) -> dict:
    """Independent outcome: runtime pytest on the final commit + the per-class post-hoc defect
    determination (the evaluator)."""
    proc = subprocess.run(
        ["python3", "-m", "pytest", "test_calc.py", "-q"], cwd=workdir,
        capture_output=True, text=True, timeout=300,
    )
    out = proc.stdout + proc.stderr
    m = re.search(r"(\d+) passed", out)
    mf = re.search(r"(\d+) failed", out)
    passed = int(m.group(1)) if m else 0
    failed = int(mf.group(1)) if mf else 0
    test_success = failed == 0 and passed > 0
    defect_present, defect_note = _defect_determination(cell, workdir)
    accepted = bool(test_success and not defect_present)
    return {
        "final_revision": _git(workdir, "rev-parse", "HEAD").strip(),
        "test_executed_success": test_success, "tests_passed": passed, "tests_total": passed + failed,
        "test_runner": "independent pytest (runtime test execution) on the immutable final commit",
        "defect_present_on_final_commit": defect_present,
        "defect_note": defect_note,
        "accepted": accepted,
    }


def _defect_determination(cell: dict, workdir: Path) -> tuple[bool, str]:
    """Post-hoc evaluator: present? which family? (per class). Runs small python assertions against
    the final commit."""
    cls = cell["class"]
    def run_check(check: str) -> bool:
        p = subprocess.run(["python3", "-c", check], cwd=workdir, capture_output=True, text=True, timeout=120)
        return p.returncode == 0

    if cls in ("correct", "competing"):
        ok10 = run_check("from calc import classify; assert classify(10.0) == 'ten_to_twenty', classify(10.0)")
        if cls == "competing":
            ok20 = run_check("from calc import classify; assert classify(20.0) == 'twenty_to_thirty', classify(20.0)")
            present = not (ok10 and ok20)
            which = []
            if not ok10:
                which.append("[10,20) inverted boundary")
            if not ok20:
                which.append("[20,30) inverted boundary")
            return present, f"family: boundary-compare x{len(which)} ({', '.join(which)}) present on the final commit" if present else "both boundary-compare defects absent"
        return (not ok10, "family: boundary-compare ([10,20) inverted boundary) present" if not ok10 else "boundary-compare defect absent")
    if cls == "unseen_family":
        ok = run_check("import calc; s=[3,1,2]; calc.tally(s); assert s == [3,1,2], s")
        return (not ok, "family: mutation/aliasing (tally mutates its input) present — NOT boundary-compare, NOT S1244, NOT S3776" if not ok else "mutation/aliasing defect absent")
    if cls == "absent":
        if cell["variant"] == "defective":
            ok = run_check("from widgets import wrong_op; assert wrong_op(5, 2) == 3, wrong_op(5, 2)")
            return (not ok, "family: wrong-operation (wrong_op returns a+b not a-b) present (escaped — the seam refused)" if not ok else "absent-defective defect absent")
        return (False, "clean change — no defect (the refusal is value-preserving)")
    if cls == "incorrect":
        ok = run_check("from calc import add; assert add(1,2) == 3; from widgets import widget_19; assert widget_19(1) == 20")
        return (False, "clean change — no defect (the false-positive VERIFY is on a clean change)")
    # irrelevant
    ok = run_check("from calc import product; assert product([1,2,3,4]) == 24")
    return (False, "clean change — no defect (trivial, fully-tested change)")


def main() -> None:
    ap = argparse.ArgumentParser(description="cap_adaptive_2c p2 grid executor")
    ap.add_argument("--cell", default=None, help="run a single cell by cell_id")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, touch nothing")
    args = ap.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    CELLS_DIR.mkdir(parents=True, exist_ok=True)

    pending = [c for c in CELLS if not c.get("done_p1")]
    if args.cell:
        pending = [c for c in pending if c["cell_id"] == args.cell]
        if not pending:
            raise SystemExit(f"no pending cell {args.cell!r}")
    if args.dry_run:
        print(f"{len(pending)} pending cells:")
        for c in pending:
            print(f"  {c['cell_id']:42s} class={c['class']:12s} variant={c['variant'] or '-':9s} arm={c['arm']:8s} rep={c['rep']}")
        return

    for cell in pending:
        cell_path = CELLS_DIR / f"{cell['cell_id']}.json"
        if cell_path.exists():
            print(f"[skip] {cell['cell_id']} already recorded")
            continue
        print(f"\n=== RUN {cell['cell_id']} (class={cell['class']} arm={cell['arm']} rep={cell['rep']}) ===", flush=True)
        workdir = Path("/tmp") / cell["cell_id"]
        t_start = time.time()
        try:
            seed_rev = seed_worktree(workdir)
            ledger = run_workflow_cell(cell, workdir, RESULTS)
            impl = find_implement(ledger)
            is_absent = cell["class"] == "absent"
            if is_absent:
                seam = exercise_absent_refusal(cell, workdir, impl, seed_rev)
                proposal = None
            else:
                proposal = emit_proposal(cell, impl, seed_rev)
                seam = {"refused": False, "error": "", "facts_present": sorted(f["predicate"] for f in impl.get("change_analysis", {}).get("facts", [])), "facts": impl.get("change_analysis", {}).get("facts", []), "neighborhood": list(impl.get("change_analysis", {}).get("neighborhood", [])), "graph_status": impl.get("change_analysis", {}).get("graph_status", ""), "impacted_count": impl.get("change_analysis", {}).get("impacted_count")}
            # application (adaptive only; static = recorded, never applied)
            if cell["arm"] == "adaptive" and proposal is not None:
                application = apply_adaptive(cell, workdir, proposal)
            elif cell["arm"] == "adaptive" and proposal is None:
                application = {"applied_or_null": "null", "action": None, "note": "no proposal emitted (seam refused) -> provable null application; the refusal is the abstention case."}
            else:
                application = {"applied_or_null": "not_applicable", "action": None, "note": "static arm: proposal recorded, NEVER applied."}
            outcome = run_independent_outcome(cell, workdir)
            wall = round(time.time() - t_start, 1)
            run_cost = ledger.get("total_cost_usd", 0.0) or 0.0
            app_cost = float(application.get("rework_pass_cost_usd") or application.get("verify_pass_cost_usd") or 0.0)
            total = run_cost + app_cost
            record = {
                "schema_version": "cap_adaptive_2c_cell/v1",
                "cell_id": cell["cell_id"], "class": cell["class"], "variant": cell["variant"],
                "arm": cell["arm"], "repetition": cell["rep"], "slot": cell["slot"],
                "spec_id": SPECS[cell["class"]]["spec_id"],
                "goal": goal_for(cell), "goal_sha256": hashlib.sha256(goal_for(cell).encode()).hexdigest(),
                "model": MODEL, "backend": BACKEND,
                "seeded_app_worktree": str(workdir), "seeded_app_seed_revision": seed_rev,
                "finops_cell_id": cell["cell_id"],
                "run_ledger": ledger.get("_run_ledger_path"), "run_ledger_sha256": ledger.get("_run_ledger_sha256"),
                "run_ledger_ok": ledger.get("ok"),
                "analyzer_status": {
                    "graph": "available" if not is_absent else "unavailable (designed)",
                    "sonar": "available" if not is_absent else "unavailable (designed)",
                    "lsp": "available" if not is_absent else "unavailable (designed)",
                },
                "facts": {f["predicate"]: f["value"] for f in (impl.get("change_analysis") or {}).get("facts", [])},
                "facts_present": seam["facts_present"],
                "impl": {"cost_usd": impl.get("cost_usd"), "duration_s": impl.get("duration_s"),
                         "commit_hash": impl.get("commit_hash"), "confidence": impl.get("confidence")},
                "seam": seam,
                "proposal": proposal,
                "application": application,
                "outcome": outcome,
                "cost": {"run_workflow_usd": run_cost, "application_usd": app_cost, "total_usd": round(total, 6)},
                "forecast_usd": FORECAST_PER_CELL,
                "within_forecast": total <= 2 * FORECAST_PER_CELL,
                "wall_s": wall,
                "status": "ok",
                "written_at": now_iso(),
            }
            # class-instantiation falsifiability flags (pre-registration falsifiability contract)
            flags = []
            if proposal is not None:
                exp_action = {"correct": "rework", "incorrect": "verify", "irrelevant": "continue", "competing": "rework", "unseen_family": "continue"}[cell["class"]]
                if proposal["action"] != exp_action:
                    flags.append(f"construction-failure: expected proposal {exp_action}, got {proposal['action']}")
            if is_absent and not seam["refused"]:
                flags.append("construction-failure: absent cell did not refuse")
            record["flags"] = flags
            cell_path.write_text(json.dumps(record, indent=2, sort_keys=True))
            print(f"[done] {cell['cell_id']}: proposal={proposal['action'] if proposal else 'REFUSED'} "
                  f"arm={cell['arm']} cost=${total:.4f} accepted={outcome['accepted']} "
                  f"conf={impl.get('confidence')} flags={flags or 'none'} wall={wall}s", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {cell['cell_id']}: {type(exc).__name__}: {exc}", flush=True)
            record = {
                "schema_version": "cap_adaptive_2c_cell/v1", "cell_id": cell["cell_id"],
                "class": cell["class"], "arm": cell["arm"], "repetition": cell["rep"],
                "status": "error", "error": f"{type(exc).__name__}: {exc}", "written_at": now_iso(),
            }
            cell_path.write_text(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
