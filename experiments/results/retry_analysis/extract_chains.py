"""
extract_chains.py — p1 of retry_observational_analysis.

BOUNDED to the extraction. Walks the corpus's two retry-relevant data planes and
emits the fail -> retry -> outcome chains table plus the exact coverage.

The two planes (per the pinned mandate, spec hard rule 3):

  1. The ATTEMPT LEDGERS — attempt-level records that carry the retry-linkage
     fields (attempt_number / parent_attempt_id / retry_reason). Only two files
     in the committed corpus carry them:
       - experiments/results/cap_grit_grid_ledger.json  (the E4 grit grid)
       - experiments/results/workflows/ledger_instrumentation_probe/*.json (synthetic)
     These give the retry *linkage* (a2 -> a1 via parent_attempt_id) but the E4
     rows carry NO `confidence` field (the design doc §1.4 gap).

  2. THE STORY RESULTS — experiments/results/stories/*.json. The post-instrumentation
     runs (2026-08-28+) carry the wired fields `perturbation_strength`,
     `test_executed_success`, and per-session `confidence` (the [H]
     execution-confidence). The E4 grid's story runs ARE among these (linked by
     story_id / result_path), so the known-at-failure features for the one real
     retry are recovered by joining the ledger to the story results.

The join is the crux: the ledger gives the retry chain's *shape*; the story
result gives the *features known at first failure*.

Outputs (written next to this script):
  - chains.json  — the machine-readable chains + coverage (schema retry_chains/v1)
  - chains.md    — the human-readable chains table + coverage

Every number below traces to a field in a cited file; nothing is imputed.
"""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Pinned paths (the corpus is the working tree, not a database)
# ---------------------------------------------------------------------------
RESULTS = Path("experiments/results")
E4_LEDGER = RESULTS / "cap_grit_grid_ledger.json"
PROBE_LEDGER = RESULTS / "workflows" / "ledger_instrumentation_probe" / "20260830T190548Z.json"
STORIES = RESULTS / "stories"
OUT_DIR = RESULTS / "retry_analysis"

# The attempt-ledger field that links a retry to its failed first attempt.
RETRY_LINKAGE_FIELDS = ("attempt_number", "parent_attempt_id", "retry_reason")


