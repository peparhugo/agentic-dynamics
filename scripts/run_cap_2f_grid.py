"""cap_adaptive_2f p1+p2 grid executor — the Option B follow-up (10 cells).

Phase p1/p2 of ``cap_adaptive_2f`` per the pre-registered table
(``docs/designs/current/cap_adaptive_2f_preregistration.md`` section 2 — 10 cells:
2 arms x 5 classes; unseen_family x2 + trivial_clean x2 + absent-defective x1 per arm). The
campaign re-tests B's capture at the ratio wall (unseen-family, expected ratio 0.5 -> the B
trigger never fires -> the wall, the fourth divergence) and MEASURES B's NEW claim — the
flag-cost leg: the decline on trivial fully test-linked clean changes (the wider net's price,
the PRIMARY outcome).

Per cell: fresh worktree, unique FINOPS_CELL_ID, proposal emitted + validated BEFORE the
outcome. The ABSTENTION arm shadow-evaluates the pinned B trigger per cell (leg 2 = risk absent
on the absent cells -> DECLINE; the B trigger = risk < 0.2 AND ratio >= 1.0 -> DECLINE on the
trivial_clean cells; the unseen-family cells measure ratio 0.5 -> no decline -> the wall,
recorded). DECLINE skips the apply pass and records the operator-review routing (the flag cost).
The STATUS_QUO arm applies exactly as proposed (continue = null). Outcomes INDEPENDENT (runtime
pytest + a per-class post-hoc defect determination).

p1 (``--p1``): (1) the unseen-family RATIO PROBE — builds the 2e-verbatim construction
(``tally(scores)`` mutation + the REQUIRED ``test_tally`` addition) in a scratch worktree and
MEASURES ``changed_symbols_with_tests_ratio`` with the REAL stack (sonar + lsp + graph + the
``code_change_facts/v2`` reducer). The pre-registered expectation: 0.5 (the wall). (2) the
trivial_clean PROBE — builds the trivial fully test-linked clean construction (private-variable
rename in a tested function) and MEASURES ratio == 1.0 AND risk < 0.2 (the B trigger MUST fire).
(3) E1 = ``cap2f_unseen_family_abstention_r1`` per the preregistration table (its p1
pre-verification measures the ratio — the wall check — before the grid runs).

p2 (default): runs the remaining 9 cells at 4-WIDE concurrency (ThreadPoolExecutor
max_workers=4), cells worktree-isolated, the p2 execution manifest written FIRST (no unlisted
cells).

Usage:
    python scripts/run_cap_2f_grid.py --p1               # p1: both probes + E1 + forecast
    python scripts/run_cap_2f_grid.py --dry-run          # print the plan, touch nothing
    python scripts/run_cap_2f_grid.py --cell <id>        # run one pending cell by cell_id
    python scripts/run_cap_2f_grid.py                    # run all pending cells at 4-wide
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
RESULTS = ROOT / "experiments" / "results" / "cap_adaptive_2f"
PROPOSALS = RESULTS / "proposals"
CELLS_DIR = RESULTS / "cells"
WORKTREES_DIR = Path("/tmp")

MODEL = os.environ.get("FINOPS_MODEL", FLASH_MODEL)
ensure_model_allowed(MODEL)
BACKEND = "opencode"
GRAPH_URI = "bolt://localhost:7687"

#: The preregistration's seed STRING (the human-readable reproducibility key). The preregistration
#: header documents ``sha256(seed_string)`` as ``e4f9c1a7...`` — p0 verification MEASURED that the
#: committed hash does NOT equal ``sha256(seed_string)`` (measured ``4d5ed42e...``). The grid is
#: fully enumerated in the preregistration table (no run-time randomization), so the mismatch does
#: not change any cell; it is recorded as a preregistration deviation, never silently corrected.
SEED_STRING = "cap_2f|option-B|flag-cost-primary|20260828"
SEED_COMMITTED_HASH = "e4f9c1a7b3d5e8f2a6c4b9d1e7f3a5c8b0d2e4f6a8c1b3d5e7f9a2c4b6d8e0f1a3"
SEED_MEASURED_HASH = hashlib.sha256(SEED_STRING.encode()).hexdigest()

#: The standard seed calc app (unseen_family + absent classes): add/subtract + their tests.
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

#: The trivial_clean seed: add() contains a private variable ``_result`` that the change renames
#: to ``_total`` — a behavior-preserving, fully test-linked clean change (the flag-cost leg).
SEED_CALC_TRIVIAL = """def add(a, b):
    _result = a + b
    return _result


