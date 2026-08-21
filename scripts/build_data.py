#!/usr/bin/env python3
"""Build data.js for the Agentic Dynamics website.

Reads the canonical-state registry (experiments/data_manifest.json) and the
measurement payloads it points at (``finding`` single-task re-runs and ``story``
multi-session results), plus inventory.json, and produces a single data.js with
``window.DYNAMICS_DATA`` containing all measured/computed/derived values with
provenance tags.

The flawed 144-entry legacy summary JSON is retired as a build input
(``docs/data_integrity_findings.md`` treatment rule 4): the perturbation corpus
now comes from the 64 clean ``finding`` records and the story corpus from the
current ``story`` records, with the 77 tombstoned story records excluded.

Usage:
    python scripts/build_data.py              # Write apps/website/data.js
    python scripts/build_data.py --dry-run    # Print what would be written
"""

import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

INVENTORY_PATH = ROOT / "experiments" / "inventory.json"
MANIFEST_PATH = ROOT / "experiments" / "data_manifest.json"
RESULTS_DIR = ROOT / "experiments" / "results"
REPORTS_DIR = RESULTS_DIR / "reports"
DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
OUTPUT_PATH = ROOT / "apps" / "website" / "data.js"

from agentic_dynamics.core.constants import MODEL_LABELS, bootstrap_ci

from agentic_dynamics.control.routing import compute_routing  # noqa: E402
from agentic_dynamics.measurement.solution import COMPOSITE_WEIGHTS  # noqa: E402
from agentic_dynamics.reporting.canonical_corpus import (  # noqa: E402
    DATA_INTEGRITY_POLICY_VERSION,
    DEFAULT_WAIVER_PATH,
    NORMALIZATION_VERSION,
    current_manifest_identity,
    load_canonical_tables,
    load_waivers,
    read_manifest,
    registry_rows,
    unwaivered_issues,
    validate_waivers,
    waiver_set_digest,
)
from agentic_dynamics.reporting.lab_contract import expected_tables, validate_contract  # noqa: E402
from agentic_dynamics.reporting.lab_manifest import (  # noqa: E402
    load_lab_manifest,
    publication_labs,
    rejection_reason,
)

#: The registry ``source_type`` values the site consumes as measurement corpus.
#: ``finding`` = the clean single-task perturbation cells (replacing the retired
#: summary); ``story`` = the multi-session story cells. Resolved once, through the
#: canonical resolver (``load_canonical_tables``) — the single publication door.
CANONICAL_SOURCE_TYPES = frozenset({"story", "finding"})


def _fmt_usd(v):
    return round(v, 4)


def _parse_model_id(model_str):
    if model_str in MODEL_LABELS:
        return model_str
    sorted_ids = sorted(MODEL_LABELS.keys(), key=lambda k: len(k), reverse=True)
    for mid in sorted_ids:
        if mid in model_str:
            return mid
    return model_str


def load_inventory():
    if not INVENTORY_PATH.exists():
        print(f"ERROR: inventory.json not found at {INVENTORY_PATH}", file=sys.stderr)
        print("  Run: python scripts/inventory.py refresh", file=sys.stderr)
        sys.exit(1)
    return json.loads(INVENTORY_PATH.read_text())


@dataclass
class CanonicalCorpus:
    """The canonical measurement corpus a repointed build_data consumes.

    ``entries`` is the perturbation corpus — every current ``finding`` registry row
    joined to its measurement payload and mapped into the summary-shaped entry dict
    the existing per-model/per-operator aggregators expect. ``stories`` is every
    current ``story`` payload with its no-op condition relabeled to ``clean``.
    ``by_operator_model`` and ``strategy_distribution`` are re-derived from
    ``entries`` (the retired summary's pre-aggregated blocks are gone with it).
    """

    entries: list = field(default_factory=list)
    stories: list = field(default_factory=list)
    by_operator_model: dict = field(default_factory=dict)
    strategy_distribution: dict = field(default_factory=dict)
    story_count: int = 0
    finding_count: int = 0
    tombstoned_count: int = 0


def _finding_entry_from_run(experiment: str, run: dict, locator: str) -> dict:
    """Map one finding payload ``run`` into a summary-shaped entry dict.

    This is the vocabulary translation the retired summary's consumers already speak:
    the finding's native field names (``cost_usd``, ``lines_of_code``, ``escape_score``,
    ``prompt_tokens``…) are remapped to the summary field names, and every field the
    finding corpus does not measure is emitted as ``None`` (renders em-dash, never a
    fabricated value). ``test_results``/``evaluator_source`` come from the measured
    ``tests_passed``/``tests_total``/``test_executed_success`` only.
    """
    cost = float(run.get("cost_usd") or 0.0)
    tests_total = int(run.get("tests_total") or 0)
    tests_passed = int(run.get("tests_passed") or 0)
    correctness = run.get("correctness")
    return {
        "experiment": experiment,
        "type": run.get("type", "perturbed"),
        "worktree_name": locator,
        "model": run.get("model", "unknown"),
        # The clean re-runs are never "narrated" — the flail dimension is unmeasured
        # in the finding corpus, so narration_failure is always False here.
        "narration_failure": False,
        "correctness": correctness if isinstance(correctness, (int, float)) else 0.0,
        "cost": cost,
        "strategy": run.get("strategy", ""),
        "code_lines": int(run.get("lines_of_code") or 0),
        "thinking_ratio": float(run.get("thinking_ratio") or 0.0),
        "escape": float(run.get("escape_score") or 0.0),
        "architecture_divergence": float(run.get("architecture_divergence") or 0.0),
        "composite_score": float(run.get("composite_score") or 0.0),
        "energy_total_j": float(run.get("energy_j") or 0.0),
        "quality_per_joule": float(run.get("quality_per_joule") or 0.0),
        "constraints_met": int(run.get("constraints_met") or 0),
        "constraints_total": int(run.get("constraints_total") or 0),
        "tokens": int(run.get("total_tokens") or 0),
        "tokens_input": int(run.get("prompt_tokens") or 0),
        "tokens_output": int(run.get("completion_tokens") or 0),
        "tokens_reasoning": int(run.get("reasoning_tokens") or 0),
        "operator": run.get("operator", "unknown"),
        "perturbation_class": run.get("perturbation_class", "unknown"),
        "perturbation_strength": run.get("perturbation_strength"),
        "test_executed_success": run.get("test_executed_success"),
        "confidence": run.get("confidence"),
        "test_results": {"total": tests_total, "passed": tests_passed},
        "evaluator_source": "tests" if tests_total > 0 else "heuristic",
        # ── no canonical replacement → None, never fabricated ──
        "narration_penalty": None,
        "structure_divergence": None,
        "code_quality_score": None,
        "comment_ratio": None,
        "correctness_per_dollar": None,
        "ast": None,
    }


def _finding_entry_from_resolved(run: dict) -> dict:
    """Map one resolver-flattened ``finding`` run into a summary-shaped entry dict.

    ``canonical_corpus.resolve_findings`` already joined each current registry row to its
    run and stamped ``_experiment`` + ``_registry`` onto a copy. This translates that
    resolved run into the retired summary's field vocabulary (via
    :func:`_finding_entry_from_run`), deriving the worktree locator from the run's own
    ``workdir`` rather than re-walking the payload file.
    """
    experiment = str(run.get("_experiment") or "")
    workdir = str(run.get("workdir") or "")
    locator = workdir.rsplit("/", 1)[-1]
    return _finding_entry_from_run(experiment, run, locator)


def _compute_by_operator_model(entries: list) -> dict:
    """Re-derive the per-operator × per-model aggregation the retired summary carried.

    Key shape matches the retired ``by_operator_model`` block
    (``"<type>|<perturbation_class>|<model>"``) so the existing ``op_comparison`` loop
    in :func:`build` is unchanged. Aggregates are computed from the canonical entries,
    not read pre-aggregated.
    """
    groups: dict[str, list] = defaultdict(list)
    for e in entries:
        typ = e.get("type", "perturbed")
        pc = e.get("perturbation_class", "unknown")
        mdl = e.get("model", "unknown")
        groups[f"{typ}|{pc}|{mdl}"].append(e)

    result = {}
    for key, rows in groups.items():
        costs = [r.get("cost", 0) for r in rows]
        escapes = [r.get("escape", 0) for r in rows]
        correctness = [r.get("correctness", 0) for r in rows]
        thinking = [r.get("thinking_ratio", 0) for r in rows]
        energy = [r.get("energy_total_j", 0) for r in rows]
        n = len(rows)
        result[key] = {
            "n": n,
            "count": n,
            "cost_avg": round(sum(costs) / n, 4),
            "cost_ci95_lo": bootstrap_ci(costs)[0] if n >= 5 else None,
            "cost_ci95_hi": bootstrap_ci(costs)[1] if n >= 5 else None,
            "escape_avg": round(sum(escapes) / n, 2),
            "escape_ci95_lo": bootstrap_ci(escapes)[0] if n >= 5 else None,
            "escape_ci95_hi": bootstrap_ci(escapes)[1] if n >= 5 else None,
            "correctness_avg": round(sum(correctness) / n, 2),
            "correctness_ci95_lo": bootstrap_ci(correctness)[0] if n >= 5 else None,
            "correctness_ci95_hi": bootstrap_ci(correctness)[1] if n >= 5 else None,
            "thinking_ratio_avg": round(sum(thinking) / n, 3),
            "energy_total_j_avg": round(sum(energy) / n, 1),
        }
    return result


