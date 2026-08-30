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

import ast
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

from agentic_dynamics.control.routing import compute_routing  # noqa: E402
from agentic_dynamics.core.constants import MODEL_LABELS, bootstrap_ci
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
from agentic_dynamics.reporting.measurement_coverage import (  # noqa: E402
    MeasurementCoverage,
    cost_captured,
    cost_coverage,
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
    #: m4: the tombstone population split by reason — the 77 contaminated early_degrade
    #: cells vs the 10 "no usable measurement payload" retractions (cost-0 Claude stubs).
    #: A retraction is NOT contamination, so the two must never be described together.
    contaminated_tombstones: int = 0
    no_measurement_tombstones: int = 0


def _opt_float(value):
    """Coerce a present finding *score* to float; ``None``/absent stays ``None``.

    For a measured score (correctness, escape, divergence, composite, thinking ratio) a
    present ``0.0`` is a real measurement and is coerced; an absent value is absent. A
    non-numeric present value is treated as absent rather than raising. Economic fields
    (cost, energy) must NOT use this — see :func:`_optional_economic`.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_economic(run: dict, key: str) -> float | None:
    """An economic field (cost/energy), or ``None`` when it was not captured.

    Reuses the shared :func:`cost_captured` test (m2): an economic value is *captured*
    only when it is a finite, positive real. A ``0.0`` — the Claude cells whose
    cost/energy parser never ran — means "not priced / not metered" and publishes as
    null, never a numeric zero that would dilute a ratio's denominator to nonsense.
    """
    value = run.get(key)
    return float(value) if cost_captured(value) else None


def _finding_entry_from_run(experiment: str, run: dict, locator: str) -> dict:
    """Map one finding payload ``run`` into a summary-shaped entry dict.

    This is the vocabulary translation the retired summary's consumers already speak:
    the finding's native field names (``cost_usd``, ``lines_of_code``, ``escape_score``,
    ``prompt_tokens``…) are remapped to the summary field names. Every field the finding
    corpus does not measure is emitted as ``None`` (renders em-dash, never a fabricated
    value) — including the economics (``cost``, ``energy_total_j``, ``quality_per_joule``)
    and the optional scores (``escape``, ``architecture_divergence``, ``composite_score``,
    ``thinking_ratio``). ``narration_failure`` is unmeasured in the finding corpus, so it
    is ``None`` (never an invented ``False``). ``test_results``/``evaluator_source`` come
    from the measured ``tests_passed``/``tests_total``/``test_executed_success`` only.
    """
    energy_total_j = _optional_economic(run, "energy_j")
    # quality_per_joule is a ratio whose denominator is energy: it is null unless energy
    # was captured (finite AND positive) — a 0.0-energy cell's payload ratio is the
    # meaningless ``composite / 0.01`` floor and must never be published.
    quality_per_joule = (
        _opt_float(run.get("quality_per_joule")) if energy_total_j is not None else None
    )
    tests_total = int(run.get("tests_total") or 0)
    tests_passed = int(run.get("tests_passed") or 0)
    return {
        "experiment": experiment,
        "type": run.get("type", "perturbed"),
        "worktree_name": locator,
        "model": run.get("model", "unknown"),
        # The flail dimension is unmeasured in the finding corpus, so narration_failure
        # is None (renders em-dash), never an invented False.
        "narration_failure": None,
        "correctness": _opt_float(run.get("correctness")),
        "cost": _optional_economic(run, "cost_usd"),
        "strategy": run.get("strategy"),
        "code_lines": int(run.get("lines_of_code") or 0),
        "thinking_ratio": _opt_float(run.get("thinking_ratio")),
        "escape": _opt_float(run.get("escape_score")),
        "architecture_divergence": _opt_float(run.get("architecture_divergence")),
        "composite_score": _opt_float(run.get("composite_score")),
        "energy_total_j": energy_total_j,
        "quality_per_joule": quality_per_joule,
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
    not read pre-aggregated. Every economic/optional field carries its coverage shape
    (m2, extended to the finding corpus): cost → the five-field captured-cost tuple, the
    optional scores → ``{value, n_available, n_total, coverage}`` — with a plain captured
    mean kept alongside, never a missing-as-zero average.
    """
    groups: dict[str, list] = defaultdict(list)
    for e in entries:
        typ = e.get("type", "perturbed")
        pc = e.get("perturbation_class", "unknown")
        mdl = e.get("model", "unknown")
        groups[f"{typ}|{pc}|{mdl}"].append(e)

    result = {}
    for key, rows in groups.items():
        costs = [r.get("cost") for r in rows if cost_captured(r.get("cost"))]
        escapes = [r.get("escape") for r in rows if r.get("escape") is not None]
        correctness = [r.get("correctness") for r in rows if r.get("correctness") is not None]
        thinking = [r.get("thinking_ratio") for r in rows if r.get("thinking_ratio") is not None]
        energy = [r.get("energy_total_j") for r in rows if r.get("energy_total_j") is not None]
        arch = [
            r.get("architecture_divergence")
            for r in rows
            if r.get("architecture_divergence") is not None
        ]
        composite = [r.get("composite_score") for r in rows if r.get("composite_score") is not None]
        qj = [r.get("quality_per_joule") for r in rows if r.get("quality_per_joule") is not None]
        n = len(rows)
        result[key] = {
            "n": n,
            "count": n,
            # cost → the five-field captured-cost tuple (m2 cost_coverage)
            **cost_coverage([r.get("cost") for r in rows], n_total=n),
            "cost_avg": round(sum(costs) / len(costs), 4) if costs else None,
            "cost_ci95_lo": bootstrap_ci(costs)[0] if len(costs) >= 5 else None,
            "cost_ci95_hi": bootstrap_ci(costs)[1] if len(costs) >= 5 else None,
            "escape_avg": round(sum(escapes) / len(escapes), 2) if escapes else None,
            "escape_ci95_lo": bootstrap_ci(escapes)[0] if len(escapes) >= 5 else None,
            "escape_ci95_hi": bootstrap_ci(escapes)[1] if len(escapes) >= 5 else None,
            "correctness_avg": round(sum(correctness) / len(correctness), 2)
            if correctness
            else None,
            "correctness_ci95_lo": bootstrap_ci(correctness)[0] if len(correctness) >= 5 else None,
            "correctness_ci95_hi": bootstrap_ci(correctness)[1] if len(correctness) >= 5 else None,
            "thinking_ratio_avg": round(sum(thinking) / len(thinking), 3) if thinking else None,
            "energy_total_j_avg": round(sum(energy) / len(energy), 1) if energy else None,
            "escape_coverage": _coverage_dict(escapes, n_total=n, round_value=2),
            "correctness_coverage": _coverage_dict(correctness, n_total=n, round_value=2),
            "thinking_ratio_coverage": _coverage_dict(thinking, n_total=n, round_value=3),
            "energy_j_coverage": _coverage_dict(energy, n_total=n, round_value=1),
            "architecture_divergence_coverage": _coverage_dict(arch, n_total=n, round_value=3),
            "composite_score_coverage": _coverage_dict(composite, n_total=n, round_value=3),
            "quality_per_joule_coverage": _coverage_dict(qj, n_total=n, round_value=4),
        }
    return result