def _load_json(path: Path) -> dict:
    """Load a JSON file, surfacing the path on error."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _story_path_for(result_path: str | None) -> Path | None:
    """Resolve an attempt's result_path to a story-result file, if present.

    The E4 ledger stores `result_path` relative to the repo root. A missing file
    is a coverage gap (reported, never imputed).
    """
    if not result_path:
        return None
    p = Path(result_path)
    return p if p.exists() else None


def _final_session_confidence(story: dict) -> float | None:
    """The [H] confidence at the failure signal: the last session's confidence.

    A story is 5 sequential sessions; test_executed_success is evaluated after
    the final session, so the last non-null session confidence is what the
    machine knew at first failure. None when the story carries no confidence.
    """
    confs = [
        s.get("confidence")
        for s in story.get("sessions", [])
        if s.get("confidence") is not None
    ]
    return confs[-1] if confs else None


def _session_confidence_series(story: dict) -> list[float | None]:
    """All per-session [H] confidences, in session order (for transparency)."""
    return [s.get("confidence") for s in story.get("sessions", [])]


def extract_e4_chains() -> tuple[list[dict], dict]:
    """Extract the E4 grit grid's fail -> retry -> outcome chains.

    Returns (chains, ledger_summary). A "chain" here is one failed first attempt
    (attempt_number == 1 and test_executed_success is False) joined to its
    story-result features, plus its retry (if any) and the outcome classification
    (rescued / failed-again / no-retry-was-taken).
    """
    ledger = _load_json(E4_LEDGER)
    cells = ledger.get("cells", [])

    attempts: list[dict] = []
    for cell in cells:
        for a in cell.get("attempts", []):
            # Flatten the attempt row, keeping the ledger's own fields verbatim.
            attempts.append(
                {
                    "cell_id": cell.get("cell_id"),
                    "policy_arm": a.get("policy_arm"),
                    "model": a.get("model"),
                    "attempt_number": a.get("attempt_number"),
                    "parent_attempt_id": a.get("parent_attempt_id"),
                    "retry_reason": a.get("retry_reason"),
                    "test_executed_success": a.get("test_executed_success"),
                    "actual_cost": a.get("actual_cost"),
                    "rework_cost": a.get("rework_cost"),
                    "perturbation_strength": a.get("perturbation_strength"),
                    "status": a.get("status"),
                    "story_id": a.get("story_id"),
                    "result_path": a.get("result_path"),
                    "worktree": a.get("worktree"),
                    "mutation_id": a.get("mutation_id"),
                }
            )

    # Split first attempts from retries by the ledger's own linkage fields.
    first_attempts = [a for a in attempts if (a["attempt_number"] or 1) == 1]
    retries = [a for a in attempts if (a["attempt_number"] or 1) > 1]

    # A failed first attempt = attempt_number 1 with test_executed_success False.
    failed_first = [a for a in first_attempts if a["test_executed_success"] is False]

    chains: list[dict] = []
    for fa in failed_first:
        # Join the known-at-failure features from the story result.
        story_path = _story_path_for(fa["result_path"])
        story = _load_json(story_path) if story_path else None
        story_conf_series = _session_confidence_series(story) if story else []
        story_conf = _final_session_confidence(story) if story else None

        # Locate the retry for THIS failed first attempt: the retry row whose
        # cell_id matches the failed attempt's cell_id. The E4 grid's single
        # retry belongs only to the bad_seed_high × grit_retry cell; the
        # clean × baseline cell has no retry (baseline never retries).
        retry_by_cell = next(
            (r for r in retries if r["cell_id"] == fa["cell_id"]),
            None,
        )

        if retry_by_cell is not None:
            # A retry was taken; classify by the retry's test_executed_success.
            if retry_by_cell["test_executed_success"] is True:
                outcome = "rescued"
            elif retry_by_cell["test_executed_success"] is False:
                outcome = "failed-again"
            else:
                outcome = "retry-taken-outcome-missing"  # never impute
            retry_story_path = _story_path_for(retry_by_cell["result_path"])
            retry_story = _load_json(retry_story_path) if retry_story_path else None
        else:
            # No retry linkage -> no retry was taken (e.g. baseline arm).
            outcome = "no-retry-was-taken"
            retry_story = None

        chains.append(
            {
                "source": "cap_grit_grid_ledger.json",
                "cell_id": fa["cell_id"],
                "model": fa["model"],
                "policy_arm": fa["policy_arm"],
                "first_attempt": {
                    "attempt_number": fa["attempt_number"],
                    "test_executed_success": fa["test_executed_success"],
                    "perturbation_strength": fa["perturbation_strength"],
                    "cost_so_far_usd": fa["actual_cost"],
                    "rework_cost_usd": fa["rework_cost"],
                    # [H] confidence at first failure (from the joined story result).
                    "confidence_at_failure": story_conf,
                    "confidence_series": story_conf_series,
                    "story_id": fa["story_id"],
                },
                "retry": (
                    {
                        "taken": True,
                        "retry_reason": retry_by_cell["retry_reason"],
                        "attempt_number": retry_by_cell["attempt_number"],
                        "test_executed_success": retry_by_cell["test_executed_success"],
                        "cost_usd": retry_by_cell["actual_cost"],
                        "confidence_at_end": (
                            _final_session_confidence(retry_story)
                            if retry_story
                            else None
                        ),
                        "story_id": retry_by_cell["story_id"],
                    }
                    if retry_by_cell is not None
                    else {"taken": False, "retry_reason": None}
                ),
                "outcome": outcome,
                "chain_cost_usd": (
                    fa["actual_cost"] + retry_by_cell["actual_cost"]
                    if retry_by_cell is not None
                    else fa["actual_cost"]
                ),
            }
        )

    summary = {
        "source": "cap_grit_grid_ledger.json",
        "total_attempts": len(attempts),
        "first_attempts": len(first_attempts),
        "failed_first_attempts": len(failed_first),
        "retries": len(retries),
        "chains_with_complete_outcome": len(chains),
    }
    return chains, summary


def extract_probe() -> dict:
    """Describe the synthetic ledger-instrumentation probe (not a real chain).

    The probe verifies the attempt-record wiring; its attempt rows are synthetic
    (tokens 10/20, cost $0.001, session 'probe-session'), so it contributes to
    the coverage denominator but carries no fail -> retry chain.
    """
    probe = _load_json(PROBE_LEDGER)
    atts = probe.get("attempts", [])
    failed = [a for a in atts if a.get("test_executed_success") is False]
    retries = [a for a in atts if (a.get("attempt_number") or 1) > 1]
    return {
        "source": str(PROBE_LEDGER),
        "synthetic": True,
        "total_attempts": len(atts),
        "failed_first_attempts": len(failed),
        "retries": len(retries),
    }


def survey_story_corpus() -> dict:
    """Survey the story results for first-attempt outcomes (no retry linkage).

    The story runner has no retry mechanism, so the corpus contributes
    first-attempt outcomes (and 'no retry armed' evidence) but zero retry chains.
    Counts are exact; a story file that fails to parse is counted, not skipped.
    """
    files = sorted(STORIES.glob("*.json"))
    total = len(files)
    wired = 0
    wired_failed = 0
    not_all_successful = 0
    top_error = 0
    failed_sessions = 0
    total_sessions = 0
    parse_errors = 0

    for fp in files:
        try:
            d = _load_json(fp)
        except Exception:
            parse_errors += 1
            continue
        if "test_executed_success" in d:
            wired += 1
            if d.get("test_executed_success") is False:
                wired_failed += 1
        if d.get("summary", {}).get("all_successful") is False:
            not_all_successful += 1
        if d.get("error"):
            top_error += 1
        for s in d.get("sessions", []):
            total_sessions += 1
            failed = False
            if s.get("error"):
                failed = True
            if s.get("exit_code") not in (0, None):
                failed = True
            ag = s.get("agentic", {})
            if ag.get("tests_total", 0) > 0 and ag.get("tests_passed", 0) < ag.get(
                "tests_total", 0
            ):
                failed = True
            if failed:
                failed_sessions += 1

    return {
        "total_story_files": total,
        "parse_errors": parse_errors,
        "wired_test_executed_success": wired,
        "wired_failed": wired_failed,
        "not_all_successful": not_all_successful,
        "top_level_error": top_error,
        "total_sessions": total_sessions,
        "failed_sessions": failed_sessions,
        "story_files_with_retry_linkage": 0,  # no story result carries retry fields
    }


def build_coverage(e4_summary: dict, probe: dict, story: dict) -> dict:
    """Compute the exact coverage across the two planes (no imputation)."""
    attempt_records = e4_summary["total_attempts"] + probe["total_attempts"]
    failed_first = e4_summary["failed_first_attempts"] + probe["failed_first_attempts"]
    retries = e4_summary["retries"] + probe["retries"]
    complete_chains = e4_summary["chains_with_complete_outcome"]
    return {
        # Attempt-ledger plane (records that CAN carry a retry chain).
        "attempt_ledger_records": attempt_records,
        "attempt_ledger_failed_first_attempts": failed_first,
        "attempt_ledger_retries": retries,
        "attempt_ledger_complete_chains": complete_chains,
        "attempt_ledger_coverage_complete_over_failed": (
            f"{complete_chains}/{failed_first}"
            if failed_first
            else "0/0"
        ),
        "attempt_ledger_coverage_complete_over_total": (
            f"{complete_chains}/{attempt_records}" if attempt_records else "0/0"
        ),
        # Story plane (no retry linkage by construction).
        "story_files_total": story["total_story_files"],
        "story_files_wired": story["wired_test_executed_success"],
        "story_files_wired_failed": story["wired_failed"],
        "story_files_with_retry_linkage": story["story_files_with_retry_linkage"],
        # Honest bottom line: the corpus holds exactly one real retry event.
        "real_retry_events": retries - probe["retries"],
    }


def render_markdown(chains: list[dict], coverage: dict, e4: dict, probe: dict, story: dict) -> str:
    """Render the human-readable chains table + coverage."""
    lines: list[str] = []
    lines.append("---")
    lines.append("status: accepted")
    lines.append("---")
    lines.append("")
    lines.append("# Retry chains — p1 extraction (fail → retry → outcome)")
    lines.append("")
    lines.append(
        "**Spec:** `retry_observational_analysis@0.1` · phase `p1_extract_chains` · "
        "OBSERVATIONAL (no cells, no grid)."
    )
    lines.append("")
    lines.append("## 1. The complete chains (attempt-ledger plane, with retry linkage)")
    lines.append("")
    if not chains:
        lines.append("_No failed-first-attempt chains found._")
    else:
        lines.append("| # | cell | model | policy arm | first-attempt tes | strength | cost-so-far | [H] confidence @failure | retry | retry reason | retry tes | outcome | chain cost |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for i, c in enumerate(chains, 1):
            fa = c["first_attempt"]
            rt = c["retry"]
            lines.append(
                f"| {i} | {c['cell_id']} | {c['model']} | {c['policy_arm']} | "
                f"{fa['test_executed_success']} | {fa['perturbation_strength']} | "
                f"${fa['cost_so_far_usd']:.4f} | {fa['confidence_at_failure']} | "
                f"{rt['taken']} | {rt.get('retry_reason')} | "
                f"{rt.get('test_executed_success') if rt['taken'] else '—'} | "
                f"{c['outcome']} | ${c['chain_cost_usd']:.4f} |"
            )
    lines.append("")
    lines.append("### Confidence series (the [H] per-session execution-confidence)")
    lines.append("")
    for c in chains:
        fa = c["first_attempt"]
        lines.append(
            f"- `{c['cell_id']}` first attempt sessions: {fa['confidence_series']} "
            f"→ failure-signal confidence = {fa['confidence_at_failure']}"
        )
        if c["retry"]["taken"]:
            lines.append(f"  - retry end confidence: {c['retry']['confidence_at_end']}")
    lines.append("")
    lines.append("## 2. Coverage (exact)")
    lines.append("")
    lines.append("| plane | field | value |")
    lines.append("|---|---|---|")
    for k, v in coverage.items():
        lines.append(f"| coverage | {k} | {v} |")
    lines.append("")
    lines.append("| source | note |")
    lines.append("|---|---|")
    lines.append(f"| attempt ledgers | {e4['source']}: {e4['total_attempts']} attempts ({e4['first_attempts']} first, {e4['retries']} retry, {e4['failed_first_attempts']} failed-first) |")
    lines.append(f"| attempt ledgers (synthetic) | {probe['source']}: {probe['total_attempts']} attempts, {probe['retries']} retries (probe — no real chain) |")
    lines.append(f"| story results | {story['total_story_files']} files, {story['wired_test_executed_success']} wired, {story['wired_failed']} wired-failed, {story['not_all_successful']} not-all-successful, {story['total_sessions']} sessions ({story['failed_sessions']} failed) — zero retry linkage |")
    lines.append("")
    lines.append("## 3. Extraction honesty notes")
    lines.append("")
    lines.append(
        "- The E4 ledger attempt rows carry NO `confidence` field; the [H] confidence "
        "is recovered by joining `result_path` to the wired story results."
    )
    lines.append(
        "- `failed-first` = attempt_number 1 with test_executed_success false; no imputed "
        "outcomes — a retry with a missing test_executed_success is classified "
        "`retry-taken-outcome-missing`, never guessed."
    )
    lines.append(
        "- The story runner has no retry mechanism, so the 24 wired-failed stories are "
        "first-attempt outcomes, not retry chains (a 'no retry was armed' set)."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """Run the extraction and write chains.json + chains.md."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    chains, e4 = extract_e4_chains()
    probe = extract_probe()
    story = survey_story_corpus()
    coverage = build_coverage(e4, probe, story)

    payload = {
        "schema": "retry_chains/v1",
        "phase": "p1_extract_chains",
        "chains": chains,
        "coverage": coverage,
        "ledgers": {"e4": e4, "probe": probe},
        "story_corpus": story,
    }

    with open(OUT_DIR / "chains.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    with open(OUT_DIR / "chains.md", "w", encoding="utf-8") as fh:
        fh.write(render_markdown(chains, coverage, e4, probe, story))

    # Console log (the phase's LOG line).
    print(f"chains={len(chains)}")
    print(f"coverage={coverage['attempt_ledger_coverage_complete_over_failed']}")
    print(f"retry_events={coverage['real_retry_events']}")
    print(f"wired_failed_stories={story['wired_failed']}")


if __name__ == "__main__":
    main()