def _compute_strategy_distribution(entries: list) -> dict:
    """Re-derive the strategy-archetype counts from the canonical entries."""
    dist: dict[str, int] = defaultdict(int)
    for e in entries:
        dist[(e.get("strategy") or "?").lower()] += 1
    return dict(dist)


def load_canonical_corpus(
    manifest_path: Path | None = None,
    tables: Any = None,
) -> CanonicalCorpus:
    """Load the canonical measurement corpus through the registry resolver.

    This is the single publication door: ``canonical_corpus.load_canonical_tables``
    resolves the current ``story``/``finding`` rows (lifecycle-aware, condition-corrected)
    and ``build_data`` maps the finding runs into the summary-shaped entry vocabulary its
    aggregators speak. Tombstoned rows are counted for reporting but never contribute a
    measurement. A missing/unreadable manifest degrades to an empty corpus with a warning
    — never a hard failure (mirroring the resolver's file-fallback posture).

    ``tables`` is the already-resolved :class:`CanonicalTables` when :func:`build` has
    resolved the full four-table input itself — pass it to avoid a second resolution pass.
    """
    path = Path(manifest_path) if manifest_path is not None else MANIFEST_PATH
    if tables is None:
        tables = load_canonical_tables("story", "finding", manifest_path=path)
    rows = registry_rows(read_manifest(path))
    if not rows:
        print(
            f"WARNING: canonical registry empty or missing at {path} — "
            "run scripts/generate_manifest.py first; emitting an empty corpus.",
            file=sys.stderr,
        )

    entries = [_finding_entry_from_resolved(run) for run in tables.findings]
    stories = tables.stories

    return CanonicalCorpus(
        entries=entries,
        stories=stories,
        by_operator_model=_compute_by_operator_model(entries),
        strategy_distribution=_compute_strategy_distribution(entries),
        story_count=sum(
            1
            for r in rows
            if r.get("lifecycle_state") == "current" and r.get("source_type") == "story"
        ),
        finding_count=sum(
            1
            for r in rows
            if r.get("lifecycle_state") == "current" and r.get("source_type") == "finding"
        ),
        tombstoned_count=sum(
            1
            for r in rows
            if r.get("lifecycle_state") == "tombstoned"
            and r.get("source_type") in CANONICAL_SOURCE_TYPES
        ),
    )


def _load_correctness_escape_quadrants():
    """Load the correctness x escape bubble points — only if the lab is publishable.

    Formerly ``_load_grit_matrix``. The lab behind it was renamed in phase s4
    (``lab_grit_matrix.py`` -> ``lab_correctness_escape_quadrants.py``) because a
    correctness x escape quadrant is NOT the formal Grit metric; ``Grit`` now means one
    thing repo-wide and is published from ``lab_grit.py`` through ``_load_labs``.

    The quadrant lab reads the RETIRED ``_results_summary.json``, so it stays quarantined
    and this returns ``[]`` — logged by name, never silent, so a missing website section is
    always traceable to a lab and a stated reason.
    """
    reason = rejection_reason("lab_correctness_escape_quadrants.py")
    if reason is not None:
        print(f"  [lab-gate] not published — {reason}")
        return []

    # Path comes from the manifest, not hard-coded: a quarantined lab's artifact lives in
    # experiments/results/legacy_labs/, and only the manifest knows where a lab writes.
    entry = load_lab_manifest().get("lab_correctness_escape_quadrants.py")
    if entry is None or not entry.output:
        return []
    grit_path = ROOT / entry.output
    if not grit_path.exists():
        return []
    try:
        data = json.loads(grit_path.read_text())
        return data.get("points", [])
    except Exception:
        return []


def _compute_sonar(entries):
    """[P] historical — SonarQube per-cell aggregates have no canonical replacement.

    The retired summary carried per-cell ``sonar_*`` fields; neither the ``finding`` nor
    the ``story`` canonical payload reproduces them, and the current corpus carries zero
    ``sonar_analyzed`` cells. Rather than fabricate zero-filled aggregates, this section
    is emitted as an explicit historical marker with a ``[P]`` (policy/prior) note so the
    site renders it as an em-dash, not a number.
    """
    return {
        "models": {},
        "_historical": True,
        "_note": (
            "[P] SonarQube per-cell aggregates retired with the legacy summary corpus — "
            "no canonical replacement in the registry."
        ),
    }


def count_game_reports():

    if not REPORTS_DIR.exists():
        return 0
    return len([f for f in REPORTS_DIR.iterdir() if f.suffix == ".md"])


def get_provider(model_id):
    if "deepseek" in model_id:
        return "deepseek"
    if "anthropic" in model_id or "claude" in model_id:
        return "anthropic"
    return "openai"


def compute_model_data(entries):
    """Compute per-model aggregate metrics from the canonical finding entries.

    Phase-2 repoint: the single-task perturbation corpus now comes from the clean
    ``finding`` records (the 64 re-runs that replace the retired 144-entry summary), so
    the model list is derived from the entries themselves rather than a hard-coded
    display order. Pass rate is derived ONLY from measured ``test_results`` — with no
    measured tests it is ``None`` (renders as an em-dash), never a fabricated rate from
    unverified self-report (``data_integrity_findings.md`` P0-1). Fields the finding
    corpus does not measure are emitted as ``None`` and listed in ``_historical_fields``.
    """
    by_model: dict[str, list] = defaultdict(list)
    for e in entries:
        by_model[_parse_model_id(e.get("model", ""))].append(e)

    models = []
    # Deterministic order: cheapest-first median cost (keeps DeepSeek's low-cost models
    # at the head, mirroring the old MODEL_DISPLAY_ORDER intent without hard-coding it).
    for mid, reports in sorted(by_model.items(), key=lambda kv: _median_cost(kv[1])):
        label = MODEL_LABELS.get(mid, mid)
        provider = get_provider(mid)

        valid = [
            r for r in reports if not r.get("narration_failure") and r.get("correctness", 0) >= 0
        ]
        narrated = [r for r in reports if r.get("narration_failure")]

        avg_cost = _fmt_usd(sum(r.get("cost", 0) for r in valid) / max(len(valid), 1))
        total_cost = _fmt_usd(sum(r.get("cost", 0) for r in reports))

        # Pass rate — measured tests only. No fabricated correctness-heuristic fallback.
        total_tests = 0
        total_passed = 0
        for r in valid:
            tr = r.get("test_results") or {}
            if tr.get("total", 0) > 0:
                total_tests += tr["total"]
                total_passed += tr["passed"]
        pass_rate_val = None
        if total_tests > 0:
            pass_rate_val = (
                f"{total_passed / total_tests:.0%} ({total_passed}/{total_tests}) [tests]"
            )

        strategies = {"conservative": 0, "exploratory": 0, "wasteful": 0, "efficient": 0}
        for r in valid:
            s = (r.get("strategy", "") or "").lower()
            if s in strategies:
                strategies[s] += 1

        avg_loc = round(sum(r.get("code_lines", 0) for r in valid) / max(len(valid), 1))
        avg_thinking = round(sum(r.get("thinking_ratio", 0) for r in valid) / max(len(valid), 1), 3)
        avg_escape = round(sum(r.get("escape", 0) for r in valid) / max(len(valid), 1), 2)
        avg_arch_div = round(
            sum(r.get("architecture_divergence", 0) for r in valid) / max(len(valid), 1), 3
        )
        avg_composite = round(
            sum(r.get("composite_score", 0) for r in valid) / max(len(valid), 1), 3
        )

        avg_energy = round(sum(r.get("energy_total_j", 0) for r in valid) / max(len(valid), 1), 1)
        avg_energy_per_loc = round(avg_energy / max(avg_loc, 1), 2)
        correctness_per_dollar = round(
            sum((r.get("correctness") or 0) / max(r.get("cost", 0), 1e-9) for r in valid)
            / max(len(valid), 1),
            4,
        )
        avg_joules_per_loc = round(
            sum(r.get("quality_per_joule", 0) for r in valid) / max(len(valid), 1), 4
        )

        avg_constraints_met = round(
            sum(r.get("constraints_met", 0) for r in valid) / max(len(valid), 1), 1
        )
        avg_constraints_total = round(
            sum(r.get("constraints_total", 0) for r in valid) / max(len(valid), 1), 1
        )

        tokens_in = sum(r.get("tokens_input", 0) for r in valid)
        tokens_out = sum(r.get("tokens_output", 0) for r in valid)
        tokens_reason = sum(r.get("tokens_reasoning", 0) for r in valid)
        total_tok = tokens_in + tokens_out + tokens_reason

        models.append(
            {
                "id": mid,
                "label": label,
                "provider": provider,
                "reports": len(reports),
                "reports_valid": len(valid),
                "reports_narrated": len(narrated),
                "n_reports": len(reports),
                "n_valid": len(valid),
                "n_narrated": len(narrated),
                "avg_cost": avg_cost,
                "total_cost": total_cost,
                "cost_ci95": bootstrap_ci([r.get("cost", 0) for r in valid])
                if len(valid) >= 5
                else None,
                "pass_rate": pass_rate_val,
                "strategy_cons": strategies["conservative"],
                "strategy_expl": strategies["exploratory"],
                "strategy_waste": strategies["wasteful"],
                "strategy_efficient": strategies["efficient"],
                "avg_loc": avg_loc,
                "avg_thinking_ratio": avg_thinking,
                "avg_escape": avg_escape,
                "avg_arch_divergence": avg_arch_div,
                "avg_composite_score": avg_composite,
                "avg_energy_j": avg_energy,
                "avg_energy_j_per_loc": avg_energy_per_loc,
                "correctness_per_dollar": correctness_per_dollar,
                "avg_quality_per_joule": avg_joules_per_loc,
                "avg_constraints_met": avg_constraints_met,
                "avg_constraints_total": avg_constraints_total,
                "tokens_total": total_tok,
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "tokens_reasoning": tokens_reason,
                # ── historical: no canonical replacement in the finding corpus → None ──
                "avg_narration_penalty": None,
                "avg_struct_divergence": None,
                "avg_code_quality": None,
                "avg_comment_ratio": None,
                "narration_rate": None,
                "ast_files": None,
                "ast_functions": None,
                "ast_classes": None,
                "ast_type_hint_pct": None,
                "ast_docstring_pct": None,
                "cost_input": None,
                "cost_output": None,
                "cost_reasoning": None,
                "cost_cache": None,
                "tokens_cache_read": None,
                "tokens_cache_write": None,
                "_historical_fields": [
                    "avg_narration_penalty",
                    "avg_struct_divergence",
                    "avg_code_quality",
                    "avg_comment_ratio",
                    "narration_rate",
                    "ast_files",
                    "ast_functions",
                    "ast_classes",
                    "ast_type_hint_pct",
                    "ast_docstring_pct",
                    "cost_input",
                    "cost_output",
                    "cost_reasoning",
                    "cost_cache",
                    "tokens_cache_read",
                    "tokens_cache_write",
                ],
                "_provenance": {
                    "reports": "M",
                    "reports_valid": "M",
                    "reports_narrated": "M",
                    "total_cost": "M",
                    "tokens_input": "M",
                    "tokens_output": "M",
                    "tokens_reasoning": "M",
                    "tokens_total": "M",
                    "avg_cost": "C",
                    "cost_ci95": "C",
                    "avg_loc": "C",
                    "avg_thinking_ratio": "C",
                    "avg_escape": "C",
                    "avg_arch_divergence": "C",
                    "avg_composite_score": "C",
                    "avg_energy_j": "C",
                    "avg_energy_j_per_loc": "C",
                    "avg_quality_per_joule": "C",
                    "correctness_per_dollar": "C",
                    "avg_constraints_met": "C",
                    "avg_constraints_total": "C",
                    "strategy_cons": "C",
                    "strategy_expl": "C",
                    "strategy_waste": "C",
                    "strategy_efficient": "C",
                    "pass_rate": "M" if total_tests > 0 else None,
                },
            }
        )

    return models