def _compute_strategy_distribution(entries: list) -> dict:
    """Re-derive the strategy-archetype counts from the canonical entries.

    An unmeasured strategy is labelled ``unknown`` (never a fabricated ``?`` or a silent
    drop): the distribution states an unknown strategy as such, and the counts sum to the
    entry total.
    """
    dist: dict[str, int] = defaultdict(int)
    for e in entries:
        dist[(e.get("strategy") or "unknown").lower()] += 1
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
        contaminated_tombstones=sum(
            1
            for r in rows
            if r.get("lifecycle_state") == "tombstoned"
            and r.get("source_type") in CANONICAL_SOURCE_TYPES
            and "contaminat" in (r.get("reason") or "").lower()
        ),
        no_measurement_tombstones=sum(
            1
            for r in rows
            if r.get("lifecycle_state") == "tombstoned"
            and r.get("source_type") in CANONICAL_SOURCE_TYPES
            and "no usable measurement" in (r.get("reason") or "").lower()
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

        valid = [r for r in reports if not r.get("narration_failure")]
        narrated = [r for r in reports if r.get("narration_failure")]

        # Cost → the five-field captured-cost tuple (m2). A missing/zero cost is "not
        # captured", never a $0 that dilutes the average.
        cost_stats = cost_coverage([r.get("cost") for r in valid], n_total=len(valid))
        avg_cost = (
            _fmt_usd(cost_stats["avg_captured_cost"])
            if cost_stats["avg_captured_cost"] is not None
            else None
        )
        total_cost = _fmt_usd(cost_stats["total_captured_cost"])

        # Optional/economic fields → coverage shapes over the non-None values only.
        correctness_vals = [r.get("correctness") for r in valid if r.get("correctness") is not None]
        thinking_vals = [
            r.get("thinking_ratio") for r in valid if r.get("thinking_ratio") is not None
        ]
        escape_vals = [r.get("escape") for r in valid if r.get("escape") is not None]
        arch_vals = [
            r.get("architecture_divergence")
            for r in valid
            if r.get("architecture_divergence") is not None
        ]
        composite_vals = [
            r.get("composite_score") for r in valid if r.get("composite_score") is not None
        ]
        energy_vals = [
            r.get("energy_total_j") for r in valid if r.get("energy_total_j") is not None
        ]
        qj_vals = [
            r.get("quality_per_joule") for r in valid if r.get("quality_per_joule") is not None
        ]

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

        # An unknown strategy is ``unknown`` — a fifth bucket, never silently dropped.
        strategies = {
            "conservative": 0,
            "exploratory": 0,
            "wasteful": 0,
            "efficient": 0,
            "unknown": 0,
        }
        for r in valid:
            s = (r.get("strategy") or "unknown").lower()
            strategies[s] += 1

        avg_loc = round(sum(r.get("code_lines", 0) for r in valid) / max(len(valid), 1))
        avg_correctness = (
            round(sum(correctness_vals) / len(correctness_vals), 2) if correctness_vals else None
        )
        avg_thinking = round(sum(thinking_vals) / len(thinking_vals), 3) if thinking_vals else None
        avg_escape = round(sum(escape_vals) / len(escape_vals), 2) if escape_vals else None
        avg_arch_div = round(sum(arch_vals) / len(arch_vals), 3) if arch_vals else None
        avg_composite = (
            round(sum(composite_vals) / len(composite_vals), 3) if composite_vals else None
        )

        avg_energy = round(sum(energy_vals) / len(energy_vals), 1) if energy_vals else None
        avg_energy_per_loc = (
            round(avg_energy / max(avg_loc, 1), 2) if avg_energy is not None else None
        )

        # Economic ratios are null unless their denominator is captured AND > 0 (m2):
        # correctness/dollar needs a captured cost; quality/joule needs a captured energy.
        cpd_vals = [
            r.get("correctness") / r.get("cost")
            for r in valid
            if r.get("correctness") is not None and cost_captured(r.get("cost"))
        ]
        correctness_per_dollar = round(sum(cpd_vals) / len(cpd_vals), 4) if cpd_vals else None

        qj_ratio_vals = [
            r.get("quality_per_joule")
            for r in valid
            if r.get("quality_per_joule") is not None
            and r.get("energy_total_j") is not None
            and r.get("energy_total_j") > 0
        ]
        avg_quality_per_joule = (
            round(sum(qj_ratio_vals) / len(qj_ratio_vals), 4) if qj_ratio_vals else None
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
                # cost → the five-field captured-cost tuple (m2)
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "total_captured_cost": cost_stats["total_captured_cost"],
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "cost_coverage": cost_stats["cost_coverage"],
                "cost_ci95": bootstrap_ci(
                    [r.get("cost") for r in valid if cost_captured(r.get("cost"))]
                )
                if cost_stats["cost_captured_records"] >= 5
                else None,
                "pass_rate": pass_rate_val,
                "strategy_cons": strategies["conservative"],
                "strategy_expl": strategies["exploratory"],
                "strategy_waste": strategies["wasteful"],
                "strategy_efficient": strategies["efficient"],
                "strategy_unknown": strategies["unknown"],
                "avg_loc": avg_loc,
                "avg_correctness": avg_correctness,
                "avg_thinking_ratio": avg_thinking,
                "avg_escape": avg_escape,
                "avg_arch_divergence": avg_arch_div,
                "avg_composite_score": avg_composite,
                "avg_energy_j": avg_energy,
                "avg_energy_j_per_loc": avg_energy_per_loc,
                "correctness_per_dollar": correctness_per_dollar,
                "avg_quality_per_joule": avg_quality_per_joule,
                "avg_constraints_met": avg_constraints_met,
                "avg_constraints_total": avg_constraints_total,
                # coverage shapes for the optional/economic fields (m2)
                "correctness_coverage": _coverage_dict(
                    correctness_vals, n_total=len(valid), round_value=2
                ),
                "thinking_ratio_coverage": _coverage_dict(
                    thinking_vals, n_total=len(valid), round_value=3
                ),
                "escape_coverage": _coverage_dict(escape_vals, n_total=len(valid), round_value=2),
                "architecture_divergence_coverage": _coverage_dict(
                    arch_vals, n_total=len(valid), round_value=3
                ),
                "composite_score_coverage": _coverage_dict(
                    composite_vals, n_total=len(valid), round_value=3
                ),
                "energy_j_coverage": _coverage_dict(energy_vals, n_total=len(valid), round_value=1),
                "quality_per_joule_coverage": _coverage_dict(
                    qj_vals, n_total=len(valid), round_value=4
                ),
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
                    "avg_captured_cost": "C",
                    "total_captured_cost": "C",
                    "cost_captured_records": "M",
                    "total_records": "M",
                    "cost_coverage": "C",
                    "cost_ci95": "C",
                    "avg_loc": "C",
                    "avg_correctness": "C",
                    "avg_thinking_ratio": "C",
                    "avg_escape": "C",
                    "avg_arch_divergence": "C",
                    "avg_composite_score": "C",
                    "avg_energy_j": "C",
                    "avg_energy_j_per_loc": "C",
                    "avg_quality_per_joule": "C",
                    "correctness_per_dollar": "C",
                    "correctness_coverage": "C",
                    "thinking_ratio_coverage": "C",
                    "escape_coverage": "C",
                    "architecture_divergence_coverage": "C",
                    "composite_score_coverage": "C",
                    "energy_j_coverage": "C",
                    "quality_per_joule_coverage": "C",
                    "avg_constraints_met": "C",
                    "avg_constraints_total": "C",
                    "strategy_cons": "C",
                    "strategy_expl": "C",
                    "strategy_waste": "C",
                    "strategy_efficient": "C",
                    "strategy_unknown": "C",
                    "pass_rate": "M" if total_tests > 0 else None,
                },
            }
        )

    return models