def subtract(a, b):
    return a - b
"""

SEED_TEST_TRIVIAL = """from calc import add, subtract


def test_add():
    assert add(1, 2) == 3


def test_subtract():
    assert subtract(3, 1) == 2
"""

#: The canonical pre-registered 10-cell table (preregistration section 2). Slot = execution
#: order within a class block. No cell outside this table is ever run.
CELLS: list[dict] = [
    # unseen_family block (the capture leg AT the ratio wall) — E1 is the first abstention cell
    {"cell_id": "cap2f_unseen_family_abstention_r1", "class": "unseen_family", "variant": None, "arm": "abstention", "rep": "r1", "slot": 1, "done_p1": True},
    {"cell_id": "cap2f_unseen_family_abstention_r2", "class": "unseen_family", "variant": None, "arm": "abstention", "rep": "r2", "slot": 2},
    {"cell_id": "cap2f_unseen_family_status_quo_r1", "class": "unseen_family", "variant": None, "arm": "status_quo", "rep": "r1", "slot": 3},
    {"cell_id": "cap2f_unseen_family_status_quo_r2", "class": "unseen_family", "variant": None, "arm": "status_quo", "rep": "r2", "slot": 4},
    # trivial_clean block (the flag-cost leg — the PRIMARY outcome)
    {"cell_id": "cap2f_trivial_clean_abstention_r1", "class": "trivial_clean", "variant": None, "arm": "abstention", "rep": "r1", "slot": 1},
    {"cell_id": "cap2f_trivial_clean_abstention_r2", "class": "trivial_clean", "variant": None, "arm": "abstention", "rep": "r2", "slot": 2},
    {"cell_id": "cap2f_trivial_clean_status_quo_r1", "class": "trivial_clean", "variant": None, "arm": "status_quo", "rep": "r1", "slot": 3},
    {"cell_id": "cap2f_trivial_clean_status_quo_r2", "class": "trivial_clean", "variant": None, "arm": "status_quo", "rep": "r2", "slot": 4},
    # absent_defective block (the leg-2 mechanical class)
    {"cell_id": "cap2f_absent-defective_abstention_r1", "class": "absent", "variant": "defective", "arm": "abstention", "rep": "r1", "slot": 1},
    {"cell_id": "cap2f_absent-defective_status_quo_r1", "class": "absent", "variant": "defective", "arm": "status_quo", "rep": "r1", "slot": 2},
]

#: Per-class cell spec + goal. The unseen-family construction is 2e-verbatim (the aliasing defect
#: + the REQUIRED test_tally); the trivial_clean construction is the private-variable rename in a
#: tested function (the B trigger must fire); the absent-defective construction is 2c-verbatim.
SPECS = {
    "unseen_family": {
        "path": "workflows/operations/cap_2e_cell_unseen_family.yaml",
        "spec_id": "cap_2e_cell_unseen_family@0.1",
        "goal": "add a tally(scores) function to calc.py: documented to return a NEW list sorted "
                "in descending order WITHOUT modifying the input; implemented with "
                "scores.sort(reverse=True); return scores (so the input IS mutated — the single "
                "real mutation/aliasing defect). REQUIRED: also add a test_tally function to "
                "test_calc.py that asserts ONLY the return-value contract (sorted descending) — "
                "a PASSING test that does NOT assert whether the input was mutated, so the "
                "aliasing defect is invisible to it (it passes on the pre-mutation surface and "
                "still passes after; do not assert the input list is unchanged).",
    },
    "trivial_clean": {
        "path": "workflows/operations/cap_2f_cell_trivial_clean.yaml",
        "spec_id": "cap_2f_cell_trivial_clean@0.1",
        "goal": "rename the private variable `_result` inside add(a, b) in calc.py to `_total` — "
                "a behavior-preserving rename of a LOCAL variable inside a TESTED function "
                "(severity signals zero, changed_symbols_with_tests_ratio == 1.0, "
                "code_change_risk < 0.2 — the B trigger must fire). Do NOT change add's "
                "behavior, do NOT change subtract, do NOT change the tests, do NOT add any new "
                "function or file.",
    },
    "absent": {
        "path": "workflows/operations/cap_2c_cell_absent.yaml",
        "spec_id": "cap_2c_cell_absent@0.1",
        "goal_clean": "add a trivial pure helper widget(x) that returns x, in a NEW module widgets.py (no test file, not imported anywhere)",
        "goal_defective": "add wrong_op(a, b) to a NEW module widgets.py (no test file, not imported anywhere): documented to return a - b, implemented to return a + b (the single real defect)",
    },
}

#: Per-class expected proposal action (the class-instantiation falsifiability contract).
EXPECTED_ACTION = {
    "unseen_family": "continue",
    "trivial_clean": "continue",
    "absent": "refuse",
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
        return spec["goal_defective"] if cell["variant"] == "defective" else spec["goal_clean"]
    return spec["goal"]


def spec_path_for(cell: dict) -> str:
    return SPECS[cell["class"]]["path"]


#: The B-trigger decision table (preregistration section 3 + spec hard-rule 3) — shadow-evaluated
#: per cell. leg 2 FIRST: code_change_risk absent -> DECLINE leg 2 (the seam's refuse state). B
#: trigger: risk < 0.2 AND ratio >= 1.0 -> DECLINE leg 3 (the wider net — fires on the trivial
#: fully test-linked clean cells; the unseen-family cells measure ratio 0.5 -> no decline -> the
#: wall, APPLY_NULL). risk >= 0.2 -> APPLY. Anything else under 0.2 -> APPLY_NULL (multi-term —
#: the wall, NOT flagged).
def evaluate_b_trigger(facts: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the Option B rule over the measured facts dict (predicate -> value).

    Returns ``{decision, leg, reason}``. ``decision`` in {DECLINE, APPLY, APPLY_NULL};
    ``leg`` in {2, 3} for a DECLINE, else None.
    """
    risk_raw = facts.get("code_change_risk")
    risk = float(risk_raw) if risk_raw not in (None, "", "null") else None
    rev_matches_raw = facts.get("analysis_revision_matches")
    rev_matches = None if rev_matches_raw in (None, "", "null") else str(rev_matches_raw).lower() == "true"
    ratio_raw = facts.get("changed_symbols_with_tests_ratio")
    ratio = float(ratio_raw) if ratio_raw not in (None, "", "null") else None

    # leg 2 FIRST: code_change_risk absent (no term measurable — the seam's refuse state).
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
    # B trigger: risk < 0.2 AND ratio >= 1.0 (fully test-linked, severity zero) -> DECLINE.
    if ratio is not None and ratio >= 1.0:
        return {"decision": "DECLINE", "leg": 3,
                "reason": f"B trigger — risk {risk} < 0.2 AND changed_symbols_with_tests_ratio "
                          f"{ratio} >= 1.0 (fully test-linked, zero severity signals); route to "
                          "operator review (the flag-cost leg — the wider net's price)."}
    # APPLY_NULL: any other risk < 0.2 (multi-term — ratio < 1.0; the unseen-family wall).
    return {"decision": "APPLY_NULL", "leg": None,
            "reason": f"risk {risk} < 0.2 but ratio {ratio} < 1.0 (NOT the B trigger — the "
                      "unseen-family wall); apply-null (unchanged, not flagged)."}