def _median_cost(entries: list) -> float:
    """Median cost of a model's entries (a robust ordering key for the model list)."""
    costs = sorted(r.get("cost", 0) for r in entries)
    if not costs:
        return float("inf")
    n = len(costs)
    mid = n // 2
    return costs[mid] if n % 2 else (costs[mid - 1] + costs[mid]) / 2


def compute_charts(models):
    labels = [m["label"] for m in models]
    cost_data = [m["avg_cost"] for m in models]
    narr_data = [m["narration_rate"] for m in models]
    loc_data = [m["avg_loc"] for m in models]
    reports = [m["reports"] for m in models]
    return {
        "labels": labels,
        "costData": cost_data,
        "narrData": narr_data,
        "locData": loc_data,
        "costY": cost_data,
        "reports": reports,
    }


def compute_calculator(models):
    model_costs = [
        {
            "n": m["label"],
            "c": m["avg_cost"],
            "p": float(str(m.get("pass_rate", "0")).split("%")[0]) / 100
            if "%" in str(m.get("pass_rate", ""))
            else 0,
        }
        for m in models
    ]

    cheapest = model_costs[0]["c"] if model_costs else 0.001
    esc_tiers = []
    for mc in model_costs[1:]:
        if cheapest > 0:
            esc_tiers.append(
                {
                    "m": f"DS→{mc['n'].replace('DeepSeek v4 Pro→', '').split(' ')[-1] if 'DeepSeek' in model_costs[0]['n'] else mc['n']}",
                    "e": round(mc["c"] / cheapest, 1),
                }
            )
    if cheapest > 0:
        esc_tiers.append({"m": "→Human ($5/job)", "e": round(5 / cheapest, 1)})
    else:
        esc_tiers.append({"m": "→Human ($5/job)", "e": 0})

    narrated = sum(1 for m in models for r in range(m.get("reports_narrated", 0)))
    total_runs = sum(m["reports"] for m in models)
    retry_rate = round(narrated / max(total_runs, 1), 3)
    woc = round(1 / (1 + retry_rate), 2)

    return {
        "model_costs": model_costs,
        "escalation_tiers": esc_tiers,
        "retry_rate_measured": retry_rate,
        "woc_ratio": woc,
    }


def compute_derived(models, inventory, report_count):
    inventory.get("counts", {})
    inventory.get("costs", {})

    valid_tests = 0
    total_tests_sum = 0
    total_model_correctness = 0
    total_model_weight = 0
    for m in models:
        pr = m.get("pass_rate", "")
        if "(" in str(pr) and "/" in str(pr):
            parts = str(pr).split("(")[1].split(")")[0].split("/")
            if len(parts) == 2:
                try:
                    total_tests_sum += int(parts[1])
                    valid_tests += int(parts[0])
                except ValueError:
                    pass
        elif "%" in str(pr) and m["reports_valid"] > 0:
            try:
                val = float(str(pr).split("%")[0])
                if val > 1:
                    val = val / 100
                total_model_correctness += val * m["reports_valid"]
                total_model_weight += m["reports_valid"]
            except ValueError:
                pass

    if total_tests_sum > 0:
        tag = " [mixed]" if total_model_weight > 0 else " [tests]"
        overall_pass_rate = (
            f"{valid_tests / total_tests_sum:.1%} ({valid_tests}/{total_tests_sum}){tag}"
        )
    elif total_model_weight > 0:
        avg_correctness = total_model_correctness / total_model_weight
        overall_pass_rate = f"{avg_correctness:.1%} [H]"
    else:
        overall_pass_rate = "N/A"

    claude = next((m for m in models if "claude" in m["id"]), None)
    deepseek = next((m for m in models if "deepseek" in m["id"]), None)
    cost_gap = None
    cost_gap_computation = None
    if claude and deepseek and deepseek["avg_cost"] > 0:
        gap = claude["avg_cost"] / deepseek["avg_cost"]
        cost_gap = f"{round(gap)}×"
        cost_gap_computation = f"${claude['avg_cost']} / ${deepseek['avg_cost']} = {gap:.1f}×"

    total_narrated = sum(m["reports_narrated"] for m in models)
    total_valid = sum(m["reports_valid"] for m in models)
    total_reports = sum(m["reports"] for m in models)

    return {
        "cost_gap": cost_gap or "N/A",
        "cost_gap_computation": cost_gap_computation or "",
        "overall_pass_rate": overall_pass_rate,
        "total_tests_passed": valid_tests,
        "total_tests_run": total_tests_sum,
        "total_cost_all_models": _fmt_usd(sum(m["total_cost"] for m in models)),
        "total_cost_deepseek": _fmt_usd(
            sum(m["total_cost"] for m in models if "deepseek" in m["id"])
        ),
        "total_cost_claude": _fmt_usd(sum(m["total_cost"] for m in models if "claude" in m["id"])),
        "total_narrated": total_narrated,
        "total_valid_reports": total_valid,
        "total_reports_analyzed": total_reports,
        "_provenance": {
            "cost_gap": "C",
            "overall_pass_rate": "C",
            "total_tests_passed": "M",
            "total_tests_run": "M",
            "total_cost_all_models": "M",
            "total_cost_deepseek": "M",
            "total_cost_claude": "M",
            "total_narrated": "M",
            "total_valid_reports": "M",
            "total_reports_analyzed": "M",
        },
    }


def _load_review_data(reviews: list[dict], stories: list[dict]) -> dict:
    """Aggregate the canonical review corpus into per-model quality metrics.

    Consumes the resolver's ``tables.reviews`` (already filtered to current review rows
    and stamped with ``_story_id``) and ``tables.stories`` (for the story→reviewed-model
    join). A review whose story is not in the current story set (tombstoned or
    payload-less) contributes nothing — it is a review of a cell the registry no longer
    publishes, not a current measurement.
    """
    import statistics
    from collections import Counter

    sid_to_model = {
        str(s.get("story_id") or ""): s.get("model") for s in stories if s.get("story_id")
    }

    by_model = {}
    total_commit_reviews = 0
    total_story_reviews = 0

    for r in reviews:
        sid = str(r.get("_story_id") or r.get("story_id") or "")
        reviewed_model = sid_to_model.get(sid)
        if reviewed_model is None:
            continue
        reviewed = reviewed_model.split("/")[-1]
        m = by_model.setdefault(
            reviewed,
            {
                "model": reviewed,
                "stories": 0,
                "coherence": [],
                "arch_fit": [],
                "convention": [],
                "bow": Counter(),
                "issue_themes": Counter(),
            },
        )
        sr = r.get("story_review")
        if sr:
            m["stories"] += 1
            total_story_reviews += 1
            coh = sr.get("overall_coherence")
            if coh is not None:
                m["coherence"].append(coh)
            for issue in sr.get("compounding_issues", []):
                m["issue_themes"][_classify_issue(issue)] += 1
        for cr in r.get("commit_reviews", []):
            total_commit_reviews += 1
            af = cr.get("architectural_fit")
            ca = cr.get("convention_adherence")
            if af is not None:
                m["arch_fit"].append(af)
            if ca is not None:
                m["convention"].append(ca)
            m["bow"][cr.get("better_or_worse", "?")] += 1

    models = []
    for reviewed, m in by_model.items():
        total_bow = sum(m["bow"].values()) or 1
        label = _short_model_label(reviewed)
        models.append(
            {
                "model": reviewed,
                "label": label,
                "stories": m["stories"],
                "overall_coherence": round(statistics.mean(m["coherence"]), 3)
                if m["coherence"]
                else None,
                "architectural_fit": round(statistics.mean(m["arch_fit"]), 3)
                if m["arch_fit"]
                else None,
                "convention_adherence": round(statistics.mean(m["convention"]), 3)
                if m["convention"]
                else None,
                "better_pct": round(m["bow"].get("better", 0) / total_bow * 100, 1),
                "worse_pct": round(m["bow"].get("worse", 0) / total_bow * 100, 1),
                "neutral_pct": round(m["bow"].get("neutral", 0) / total_bow * 100, 1),
                "top_issues": [
                    {"theme": t, "count": c} for t, c in m["issue_themes"].most_common(5)
                ],
            }
        )
    models.sort(key=lambda x: x.get("overall_coherence") or 0, reverse=True)

    return {
        "models": models,
        "commit_reviews": total_commit_reviews,
        "story_reviews": total_story_reviews,
        "reviewer": "deepseek/deepseek-v4-flash",
    }


