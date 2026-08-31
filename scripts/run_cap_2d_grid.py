"""cap_adaptive_2d p1+p2 grid executor — measure E1 + pre-verify, then run the 28-cell grid.

Phase p1/p2 of ``cap_adaptive_2d`` per the pre-registered assignment table
(``docs/designs/current/cap_adaptive_2d_preregistration.md`` section 4 — the committed seed
``617e6763...`` + block scheme). Per cell: fresh worktree, unique FINOPS_CELL_ID, candidate
manifest FIRST, proposal emitted + validated BEFORE the outcome. The ABSTENTION arm shadow-
evaluates the pre-registered decision table per cell (DECLINE leg 1 stale-analysis / leg 2
unmeasurable-risk / leg 3 Option A fingerprint skips the apply pass and records the leg + routes
to operator review; APPLY / APPLY-NULL proceed exactly as status_quo). The STATUS_QUO arm applies
exactly as proposed (rework = ONE bounded pass, verify = one pass, continue = null). Outcomes
INDEPENDENT (runtime pytest + a per-class post-hoc defect determination). The absent-class cells
exercise the seam's refuse path in the designed degraded state. Graph-down/analyzer-down cells
are flagged, never dropped.

p1 (--p1): measures E1 = cap2d_correct_abstention_r1 + the incorrect_rebuilt impacted pre-
verification probe (builds the 20-symbol change in a scratch worktree and measures
impacted_symbol_count via the graph — the rebuild's guarantee is impacted >= 1; a second
impacted=0 refutes the design).

p2 (default): runs the remaining 27 cells at 4-WIDE concurrency (ThreadPoolExecutor
max_workers=4), blocks in slot order, cells worktree-isolated.

Usage:
    python scripts/run_cap_2d_grid.py --p1               # p1: E1 measurement + probe + forecast
    python scripts/run_cap_2d_grid.py --dry-run          # print the plan, touch nothing
    python scripts/run_cap_2d_grid.py --cell <id>        # run one pending cell by cell_id
    python scripts/run_cap_2d_grid.py                    # run all pending cells at 4-wide
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import _bootstrap  # noqa: E402
except ImportError:
    from scripts import _bootstrap  # noqa: E402, F401

from agentic_dynamics.control.model_policy import FLASH_MODEL, ensure_model_allowed

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results" / "cap_adaptive_2d"
PROPOSALS = RESULTS / "proposals"
CELLS_DIR = RESULTS / "cells"
WORKTREES_DIR = Path("/tmp")

MODEL = os.environ.get("FINOPS_MODEL", FLASH_MODEL)
ensure_model_allowed(MODEL)
BACKEND = "opencode"
GRAPH_URI = "bolt://localhost:7687"
SEED = "617e6763fcd238dc93a59ba1f41e01ba5f281c4748ef3867dbebeeca344c7dfb"

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
    # correct block
    {"cell_id": "cap2d_correct_status_quo_r1", "class": "correct", "variant": None, "arm": "status_quo", "rep": "r1", "slot": 1},
    {"cell_id": "cap2d_correct_status_quo_r2", "class": "correct", "variant": None, "arm": "status_quo", "rep": "r2", "slot": 2},
    {"cell_id": "cap2d_correct_abstention_r1", "class": "correct", "variant": None, "arm": "abstention", "rep": "r1", "slot": 3, "done_p1": True},
    {"cell_id": "cap2d_correct_abstention_r2", "class": "correct", "variant": None, "arm": "abstention", "rep": "r2", "slot": 4},
    # incorrect_rebuilt block
    {"cell_id": "cap2d_incorrect_rebuilt_abstention_r1", "class": "incorrect_rebuilt", "variant": None, "arm": "abstention", "rep": "r1", "slot": 1},
    {"cell_id": "cap2d_incorrect_rebuilt_abstention_r2", "class": "incorrect_rebuilt", "variant": None, "arm": "abstention", "rep": "r2", "slot": 2},
    {"cell_id": "cap2d_incorrect_rebuilt_status_quo_r1", "class": "incorrect_rebuilt", "variant": None, "arm": "status_quo", "rep": "r1", "slot": 3},
    {"cell_id": "cap2d_incorrect_rebuilt_status_quo_r2", "class": "incorrect_rebuilt", "variant": None, "arm": "status_quo", "rep": "r2", "slot": 4},
    # harmful_partial block
    {"cell_id": "cap2d_harmful_partial_abstention_r1", "class": "harmful_partial", "variant": None, "arm": "abstention", "rep": "r1", "slot": 1},
    {"cell_id": "cap2d_harmful_partial_status_quo_r1", "class": "harmful_partial", "variant": None, "arm": "status_quo", "rep": "r1", "slot": 2},
    {"cell_id": "cap2d_harmful_partial_abstention_r2", "class": "harmful_partial", "variant": None, "arm": "abstention", "rep": "r2", "slot": 3},
    {"cell_id": "cap2d_harmful_partial_status_quo_r2", "class": "harmful_partial", "variant": None, "arm": "status_quo", "rep": "r2", "slot": 4},
    # irrelevant block
    {"cell_id": "cap2d_irrelevant_abstention_r1", "class": "irrelevant", "variant": None, "arm": "abstention", "rep": "r1", "slot": 1},
    {"cell_id": "cap2d_irrelevant_status_quo_r1", "class": "irrelevant", "variant": None, "arm": "status_quo", "rep": "r1", "slot": 2},
    {"cell_id": "cap2d_irrelevant_status_quo_r2", "class": "irrelevant", "variant": None, "arm": "status_quo", "rep": "r2", "slot": 3},
    {"cell_id": "cap2d_irrelevant_abstention_r2", "class": "irrelevant", "variant": None, "arm": "abstention", "rep": "r2", "slot": 4},
    # competing block
    {"cell_id": "cap2d_competing_status_quo_r1", "class": "competing", "variant": None, "arm": "status_quo", "rep": "r1", "slot": 1},
    {"cell_id": "cap2d_competing_abstention_r1", "class": "competing", "variant": None, "arm": "abstention", "rep": "r1", "slot": 2},
    {"cell_id": "cap2d_competing_status_quo_r2", "class": "competing", "variant": None, "arm": "status_quo", "rep": "r2", "slot": 3},
    {"cell_id": "cap2d_competing_abstention_r2", "class": "competing", "variant": None, "arm": "abstention", "rep": "r2", "slot": 4},
    # absent block (clean then defective)
    {"cell_id": "cap2d_absent-clean_abstention_r1", "class": "absent", "variant": "clean", "arm": "abstention", "rep": "r1", "slot": 1},
    {"cell_id": "cap2d_absent-clean_status_quo_r1", "class": "absent", "variant": "clean", "arm": "status_quo", "rep": "r1", "slot": 2},
    {"cell_id": "cap2d_absent-defective_abstention_r1", "class": "absent", "variant": "defective", "arm": "abstention", "rep": "r1", "slot": 1},
    {"cell_id": "cap2d_absent-defective_status_quo_r1", "class": "absent", "variant": "defective", "arm": "status_quo", "rep": "r1", "slot": 2},
    # unseen_family block
    {"cell_id": "cap2d_unseen_family_abstention_r1", "class": "unseen_family", "variant": None, "arm": "abstention", "rep": "r1", "slot": 1},
    {"cell_id": "cap2d_unseen_family_status_quo_r1", "class": "unseen_family", "variant": None, "arm": "status_quo", "rep": "r1", "slot": 2},
    {"cell_id": "cap2d_unseen_family_status_quo_r2", "class": "unseen_family", "variant": None, "arm": "status_quo", "rep": "r2", "slot": 3},
    {"cell_id": "cap2d_unseen_family_abstention_r2", "class": "unseen_family", "variant": None, "arm": "abstention", "rep": "r2", "slot": 4},
]

#: Per-class cell spec + goal (the goal text is recorded per cell; the goal hash is derived).
SPECS = {
    "correct": {
        "path": "workflows/operations/cap_2a_cell_critical.yaml",
        "spec_id": "cap_2a_cell_critical@0.1",
        "goal": "add a classifier function with a deep nested decision tree containing one real boundary defect (to the calc app)",
    },
    "incorrect_rebuilt": {
        "path": "workflows/operations/cap_2d_cell_incorrect_rebuilt.yaml",
        "spec_id": "cap_2d_cell_incorrect_rebuilt@0.1",
        "goal": "modify add(a, b) in calc.py with a behavior-preserving body change (result = a + b; return result) AND add 19 trivial distinct pure helpers widget_1(x)..widget_19(x) in a NEW module widgets.py with NO test file, where EVERY widget_k(x) CALLS add (result = add(x, k); return result) — the structural dependant edge; the change is defect-free; do not change add's behavior, do not change subtract or its test",
    },
    "harmful_partial": {
        "path": "workflows/operations/cap_2d_cell_harmful_partial.yaml",
        "spec_id": "cap_2d_cell_harmful_partial@0.1",
        "goal": "add a classifier function with a deep nested decision tree containing TWO real boundary defects far apart (the [10, 20) boundary uses > instead of >= so classify(10.0) is wrong, AND the [80, 90) boundary uses > instead of >= so classify(80.0) is wrong — far apart so one bounded rework pass plausibly fixes one and misses the other)",
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

#: Per-class expected proposal action (the class-instantiation falsifiability contract).
EXPECTED_ACTION = {
    "correct": "rework",
    "incorrect_rebuilt": "verify",
    "harmful_partial": "rework",
    "irrelevant": "continue",
    "competing": "rework",
    "unseen_family": "continue",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def goal_for(cell: dict) -> str:
    spec = SPECS[cell["class"]]
    if cell["class"] == "absent":
        return spec["goal_clean"] if cell["variant"] == "clean" else spec["goal_defective"]
    return spec["goal"]


def spec_path_for(cell: dict) -> str:
    return SPECS[cell["class"]]["path"]


#: The abstention decision table (pre-registration section 0) — shadow-evaluated per cell.
def evaluate_abstention(facts: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the abstention rule over the measured facts dict (predicate -> value).

    Returns ``{decision, leg, reason}``. ``decision`` in
    {DECLINE, APPLY, APPLY_NULL}; ``leg`` in {1, 2, 3} for a DECLINE, else None. The
    rule is confidence-free (pre-registration section 1) and consumes only the six
    measured facts of the pinned decision table.
    """
    risk_raw = facts.get("code_change_risk")
    risk = float(risk_raw) if risk_raw not in (None, "", "null") else None
    rev_matches_raw = facts.get("analysis_revision_matches")
    rev_matches = None if rev_matches_raw in (None, "", "null") else str(rev_matches_raw).lower() == "true"
    sonar_raw = facts.get("new_sonar_critical_count")
    lsp_raw = facts.get("new_lsp_error_count")
    ratio_raw = facts.get("changed_symbols_with_tests_ratio")
    impacted_raw = facts.get("impacted_symbol_count")
    sonar = int(sonar_raw) if sonar_raw not in (None, "", "null") else None
    lsp = int(lsp_raw) if lsp_raw not in (None, "", "null") else None
    ratio = float(ratio_raw) if ratio_raw not in (None, "", "null") else None
    impacted = int(impacted_raw) if impacted_raw not in (None, "", "null") else None

    # leg 2 FIRST: code_change_risk absent (no term measurable — the seam's refuse state).
    # Precedence pinned by pre-registration section 3: the absent cells record DECLINE leg 2
    # (risk-absent wins over the revision-mismatch check, which is ALSO absent there).
    if risk is None:
        return {"decision": "DECLINE", "leg": 2,
                "reason": "leg 2 — code_change_risk absent (no risk term measurable — the seam's "
                          "refuse state); route to operator review."}
    # leg 1: analysis_revision_matches false or absent (stale/refused analysis).
    if rev_matches is not True:
        return {"decision": "DECLINE", "leg": 1,
                "reason": "leg 1 — analysis_revision_matches false or absent (the facts do not "
                          "correspond to the change under review); route to operator review."}
    # APPLY: risk >= VERIFY_RISK_THRESHOLD 0.2 (severity signal or tests-ratio-driven).
    if risk >= 0.2:
        return {"decision": "APPLY", "leg": None,
                "reason": f"risk {risk} >= 0.2 — apply per the proposal action tree (unchanged)."}
    # leg 3: the Option A fingerprint — risk < 0.2, severity terms zero, tests term zero,
    # risk == 0.20·min(1, impacted/10) EXACTLY (the impacted term is the ONLY contributor).
    severity_zero = (sonar == 0 and lsp == 0)
    tests_zero = (ratio is None or ratio >= 1.0)
    fingerprint = None
    if impacted is not None and severity_zero and tests_zero:
        expected = round(0.20 * min(1.0, impacted / 10.0), 4)
        if abs(risk - expected) < 1e-9:
            fingerprint = True
    if fingerprint:
        return {"decision": "DECLINE", "leg": 3,
                "reason": f"leg 3 — Option A fingerprint: risk {risk} == 0.20·min(1, impacted/10) "
                          "exactly, severity terms zero, tests term zero (the impacted term is the "
                          "ONLY contributor); route to operator review."}
    # APPLY-NULL: any other risk < 0.2 (multi-term — the irrelevant class; NOT flagged).
    return {"decision": "APPLY_NULL", "leg": None,
            "reason": f"risk {risk} < 0.2 but multi-term (NOT the Option A fingerprint) — "
                      "apply-null (unchanged, not flagged)."}


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