def b_trigger_check(facts: dict[str, Any]) -> dict[str, Any]:
    """The pre-registered B-trigger check (preregistration section 3) — re-derived from the
    recorded facts: ``risk < 0.2 AND ratio >= 1.0`` fires; ratio 0.5 (the wall) does not."""
    risk_raw = facts.get("code_change_risk")
    risk = float(risk_raw) if risk_raw not in (None, "", "null") else None
    ratio_raw = facts.get("changed_symbols_with_tests_ratio")
    ratio = float(ratio_raw) if ratio_raw not in (None, "", "null") else None
    sonar = int(facts.get("new_sonar_critical_count") or 0)
    lsp = int(facts.get("new_lsp_error_count") or 0)
    severity_zero = (sonar == 0 and lsp == 0)
    risk_ok = risk is not None and risk < 0.2
    ratio_ok = ratio is not None and ratio >= 1.0
    fires = bool(risk_ok and ratio_ok and severity_zero)
    note = (
        "B trigger fires: risk < 0.2 AND ratio >= 1.0 AND severity terms zero — the wider net "
        "declines (the flag-cost leg)."
        if fires
        else f"B trigger does NOT fire — the wall. measured: risk={risk}, ratio={ratio}, "
             f"new_sonar_critical={sonar}, new_lsp_error={lsp}."
    )
    return {
        "risk": risk, "risk_ok": risk_ok,
        "ratio": ratio, "ratio_ok": ratio_ok,
        "severity_terms_zero": severity_zero,
        "new_sonar_critical_count": sonar, "new_lsp_error_count": lsp,
        "fires": fires, "note": note,
    }