def _median_cost(entries: list) -> float:
    """Median cost of a model's entries (a robust ordering key for the model list).

    Skips uncaptured costs (``None``/zero — m2) so a model with missing costs orders by its
    captured costs only, never by a fabricated ``0``.
    """
    costs = sorted(c for c in (r.get("cost") for r in entries) if cost_captured(c))
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

    Thin wrapper over :class:`MeasurementCoverage` (m2) for the call sites that already
    hold a pre-rounded value rather than a list — the shared primitive, one denominator
    policy.
    """
    return MeasurementCoverage(
        value=value,
        n_available=n_available,
        n_total=n_total,
        coverage=round(n_available / n_total, 4) if n_total else 0.0,
    ).to_dict()


def _coverage_dict(values, *, n_total: int, round_value: int = 3) -> dict:
    """The m2 coverage shape ``{value, n_available, n_total, coverage}`` over non-None values.

    A list-based sibling of :func:`_optional_measurement` for the finding-corpus
    aggregations: it drops ``None`` values first (so an uncaptured economic/optional
    measurement never folds into the mean as zero) and delegates the denominator policy to
    the shared :class:`MeasurementCoverage` primitive.
    """
    available = [v for v in values if v is not None]
    return MeasurementCoverage.over(available, n_total=n_total, round_value=round_value).to_dict()


def _append_if_present(target: list, value) -> None:
    """Append ``value`` to ``target`` only when it is a real measurement (not ``None``).

    The m2 null-not-zero rule: an absent field (``None``) is "not measured" and must not
    be folded into an average as zero; a present field — even ``0.0`` — is a real value.
    """
    if value is not None:
        target.append(value)


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
            # m2 null-not-zero: an absent deep metric (None) is "not measured" and must
            # not enter the average as zero; a present field — even 0.0 — is a real value.
            _append_if_present(m["solution_correctness"], sol.get("correctness_score"))
            _append_if_present(m["solution_constraints"], sol.get("constraint_score"))
            _append_if_present(m["solution_quality"], sol.get("code_quality_score"))
            _append_if_present(m["solution_novelty"], sol.get("novelty_score"))
            _append_if_present(m["solution_composite"], sol.get("composite_score"))
            basin = deep.get("basin", {})
            _append_if_present(m["basin_escape"], basin.get("escape_score"))
            m["strategies"][deep.get("strategy", {}).get("strategy", "?")] += 1

    def _deep_coverage(values):
        # m2: publish each optional deep metric as {value, n_available, n_total, coverage}
        # — None when no analysis carried the field, rather than an averaged-in zero.
        return MeasurementCoverage.over(values, n_total=m["deep_cells"], round_value=3).to_dict()

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
                "solution_correctness": _deep_coverage(m["solution_correctness"]),
                "solution_constraints": _deep_coverage(m["solution_constraints"]),
                "solution_quality": _deep_coverage(m["solution_quality"]),
                "solution_novelty": _deep_coverage(m["solution_novelty"]),
                "solution_composite": _deep_coverage(m["solution_composite"]),
                "basin_escape": _deep_coverage(m["basin_escape"]),
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
                "total_tokens": summary.get("total_tokens"),
                "total_cost": summary.get("total_cost"),
                "cache_hit_rate": summary.get("cache_hit_rate"),
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
                    "total_tokens": a.get("total_tokens"),
                    "cache_read_tokens": a.get("cache_read_tokens", 0) or 0,
                    "cost_usd": s.get("cost_usd"),
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
    for mid, rows in sorted(by_model.items(), key=lambda kv: _total_captured_cost(kv[1])):
        n = len(rows)
        cost_stats = _captured_cost_stats(rows)
        models.append(
            {
                "model": mid,
                "cells": n,
                "total_cost": round(_total_captured_cost(rows), 6),
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "total_captured_cost": cost_stats["total_captured_cost"],
                "cost_coverage": cost_stats["cost_coverage"],
                "total_tokens": sum(
                    c["total_tokens"] for c in rows if c["total_tokens"] is not None
                ),
                "avg_cache_hit": round(
                    sum(c["cache_hit_rate"] for c in rows if c["cache_hit_rate"] is not None)
                    / max(len([c for c in rows if c["cache_hit_rate"] is not None]), 1),
                    3,
                )
                if any(c["cache_hit_rate"] is not None for c in rows)
                else None,
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
                "total_cost": round(_total_captured_cost(rows), 6),
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "total_captured_cost": cost_stats["total_captured_cost"],
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
    for name, rows in sorted(by_story.items(), key=lambda kv: _total_captured_cost(kv[1])):
        n = len(rows)
        cost_stats = _captured_cost_stats(rows)
        stories_out.append(
            {
                "story": name,
                "cells": n,
                "total_cost": round(_total_captured_cost(rows), 6),
                "avg_cost": cost_stats["avg_captured_cost"],
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "total_captured_cost": cost_stats["total_captured_cost"],
                "cost_coverage": cost_stats["cost_coverage"],
                "sessions": sum(c["session_count"] for c in rows),
                "avg_duration_s": round(sum(c["total_duration"] for c in rows) / n, 0),
                "avg_tokens_per_session": round(
                    sum(
                        c["total_tokens"] / max(c["session_count"], 1)
                        for c in rows
                        if c["total_tokens"] is not None
                    )
                    / max(len([c for c in rows if c["total_tokens"] is not None]), 1),
                    0,
                )
                if any(c["total_tokens"] is not None for c in rows)
                else None,
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
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "total_captured_cost": cost_stats["total_captured_cost"],
                "cost_coverage": cost_stats["cost_coverage"],
                "avg_tokens_per_session": round(
                    sum(
                        c["total_tokens"] / max(c["session_count"], 1)
                        for c in rows
                        if c["total_tokens"] is not None
                    )
                    / max(len([c for c in rows if c["total_tokens"] is not None]), 1),
                    0,
                )
                if any(c["total_tokens"] is not None for c in rows)
                else None,
                "avg_session_duration_s": round(
                    sum(c["total_duration"] / max(c["session_count"], 1) for c in rows) / n, 0
                ),
            }
        )

    # Per-session stats. m2 null-not-zero: a session with no captured cost (cost_usd None)
    # contributes nothing to the cost total rather than a fabricated zero.
    total_cost = sum(s["cost_usd"] for s in sessions if s["cost_usd"] is not None)
    total_tokens = sum(s["total_tokens"] for s in sessions if s["total_tokens"] is not None)
    cached = [
        s for s in sessions if s["cache_read_tokens"] is not None and s["prompt_tokens"] is not None
    ]
    total_cache_reads = sum(s["cache_read_tokens"] for s in cached)
    total_prompt = sum(s["prompt_tokens"] for s in cached)
    denom = total_cache_reads + total_prompt
    cache_hit_rate = (total_cache_reads / denom) if denom else None

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
            "cache_hit_rate": round(cache_hit_rate, 3) if cache_hit_rate is not None else None,
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
    Delegates to the shared :func:`cost_coverage` primitive (m2) so the website and every
    lab use the exact same captured-cost determination and the same five published fields
    (``avg_captured_cost`` / ``total_captured_cost`` / ``cost_captured_records`` /
    ``total_records`` / ``cost_coverage``).
    """
    return cost_coverage([c["total_cost"] for c in rows], n_total=len(rows))