def _classify_issue(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ("secret", "hard-coded", "hardcoded", "auth", "jwt", "password")):
        return "security"
    if "test" in low:
        return "test gaps"
    if any(k in low for k in ("migration", "schema", "alter table")):
        return "schema drift"
    if any(k in low for k in ("coupl", "orchestrat")):
        return "coupling"
    if any(k in low for k in ("refactor", "repository", "layer")):
        return "incomplete refactor"
    if any(k in low for k in ("pagination", "delete", "missing", "rate limit")):
        return "missing surface"
    return "other"


def _optional_measurement(value, n_available: int, n_total: int) -> dict:
    """One publication shape for an optional measurement (public-truth P0/P1).

    An optional signal (e.g. LSP diagnostics) is not available on every cell. Publishing
    it as a bare average over all cells turns *not measured* into *measured as zero*.
    Instead every optional measurement carries ``value`` (the average over the cells that
    actually measured it, ``None`` when none did) plus the availability accounting, so a
    reader can tell "0 errors" from "no diagnostics tool ran".
    """
    return {
        "value": value,
        "n_available": n_available,
        "n_total": n_total,
        "coverage": round(n_available / n_total, 4) if n_total else 0.0,
    }


def _load_analysis_data(analysis: list[dict], stories: list[dict]) -> dict:
    """Aggregate AST + SonarQube + convention data from canonical analysis payloads.

    Consumes the resolver's ``tables.analysis`` (already filtered to the current story
    registry and stamped with ``_story_id``) plus ``tables.stories`` for the
    story→reviewed-model join. An analysis payload whose story is not current contributes
    nothing, mirroring the review path.
    """
    from collections import Counter

    sid_to_model = {
        str(s.get("story_id") or ""): s.get("model") for s in stories if s.get("story_id")
    }

    by_model = {}
    n_analysis = 0
    n_sonar_available = 0
    n_commits = 0

    for d in analysis:
        sid = str(d.get("_story_id") or d.get("story_id") or "")
        reviewed_model = sid_to_model.get(sid)
        if reviewed_model is None:
            continue
        reviewed = reviewed_model.split("/")[-1]
        n_analysis += 1
        m = by_model.setdefault(
            reviewed,
            {
                "model": reviewed,
                "commits": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "functions_added": 0,
                "functions_removed": 0,
                "classes_added": 0,
                "imports_added": 0,
                "sonar_available": 0,
                "sonar_bugs_delta": 0,
                "sonar_smells_delta": 0,
                "sonar_complexity_delta": 0,
                "convention_scores": [],
                "deep_cells": 0,
                "lsp_available": 0,
                "lsp_errors": 0,
                "lsp_warnings": 0,
                "solution_correctness": [],
                "solution_constraints": [],
                "solution_quality": [],
                "solution_novelty": [],
                "solution_composite": [],
                "basin_escape": [],
                "strategies": Counter(),
            },
        )
        summary = d.get("summary", {})
        conv = summary.get("average_convention_score")
        if conv is not None:
            m["convention_scores"].append(conv)
        for c in d.get("commits", []):
            m["commits"] += 1
            n_commits += 1
            ast = c.get("ast", {})
            m["lines_added"] += ast.get("lines_added", 0)
            m["lines_removed"] += ast.get("lines_removed", 0)
            m["functions_added"] += ast.get("functions_added", 0)
            m["functions_removed"] += ast.get("functions_removed", 0)
            m["classes_added"] += ast.get("classes_added", 0)
            m["imports_added"] += ast.get("imports_added", 0)
            sonar = c.get("sonar", {})
            if sonar.get("available"):
                m["sonar_available"] += 1
                n_sonar_available += 1
                m["sonar_bugs_delta"] += sonar.get("bugs_delta", 0)
                m["sonar_smells_delta"] += sonar.get("smells_delta", 0)
                m["sonar_complexity_delta"] += sonar.get("complexity_delta", 0)

        deep = d.get("deep", {})
        if deep:
            m["deep_cells"] += 1
            lsp = deep.get("lsp", {})
            # Zero-as-missing guard: an unavailable language server contributes no
            # error/warning count, so "not measured" can never dilute the average to 0.
            if lsp.get("available"):
                m["lsp_available"] += 1
                m["lsp_errors"] += lsp.get("errors", 0) or 0
                m["lsp_warnings"] += lsp.get("warnings", 0) or 0
            sol = deep.get("solution", {})
            m["solution_correctness"].append(sol.get("correctness_score", 0) or 0)
            m["solution_constraints"].append(sol.get("constraint_score", 0) or 0)
            m["solution_quality"].append(sol.get("code_quality_score", 0) or 0)
            m["solution_novelty"].append(sol.get("novelty_score", 0) or 0)
            m["solution_composite"].append(sol.get("composite_score", 0) or 0)
            basin = deep.get("basin", {})
            m["basin_escape"].append(basin.get("escape_score", 0) or 0)
            m["strategies"][deep.get("strategy", {}).get("strategy", "?")] += 1

    def _avg(lst):
        return round(sum(lst) / len(lst), 3) if lst else None

    models = []
    for reviewed, m in by_model.items():
        n = len(m["convention_scores"])
        models.append(
            {
                "model": reviewed,
                "label": _short_model_label(reviewed),
                "commits": m["commits"],
                "lines_added": m["lines_added"],
                "lines_removed": m["lines_removed"],
                "functions_added": m["functions_added"],
                "classes_added": m["classes_added"],
                "imports_added": m["imports_added"],
                "sonar_available": m["sonar_available"],
                "sonar_bugs_delta": m["sonar_bugs_delta"],
                "sonar_smells_delta": m["sonar_smells_delta"],
                "sonar_complexity_delta": m["sonar_complexity_delta"],
                "avg_convention": round(sum(m["convention_scores"]) / n, 3) if n else None,
                "deep_cells": m["deep_cells"],
                "lsp_available": m["lsp_available"],
                "lsp_errors_per_cell": _optional_measurement(
                    round(m["lsp_errors"] / m["lsp_available"], 1) if m["lsp_available"] else None,
                    m["lsp_available"],
                    m["deep_cells"],
                ),
                "lsp_warnings_per_cell": _optional_measurement(
                    round(m["lsp_warnings"] / m["lsp_available"], 1)
                    if m["lsp_available"]
                    else None,
                    m["lsp_available"],
                    m["deep_cells"],
                ),
                "solution_correctness": _avg(m["solution_correctness"]),
                "solution_constraints": _avg(m["solution_constraints"]),
                "solution_quality": _avg(m["solution_quality"]),
                "solution_novelty": _avg(m["solution_novelty"]),
                "solution_composite": _avg(m["solution_composite"]),
                "basin_escape": _avg(m["basin_escape"]),
                "strategies": dict(m["strategies"]),
            }
        )
    models.sort(key=lambda x: -(x["lines_added"]))

    return {
        "models": models,
        "stories_analyzed": n_analysis,
        "commits_analyzed": n_commits,
        "sonar_commits_available": n_sonar_available,
    }