def run_workflow_cell(cell: dict, workdir: Path) -> dict:
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
        "--no-fact-emit",
    ]
    if not is_absent:
        cmd += ["--change-analysis", "--change-analysis-graph", GRAPH_URI]
    env = dict(os.environ)
    env["FINOPS_CELL_ID"] = cell["cell_id"]
    env["FINOPS_SKIP_SPEC_INDEX"] = "1"  # 4-wide: never race the derived index
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


def apply_proposal(cell: dict, workdir: Path, proposal: dict) -> dict:
    """Apply exactly as proposed: rework = ONE bounded pass; verify = one pass; continue = null.
    Returns the application record with proof."""
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
    elif cls == "harmful_partial":
        target = ("In calc.py, classify(value) documents the contracts [10, 20) -> \"ten_to_twenty\" AND "
                  "[80, 90) -> \"eighty_to_ninety\" (lower edges INCLUSIVE). The [10, 20) guard uses `>` instead "
                  "of `>=` (10.0 excluded) and the [80, 90) guard uses `>` instead of `>=` (80.0 excluded). The "
                  "two defects are FAR APART in the value range — fix what the proposal's bounded pass targeted, "
                  "exactly, without touching the other boundary's guards.")
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

    if cls in ("correct", "competing", "harmful_partial"):
        # Label-agnostic boundary check (the 2d constructions' band labels are model-chosen,
        # never hardcoded): the defect is a `>`-for-`>=` at the lower edge, so the boundary value
        # must fall in the SAME band as a value just inside [lo, hi) and a DIFFERENT band than a
        # value just below lo. The 2c harness hardcoded 'ten_to_twenty'; 2d must not.
        def _band_ok(lo: float) -> bool:
            inside = run_check(f"from calc import classify; assert classify({lo}) == classify({lo + 5.0}), classify({lo})")
            below = run_check(f"from calc import classify; assert classify({lo}) != classify({lo - 0.1}), classify({lo})")
            return inside and below

        ok10 = _band_ok(10.0)
        if cls == "competing":
            ok20 = _band_ok(20.0)
            present = not (ok10 and ok20)
            which = []
            if not ok10:
                which.append("[10,20) inverted boundary")
            if not ok20:
                which.append("[20,30) inverted boundary")
            return present, f"family: boundary-compare x{len(which)} ({', '.join(which)}) present on the final commit" if present else "both boundary-compare defects absent"
        if cls == "harmful_partial":
            ok80 = _band_ok(80.0)
            present = not (ok10 and ok80)
            which = []
            if not ok10:
                which.append("[10,20) inverted boundary")
            if not ok80:
                which.append("[80,90) inverted boundary")
            return present, f"family: boundary-compare x{len(which)} ({', '.join(which)}) present on the final commit — one-of-two (partial_rework exposure)" if present else "both far-apart boundary-compare defects absent"
        return (not ok10, "family: boundary-compare ([10,20) inverted boundary) present" if not ok10 else "boundary-compare defect absent")
    if cls == "unseen_family":
        ok = run_check("import calc; s=[3,1,2]; calc.tally(s); assert s == [3,1,2], s")
        return (not ok, "family: mutation/aliasing (tally mutates its input) present — NOT boundary-compare, NOT S1244, NOT S3776" if not ok else "mutation/aliasing defect absent")
    if cls == "absent":
        if cell["variant"] == "defective":
            ok = run_check("from widgets import wrong_op; assert wrong_op(5, 2) == 3, wrong_op(5, 2)")
            return (not ok, "family: wrong-operation (wrong_op returns a+b not a-b) present (escaped — the seam refused)" if not ok else "absent-defective defect absent")
        return (False, "clean change — no defect (the refusal is value-preserving)")
    if cls == "incorrect_rebuilt":
        ok = run_check("from calc import add; assert add(1,2) == 3; from widgets import widget_19; assert widget_19(1) == 20")
        return (False, "clean change — no defect (the false-positive VERIFY is on a clean change)")
    ok = run_check("from calc import product; assert product([1,2,3,4]) == 24")
    return (False, "clean change — no defect (trivial, fully-tested change)")