def _total_captured_cost(rows: list[dict]) -> float:
    """Sum of captured cell costs only — skips missing (``None``) and zero costs (m2)."""
    return sum(c["total_cost"] for c in rows if cost_captured(c["total_cost"]))


def _captured_cost_key(rows: list[dict]) -> float:
    """Ordering key: mean captured cost (inf when nothing captured), matching the old
    ``ORDER BY avg_cost`` (NULLs last). Uses the shared :func:`cost_captured` test (m2)."""
    captured = [c["total_cost"] for c in rows if cost_captured(c["total_cost"])]
    return sum(captured) / len(captured) if captured else float("inf")


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
        cost_cells = cost_stats["cost_captured_records"]
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
                "total_cost": round(_total_captured_cost(rows), 6),
                "avg_cost": avg_cost,
                "cost_cells": cost_cells,
                "avg_captured_cost": cost_stats["avg_captured_cost"],
                "cost_captured_records": cost_stats["cost_captured_records"],
                "total_records": cost_stats["total_records"],
                "total_captured_cost": cost_stats["total_captured_cost"],
                "cost_coverage": cost_stats["cost_coverage"],
                "avg_cache_hit": round(
                    sum(c["cache_hit_rate"] for c in rows if c["cache_hit_rate"] is not None)
                    / max(len([c for c in rows if c["cache_hit_rate"] is not None]), 1),
                    3,
                )
                if any(c["cache_hit_rate"] is not None for c in rows)
                else None,
                "avg_tests": round(sum(c["test_count"] for c in rows) / total_runs, 1),
                "avg_test_code_ratio": round(
                    sum(c["test_code_ratio"] for c in rows) / total_runs, 3
                ),
                "avg_tok_per_session": round(
                    sum(
                        c["total_tokens"] / max(c["session_count"], 1)
                        for c in rows
                        if c["total_tokens"] is not None
                    )
                    / max(len([c for c in rows if c["total_tokens"] is not None]), 1),
                    0,
                )
                if any(c["total_tokens"] is not None for c in rows)
                else None,
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
                # keep legacy keys populated for existing charts — but a null captured-cost
                # average stays null (m2), never a fabricated $0 per session.
                "avg_cost_per_session": (
                    round(avg_cost / max(sessions_sum / max(total_runs, 1), 1), 6)
                    if avg_cost is not None
                    else None
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
#:
#: m4: the file list is DERIVED from ``build_data``'s import graph
#: (:func:`_generator_source_files`) rather than a hand-maintained tuple. The P2 finding
#: was that the hand tuple silently omitted ``core.constants``, ``control.routing`` and
#: ``measurement.solution`` — a derived manifest cannot omit a module build_data actually
#: imports.


def _source_closure(entry: Path, src_root: Path, *, root_module: str) -> list[Path]:
    """The transitive source closure of ``entry`` over the package rooted at ``src_root``.

    (f4 — transitive identity.) Walks ``entry``'s imports recursively and returns every source
    file reachable, sorted for determinism. Both absolute imports (``from agentic_dynamics.x
    import ...``) and RELATIVE imports (``from .x import ...``) are resolved — a relative import
    is resolved against the importing file's own package, so ``from .canonical_corpus import …``
    inside ``lab_contract.py`` contributes ``canonical_corpus.py`` (and its own dependencies)
    transitively. The list is *computed*, never hand-maintained.
    """
    seen: dict[Path, None] = {}

    def resolve(name: str) -> None:
        """Resolve an absolute ``root_module.*`` name to a file (or a package ``__init__``)."""
        if not name.startswith(root_module):
            return
        suffix = name[len(root_module) :]
        rel = suffix[1:].replace(".", "/") if suffix.startswith(".") else ""
        if rel:
            candidate = src_root / f"{rel}.py"
            if candidate.is_file():
                visit(candidate)
                return
            package = src_root / rel / "__init__.py"
            if package.is_file():
                visit(package)
        else:
            package = src_root / "__init__.py"
            if package.is_file():
                visit(package)

    def _module_parts(path: Path) -> list[str]:
        """The dotted module name of ``path`` (``[]`` for files outside ``src_root``).

        ``src_root/reporting/lab_contract.py`` → ``("agentic_dynamics", "reporting",
        "lab_contract")``; ``src_root/reporting/__init__.py`` → ``("agentic_dynamics",
        "reporting")``.
        """
        try:
            rel = path.relative_to(src_root)
        except ValueError:
            return []
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return [root_module, *parts]

    def _resolve_from(node: ast.ImportFrom, package_parts: list[str]) -> None:
        """Resolve an ImportFrom: relative (``level > 0``) against ``package_parts``, else absolute.

        ``from .x import ...`` (level 1) targets the current package; each extra level climbs one
        package (``from ..x`` → the parent package). A level that climbs above the package root
        resolves outside the tree and is skipped.
        """
        if node.level and node.level > 0:
            if node.level - 1 >= len(package_parts):
                return
            base = package_parts[: len(package_parts) - (node.level - 1)]
            name = ".".join([*base, node.module]) if node.module else ".".join(base)
            resolve(name)
        elif node.module:
            resolve(node.module)

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in seen:
            return
        seen[path] = None
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            return
        module_parts = _module_parts(path)
        package_parts = module_parts[:-1] if module_parts else []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolve(alias.name)
            elif isinstance(node, ast.ImportFrom):
                _resolve_from(node, package_parts)

    visit(entry)
    return sorted(seen)


def _generator_source_files() -> list[Path]:
    """The direct computation-dependency manifest, DERIVED from the import graph.

    (f4 — transitive identity.) Delegates to :func:`_source_closure` over ``build_data.py``'s
    imports inside the ``agentic_dynamics`` package.
    """
    return _source_closure(
        ROOT / "scripts" / "build_data.py",
        ROOT / "src" / "agentic_dynamics",
        root_module="agentic_dynamics",
    )


def _source_tree_identity(paths: list[Path], *, base: Path) -> str:
    """``sha256`` over ``(repo-relative path, file length, file bytes)`` for each source file.

    (f4 — transitive identity.) The repo-relative path is hashed — not just ``path.name`` — so
    two ``__init__.py`` files in different packages are distinct; the file length is folded in so
    a truncation/extension is distinguishable from a same-name rename. Deterministic and
    environment-independent: only the relative path and the bytes enter the digest.
    """
    h = hashlib.sha256()
    for path in paths:
        rel = path.relative_to(base).as_posix()
        data = path.read_bytes()
        h.update(rel.encode("utf-8"))
        h.update(str(len(data)).encode("utf-8"))
        h.update(data)
    return h.hexdigest()


def generator_source_tree_identity() -> str:
    """``sha256`` over the generated source-tree dependency manifest.

    Deterministic and environment-independent. The file list comes from
    :func:`_generator_source_files` (derived from the import graph — now resolving relative
    imports transitively), and each file is hashed as (repo-relative path, length, bytes), so the
    identity tracks the full computation surface, not a remembered subset.
    """
    return _source_tree_identity(_generator_source_files(), base=ROOT)


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


#: Immutable campaign score artifacts that ground the site's verdict surfaces (the field
#: layer's new evidence). Each is the rank-1 source for its verdict; the site consumes the
#: transcribed fields below — it never hand-types a verdict value into HTML.
CAP_2B_SCORE_PATH = RESULTS_DIR / "cap_2b" / "cap_2b_score_20260826T160018Z.json"
ESCALATION_SCORE_PATH = (
    RESULTS_DIR
    / "cap_escalation_measurement"
    / "cap_escalation_measurement_score_20260826T125726Z.json"
)
CALIBRATION_SCORE_PATH = (
    RESULTS_DIR / "cap_2a_rerun2" / "cap_2a_rerun2_score_20260826T015846Z.json"
)


def _load_json_artifact(path: Path) -> dict | None:
    """Read a campaign score artifact; a missing/unreadable artifact degrades to ``None``.

    The verdict surfaces then render a named-null state (the honest-null rule) instead of a
    fabricated number — the generator never guesses a verdict value.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"  [verdicts] missing/unreadable artifact: {path}")
        return None


def _load_verdicts() -> dict:
    """Load the field-layer verdict surfaces from the immutable campaign score artifacts.

    Three verdicts feed the revamp's new evidence:

    - ``cap_2b`` — the randomized non-inferiority decision (CPVO ratio, CI, margin, arms)
      :cite: `docs/experiments/results/cap_2b.md`
    - ``escalation`` — the measured escalation-chain E_x figures (Sol / Sonnet)
      :cite: `experiments/results/cap_escalation_measurement/`
    - ``calibration`` — the 0/3 → 2/3 calibration arc
      :cite: `docs/experiments/results/cap_2a_rerun2.md`

    Every value keeps its evidence class and its authorization boundary in-band, so the page
    renders scope and limitation at the point of reading (the provenance rule).
    """
    verdicts: dict = {"sources": {}, "cap_2b": {}, "escalation": {}, "calibration": {}}

    score = _load_json_artifact(CAP_2B_SCORE_PATH)
    if score:
        verdicts["sources"]["cap_2b"] = str(CAP_2B_SCORE_PATH.relative_to(ROOT))
        verdicts["cap_2b"] = {
            "decision": score.get("decision_rule", {}).get("decision"),
            "cpvo_ratio": score.get("decision_rule", {}).get("cpvo_ratio"),
            "cpvo_ratio_ci_95": score.get("decision_rule", {}).get("cpvo_ratio_ci_95"),
            "margin_cpvo_ratio_le": score.get("decision_rule", {}).get("margin_cpvo_ratio_le"),
            "success_gap_static_minus_adaptive": score.get("decision_rule", {}).get(
                "success_gap_static_minus_adaptive"
            ),
            "margin_success_gap_le": score.get("decision_rule", {}).get("margin_success_gap_le"),
            "authorization": "design review only, not control activation",
            "per_arm": score.get("per_arm", {}),
            "defect_bearing": score.get("defect_bearing", {}),
            "n_total": score.get("denominators", {}).get("n_total"),
            "n_defect_bearing": score.get("denominators", {}).get("n_defect_bearing"),
        }

    esc = _load_json_artifact(ESCALATION_SCORE_PATH)
    if esc:
        verdicts["sources"]["escalation"] = str(ESCALATION_SCORE_PATH.relative_to(ROOT))
        verdicts["escalation"] = {
            "baseline_cost_usd": esc.get("original_cell_cost_usd"),
            "baseline_source": esc.get("original_cell_cost_source"),
            "base_downstream_defect_cost_usd": esc.get("base_downstream_defect_cost_usd"),
            "per_model": [
                {
                    "model": row.get("escalation_model"),
                    "fix_cost_usd": row.get("escalation_fix_cost_usd"),
                    "E_x": row.get("E_x"),
                    "E_x_formula": row.get("E_x_formula"),
                    "defect_fixed": row.get("defect_fixed"),
                    "tests_passing": row.get("tests_passing"),
                }
                for row in esc.get("per_model", [])
            ],
            "note": "n=1 per escalation model; descriptive, no CI",
        }

    cal = _load_json_artifact(CALIBRATION_SCORE_PATH)
    if cal:
        verdicts["sources"]["calibration"] = str(CALIBRATION_SCORE_PATH.relative_to(ROOT))
        verdicts["calibration"] = {
            "initial": "0/3",
            "rerun_hit_rate": cal.get("aggregates", {}).get("hit_rate"),
            "rerun_n": cal.get("aggregates", {}).get("hit_rate_n"),
            "rerun_wilson_95": [0.2077, 0.9385],
            "note": "2/3 = 0.667, Wilson [0.2077, 0.9385], n=3; descriptive, not statistical clearance",
        }

    return verdicts


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
                "avg_cost": agg.get("cost_avg"),
                "cost_ci95": [agg.get("cost_ci95_lo"), agg.get("cost_ci95_hi")]
                if agg.get("cost_ci95_lo") is not None
                else None,
                "avg_escape": agg.get("escape_avg"),
                "escape_ci95": [agg.get("escape_ci95_lo"), agg.get("escape_ci95_hi")]
                if agg.get("escape_ci95_lo") is not None
                else None,
                "avg_correctness": agg.get("correctness_avg"),
                "correctness_ci95": [agg.get("correctness_ci95_lo"), agg.get("correctness_ci95_hi")]
                if agg.get("correctness_ci95_lo") is not None
                else None,
                "avg_thinking_ratio": agg.get("thinking_ratio_avg"),
                "avg_energy_j": agg.get("energy_total_j_avg"),
                # coverage shapes (m2): cost five-field + optional-field coverage
                "avg_captured_cost": agg.get("avg_captured_cost"),
                "total_captured_cost": agg.get("total_captured_cost"),
                "cost_captured_records": agg.get("cost_captured_records"),
                "total_records": agg.get("total_records"),
                "cost_coverage": agg.get("cost_coverage"),
                "correctness_coverage": agg.get("correctness_coverage"),
                "thinking_ratio_coverage": agg.get("thinking_ratio_coverage"),
                "escape_coverage": agg.get("escape_coverage"),
                "architecture_divergence_coverage": agg.get("architecture_divergence_coverage"),
                "composite_score_coverage": agg.get("composite_score_coverage"),
                "energy_j_coverage": agg.get("energy_j_coverage"),
                "quality_per_joule_coverage": agg.get("quality_per_joule_coverage"),
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
        pb["costs"].append(e.get("cost"))
        pb["escapes"].append(e.get("escape"))
        pb["correctness"].append(e.get("correctness"))
        pb["thinking_ratios"].append(e.get("thinking_ratio"))
        pb["locs"].append(e.get("code_lines", 0))
        pb["tokens"].append(e.get("tokens", 0))

    pert_class_summary = {}
    for pc, pc_models in pert_class_breakdown.items():
        pert_class_summary[pc] = {}
        for label, pb in pc_models.items():
            n = pb["count"]
            costs = [c for c in pb["costs"] if cost_captured(c)]
            escapes = [v for v in pb["escapes"] if v is not None]
            correctness = [v for v in pb["correctness"] if v is not None]
            thinking = [v for v in pb["thinking_ratios"] if v is not None]
            pert_class_summary[pc][label] = {
                "n": n,
                "low_n": n < 5,
                "avg_cost": round(sum(costs) / len(costs), 4) if costs else None,
                "cost_ci95": bootstrap_ci(costs) if len(costs) >= 5 else None,
                "avg_escape": round(sum(escapes) / len(escapes), 2) if escapes else None,
                "escape_ci95": bootstrap_ci(escapes) if len(escapes) >= 5 else None,
                "avg_correctness": round(sum(correctness) / len(correctness), 2)
                if correctness
                else None,
                "correctness_ci95": bootstrap_ci(correctness) if len(correctness) >= 5 else None,
                "avg_thinking_ratio": round(sum(thinking) / len(thinking), 3) if thinking else None,
                "avg_loc": round(sum(pb["locs"]) / n),
                "avg_tokens": round(sum(pb["tokens"]) / n),
                # cost → five-field captured-cost tuple + optional-field coverage (m2)
                **cost_coverage(pb["costs"], n_total=n),
                "correctness_coverage": _coverage_dict(correctness, n_total=n, round_value=2),
                "thinking_ratio_coverage": _coverage_dict(thinking, n_total=n, round_value=3),
                "escape_coverage": _coverage_dict(escapes, n_total=n, round_value=2),
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
            # ── m4: the tombstone population split by reason — a retraction (no usable
            # ── measurement payload) is NOT contamination, so the two categories are
            # ── published separately, never merged into a single "contaminated, excluded".
            "contaminated_tombstones": corpus.contaminated_tombstones,
            "no_measurement_tombstones": corpus.no_measurement_tombstones,
            "tombstones_total": corpus.tombstoned_count,
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
                "contaminated_tombstones": "M",
                "no_measurement_tombstones": "M",
                "tombstones_total": "M",
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
            # The measured-spend figure is STORY-CORPUS scoped: it is the total measured cost
            # of the canonical resolved story corpus, not "all money ever spent in this repo".
            # Workflow-run ledger spend is NOT published (the run ledgers under
            # experiments/results/workflows/ are gitignored, local-transient), so the public
            # figure must never be read as the whole-repo total. cap_stabilization_release p5.
            "measured_spend_scope": "story-corpus",
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
                "measured_spend_scope": "P",
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
        "verdicts": _load_verdicts(),
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