def _load_labs() -> dict:
    """Load the publication-eligible, contract-valid lab book outputs for the evidence page.

    Two gates, in order — eligibility (s1) then lineage (s2):

    1. **Eligibility** — the lab set is derived from ``scripts/lab_manifest.json``, never
       hand-listed here. This builder used to load lab JSONs with zero provenance checks,
       so a lab reading the retired ``_results_summary.json`` could publish alongside
       canonical registry metrics: the "split publication path" the review named. A lab
       reaches ``data.js`` only when the manifest marks it ``publication_eligible`` *and*
       names a ``website_key``.
    2. **Lineage** — the artifact must carry a ``lab_contract`` block whose
       ``registry_identity_sha256`` matches the identity of the CURRENT
       ``data_manifest.json`` registry, whose semantic fields match the manifest entry
       exactly (review P1), and whose ``resolved_input_sha256`` matches the payload content
       the CURRENT resolver produces (review P2). Eligibility is a property of the lab;
       freshness is a property of the file. A lab that was eligible yesterday produced stale
       numbers if records have since been added, superseded, or tombstoned.

    Every rejection is logged with the lab name and the reason — a website section may
    disappear, but never silently. A missing artifact is still skipped quietly: a lab that
    has not been run yet is a gap, not an integrity failure.
    """
    manifest = load_lab_manifest()
    labs: dict[str, dict] = {}

    # Computed once: the identity every contract is compared against.
    identity = current_manifest_identity(MANIFEST_PATH)

    # --- gate 1: website_key -> LabEntry (quarantined already excluded) -----------------
    for website_key, entry in sorted(publication_labs(manifest).items()):
        if not entry.output:
            continue  # stdout-only lab: no artifact to publish
        artifact = ROOT / entry.output
        if not artifact.exists():
            continue
        try:
            payload = json.loads(artifact.read_text())
        except (json.JSONDecodeError, OSError):
            print(f"  [lab-gate] rejected — {entry.script}: unreadable artifact {entry.output}")
            continue

        # --- gate 2: the canonical lab contract -----------------------------------------
        # Semantic validation against the manifest entry (review P1) + the registry
        # identity + the payload-content hash (review P2). The content hash is recomputed
        # from THIS lab's own resolved tables, so a payload drift is caught per lab, not
        # per the whole four-table corpus.
        expected_content = None
        try:
            lab_tables = load_canonical_tables(*expected_tables(entry), manifest_path=MANIFEST_PATH)
            expected_content = lab_tables.resolved_input_sha256
        except ValueError:
            # expected_tables returned an empty/unknown slice — validate_contract's
            # input_dataset_id check will reject it; leave the content hash unverified here.
            expected_content = None

        reason = validate_contract(
            payload,
            manifest_entry=entry,
            current_identity=identity,
            expected_resolved_input_sha256=expected_content,
        )
        if reason is not None:
            print(f"  [lab-gate] rejected — {reason}")
            continue

        labs[website_key] = payload

    # --- log every exclusion, so a dropped section is traceable rather than silent ------
    for entry in manifest:
        if entry.quarantined:
            print(f"  [lab-gate] not published — {entry.script}: quarantined")

    return labs


def _short_model_label(model_id: str) -> str:
    mapping = {
        "deepseek-v4-pro": "DeepSeek v4 Pro",
        "gpt-5.6-luna": "GPT-5.6 Luna",
        "claude-sonnet-5": "Claude Sonnet 5",
        "deepseek-v4-flash": "DeepSeek v4 Flash",
        # "claude-fable-5" is the historical alias that actually ran sonnet-5
        # (docs/HANDOFF_2026-08-19.md) — normalized to "Claude Sonnet 5".
        "claude-fable-5": "Claude Sonnet 5",
    }
    if model_id in mapping:
        return mapping[model_id]
    for full, label in MODEL_LABELS.items():
        if model_id in full:
            return label
    return model_id


def _extract_tier_quality(codebase_path: str) -> tuple[str, str]:
    """Split a story ``codebase_path`` into its ``(tier, quality)`` trailing segments.

    ``experiments/codebases/<lang>/<tier>/<quality>`` -> ``("<tier>", "<quality>")``.
    """
    parts = Path(codebase_path).parts
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "", ""


def _story_pipeline_rows(stories: list[dict]) -> tuple[list[dict], list[dict]]:
    """Flatten canonical story payloads into ``(cell_rows, session_rows)``.

    The in-memory equivalent of the retired parquet tables. The condition a cell carries
    is ``_canonical_condition`` — the resolver's no-op relabel — so every aggregation
    built from these rows matches the canonical lab split instead of the raw labels.
    """
    cells: list[dict] = []
    sessions: list[dict] = []
    for d in stories:
        summary = d.get("summary", {}) or {}
        model = d.get("model", "")
        story_name = d.get("story_name", "")
        tier, quality = _extract_tier_quality(d.get("codebase_path", ""))
        condition = d.get("_canonical_condition") or "clean"
        session_count = summary.get("session_count", len(d.get("sessions", []))) or 0
        cells.append(
            {
                "story_name": story_name,
                "model": model,
                "tier": tier,
                "quality": quality,
                "condition": condition,
                "session_count": session_count,
                "total_tokens": summary.get("total_tokens", 0) or 0,
                "total_cost": summary.get("total_cost", 0.0) or 0.0,
                "cache_hit_rate": summary.get("cache_hit_rate", 0.0) or 0.0,
                "total_duration": summary.get("total_duration", 0.0) or 0.0,
                "all_successful": bool(summary.get("all_successful", False)),
                "test_count": summary.get("test_count", 0) or 0,
                "code_lines": summary.get("code_lines", 0) or 0,
                "test_code_ratio": summary.get("test_code_ratio", 0.0) or 0.0,
            }
        )
        for s in d.get("sessions", []):
            a = s.get("agentic", {}) or {}
            sessions.append(
                {
                    "model": model,
                    "tests_passed": a.get("tests_passed", 0) or 0,
                    "tests_total": a.get("tests_total", 0) or 0,
                    "prompt_tokens": a.get("prompt_tokens", 0) or 0,
                    "completion_tokens": a.get("completion_tokens", 0) or 0,
                    "reasoning_tokens": a.get("reasoning_tokens", 0) or 0,
                    "total_tokens": a.get("total_tokens", 0) or 0,
                    "cache_read_tokens": a.get("cache_read_tokens", 0) or 0,
                    "cost_usd": s.get("cost_usd", 0.0) or 0.0,
                    "duration_s": s.get("duration_s", 0.0) or 0.0,
                    "exit_code": s.get("exit_code", 0) or 0,
                }
            )
    return cells, sessions