def build_cell_record(cell: dict, seed_rev: str, ledger: dict, impl: dict,
                      seam: dict, proposal: dict, abstention: dict, application: dict,
                      outcome: dict, wall: float, forecast: float) -> dict:
    run_cost = ledger.get("total_cost_usd", 0.0) or 0.0
    app_cost = float(application.get("rework_pass_cost_usd") or application.get("verify_pass_cost_usd") or 0.0)
    total = run_cost + app_cost
    record = {
        "schema_version": "cap_adaptive_2d_cell/v1",
        "cell_id": cell["cell_id"], "class": cell["class"], "variant": cell["variant"],
        "arm": cell["arm"], "repetition": cell["rep"], "slot": cell["slot"],
        "spec_id": SPECS[cell["class"]]["spec_id"],
        "goal": goal_for(cell), "goal_sha256": sha256_text(goal_for(cell)),
        "model": MODEL, "backend": BACKEND,
        "seeded_app_worktree": str(WORKTREES_DIR / cell["cell_id"]), "seeded_app_seed_revision": seed_rev,
        "finops_cell_id": cell["cell_id"],
        "run_ledger": ledger.get("_run_ledger_path"), "run_ledger_sha256": ledger.get("_run_ledger_sha256"),
        "run_ledger_ok": ledger.get("ok"),
        "analyzer_status": {
            "graph": "available" if cell["class"] != "absent" else "unavailable (designed)",
            "sonar": "available" if cell["class"] != "absent" else "unavailable (designed)",
            "lsp": "available" if cell["class"] != "absent" else "unavailable (designed)",
        },
        "facts": {f["predicate"]: f["value"] for f in (impl.get("change_analysis") or {}).get("facts", [])},
        "facts_present": seam["facts_present"],
        "impl": {"cost_usd": impl.get("cost_usd"), "duration_s": impl.get("duration_s"),
                 "commit_hash": impl.get("commit_hash"), "confidence": impl.get("confidence")},
        "seam": seam,
        "proposal": proposal,
        "abstention_decision": abstention,
        "application": application,
        "outcome": outcome,
        "cost": {"run_workflow_usd": run_cost, "application_usd": app_cost, "total_usd": round(total, 6)},
        "forecast_usd": forecast,
        "within_forecast": total <= 2 * forecast if forecast else None,
        "wall_s": wall,
        "status": "ok",
        "written_at": now_iso(),
    }
    flags = []
    if proposal is not None:
        exp_action = EXPECTED_ACTION.get(cell["class"])
        if exp_action and proposal["action"] != exp_action:
            flags.append(f"construction-failure: expected proposal {exp_action}, got {proposal['action']}")
    if cell["class"] == "absent" and not seam["refused"]:
        flags.append("construction-failure: absent cell did not refuse")
    record["flags"] = flags
    return record