def seed_worktree(workdir: Path, trivial: bool = False) -> str:
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "calc.py").write_text(SEED_CALC_TRIVIAL if trivial else SEED_CALC)
    (workdir / "test_calc.py").write_text(SEED_TEST_TRIVIAL if trivial else SEED_TEST)
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
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=2400, env=env)
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
    measured confidence field. Raises on a seam refusal."""
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
        "AgenticResult.confidence); recorded BEFORE the outcome."
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


def apply_proposal(cell: dict, workdir: Path, proposal: dict) -> dict:
    """Apply exactly as proposed: continue = provable null application (the unseen-family and
    trivial_clean action)."""
    action = proposal["action"]
    scope = ", ".join(proposal["scope"]) or "(empty)"
    if action == "continue":
        return {
            "applied_or_null": "null", "action": "continue", "rework_passes": 0,
            "note": "continue proposal -> provable null application (no extra pass); the change "
                    "stands exactly as implemented.",
            "proof": "provable-null:commit-trail",
        }
    raise RuntimeError(f"unexpected proposal action for cap_adaptive_2f: {action} (scope {scope})")


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
    """Post-hoc evaluator: present? which family? (per class)."""
    cls = cell["class"]
    def run_check(check: str) -> bool:
        p = subprocess.run(["python3", "-c", check], cwd=workdir, capture_output=True, text=True, timeout=120)
        return p.returncode == 0

    if cls == "unseen_family":
        ok = run_check("import calc; s=[3,1,2]; calc.tally(s); assert s == [3,1,2], s")
        return (not ok, "family: mutation/aliasing (tally mutates its input) present — NOT boundary-compare, NOT S1244, NOT S3776" if not ok else "mutation/aliasing defect absent")
    if cls == "trivial_clean":
        ok = run_check("import calc; assert calc.add(1, 2) == 3")
        return (not ok, "trivial_clean: behavior-preserving rename — no defect (clean change)" if ok else "trivial_clean: behavior NOT preserved (defect)")
    if cls == "absent":
        ok = run_check("from widgets import wrong_op; assert wrong_op(5, 2) == 3, wrong_op(5, 2)")
        return (not ok, "family: wrong-operation (wrong_op returns a+b not a-b) present (escaped — the seam refused)" if not ok else "absent-defective defect absent")
    return (False, "no defect (clean change)")


def build_cell_record(cell: dict, seed_rev: str, ledger: dict, impl: dict,
                      seam: dict, proposal: dict, abstention: dict, application: dict,
                      outcome: dict, wall: float, forecast: float,
                      trigger: dict | None = None) -> dict:
    run_cost = ledger.get("total_cost_usd", 0.0) or 0.0
    app_cost = float(application.get("rework_pass_cost_usd") or application.get("verify_pass_cost_usd") or 0.0)
    total = run_cost + app_cost
    facts = {f["predicate"]: f["value"] for f in (impl.get("change_analysis") or {}).get("facts", [])}
    if cell["class"] == "absent":
        facts = {f["predicate"]: f["value"] for f in seam.get("facts", [])}
    record = {
        "schema_version": "cap_adaptive_2f_cell/v1",
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
        "facts": facts,
        "facts_present": seam["facts_present"],
        "b_trigger_check": trigger,
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
    if cell["class"] == "trivial_clean" and (trigger or {}).get("fires") is False:
        flags.append(
            "construction-failure: the trivial_clean B trigger did NOT fire (ratio must be 1.0, "
            "risk < 0.2, severity zero)"
        )
    if cell["class"] == "unseen_family" and (trigger or {}).get("fires"):
        flags.append(
            "unexpected: the unseen-family B trigger fired (the pre-registered wall expects ratio "
            "0.5 -> no decline — a construction divergence if it fires)"
        )
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
        trivial = cell["class"] == "trivial_clean"
        seed_rev = seed_worktree(workdir, trivial=trivial)
        ledger = run_workflow_cell(cell, workdir)
        impl = find_implement(ledger)
        is_absent = cell["class"] == "absent"
        if is_absent:
            seam = exercise_absent_refusal(cell, workdir, impl, seed_rev)
            proposal = None
        else:
            proposal = emit_proposal(cell, impl, seed_rev)
            seam = {"refused": False, "error": "", "facts_present": sorted(f["predicate"] for f in impl.get("change_analysis", {}).get("facts", [])), "facts": impl.get("change_analysis", {}).get("facts", []), "neighborhood": list(impl.get("change_analysis", {}).get("neighborhood", [])), "graph_status": impl.get("change_analysis", {}).get("graph_status", ""), "impacted_count": impl.get("change_analysis", {}).get("impacted_count")}
        facts = {f["predicate"]: f["value"] for f in seam.get("facts", [])}
        trigger = b_trigger_check(facts) if cell["class"] in ("unseen_family", "trivial_clean") else None
        abstention = evaluate_b_trigger(facts)
        # application policy: the abstention arm acts on the decision; status_quo applies exactly
        # as proposed (continue = null).
        if cell["arm"] == "abstention" and abstention["decision"] == "DECLINE":
            application = {
                "applied_or_null": "declined", "action": proposal["action"] if proposal else None,
                "decline_leg": abstention["leg"],
                "note": f"abstention DECLINE (leg {abstention['leg']}) — the apply pass is SKIPPED; "
                        "routed to operator review (pilot flag-only, no activation). The decline "
                        "overhead + operator-review routing on a change that needed nothing = the "
                        "flag cost (the PRIMARY).",
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
                                   abstention, application, outcome, wall, forecast,
                                   trigger=trigger)
        cell_path.write_text(json.dumps(record, indent=2, sort_keys=True))
        print(f"[done] {cell['cell_id']}: proposal={proposal['action'] if proposal else 'REFUSED'} "
              f"abstention={abstention['decision']}{'/leg' + str(abstention['leg']) if abstention['leg'] else ''} "
              f"b_trigger_fires={bool(trigger and trigger['fires'])} "
              f"arm={cell['arm']} cost=${record['cost']['total_usd']:.4f} accepted={outcome['accepted']} "
              f"conf={impl.get('confidence')} flags={record['flags'] or 'none'} wall={wall}s", flush=True)
        return record
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {cell['cell_id']}: {type(exc).__name__}: {exc}", flush=True)
        record = {
            "schema_version": "cap_adaptive_2f_cell/v1", "cell_id": cell["cell_id"],
            "class": cell["class"], "arm": cell["arm"], "repetition": cell["rep"],
            "status": "error", "error": f"{type(exc).__name__}: {exc}", "written_at": now_iso(),
        }
        cell_path.write_text(json.dumps(record, indent=2, sort_keys=True))
        return record


def probe_unseen_family_ratio() -> dict:
    """p1 pre-verification probe: build the 2e-verbatim unseen-family construction (the
    ``tally(scores)`` mutation + the REQUIRED ``test_tally`` addition — a passing test whose
    aliasing is invisible to it) in a scratch worktree and MEASURE ``changed_symbols_with_tests_ratio``
    with the REAL stack (sonar + lsp + graph + the code_change_facts/v2 reducer). The
    preregistration expectation: 0.5 (the wall — the 2e mutual-exclusivity verdict). A ratio of
    1.0 would be a CONSTRUCTION DIVERGENCE (recorded; the wall check is the p1 finding either way)."""
    from agentic_dynamics.control.evidence_analyzer import EvidenceChangeAnalyzer
    from agentic_dynamics.knowledge.graph import Neo4jClient
    from agentic_dynamics.runtime.workflow_runner import (
        PhaseResult,
        _git_full_sha,
        _run_change_analysis,
    )

    probe_dir = WORKTREES_DIR / "cap2f_probe_unseen_family"
    seed_rev = seed_worktree(probe_dir)
    (probe_dir / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef subtract(a, b):\n    return a - b\n\n\n"
        "def tally(scores):\n    scores.sort(reverse=True)\n    return scores\n"
    )
    (probe_dir / "test_calc.py").write_text(
        "from calc import add, subtract, tally\n\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n\n\n"
        "def test_subtract():\n    assert subtract(3, 1) == 2\n\n\n"
        "def test_tally():\n    s = [3, 1, 2]\n    result = tally(s)\n"
        "    assert result == [3, 2, 1]\n"
    )
    _git(probe_dir, "add", "-A")
    _git(probe_dir, "commit", "-q", "-m", "[workflow] implement (probe)")
    full = _git_full_sha(probe_dir, "HEAD") or "HEAD"
    pr = PhaseResult(phase="implement", kind="agent", status="ok", commit_hash=full[:12], model="probe")
    client = Neo4jClient(uri=GRAPH_URI)
    try:
        analyzer = EvidenceChangeAnalyzer(graph_client=client, graph_requested=True)
        _run_change_analysis(pr, probe_dir, analyzer)
    finally:
        client.close()
    ca = pr.change_analysis
    facts = {f["predicate"]: f["value"] for f in ca["facts"]}
    check = b_trigger_check(facts)
    return {
        "probe": "unseen-family-ratio",
        "seed_revision": seed_rev, "final_revision": full,
        "construction": "2e-verbatim: tally(scores) mutation (sorts in place) + REQUIRED test_tally "
                        "addition (asserts only the return-value contract — the aliasing defect is invisible)",
        "facts": facts,
        "graph_status": ca.get("graph_status"),
        "neighborhood": list(ca.get("neighborhood")),
        "impacted_symbol_count": ca.get("impacted_count"),
        "b_trigger_check": check,
        "construction_divergence": check["fires"],
        "note": "The pre-registered expectation is ratio 0.5 (the wall — the 2e mutual-exclusivity "
                "verdict: a new test-file function is a changed symbol but is never test-linked, so "
                "the REQUIRED test_tally forces changed_symbol_count = 2 while only tally is "
                "test-linked -> ratio 0.5 -> multi-term risk, B's ratio-1.0 trigger never fires). "
                "A measured ratio of 1.0 would be a CONSTRUCTION DIVERGENCE (recorded; the wall "
                "check is the p1 finding either way).",
    }


def probe_trivial_clean() -> dict:
    """p1 pre-verification probe: build the trivial_clean construction (the private-variable rename
    in a tested function — behavior-preserving, severity zero) in a scratch worktree and MEASURE
    ratio == 1.0 AND risk < 0.2 with the REAL stack — the B trigger MUST fire on it (the flag-cost
    leg's construction). A non-firing trigger is a CONSTRUCTION DIVERGENCE."""
    from agentic_dynamics.control.evidence_analyzer import EvidenceChangeAnalyzer
    from agentic_dynamics.knowledge.graph import Neo4jClient
    from agentic_dynamics.runtime.workflow_runner import (
        PhaseResult,
        _git_full_sha,
        _run_change_analysis,
    )

    probe_dir = WORKTREES_DIR / "cap2f_probe_trivial_clean"
    seed_rev = seed_worktree(probe_dir, trivial=True)
    (probe_dir / "calc.py").write_text(
        "def add(a, b):\n    _total = a + b\n    return _total\n\n\n"
        "def subtract(a, b):\n    return a - b\n"
    )
    (probe_dir / "test_calc.py").write_text(
        "from calc import add, subtract\n\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n\n\n"
        "def test_subtract():\n    assert subtract(3, 1) == 2\n"
    )
    _git(probe_dir, "add", "-A")
    _git(probe_dir, "commit", "-q", "-m", "[workflow] implement (probe)")
    full = _git_full_sha(probe_dir, "HEAD") or "HEAD"
    pr = PhaseResult(phase="implement", kind="agent", status="ok", commit_hash=full[:12], model="probe")
    client = Neo4jClient(uri=GRAPH_URI)
    try:
        analyzer = EvidenceChangeAnalyzer(graph_client=client, graph_requested=True)
        _run_change_analysis(pr, probe_dir, analyzer)
    finally:
        client.close()
    ca = pr.change_analysis
    facts = {f["predicate"]: f["value"] for f in ca["facts"]}
    check = b_trigger_check(facts)
    return {
        "probe": "trivial-clean-b-trigger",
        "seed_revision": seed_rev, "final_revision": full,
        "construction": "private-variable rename (_result -> _total) inside the tested function "
                        "add() — behavior-preserving, severity signals zero, fully test-linked",
        "facts": facts,
        "graph_status": ca.get("graph_status"),
        "neighborhood": list(ca.get("neighborhood")),
        "impacted_symbol_count": ca.get("impacted_count"),
        "b_trigger_check": check,
        "construction_divergence": not check["fires"],
        "note": "The B trigger MUST fire on the trivial_clean construction (ratio == 1.0 AND "
                "risk < 0.2 AND severity zero) — that is the flag-cost leg's construction. A "
                "non-firing trigger is a CONSTRUCTION DIVERGENCE.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="cap_adaptive_2f p1+p2 grid executor")
    ap.add_argument("--p1", action="store_true", help="run the probes + E1")
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
            print(f"  {c['cell_id']:46s} class={c['class']:12s} arm={c['arm']:10s} rep={c['rep']}")
        return

    if args.p1:
        # (1) the unseen-family RATIO probe FIRST (the pre-verification wall check).
        probe_wall = probe_unseen_family_ratio()
        (RESULTS / "p1_unseen_family_probe.json").write_text(json.dumps(probe_wall, indent=2, sort_keys=True))
        print(f"[p1] probe unseen-family: ratio={probe_wall['b_trigger_check']['ratio']} "
              f"risk={probe_wall['b_trigger_check']['risk']} "
              f"fires={probe_wall['b_trigger_check']['fires']} "
              f"divergence={probe_wall['construction_divergence']}", flush=True)
        # (2) the trivial_clean B-trigger probe (the flag-cost leg's construction).
        probe_triv = probe_trivial_clean()
        (RESULTS / "p1_trivial_clean_probe.json").write_text(json.dumps(probe_triv, indent=2, sort_keys=True))
        print(f"[p1] probe trivial_clean: ratio={probe_triv['b_trigger_check']['ratio']} "
              f"risk={probe_triv['b_trigger_check']['risk']} "
              f"fires={probe_triv['b_trigger_check']['fires']} "
              f"divergence={probe_triv['construction_divergence']}", flush=True)
        # (3) E1 = the unseen-family abstention r1 cell (the wall check on a real cell).
        p1_cell = [c for c in CELLS if c["cell_id"] == "cap2f_unseen_family_abstention_r1"]
        if not p1_cell:
            raise SystemExit("E1 cap2f_unseen_family_abstention_r1 not in table")
        cell = p1_cell[0]
        rec = run_one_cell(cell, forecast=0.01)
        measured = rec.get("cost", {}).get("total_usd")
        forecast = round(measured * 2, 6) if measured else 0.01
        print(f"[p1] E1 {cell['cell_id']} measured ${measured} -> FORECAST ${forecast} (measured x 2)", flush=True)
        if rec.get("status") == "ok":
            rec["forecast_usd"] = forecast
            rec["within_forecast"] = rec["cost"]["total_usd"] <= 2 * forecast
            (CELLS_DIR / f"{cell['cell_id']}.json").write_text(json.dumps(rec, indent=2, sort_keys=True))
        manifest = {
            "schema_version": "cap_adaptive_2f_p1_manifest/v1",
            "campaign": "cap_adaptive_2f", "phase": "p1_probe_and_e1",
            "written_at": now_iso(), "seed_string": SEED_STRING,
            "seed_committed_hash": SEED_COMMITTED_HASH, "seed_measured_sha256": SEED_MEASURED_HASH,
            "seed_mismatch": SEED_COMMITTED_HASH != SEED_MEASURED_HASH,
            "preregistration": "docs/designs/current/cap_adaptive_2f_preregistration.md",
            "preregistration_revision": "d199c50b6",
            "probe_unseen_family": probe_wall,
            "probe_trivial_clean": probe_triv,
            "e1_cell": cell["cell_id"], "e1_status": rec.get("status"),
            "e1_total_cost_usd": measured,
            "forecast_per_cell_usd": forecast,
            "cells": [c["cell_id"] for c in CELLS],
            "totals": {"cells": len(CELLS), "status_quo": sum(1 for c in CELLS if c["arm"] == "status_quo"),
                       "abstention": sum(1 for c in CELLS if c["arm"] == "abstention")},
        }
        (RESULTS / "p1_execution_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
        return

    # p2: write the execution manifest FIRST (immutable), then run the remaining cells at 4-wide.
    manifest = {
        "schema_version": "cap_adaptive_2f_p2_manifest/v1",
        "campaign": "cap_adaptive_2f", "phase": "p2_run_grid",
        "written_at": now_iso(), "seed_string": SEED_STRING,
        "seed_committed_hash": SEED_COMMITTED_HASH, "seed_measured_sha256": SEED_MEASURED_HASH,
        "seed_mismatch": SEED_COMMITTED_HASH != SEED_MEASURED_HASH,
        "preregistration": "docs/designs/current/cap_adaptive_2f_preregistration.md",
        "preregistration_revision": "d199c50b6",
        "cells": [
            {**c, "repetition": c["rep"]}
            for c in CELLS
        ],
        "totals": {"cells": len(CELLS), "status_quo": sum(1 for c in CELLS if c["arm"] == "status_quo"),
                   "abstention": sum(1 for c in CELLS if c["arm"] == "abstention")},
    }
    (RESULTS / "p2_execution_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    pending = [c for c in CELLS if not c.get("done_p1")]
    if args.cell:
        pending = [c for c in pending if c["cell_id"] == args.cell]
        if not pending:
            raise SystemExit(f"no pending cell {args.cell!r}")
    if not pending:
        print("all cells recorded — nothing to run")
        return
    forecast = 0.01
    p1_manifest_path = RESULTS / "p1_execution_manifest.json"
    if p1_manifest_path.exists():
        forecast = json.loads(p1_manifest_path.read_text()).get("forecast_per_cell_usd", forecast)
    print(f"[p2] {len(pending)} cells at {args.workers}-wide concurrency, forecast=${forecast}", flush=True)
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

    # immutable record-SHA index (the p2 deliverable).
    records = {}
    for c in CELLS:
        p = CELLS_DIR / f"{c['cell_id']}.json"
        if p.exists():
            records[c["cell_id"]] = {"sha256": sha256_file(p), "status": json.loads(p.read_text()).get("status")}
    (RESULTS / "p2_records_sha_index.json").write_text(
        json.dumps({"schema_version": "cap_adaptive_2f_p2_records_sha_index/v1",
                    "campaign": "cap_adaptive_2f", "written_at": now_iso(),
                    "records": records}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