def _load_story_data(stories: list[dict]) -> dict:
    """Aggregate the canonical story payloads into the website's story section.

    Consumes ``tables.stories`` directly — no parquet, no raw-dir glob — so the condition
    split carries the resolver's relabel (no ``bad_seed``/``early_degrade`` no-op arms).
    """
    cells, sessions = _story_pipeline_rows(stories)

    # Per-model aggregates (ordered by total cost, as before).
    by_model: dict[str, list] = defaultdict(list)
    for c in cells:
        by_model[c["model"]].append(c)
    models = []
    for mid, rows in sorted(by_model.items(), key=lambda kv: sum(c["total_cost"] for c in kv[1])):
        n = len(rows)
        cost_stats = _captured_cost_stats(rows)
        models.append(
            {
                "model": mid,
                "cells": n,
                "total_cost": round(sum(c["total_cost"] for c in rows), 6),
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_cells": cost_stats["cost_captured_cells"],
                "total_cells": cost_stats["total_cells"],
                "cost_coverage": cost_stats["cost_coverage"],
                "total_tokens": sum(c["total_tokens"] for c in rows),
                "avg_cache_hit": round(sum(c["cache_hit_rate"] for c in rows) / n, 3),
                "avg_duration_s": round(sum(c["total_duration"] for c in rows) / n, 0),
            }
        )

    # Condition comparison (the canonical split — clean vs early_degrade only).
    by_condition: dict[str, list] = defaultdict(list)
    for c in cells:
        by_condition[c["condition"]].append(c)
    conditions = []
    for cond in sorted(by_condition):
        rows = by_condition[cond]
        n = len(rows)
        variants = len({(c["story_name"], c["tier"], c["quality"]) for c in rows})
        cost_stats = _captured_cost_stats(rows)
        conditions.append(
            {
                "condition": cond,
                "cells": n,
                "variants": variants,
                "total_cost": round(sum(c["total_cost"] for c in rows), 6),
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_cells": cost_stats["cost_captured_cells"],
                "total_cells": cost_stats["total_cells"],
                "cost_coverage": cost_stats["cost_coverage"],
                "success": sum(1 for c in rows if c["all_successful"]),
                "fail": sum(1 for c in rows if not c["all_successful"]),
            }
        )

    # Story type comparison.
    by_story: dict[str, list] = defaultdict(list)
    for c in cells:
        by_story[c["story_name"]].append(c)
    stories_out = []
    for name, rows in sorted(by_story.items(), key=lambda kv: sum(c["total_cost"] for c in kv[1])):
        n = len(rows)
        cost_stats = _captured_cost_stats(rows)
        stories_out.append(
            {
                "story": name,
                "cells": n,
                "total_cost": round(sum(c["total_cost"] for c in rows), 6),
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_cells": cost_stats["cost_captured_cells"],
                "total_cells": cost_stats["total_cells"],
                "cost_coverage": cost_stats["cost_coverage"],
                "sessions": sum(c["session_count"] for c in rows),
                "avg_duration_s": round(sum(c["total_duration"] for c in rows) / n, 0),
                "avg_tokens_per_session": round(
                    sum(c["total_tokens"] / max(c["session_count"], 1) for c in rows) / n, 0
                ),
            }
        )

    # Tier comparison.
    by_tier: dict[tuple, list] = defaultdict(list)
    for c in cells:
        by_tier[(c["tier"], c["quality"])].append(c)
    tiers = []
    for (tier, quality), rows in sorted(by_tier.items()):
        n = len(rows)
        cost_stats = _captured_cost_stats(rows)
        tiers.append(
            {
                "tier": tier,
                "quality": quality,
                "cells": n,
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_cells": cost_stats["cost_captured_cells"],
                "total_cells": cost_stats["total_cells"],
                "cost_coverage": cost_stats["cost_coverage"],
                "avg_tokens_per_session": round(
                    sum(c["total_tokens"] / max(c["session_count"], 1) for c in rows) / n, 0
                ),
                "avg_session_duration_s": round(
                    sum(c["total_duration"] / max(c["session_count"], 1) for c in rows) / n, 0
                ),
            }
        )

    # Per-session stats.
    total_cost = sum(s["cost_usd"] for s in sessions)
    total_tokens = sum(s["total_tokens"] for s in sessions)
    total_cache_reads = sum(s["cache_read_tokens"] for s in sessions)
    total_prompt = sum(s["prompt_tokens"] for s in sessions)
    denom = total_cache_reads + total_prompt
    cache_hit_rate = (total_cache_reads / denom) if denom else 0.0

    return {
        "_provenance": "[M] token counts from session.jsonl; cost from opencode DB verified",
        "models": models,
        "conditions": conditions,
        "stories": stories_out,
        "tiers": tiers,
        "sessions": {
            "total": len(sessions),
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "total_cache_reads": total_cache_reads,
            "cache_hit_rate": round(cache_hit_rate, 3),
            "duration_s": sum(s["duration_s"] for s in sessions),
            "successful": sum(1 for s in sessions if s["exit_code"] == 0),
            "failed": sum(1 for s in sessions if s["exit_code"] != 0),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _honest_pass_rate(passed: int, run: int) -> str:
    """Honest pass-rate string. Never fabricates 100% from unmeasured data."""
    if run <= 0:
        return "unknown"
    return f"{passed / run:.0%} ({passed}/{run})"


def _merge_story_strategy(story_models: list[dict], analysis_data: dict) -> None:
    """Attach real strategy-archetype counts to story models.

    compute_story_models cannot source strategy (it lives in the deep-metrics
    analysis), so merge it here instead of fabricating zeros.
    """
    strat_by_model = {m["model"]: m.get("strategies", {}) for m in analysis_data.get("models", [])}
    for sm in story_models:
        strat = strat_by_model.get(sm["id"].split("/")[-1], {})
        sm["strategy_cons"] = strat.get("conservative", 0)
        sm["strategy_expl"] = strat.get("exploratory", 0)
        sm["strategy_waste"] = strat.get("wasteful", 0)
        sm["strategy_efficient"] = strat.get("efficient", 0)


def _captured_cost_stats(rows: list[dict]) -> dict:
    """One cost-denominator policy: average captured costs only, never missing-as-zero.

    A cell whose cost was not captured must not enter the average as ``0`` — that would
    lower the same model's average in one view and not another (public-truth review P1).
    Every aggregation over cost therefore publishes the same four fields, so two views of
    the same model can never disagree on its average cost.
    """
    costs = [c["total_cost"] for c in rows if c.get("total_cost", 0) > 0]
    captured = len(costs)
    total = len(rows)
    return {
        "total_cells": total,
        "cost_captured_cells": captured,
        "avg_captured_cost": round(sum(costs) / captured, 6) if captured else None,
        "cost_coverage": round(captured / total, 4) if total else 0.0,
    }


def _captured_cost_key(rows: list[dict]) -> float:
    """Ordering key: mean captured cost (inf when nothing captured), matching the old
    ``ORDER BY avg_cost`` (NULLs last)."""
    costs = [c["total_cost"] for c in rows if c["total_cost"] > 0]
    return sum(costs) / len(costs) if costs else float("inf")


def compute_story_models(stories: list[dict]) -> list[dict]:
    """Build the model comparison from the canonical story payloads (source of truth).

    Consumes ``tables.stories`` directly — no parquet — so the per-model story metrics
    and the condition split share the resolver's relabel with the labs.
    """
    cells, sessions = _story_pipeline_rows(stories)

    # Real test pass/fail + token splits per model, from the session transcripts.
    test_by_model: dict[str, dict] = defaultdict(
        lambda: {"passed": 0, "run": 0, "prompt": 0, "completion": 0, "reasoning": 0}
    )
    for s in sessions:
        t = test_by_model[s["model"]]
        t["passed"] += s["tests_passed"]
        t["run"] += s["tests_total"]
        t["prompt"] += s["prompt_tokens"]
        t["completion"] += s["completion_tokens"]
        t["reasoning"] += s["reasoning_tokens"]

    by_model: dict[str, list] = defaultdict(list)
    for c in cells:
        by_model[c["model"]].append(c)

    models = []
    for mid, rows in sorted(by_model.items(), key=lambda kv: _captured_cost_key(kv[1])):
        total_runs = len(rows)
        cell_keys = {
            f"{c['story_name']}|{mid}|{c['tier']}|{c['quality']}|{c['condition']}" for c in rows
        }
        unique_cells = len(cell_keys)
        t = test_by_model[mid]
        sessions_sum = sum(c["session_count"] for c in rows)
        cost_stats = _captured_cost_stats(rows)
        cost_cells = cost_stats["cost_captured_cells"]
        avg_cost = cost_stats["avg_captured_cost"]
        avg_code_lines = round(sum(c["code_lines"] for c in rows) / total_runs, 0)
        # Energy is a [C]omputed estimate from measured tokens (J per token).
        avg_energy_j = round(
            (t["prompt"] * 0.08 + t["completion"] * 0.23 + t["reasoning"] * 0.47)
            / max(total_runs, 1),
            1,
        )
        models.append(
            {
                "id": mid,
                "label": MODEL_LABELS.get(mid, mid),
                "provider": get_provider(mid),
                "cells": total_runs,
                "unique_cells": unique_cells,
                "re_runs": total_runs - unique_cells,
                "sessions": sessions_sum,
                "total_cost": round(sum(c["total_cost"] for c in rows), 6),
                "avg_cost": avg_cost,
                "cost_cells": cost_cells,
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_cells": cost_stats["cost_captured_cells"],
                "total_cells": cost_stats["total_cells"],
                "cost_coverage": cost_stats["cost_coverage"],
                "avg_cache_hit": round(sum(c["cache_hit_rate"] for c in rows) / total_runs, 3),
                "avg_tests": round(sum(c["test_count"] for c in rows) / total_runs, 1),
                "avg_test_code_ratio": round(
                    sum(c["test_code_ratio"] for c in rows) / total_runs, 3
                ),
                "avg_tok_per_session": round(
                    sum(c["total_tokens"] / max(c["session_count"], 1) for c in rows) / total_runs,
                    0,
                ),
                "avg_duration_s": round(sum(c["total_duration"] for c in rows) / total_runs, 0),
                "avg_code_lines": avg_code_lines,
                # ── Test-count scope (review "smaller"): two DIFFERENT quantities, no longer
                # ── conflated under one name. `final_tests_discovered` is the story-level peak
                # ── (how many tests the final codebase has); `test_executions_*` is summed
                # ── across every session execution (each session re-runs the suite).
                "final_tests_discovered": sum(c["test_count"] for c in rows),
                "test_executions_passed": t["passed"],
                "test_executions_run": t["run"],
                "pass_rate": _honest_pass_rate(t["passed"], t["run"]),
                "pass_rate_scope": (
                    "weighted over repeated session-level test executions (each session "
                    "re-runs the suite; the count is summed across sessions)"
                ),
                # keep legacy keys populated for existing charts
                "avg_cost_per_session": round(
                    (avg_cost or 0) / max(sessions_sum / max(total_runs, 1), 1), 6
                ),
                "avg_loc": avg_code_lines,
                "avg_energy_j": avg_energy_j,
                "avg_energy_j_per_loc": round(avg_energy_j / max(avg_code_lines, 1), 2),
                # Not measured for the story corpus — do not fabricate zeros.
                "narration_rate": None,
                "avg_narration_penalty": None,
                "strategy_cons": 0,
                "strategy_expl": 0,
                "strategy_waste": 0,
                "strategy_efficient": 0,
                "reports": total_runs,
                "reports_valid": total_runs,
                "reports_narrated": 0,
            }
        )

    return models


def _assert_resolution_complete(tables, waiver_path=None) -> list[dict]:
    """Fail closed on unresolved current rows unless a valid, hard-bound waiver covers them.

    Review P1 (tightened in public-truth P1/p4): a current registry row whose payload cannot
    be resolved must not silently drop out of the published dataset. It is repaired,
    tombstoned, or covered by a hard-bound waiver — and the waiver is validated first, so a
    stale/duplicate/unmatched waiver is a publication-blocking defect, not a silent no-op.
    Returns the waivered issues as plain dicts so :func:`build` can emit them into ``data.js``
    (the waiver is *visible*, not just permitted). Raises :class:`RuntimeError` naming every
    rejected waiver and every unwaivered row.
    """
    waivers = load_waivers(waiver_path)
    valid_waivers, rejected = validate_waivers(tables.resolution, waivers)
    unwaivered = unwaivered_issues(tables.resolution, valid_waivers)

    problems = list(rejected)
    if unwaivered:
        detail = "\n".join(
            f"  - {i.table} {i.logical_locator!r} ({i.kind}) entity_id={i.entity_id}"
            for i in unwaivered
        )
        problems.append(
            "publication aborted: current registry rows could not be resolved to a "
            "measurement payload and are not covered by a valid waiver:\n"
            f"{detail}\n"
            "Repair the payload, tombstone the row, or add a hard-bound waiver entry to "
            f"{DEFAULT_WAIVER_PATH.relative_to(ROOT)}."
        )
    if problems:
        raise RuntimeError("waiver/resolution failures:\n" + "\n".join(problems))

    # Waiver visibility: the waivered issues (matched to their reason) travel into data.js.
    reason_by_key = {w.key: w.reason for w in valid_waivers}
    waived = []
    for i in tables.resolution.issues:
        reason = reason_by_key.get((i.table, i.logical_locator, i.kind))
        if reason is not None:
            waived.append(
                {
                    "table": i.table,
                    "logical_locator": i.logical_locator,
                    "entity_id": i.entity_id,
                    "kind": i.kind,
                    "reason": reason,
                }
            )
    return waived


#: The source files whose code produces ``data.js`` — the *generator source tree*
#: (public-truth review P1/P2). Their contents are hashed so the publication contract
#: records *which code* produced the numbers, not just *which data*: a generator change
#: (a new reducer, a projection change) is visible even when the input is unchanged.
GENERATOR_SOURCES = (
    ROOT / "scripts" / "build_data.py",
    ROOT / "src" / "agentic_dynamics" / "reporting" / "canonical_corpus.py",
    ROOT / "src" / "agentic_dynamics" / "reporting" / "lab_contract.py",
    ROOT / "src" / "agentic_dynamics" / "reporting" / "lab_manifest.py",
)


def generator_source_tree_identity() -> str:
    """``sha256`` over the generator source files (name + bytes, in a fixed order).

    Deterministic and environment-independent: only the source file *contents* enter the
    digest, never their absolute paths.
    """
    h = hashlib.sha256()
    for path in GENERATOR_SOURCES:
        h.update(path.name.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()


#: The generated spec lifecycle index (``scripts/spec_status.py``) — the machine-readable
#: source for the experiment-vs-workflow spec counts (public-truth review "smaller": the
#: README displays 80 specs = 6 experiments + 74 workflows).
SPEC_INDEX_PATH = ROOT / "experiments" / "specs" / "index.json"


def _spec_counts() -> dict[str, int]:
    """Count experiment vs workflow specs from the generated spec index.

    A missing/unreadable index degrades to zeros — the figure is simply absent, never
    fabricated — matching the resolver's file-fallback posture elsewhere.
    """
    try:
        index = json.loads(SPEC_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"experiment_specs": 0, "workflow_specs": 0}
    n_experiment = n_workflow = 0
    for spec in index.get("specs", []):
        kind = spec.get("artifact_kind")
        if kind == "experiment":
            n_experiment += 1
        elif kind == "workflow":
            n_workflow += 1
    return {"experiment_specs": n_experiment, "workflow_specs": n_workflow}


def _lab_status_counts() -> dict[str, int]:
    """Count canonical vs quarantined lab books from the lab manifest."""
    counts = Counter(entry.lab_status for entry in load_lab_manifest())
    return {
        "lab_books_canonical": counts.get("canonical", 0),
        "lab_books_quarantined": counts.get("quarantined", 0),
    }


def build():
    print("Building data.js...")

    inventory = load_inventory()
    print(
        f"  Loaded inventory: {inventory['counts']['db_sessions_experiments']} experiment sessions"
    )

    # ── The single publication door ──────────────────────────────────────────
    # One complete canonical input: story + finding + review + analysis resolved
    # together, so every section below (models, story pipeline, reviews, analysis)
    # shares the resolver's lifecycle filter and condition relabel.
    tables = load_canonical_tables("story", "finding", "review", "analysis")
    corpus = load_canonical_corpus(tables=tables)
    entries = corpus.entries

    # ── Fail closed on unresolved rows (review P1) ───────────────────────────
    # A current registry row with no payload is a publication-blocking defect unless a
    # committed, reason-bearing waiver covers it. The returned list is the waived rows,
    # emitted below so the waiver is visible in data.js.
    waivers = _assert_resolution_complete(tables)

    print(
        f"  Loaded canonical corpus: {corpus.finding_count} finding + "
        f"{corpus.story_count} story current records "
        f"({corpus.tombstoned_count} tombstoned excluded); {len(entries)} perturbation entries; "
        f"{len(tables.reviews)} reviews + {len(tables.analysis)} analysis; "
        f"resolution {tables.resolution.resolved}/{tables.resolution.expected_current} "
        f"({tables.resolution.unresolved} unresolved, {len(waivers)} waivered)"
    )

    report_count = count_game_reports()
    print(f"  Game reports on disk: {report_count}")

    models = compute_model_data(entries)
    perturbation_models = models  # preserve real perturbation metrics (energy/strategy/…)
    print(f"  Computed: {len(models)} perturbation models")

    # Story pipeline models are the source of truth for cross-model comparison.
    # The perturbation models are preserved under a separate key — never discarded.
    story_models = compute_story_models(tables.stories)
    analysis_data = _load_analysis_data(tables.analysis, tables.stories)
    if story_models:
        _merge_story_strategy(story_models, analysis_data)
        models = story_models
        print(f"  Story models: {len(models)} (from the canonical story table)")

    charts = compute_charts(models)
    calculator = compute_calculator(models)
    derived = compute_derived(models, inventory, report_count)

    # ── Operator comparison — per-operator × per-model matrices ──
    # Re-derived from the canonical finding entries (corpus.by_operator_model).
    by_op_model = corpus.by_operator_model
    op_comparison = {}
    for key, agg in by_op_model.items():
        parts = key.split("|", 2)
        if len(parts) >= 3:
            op = parts[0]
            pc = parts[1]
            mdl = parts[2]
            model_label = MODEL_LABELS.get(mdl, mdl)
            if op not in op_comparison:
                op_comparison[op] = {"perturbation_class": pc, "models": {}}
            op_comparison[op]["models"][model_label] = {
                "n": agg.get("n", agg.get("count", 0)),
                "avg_cost": agg.get("cost_avg", 0),
                "cost_ci95": [agg.get("cost_ci95_lo"), agg.get("cost_ci95_hi")]
                if agg.get("cost_ci95_lo") is not None
                else None,
                "avg_escape": agg.get("escape_avg", 0),
                "escape_ci95": [agg.get("escape_ci95_lo"), agg.get("escape_ci95_hi")]
                if agg.get("escape_ci95_lo") is not None
                else None,
                "avg_correctness": agg.get("correctness_avg", 0),
                "correctness_ci95": [agg.get("correctness_ci95_lo"), agg.get("correctness_ci95_hi")]
                if agg.get("correctness_ci95_lo") is not None
                else None,
                "avg_thinking_ratio": agg.get("thinking_ratio_avg", 0),
                "avg_energy_j": agg.get("energy_total_j_avg", 0),
                "low_n": (agg.get("n", agg.get("count", 0)) < 5),
            }

    # ── Perturbation class breakdown — specification / objective / process vs baseline ──
    pert_class_breakdown = {}
    for e in entries:
        if e.get("narration_failure"):
            continue
        pc = e.get("perturbation_class", "unknown")
        mdl = e.get("model", "unknown")
        if pc not in pert_class_breakdown:
            pert_class_breakdown[pc] = {}
        model_label = MODEL_LABELS.get(mdl, mdl)
        if model_label not in pert_class_breakdown[pc]:
            pert_class_breakdown[pc][model_label] = {
                "count": 0,
                "costs": [],
                "escapes": [],
                "correctness": [],
                "thinking_ratios": [],
                "locs": [],
                "tokens": [],
            }
        pb = pert_class_breakdown[pc][model_label]
        pb["count"] += 1
        pb["costs"].append(e.get("cost", 0))
        pb["escapes"].append(e.get("escape", 0))
        pb["correctness"].append(e.get("correctness", 0))
        pb["thinking_ratios"].append(e.get("thinking_ratio", 0))
        pb["locs"].append(e.get("code_lines", 0))
        pb["tokens"].append(e.get("tokens", 0))

    pert_class_summary = {}
    for pc, pc_models in pert_class_breakdown.items():
        pert_class_summary[pc] = {}
        for label, pb in pc_models.items():
            n = pb["count"]
            pert_class_summary[pc][label] = {
                "n": n,
                "low_n": n < 5,
                "avg_cost": round(sum(pb["costs"]) / n, 4),
                "cost_ci95": bootstrap_ci(pb["costs"]) if n >= 5 else None,
                "avg_escape": round(sum(pb["escapes"]) / n, 2),
                "escape_ci95": bootstrap_ci(pb["escapes"]) if n >= 5 else None,
                "avg_correctness": round(sum(pb["correctness"]) / n, 2),
                "correctness_ci95": bootstrap_ci(pb["correctness"]) if n >= 5 else None,
                "avg_thinking_ratio": round(sum(pb["thinking_ratios"]) / n, 3),
                "avg_loc": round(sum(pb["locs"]) / n),
                "avg_tokens": round(sum(pb["tokens"]) / n),
                # Historical: narration is not measured in the finding corpus → None.
                "avg_narration_penalty": None,
            }

    # ── Energy ranking — per-model energy metrics ──
    energy_ranking = sorted(
        [
            {
                "id": m["id"],
                "label": m["label"],
                "avg_energy_j": m["avg_energy_j"],
                "avg_energy_j_per_loc": m["avg_energy_j_per_loc"],
                "avg_cost": m["avg_cost"],
                "avg_loc": m["avg_loc"],
            }
            for m in models
            if m["avg_energy_j"] > 0
        ],
        key=lambda x: x["avg_energy_j_per_loc"],
    )

    counts = inventory.get("counts", {})
    inventory.get("costs", {})

    # Headline figures the README "By the Numbers" block displays that are NOT part of the
    # story corpus (public-truth review "smaller"): the provider count, the experiment-vs-
    # workflow spec split, and the canonical-vs-quarantined lab split. All three are read
    # from their canonical source (the models, the generated spec index, the lab manifest).
    spec_counts = _spec_counts()
    lab_counts = _lab_status_counts()
    provider_count = len({m.get("provider") for m in models})

    data = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_inventory": str(INVENTORY_PATH),
            "source_registry": str(MANIFEST_PATH),
            "source_db": str(DB_PATH),
            "provenance_note": "All values tagged [M]easured, [C]omputed, [H]euristic, or e[X]ternal. See methodology.html.",
        },
        "summary": {
            "worktrees_total": counts.get("worktrees_total", 0),
            "sessions_total": sum(m.get("sessions", 0) for m in models),
            "game_reports": report_count,
            "total_cost": _fmt_usd(sum(m.get("total_cost", 0) for m in models)),
            "architectures": 3,
            "variants": len(story_models) if story_models else 8,
            "stories_total": sum(m.get("cells", 0) for m in models),
            "stories_unique": sum(m.get("unique_cells", 0) for m in models),
            "stories_re_runs": sum(m.get("re_runs", 0) for m in models),
            "story_sessions": sum(m.get("sessions", 0) for m in models),
            "story_total_cost": _fmt_usd(sum(m.get("total_cost", 0) for m in models)),
            "configs": counts.get("config_files", 0),
            # ── Scoped counts (review P1) — the registry claim, what resolved, what was
            # ── eligible, what was used. No more blanket "canonical stories": the 225-vs-215
            # ── gap (the 10 payload-less, waived Claude stubs) is now explicit.
            "registry_current_records": corpus.story_count,
            "resolved_measurement_payloads": len(tables.stories),
            "eligible_records": len(tables.stories),
            "records_used": len(tables.stories),
            "unresolved_waivered": len(waivers),
            "canonical_findings": corpus.finding_count,
            "tombstoned_excluded": corpus.tombstoned_count,
            "_provenance": {
                "worktrees_total": "M",
                "sessions_total": "M",
                "game_reports": "M",
                "total_cost": "M",
                "architectures": "M",
                "variants": "M",
                "stories_total": "C",
                "stories_unique": "C",
                "stories_re_runs": "C",
                "story_sessions": "C",
                "story_total_cost": "C",
                "configs": "M",
                "registry_current_records": "M",
                "resolved_measurement_payloads": "M",
                "eligible_records": "C",
                "records_used": "C",
                "unresolved_waivered": "M",
                "canonical_findings": "M",
                "tombstoned_excluded": "M",
            },
        },
        # ── Resolution completeness (review P1) — the report + the waived rows, so the
        # ── publication boundary and its exemptions are visible in the output itself.
        "resolution_report": {
            "expected_current": tables.resolution.expected_current,
            "resolved": tables.resolution.resolved,
            "missing": tables.resolution.missing,
            "unreadable": tables.resolution.unreadable,
            "ambiguous": tables.resolution.ambiguous,
            "duplicate": tables.resolution.duplicate,
            "waivers": waivers,
        },
        # ── Global publication contract (public-truth review P1/P2) — the six identities
        # ── that attest to *what* produced this dataset and *how*. They are the dataset's
        # ── lineage: which registry selection, which resolved payloads, which policy/normal-
        # ── ization versions, which waiver set, and which generator source tree.
        "publication_contract": {
            "registry_identity": tables.identity.registry_identity_sha256,
            "resolved_input_identity": tables.resolved_input_sha256,
            "data_integrity_policy_version": DATA_INTEGRITY_POLICY_VERSION,
            "normalization_version": NORMALIZATION_VERSION,
            "waiver_digest": waiver_set_digest(),
            "generator_source_tree_identity": generator_source_tree_identity(),
        },
        # ── Public statistics (review "smaller"): the ONE artifact README prose cites, so a
        # ── headline figure can never drift from the published dataset again. README.md's
        # ── "By the Numbers" table and the home-page hero are reconciled to THIS block.
        "public_statistics": {
            "story_sessions": sum(m.get("sessions", 0) for m in models),
            "stories_total": sum(m.get("cells", 0) for m in models),
            "story_total_cost": _fmt_usd(sum(m.get("total_cost", 0) for m in models)),
            "db_sessions_total": counts.get("db_sessions_total", 0),
            "game_reports": report_count,
            "model_variants": len(models),
            "providers": provider_count,
            "experiment_configs": counts.get("config_files", 0),
            "experiment_specs": spec_counts["experiment_specs"],
            "workflow_specs": spec_counts["workflow_specs"],
            "perturbation_operators": 10,
            "lab_books": len(load_lab_manifest()),
            "lab_books_canonical": lab_counts["lab_books_canonical"],
            "lab_books_quarantined": lab_counts["lab_books_quarantined"],
            "measured_spend_usd": round(sum(m.get("total_cost", 0) for m in models), 2),
            "_provenance": {
                "story_sessions": "M",
                "stories_total": "C",
                "story_total_cost": "C",
                "db_sessions_total": "M",
                "game_reports": "M",
                "model_variants": "M",
                "providers": "M",
                "experiment_configs": "M",
                "experiment_specs": "M",
                "workflow_specs": "M",
                "perturbation_operators": "M",
                "lab_books": "M",
                "lab_books_canonical": "M",
                "lab_books_quarantined": "M",
                "measured_spend_usd": "M",
            },
        },
        "models": models,
        "perturbation_models": perturbation_models,
        "charts": charts,
        "calculator": calculator,
        "derived": derived,
        "operator_comparison": op_comparison,
        "perturbation_class_breakdown": pert_class_summary,
        "energy_ranking": energy_ranking,
        "strategy_distribution": corpus.strategy_distribution,
        "routing": compute_routing(entries),
        "correctness_escape_quadrants": _load_correctness_escape_quadrants(),
        "sonar": _compute_sonar(entries),
        "design_parameters": {
            "beta": {
                "value": 0.001,
                "provenance": "design",
                "note": "Context inflation rate — calibrate to your codebase",
            },
            "woc_healthy": {"value": 0.85, "provenance": "design"},
            "woc_critical": {"value": 0.70, "provenance": "design"},
            "strategy_thresholds": {
                "correctness_min": 0.7,
                "escape_min": 0.5,
                "novelty_min": 0.4,
                "efficient_cost_max": 0.003,
                "wasteful_correctness_max": 0.3,
                "provenance": "design",
            },
            "composite_weights": {
                **COMPOSITE_WEIGHTS,
                "provenance": "design",
            },
        },
        "external_sources": {
            "epm_baseline": {
                "value": "1.6%/yr",
                "provenance": "X",
                "source": "IEA World Energy Outlook 2024",
            },
            "epm_aggressive": {
                "value": "2.5%/yr",
                "provenance": "X",
                "source": "Aggressive scenario",
            },
            "energy_per_token_prompt": {
                "value": 0.08,
                "unit": "J",
                "provenance": "X",
                "source": "TokenPowerBench (Niu et al., AAAI 2026)",
            },
            "energy_per_token_output": {
                "value": 0.23,
                "unit": "J",
                "provenance": "X",
                "source": "TokenPowerBench (Niu et al., AAAI 2026)",
            },
            "energy_per_token_reasoning": {
                "value": 0.47,
                "unit": "J",
                "provenance": "X",
                "source": "TokenPowerBench (Niu et al., AAAI 2026)",
            },
            "energy_model_available": {
                "value": False,
                "provenance": "X",
                "note": "Claude/GPT architecture undisclosed — energy model disabled",
            },
            "deepseek_active_params": {
                "value": "49e9",
                "provenance": "X",
                "note": "MoE V4 Pro, publicly disclosed (49B active)",
            },
        },
        "stories": _load_story_data(tables.stories),
        "reviews": _load_review_data(tables.reviews, tables.stories),
        "analysis": analysis_data,
        "labs": _load_labs(),
    }

    import math

    # Strip NaN values (replace with null) and remove local paths
    def _clean_value(obj):
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {
                k: _clean_value(v)
                for k, v in obj.items()
                if k not in ("source_inventory", "source_registry", "source_db")
            }
        if isinstance(obj, list):
            return [_clean_value(v) for v in obj]
        if isinstance(obj, str):
            return obj.replace(str(ROOT), ".").replace(str(Path.home()), "~")
        return obj

    clean_data = _clean_value(data)

    js = f"/* Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} by build_data.py */\n"
    js += "/* DO NOT EDIT — regenerate with: python scripts/build_data.py */\n"
    js += "window.DYNAMICS_DATA = " + json.dumps(clean_data, indent=2, default=str) + ";\n"

    return js, data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build data.js for the Agentic Dynamics website")
    parser.add_argument("--dry-run", action="store_true", help="Print instead of writing")
    args = parser.parse_args()

    if not INVENTORY_PATH.exists() and os.environ.get("ALLOW_MISSING_EXPERIMENT_DATA"):
        print(
            "SKIP: experiment inventory not present "
            "(ALLOW_MISSING_EXPERIMENT_DATA set) — exiting without building data.js.",
            file=sys.stderr,
        )
        return

    js, data = build()

    if args.dry_run:
        print("\n--- DRY RUN: data.js would contain ---\n")
        print(json.dumps(data, indent=2, default=str)[:8000])
        if len(json.dumps(data, indent=2)) > 8000:
            print(f"\n... ({len(json.dumps(data, indent=2))} chars total, truncated)")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(js)
    print(f"\nWrote {OUTPUT_PATH} ({len(js)} bytes)")


if __name__ == "__main__":
    main()