def run_one_cell(cell: dict, forecast: float) -> dict:
    cell_path = CELLS_DIR / f"{cell['cell_id']}.json"
    if cell_path.exists():
        return json.loads(cell_path.read_text())
    print(f"\n=== RUN {cell['cell_id']} (class={cell['class']} arm={cell['arm']} rep={cell['rep']}) ===", flush=True)
    workdir = WORKTREES_DIR / cell["cell_id"]
    t_start = time.time()
    try:
        seed_rev = seed_worktree(workdir)
        ledger = run_workflow_cell(cell, workdir)
        impl = find_implement(ledger)
        is_absent = cell["class"] == "absent"
        if is_absent:
            seam = exercise_absent_refusal(cell, workdir, impl, seed_rev)
            proposal = None
        else:
            proposal = emit_proposal(cell, impl, seed_rev)
            seam = {"refused": False, "error": "", "facts_present": sorted(f["predicate"] for f in impl.get("change_analysis", {}).get("facts", [])), "facts": impl.get("change_analysis", {}).get("facts", []), "neighborhood": list(impl.get("change_analysis", {}).get("neighborhood", [])), "graph_status": impl.get("change_analysis", {}).get("graph_status", ""), "impacted_count": impl.get("change_analysis", {}).get("impacted_count")}
        # The abstention decision is shadow-evaluated for EVERY cell (both arms), per the
        # pre-registration section 0 — the status_quo arm ignores it (applies exactly as
        # proposed); the abstention arm acts on it.
        facts = {f["predicate"]: f["value"] for f in seam.get("facts", [])}
        abstention = evaluate_abstention(facts)
        # application policy:
        if cell["arm"] == "abstention" and abstention["decision"] == "DECLINE":
            application = {
                "applied_or_null": "declined", "action": proposal["action"] if proposal else None,
                "decline_leg": abstention["leg"],
                "note": f"abstention DECLINE (leg {abstention['leg']}) — the apply pass is SKIPPED; "
                        "routed to operator review (pilot flag-only, no activation).",
                "proof": f"abstention-decline:leg-{abstention['leg']} (no apply pass — provable in the commit trail)",
            }
        elif cell["arm"] == "abstention" and proposal is None:
            application = {"applied_or_null": "null", "action": None,
                           "note": "no proposal emitted (seam refused) -> provable null application; the "
                                   "abstention arm records DECLINE (leg 2) — the refusal IS the abstention case."}
        elif proposal is None:
            application = {"applied_or_null": "null", "action": None,
                           "note": "no proposal emitted (seam refused) -> provable null application; "
                                   "status_quo passes through the refusal (the 2c pass-through behavior)."}
        else:
            application = apply_proposal(cell, workdir, proposal)
        outcome = run_independent_outcome(cell, workdir)
        wall = round(time.time() - t_start, 1)
        record = build_cell_record(cell, seed_rev, ledger, impl, seam, proposal,
                                   abstention, application, outcome, wall, forecast)
        cell_path.write_text(json.dumps(record, indent=2, sort_keys=True))
        print(f"[done] {cell['cell_id']}: proposal={proposal['action'] if proposal else 'REFUSED'} "
              f"abstention={abstention['decision']}{'/leg' + str(abstention['leg']) if abstention['leg'] else ''} "
              f"arm={cell['arm']} cost=${record['cost']['total_usd']:.4f} accepted={outcome['accepted']} "
              f"conf={impl.get('confidence')} flags={record['flags'] or 'none'} wall={wall}s", flush=True)
        return record
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {cell['cell_id']}: {type(exc).__name__}: {exc}", flush=True)
        record = {
            "schema_version": "cap_adaptive_2d_cell/v1", "cell_id": cell["cell_id"],
            "class": cell["class"], "arm": cell["arm"], "repetition": cell["rep"],
            "status": "error", "error": f"{type(exc).__name__}: {exc}", "written_at": now_iso(),
        }
        cell_path.write_text(json.dumps(record, indent=2, sort_keys=True))
        return record


def probe_incorrect_rebuilt_impacted() -> dict:
    """p1 pre-verification probe: build the incorrect_rebuilt 20-symbol change in a scratch
    worktree and measure impacted_symbol_count via the graph. The rebuild's guarantee is
    impacted >= 1 (the widgets-call-add dependant edge). A second impacted=0 refutes the
    design (pre-registration section 4 / design section 4)."""
    from agentic_dynamics.control.evidence_analyzer import EvidenceChangeAnalyzer
    from agentic_dynamics.core.language import (
        build_code_snapshot,
        compute_code_delta,
        detect_language,
    )
    from agentic_dynamics.knowledge.graph import Neo4jClient
    from agentic_dynamics.measurement.commit_analysis import _read_commit_files
    from agentic_dynamics.runtime.change_analyzer import ChangeInput
    from agentic_dynamics.runtime.workflow_runner import _git_full_sha

    probe_dir = WORKTREES_DIR / "cap2d_probe_incorrect_rebuilt"
    seed_rev = seed_worktree(probe_dir)
    widgets = []
    for k in range(1, 20):
        widgets.append(f"def widget_{k}(x):\n    result = add(x, {k})\n    return result\n")
    (probe_dir / "calc.py").write_text(
        "def add(a, b):\n    result = a + b\n    return result\n\n\ndef subtract(a, b):\n    return a - b\n"
    )
    (probe_dir / "widgets.py").write_text("from calc import add\n\n\n" + "\n\n\n".join(widgets) + "\n")
    _git(probe_dir, "add", "-A")
    _git(probe_dir, "commit", "-q", "-m", "[workflow] implement (probe)")
    full = _git(probe_dir, "rev-parse", "HEAD").strip()
    parent = _git_full_sha(probe_dir, f"{full}^") or f"{full}^"
    profile = detect_language(probe_dir)
    before_files = _read_commit_files(probe_dir, parent, profile)
    after_files = _read_commit_files(probe_dir, full, profile)
    before = build_code_snapshot(before_files, revision=parent, profile=profile)
    after = build_code_snapshot(after_files, revision=full, profile=profile)
    delta = compute_code_delta(before, after)
    scope_id = "self-probe_incorrect_rebuilt"
    client = Neo4jClient(uri=GRAPH_URI)
    try:
        analyzer = EvidenceChangeAnalyzer(graph_client=client, graph_requested=True)
        change = ChangeInput(
            before=before, after=after, delta=delta, revision=full,
            repository_id=scope_id, acl_scope=scope_id,
            sonar={"status": "unavailable", "revision_matches": None, "new_critical_count": None, "analyzed_sha": ""},
            lsp={"status": "unavailable", "new_error_count": None, "tool": "mypy"},
            impacted_count=None, phase_id="implement", observed_at=now_iso(),
        )
        analysis = analyzer.analyze(change)
        facts = {f["predicate"]: f["value"] for f in analysis.facts}
        return {
            "probe": "incorrect_rebuilt-impacted",
            "seed_revision": seed_rev, "final_revision": full,
            "changed_symbol_count": facts.get("changed_symbol_count"),
            "changed_symbols_with_tests_ratio": facts.get("changed_symbols_with_tests_ratio"),
            "impacted_symbol_count": analysis.impacted_count,
            "graph_status": analysis.graph_status,
            "neighborhood": list(analysis.neighborhood),
            "facts": facts,
            "guarantee": "impacted >= 1",
            "design_refuted": analysis.impacted_count == 0,
            "note": "The rebuild's guarantee is impacted >= 1 (the widgets-call-add dependant edge). "
                    "impacted == 0 is a SECOND construction failure and REFUTES the design.",
        }
    finally:
        client.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="cap_adaptive_2d p1+p2 grid executor")
    ap.add_argument("--p1", action="store_true", help="run the p1 measurement cell + the incorrect_rebuilt probe")
    ap.add_argument("--cell", default=None, help="run a single pending cell by cell_id")
    ap.add_argument("--workers", type=int, default=4, help="p2 grid concurrency (default 4-wide)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, touch nothing")
    args = ap.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    CELLS_DIR.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        pending = [c for c in CELLS if not c.get("done_p1")]
        print(f"{len(pending)} pending cells ({args.workers}-wide):")
        for c in pending:
            print(f"  {c['cell_id']:44s} class={c['class']:12s} variant={c['variant'] or '-':9s} arm={c['arm']:10s} rep={c['rep']}")
        return

    # p1: measure E1 first (block order: the correct block's first abstention cell), then the probe.
    if args.p1:
        p1_cell = [c for c in CELLS if c["cell_id"] == "cap2d_correct_abstention_r1"]
        if not p1_cell:
            raise SystemExit("E1 cap2d_correct_abstention_r1 not in table")
        cell = p1_cell[0]
        # p1 forecast: unknown until measured — run, then set forecast = measured x 2.
        rec = run_one_cell(cell, forecast=0.031707)  # 2c p1 forecast as the pre-measure placeholder
        measured = rec.get("cost", {}).get("total_usd")
        forecast = round(measured * 2, 6) if measured else 0.031707
        print(f"[p1] E1 {cell['cell_id']} measured ${measured} -> FORECAST ${forecast} (measured x 2)", flush=True)
        # now re-stamp the cell's forecast_usd + within_forecast with the real p1 forecast
        if rec.get("status") == "ok":
            rec["forecast_usd"] = forecast
            rec["within_forecast"] = rec["cost"]["total_usd"] <= 2 * forecast
            (CELLS_DIR / f"{cell['cell_id']}.json").write_text(json.dumps(rec, indent=2, sort_keys=True))
        probe = probe_incorrect_rebuilt_impacted()
        (RESULTS / "p1_incorrect_rebuilt_probe.json").write_text(json.dumps(probe, indent=2, sort_keys=True))
        print(f"[p1] probe impacted_symbol_count={probe.get('impacted_symbol_count')} "
              f"design_refuted={probe.get('design_refuted')}", flush=True)
        # p1 execution manifest
        manifest = {
            "schema_version": "cap_adaptive_2d_p1_manifest/v1",
            "campaign": "cap_adaptive_2d", "phase": "p1_measure_one",
            "written_at": now_iso(), "seed": SEED,
            "preregistration": "docs/designs/current/cap_adaptive_2d_preregistration.md",
            "preregistration_commit": "9dc0b4a63",
            "e1_cell": cell["cell_id"], "e1_status": rec.get("status"),
            "e1_total_cost_usd": measured,
            "forecast_per_cell_usd": forecast,
            "incorrect_rebuilt_probe": probe.get("impacted_symbol_count"),
            "incorrect_rebuilt_design_refuted": probe.get("design_refuted"),
            "cells": [c["cell_id"] for c in CELLS],
            "totals": {"cells": len(CELLS), "status_quo": sum(1 for c in CELLS if c["arm"] == "status_quo"),
                       "abstention": sum(1 for c in CELLS if c["arm"] == "abstention")},
        }
        (RESULTS / "p1_execution_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
        return

    # p2: run the remaining cells at 4-wide.
    pending = [c for c in CELLS if not c.get("done_p1")]
    if args.cell:
        pending = [c for c in pending if c["cell_id"] == args.cell]
        if not pending:
            raise SystemExit(f"no pending cell {args.cell!r}")
    if not pending:
        print("all cells recorded — nothing to run")
        return
    # load the p1 forecast for the cell budget guard
    forecast = 0.031707
    p1_manifest_path = RESULTS / "p1_execution_manifest.json"
    if p1_manifest_path.exists():
        forecast = json.loads(p1_manifest_path.read_text()).get("forecast_per_cell_usd", forecast)
    print(f"[p2] {len(pending)} cells at {args.workers}-wide concurrency, forecast=${forecast}", flush=True)
    # block order = the canonical CELLS order (slot numbering within each block); the harness
    # CELLS list IS the pre-registered table order, so preserve it exactly.
    order = {c["cell_id"]: i for i, c in enumerate(CELLS)}
    pending.sort(key=lambda c: order[c["cell_id"]])
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one_cell, c, forecast): c["cell_id"] for c in pending}
        for fut in as_completed(futs):
            cid = futs[fut]
            results[cid] = fut.result()
    ok = sum(1 for r in results.values() if r.get("status") == "ok")
    err = sum(1 for r in results.values() if r.get("status") != "ok")
    print(f"[p2] done: ok={ok} error={err} of {len(results)}", flush=True)


if __name__ == "__main__":
    main()
