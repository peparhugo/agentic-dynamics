#!/usr/bin/env python3
"""Confidence-cascade study, Phase A — retrospective analysis (machine artifact producer).

WHAT THIS DOES
--------------
Computes every number the retrospective quotes, from the live data root, and writes
`experiments/results/confidence_cascade/retrospective.json` (the machine artifact; the
committed prose is docs/reviews/confidence_cascade_retrospective.md).

TRACKING (2026-09-22)
---------------------
The script was BORN under the gitignored `experiments/results/` path, so the prose cited a
command no clean checkout could run (register L28). It now lives here — tracked, CLI-wired
(`agentic-dynamics analyze confidence-cascade-retrospective`) — and the prose points at this
path. Run it from the repo root; `--data-root` selects a mounted data root.

WHY A SCRIPT AND NOT INLINE PROSE
---------------------------------
Every claim in `docs/reviews/confidence_cascade_retrospective.md` must be reproducible
from a recorded command. Rather than paste six long heredocs into the doc, the doc
records this one command; the doc ALSO inlines the per-question snippets (Q1..Q6) so a
reader with only the commit can re-derive the numbers without this file.

DATA ROOTS (two roots; see notes/world_model.md §1)
---------------------------------------------------
  /repo : the git checkout (tracked registry manifest, fixture, parquet)
  /app  : the live data root (the registry index + the kb artifacts + the run ledgers)
`/repo/experiments/results/` is gitignored and EMPTY of the live payloads, which is why
the script hard-defaults its root to `/app` but accepts `--root` for a re-run elsewhere.

JOIN CONTRACT (the one non-obvious step)
----------------------------------------
The registry index carries identities + content hashes only — NEVER values. A row's
`knowledge_id` names a durable artifact `<root>/experiments/results/kb/<knowledge_id>.json`
whose `text` field is a JSON STRING; the value is `json.loads(artifact["text"])["value"]`.
An attempt key is parsed out of
`source_uri == fact://attempt/<cell>:<phase>:<runhash>/<predicate>`.

NULL-NOT-ZERO
-------------
An attempt whose artifact is absent/unparseable is ABSENT — reported as a coverage gap,
never imputed as 0.0 confidence and never as a failed outcome.

USAGE
-----
  python3 /app/experiments/results/confidence_cascade/retrospective_analysis.py
  python3 .../retrospective_analysis.py --root /app --out /app/experiments/results/confidence_cascade/retrospective.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from glob import glob

# --------------------------------------------------------------------------------------
# Predicates the study requires. The attempt-scoped facts are emitted by the
# `attempt_facts/v1` reducer (src/agentic_dynamics/control/reducers/attempt_facts.py) as
# source_type == "fact"; `phase_test_verified` is the INDEPENDENT (test_runner) outcome.
# --------------------------------------------------------------------------------------
ATTEMPT_PREDICATES = [
    "attempt_confidence",
    "phase_status",
    "attempt_model",
    "attempt_cost_usd",
    "phase_test_verified",
    "attempt_tokens_in",
    "attempt_tokens_out",
    "phase_commit",
]

# Confidence bins for the calibration table. Edges chosen to isolate the two point masses
# (0.0 and 1.0) that the inventory observed, and to keep the mid-range readable.
BIN_EDGES = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
CANDIDATE_THETAS = [0.3, 0.5, 0.7]

# The five candidate threshold arms the pre-registration considers, plus two degenerate
# always-* arms. Recorded here so the doc's power section cites one source.
CASCADE_THETAS = [0.3, 0.4, 0.5, 0.7, 0.9]


def _line_count(path: str) -> int:
    """The registry's line count, context-managed (the tracked linter requires it)."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def sha256_file(path: str) -> str:
    """Streamed sha256 — the registry is ~35 MB, so never load it whole for hashing."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_attempt_uri(uri: str):
    """Parse `fact://attempt/<key>/<predicate>` -> (attempt_key, predicate) or (None, None)."""
    if not uri.startswith("fact://attempt/"):
        return None, None
    tail = uri[len("fact://attempt/") :]
    if "/" not in tail:
        return None, None
    key, pred = tail.rsplit("/", 1)
    return key, pred


def load_kb_value(root: str, knowledge_id: str):
    """Resolve a fact artifact's VALUE. Returns (value, parse_ok). Absent -> (None, False)."""
    path = os.path.join(root, "experiments", "results", "kb", f"{knowledge_id}.json")
    try:
        with open(path) as fh:
            artifact = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None, False
    # The artifact's `text` is a JSON STRING; tolerate a already-decoded dict too.
    text = artifact.get("text")
    if isinstance(text, dict):
        payload = text
    elif isinstance(text, str):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None, False
    else:
        return None, False
    if not isinstance(payload, dict) or "value" not in payload:
        return None, False
    return payload["value"], True


def to_float(value):
    """Best-effort float; None when absent/unparseable (never 0.0)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_bool(value):
    """Best-effort bool; None when absent/unparseable (never False)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "1", "yes"):
            return True
        if low in ("false", "0", "no"):
            return False
    return None


# ======================================================================================
# Q1 — attempt coverage: which predicates land on which attempts, and how they co-occur
# ======================================================================================
def q1_coverage(registry_path: str):
    """Build attempt_key -> {predicate: knowledge_id} from current attempt facts.

    Returns the decoder counters and the per-attempt predicate map. Only rows whose
    `source_type` is `fact`, whose `lifecycle_state` is `current`, and whose `source_uri`
    is an `fact://attempt/...` URI participate.
    """
    by_attempt = defaultdict(dict)
    source_type_counts = Counter()
    total_rows = 0
    with open(registry_path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            total_rows += 1
            source_type_counts[row.get("source_type")] += 1
            if row.get("source_type") != "fact" or row.get("lifecycle_state") != "current":
                continue
            key, pred = parse_attempt_uri(str(row.get("source_uri") or ""))
            if key is None:
                continue
            by_attempt[key][pred] = row["knowledge_id"]

    def coverage(*preds):
        """How many distinct attempts carry ALL of `preds`."""
        wanted = set(preds)
        return sum(1 for v in by_attempt.values() if wanted <= set(v))

    coverage_table = {
        "distinct_attempts": len(by_attempt),
        "attempt_confidence": coverage("attempt_confidence"),
        "phase_status": coverage("phase_status"),
        "attempt_model": coverage("attempt_model"),
        "attempt_cost_usd": coverage("attempt_cost_usd"),
        "phase_test_verified": coverage("phase_test_verified"),
        "confidence+status": coverage("attempt_confidence", "phase_status"),
        "confidence+cost+model+status": coverage(
            "attempt_confidence", "attempt_cost_usd", "attempt_model", "phase_status"
        ),
        "tokens_in+out+cost": coverage(
            "attempt_tokens_in", "attempt_tokens_out", "attempt_cost_usd"
        ),
        "phase_test_verified+confidence": coverage("phase_test_verified", "attempt_confidence"),
    }
    return by_attempt, dict(source_type_counts), total_rows, coverage_table


# ======================================================================================
# Q2 — calibration: resolve values, bin confidence, P(ok | bin), and stratify
# ======================================================================================
def q2_calibration(root: str, by_attempt: dict):
    """Join each attempt fact to its kb value, then compute the calibration sample.

    Returns:
      confidence_values: {attempt_key: float}
      status_values:     {attempt_key: str}   ("ok" | "failed" | "awaiting")
      paired:            {attempt_key: (confidence, status)}  -- the calibration sample
      model_values:      {attempt_key: str}
      cost_values:       {attempt_key: float}
      verified_values:   {attempt_key: bool}
      observed_at:       {attempt_key: iso_date-string}
      missing_artifacts: Counter(predicate -> count)
    """
    confidence_values, status_values, model_values = {}, {}, {}
    cost_values, verified_values, token_rows = {}, {}, {}
    observed_at = {}
    missing = Counter()

    for key, preds in by_attempt.items():
        for pred, kid in preds.items():
            if pred not in ATTEMPT_PREDICATES:
                continue
            value, ok = load_kb_value(root, kid)
            if not ok:
                missing[pred] += 1
                continue
            if pred == "attempt_confidence":
                f = to_float(value)
                if f is not None:
                    confidence_values[key] = f
            elif pred == "phase_status":
                status_values[key] = str(value)
            elif pred == "attempt_model":
                model_values[key] = str(value)
            elif pred == "attempt_cost_usd":
                f = to_float(value)
                if f is not None:
                    cost_values[key] = f
            elif pred == "phase_test_verified":
                b = to_bool(value)
                if b is not None:
                    verified_values[key] = b
            elif pred in ("attempt_tokens_in", "attempt_tokens_out"):
                token_rows.setdefault(key, {})[pred] = to_float(value)

    # Attempt key encodes the run hash; observed_at comes from the registry row for the
    # confidence fact specifically. Re-read only those rows (cheap, keyed by knowledge_id).
    conf_kids = {
        preds["attempt_confidence"]: key
        for key, preds in by_attempt.items()
        if "attempt_confidence" in preds
    }
    with open(os.path.join(root, "experiments", "results", "registry_index.jsonl")) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            kid = row.get("knowledge_id")
            if kid in conf_kids:
                observed_at[conf_kids[kid]] = str(row.get("observed_at") or "")

    paired = {
        k: (confidence_values[k], status_values[k]) for k in confidence_values if k in status_values
    }
    return (
        confidence_values,
        status_values,
        paired,
        model_values,
        cost_values,
        verified_values,
        observed_at,
        dict(missing),
    )


def bin_pairs(pairs, positive):
    """Generic left-open/right-closed binning of (confidence, outcome) pairs.

    `pairs` is an iterable of (confidence: float, outcome). An outcome counts as a success
    when `outcome == positive` — pass "ok" for a phase_status, or True for a boolean
    first_pass / accepted. Bins: the singleton [0.0], then (0.0,0.2], (0.2,0.3], ...,
    (0.8,0.9], (0.9,1.0]. The 0.0 point mass gets its own row because it is the only
    candidate separating cell; the 1.0 point mass sits inside (0.9,1.0].
    """
    pairs = list(pairs)
    table = []
    edges = BIN_EDGES
    zero = [(c, o) for c, o in pairs if c == 0.0]
    if zero:
        n = len(zero)
        ok = sum(1 for _, o in zero if o == positive)
        table.append(
            {
                "bin": "[0.0]",
                "lo": 0.0,
                "hi": 0.0,
                "n": n,
                "ok": ok,
                "p_ok": (ok / n) if n else None,
            }
        )
    for i in range(1, len(edges)):
        lo, hi = edges[i - 1], edges[i]
        rows = [(c, o) for c, o in pairs if c > lo and c <= hi]
        n = len(rows)
        ok = sum(1 for _, o in rows if o == positive)
        table.append(
            {
                "bin": f"({lo},{hi}]",
                "lo": lo,
                "hi": hi,
                "n": n,
                "ok": ok,
                "p_ok": (ok / n) if n else None,
            }
        )
    return table


def confidence_bins(paired: dict):
    """P(status == 'ok' | confidence bin) over the registry calibration sample."""
    return bin_pairs(((c, s) for c, s in paired.values()), positive="ok")


def discriminant(paired: dict):
    """AUC + Spearman rho of confidence as a predictor of the completion outcome.

    Reported with AND without the exactly-0.0 cell, because that cell is (a) the only one
    that separates and (b) partly definitional (confidence is 0.0 on session error, which
    also makes phase_status "failed" — opencode.py:113). The "excl. 0.0" number is the
    honest measure of whether confidence carries ordinal information beyond the error flag.
    """
    import numpy as np
    from scipy import stats  # type: ignore

    def _auc(conf, y):
        """Rank-based AUC (Mann-Whitney U / (n_pos * n_neg)); 0.5 = no discrimination."""
        n_pos = int(y.sum())
        n_neg = len(y) - n_pos
        if n_pos == 0 or n_neg == 0:
            return None
        order = np.argsort(conf, kind="mergesort")
        ranks = np.empty(len(conf), dtype=float)
        ranks[order] = np.arange(1, len(conf) + 1)
        # average ranks for ties
        _, inv, counts = np.unique(conf, return_inverse=True, return_counts=True)
        tie_rank = {}
        for idx, cnt in zip(inv, counts, strict=False):
            if cnt > 1:
                mask = inv == idx
                tie_rank[idx] = ranks[mask].mean()
                ranks[mask] = tie_rank[idx]
        return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))

    out = {}
    full = [(c, 1 if s == "ok" else 0) for c, s in paired.values()]
    nonzero = [(c, 1 if s == "ok" else 0) for c, s in paired.values() if c != 0.0]
    for label, rows in (("including_0.0", full), ("excluding_0.0", nonzero)):
        if not rows:
            out[label] = None
            continue
        conf = np.array([c for c, _ in rows], float)
        y = np.array([o for _, o in rows], int)
        rho = None
        if len(set(conf.tolist())) > 1 and len(set(y.tolist())) > 1:
            rho = float(stats.spearmanr(conf, y).statistic)
        out[label] = {"n": len(rows), "auc": _auc(conf, y), "spearman_rho": rho}
    return out


def missingness_by_outcome(status_values: dict, confidence_values: dict):
    """Is the confidence signal missing at random, or differentially by outcome?

    This is the selection-bias check that decides whether the calibration subsample is
    even representative. If confidence is present far less often on failed phases than on
    completed ones, then every calibration number computed on the paired subsample is
    conditional on a success-correlated selection, and a policy trained on it inherits the
    bias. Reported as rates per outcome class plus the risk difference and risk ratio.
    """
    out = {}
    for label, wanted in (("ok", "ok"), ("failed", "failed"), ("awaiting", "awaiting")):
        keys = [k for k, s in status_values.items() if s == wanted]
        with_conf = [k for k in keys if k in confidence_values]
        out[label] = {
            "n_total": len(keys),
            "n_with_confidence": len(with_conf),
            "confidence_present_rate": (len(with_conf) / len(keys)) if keys else None,
        }
    ok = out["ok"]["confidence_present_rate"]
    failed = out["failed"]["confidence_present_rate"]
    out["risk_difference_ok_minus_failed"] = (
        (ok - failed) if (ok is not None and failed is not None) else None
    )
    out["risk_ratio_ok_over_failed"] = (ok / failed) if (ok and failed) else None
    return out


def stratum_calibration(paired: dict, labels: dict, min_n: int = 5):
    """P(ok | confidence bin) per stratum, only reporting bins with n >= min_n.

    Strata with fewer than `min_n` paired attempts in total are returned as counts in
    `strata_below_min` rather than silently pooled.
    """
    out = {}
    below = {}
    for name in sorted(set(labels.get(k) for k in paired)):
        if name is None:
            continue
        sub = {k: v for k, v in paired.items() if labels.get(k) == name}
        if len(sub) < min_n:
            below[name] = len(sub)
            continue
        out[name] = {
            "n": len(sub),
            "bins": [b for b in confidence_bins(sub) if b["n"] >= min_n],
        }
    return out, below


# ======================================================================================
# Q2b — independent corroboration: the runner's typed AttemptRecords in the run ledgers
# ======================================================================================
def q2_ledger_calibration(workflows_glob: str):
    """Calibrate the same confidence signal from the workflow run ledgers.

    A genuinely different data path from the registry fact layer: the ledgers are the
    runner's typed `AttemptRecord`s. Crucially they carry `first_pass` and `accepted` —
    two of the quality metrics the pre-registration wants and the ONLY place those are
    measured — plus `test_executed_success` (the independent outcome) and `cost_usd`.
    """
    rows = []
    for path in sorted(glob(workflows_glob, recursive=True)):
        try:
            with open(path) as fh:
                ledger = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        for a in ledger.get("attempts") or []:
            if isinstance(a, dict):
                a = dict(a)
                a["_ledger"] = path
                rows.append(a)

    def nonnull(k):
        return sum(1 for r in rows if r.get(k) is not None)

    # Confidence-present attempts with each outcome/quality predicate.
    conf_rows = [r for r in rows if to_float(r.get("confidence")) is not None]
    status_pairs = [
        (to_float(r["confidence"]), r.get("status")) for r in conf_rows if r.get("status")
    ]
    first_pass_pairs = [
        (to_float(r["confidence"]), bool(r.get("first_pass")))
        for r in conf_rows
        if r.get("first_pass") is not None
    ]
    accepted_pairs = [
        (to_float(r["confidence"]), bool(r.get("accepted")))
        for r in conf_rows
        if r.get("accepted") is not None
    ]

    costs = [to_float(r["cost_usd"]) for r in conf_rows if to_float(r.get("cost_usd")) is not None]
    n = len(conf_rows)

    # The ALL-attempts rates are the honest population baseline for power (the confidence
    # subset is success-biased — see the registry missingness analysis); both are reported
    # with explicit denominators so neither can be quoted without its base.
    def _rate(pred):
        vals = [bool(r.get(pred)) for r in rows if r.get(pred) is not None]
        return {
            "rate": (sum(1 for v in vals if v) / len(vals)) if vals else None,
            "n_success": sum(1 for v in vals if v),
            "n": len(vals),
        }

    first_pass_all = _rate("first_pass")
    accepted_all = _rate("accepted")
    trigger = {}
    for theta in CASCADE_THETAS:
        below = sum(1 for c, _ in status_pairs if c < theta)
        trigger[str(theta)] = {
            "n_below_theta": below,
            "rate_below_theta": (below / n) if n else None,
        }
    return {
        "n_attempt_rows": len(rows),
        "coverage": {
            "confidence": nonnull("confidence"),
            "first_pass": nonnull("first_pass"),
            "accepted": nonnull("accepted"),
            "status": nonnull("status"),
            "cost_usd": nonnull("cost_usd"),
            "test_executed_success": nonnull("test_executed_success"),
            "perturbation_strength": nonnull("perturbation_strength"),
            "escalation_from": nonnull("escalation_from"),
            "escalation_to": nonnull("escalation_to"),
            "parent_attempt_id": nonnull("parent_attempt_id"),
        },
        "status_breakdown": dict(Counter(r.get("status") for r in rows)),
        "model_breakdown": dict(Counter(r.get("model") for r in rows)),
        "calibration_status_ok": bin_pairs(status_pairs, positive="ok"),
        "calibration_first_pass": bin_pairs(first_pass_pairs, positive=True),
        "calibration_accepted": bin_pairs(accepted_pairs, positive=True),
        "first_pass_all_attempts": first_pass_all,
        "accepted_all_attempts": accepted_all,
        "first_pass_rate_confidence_subset": (
            (sum(1 for _, o in first_pass_pairs if o) / len(first_pass_pairs))
            if first_pass_pairs
            else None
        ),
        "accepted_rate_confidence_subset": (
            (sum(1 for _, o in accepted_pairs if o) / len(accepted_pairs))
            if accepted_pairs
            else None
        ),
        "trigger_rates": trigger,
        "cost_shape": {
            "n_with_cost": len(costs),
            "mean": statistics.fmean(costs) if costs else None,
            "median": statistics.median(costs) if costs else None,
            "p90": _percentile(costs, 0.90) if costs else None,
            "max": max(costs) if costs else None,
        },
    }


# ======================================================================================
# Q2c — do the kb artifacts' STRUCTURED fields carry the signal at scale?
# ======================================================================================
def q2c_kb_structured_fields(root: str):
    """Count non-null top-level `confidence` / `test_executed_success` /
    `perturbation_strength` on the kb artifacts.

    Fact artifacts carry their value inside `text` (the `attempt_confidence` predicate);
    the TOP-LEVEL fields are populated only by the story/session producers. This measures
    whether that second channel could substitute for the fact layer — it cannot (n is
    tiny), and saying so prevents a future reader from assuming the field is at scale.
    """
    counts = {k: 0 for k in ("confidence", "test_executed_success", "perturbation_strength")}
    present = {k: 0 for k in counts}
    total = 0
    for path in glob(os.path.join(root, "experiments", "results", "kb", "*.json")):
        total += 1
        try:
            with open(path) as fh:
                artifact = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        for key in counts:
            if key in artifact:
                present[key] += 1
                if artifact.get(key) is not None:
                    counts[key] += 1
    return {"n_artifacts": total, "present": present, "non_null": counts}


# ======================================================================================
# Q3 — escalation history: is there ANY realised escalation to estimate ROI from?
# ======================================================================================
def q3_escalation(workflows_glob: str):
    """Scan run ledgers for lineage fields and retries.

    `escalation_from` / `escalation_to` / `parent_attempt_id` non-empty => a REAL
    escalation. `attempt_number > 1` => a retry (same model, not an escalation).
    """
    n_ledgers = 0
    n_phase_rows = 0
    n_attempt_rows = 0
    esc_from = esc_to = parent = 0
    retries = 0
    with_confidence = 0
    for path in sorted(glob(workflows_glob, recursive=True)):
        try:
            with open(path) as fh:
                ledger = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        n_ledgers += 1
        attempts = ledger.get("attempts") or []
        if not isinstance(attempts, list):
            attempts = []
        n_attempt_rows += len(attempts)
        for a in attempts:
            if not isinstance(a, dict):
                continue
            if a.get("escalation_from"):
                esc_from += 1
            if a.get("escalation_to"):
                esc_to += 1
            if a.get("parent_attempt_id"):
                parent += 1
            an = a.get("attempt_number")
            if isinstance(an, (int, float)) and an > 1:
                retries += 1
            if a.get("confidence") is not None:
                with_confidence += 1
        # phase rows live under `phases` in some ledger shapes
        for ph in ledger.get("phases") or []:
            if isinstance(ph, dict):
                n_phase_rows += 1
    return {
        "n_ledgers": n_ledgers,
        "n_phase_rows": n_phase_rows,
        "n_attempt_rows": n_attempt_rows,
        "attempts_with_confidence": with_confidence,
        "escalation_from": esc_from,
        "escalation_to": esc_to,
        "parent_attempt_id": parent,
        "retries_attempt_number_gt_1": retries,
    }


# ======================================================================================
# Q4 — the prior retrospective baseline (cite, do not recompute a competing number)
# ======================================================================================
def q4_prior_baseline(path: str):
    """Read the prior cascade retrospective JSON and surface the baseline + triggers."""
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"available": False}
    base = data.get("baseline", {})
    return {
        "available": True,
        "schema": data.get("schema") or data.get("schema_version"),
        "n_runs": data.get("n_runs"),
        "n_phases": data.get("n_phases"),
        "coverage_precheck": data.get("coverage_precheck"),
        "baseline_cost_per_verified_outcome": base.get("cost_per_verified_outcome"),
        "null_testable": data.get("null_hypothesis") or data.get("null_testable"),
    }


# ======================================================================================
# Q5 — parquet exposure (the negative control): can the parquet answer the question?
# ======================================================================================
def q5_parquet_columns(data_roots):
    """List parquet columns to prove the calibration fields are absent.

    The parquet is a TRACKED artifact living in the git checkout (`/repo`), not the live
    data root — so every candidate root is searched and the path actually read is recorded.
    Uses pyarrow when available (read-only), falling back to duckdb. Never runs
    `sync_data.py` itself (its positional `check` verb silently syncs; use `--check`).
    """
    studied = {
        "confidence",
        "perturbation_strength",
        "test_executed_success",
        "first_pass",
        "accepted",
    }
    out = {}
    for name in ("sessions", "stories"):
        found = None
        for root in data_roots:
            candidate = os.path.join(root, "experiments", "data", f"{name}.parquet")
            if os.path.exists(candidate):
                found = candidate
                break
        if found is None:
            out[name] = {"available": False, "searched_roots": list(data_roots)}
            continue
        cols = None
        try:
            import pyarrow.parquet as pq  # type: ignore

            cols = list(pq.read_schema(found).names)
        except Exception:
            try:
                import duckdb  # type: ignore

                cols = [
                    r[0]
                    for r in duckdb.sql(
                        f"describe select * from read_parquet('{found}')"
                    ).fetchall()
                ]
            except Exception:
                cols = None
        out[name] = {
            "available": cols is not None,
            "path": found,
            "columns": cols,
            "studied_fields_present": sorted(set(cols or []) & studied),
        }
    all_present = set()
    for v in out.values():
        if v.get("columns"):
            all_present |= set(v["columns"]) & studied
    out["studied_fields_present"] = sorted(all_present)
    return out


# ======================================================================================
# Q6 — the design's power inputs: separation, trigger rates, cost shape
# ======================================================================================
def q6_power_inputs(paired: dict, cost_values: dict):
    """Everything the pre-registration's power section is allowed to derive from.

    - separation: P(ok) spread across bins that carry n >= 5 (the only ones that could
      support a threshold estimate);
    - trigger fractions: fraction of the paired sample below each candidate theta;
    - cost shape: mean/median/p90 of attempt_cost_usd on attempts that carry both cost
      and confidence (the only ones a cascade arm could re-price).
    """
    bins = confidence_bins(paired)
    mass_bins = [b for b in bins if b["n"] >= 5]
    # (a) all mass bins, including the definitional 0.0 cell;
    # (b) strictly-positive bins only — the honest test of ordinal content beyond 0.0.
    pos_mass_bins = [b for b in mass_bins if b["lo"] > 0.0]

    def _spread(bs):
        ps = [b["p_ok"] for b in bs if b["p_ok"] is not None]
        return {
            "p_ok_min": min(ps) if ps else None,
            "p_ok_max": max(ps) if ps else None,
            "p_ok_spread": (max(ps) - min(ps)) if ps else None,
        }

    separation = {
        "bins_with_n_ge_5": len(mass_bins),
        **_spread(mass_bins),
        "non_monotone_where_mass": _non_monotone(mass_bins),
        "positive_bins_with_n_ge_5": len(pos_mass_bins),
        **_spread(pos_mass_bins),
        "non_monotone_above_0.0": _non_monotone(pos_mass_bins),
    }
    n = len(paired)
    trigger = {}
    for theta in CASCADE_THETAS:
        below = sum(1 for c, _ in paired.values() if c < theta)
        at_or_above = n - below
        trigger[str(theta)] = {
            "n_below_theta": below,
            "rate_below_theta": (below / n) if n else None,
            "n_at_or_above_theta": at_or_above,
        }
    # Point masses (the reason a threshold has little room to act).
    counts = Counter(c for c, _ in paired.values())
    paired_cost_keys = [k for k in paired if k in cost_values]
    costs = [cost_values[k] for k in paired_cost_keys]
    cost_shape = {
        "n_with_cost": len(costs),
        "mean": statistics.fmean(costs) if costs else None,
        "median": statistics.median(costs) if costs else None,
        "p90": _percentile(costs, 0.90) if costs else None,
        "max": max(costs) if costs else None,
    }
    return {
        "separation": separation,
        "trigger_rates": trigger,
        "confidence_point_masses": {
            "exactly_1.0": counts.get(1.0, 0),
            "exactly_0.0": counts.get(0.0, 0),
            "fraction_exactly_1.0": (counts.get(1.0, 0) / n) if n else None,
            "distinct_values": len(counts),
        },
        "cost_shape": cost_shape,
    }


def _non_monotone(bins):
    """True iff P(ok), ordered by confidence, ever DECREASES across bins with n >= 5.

    A monotone-non-decreasing signal is what a threshold policy needs: acting on "low
    confidence" is only sound if low confidence really does mean lower P(ok). Any drop
    refutes that, even one that is later recovered.
    """
    seq = [(b["lo"], b["p_ok"]) for b in bins if b["p_ok"] is not None and b["n"] >= 5]
    seq.sort()
    return any(
        b < a - 1e-9 for (_, a), (_, b) in zip(seq, seq[1:], strict=False)
    )  # a decrease => non-monotone


def _percentile(values, q):
    """Nearest-rank percentile; deterministic and dependency-free."""
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(math.ceil(q * len(ordered))) - 1))
    return ordered[idx]


# ======================================================================================
# Main
# ======================================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/app", help="live data root (default /app)")
    ap.add_argument("--repo-root", default="/repo", help="git checkout (parquet lives here)")
    ap.add_argument("--out", default=None, help="output JSON path")
    args = ap.parse_args()
    root = args.root
    repo_root = args.repo_root
    registry_path = os.path.join(root, "experiments", "results", "registry_index.jsonl")
    out_path = args.out or os.path.join(
        root, "experiments", "results", "confidence_cascade", "retrospective.json"
    )

    # --- pin the snapshot -------------------------------------------------------------
    snapshot = {
        "registry_path": registry_path,
        "registry_sha256": sha256_file(registry_path),
        "registry_lines": _line_count(registry_path),
        "kb_artifact_count": len(
            glob(os.path.join(root, "experiments", "results", "kb", "*.json"))
        ),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repo_root": repo_root,
        "workflows_glob": os.path.join(root, "experiments", "results", "workflows", "**", "*.json"),
    }
    print(
        f"[pin] sha256={snapshot['registry_sha256']} lines={snapshot['registry_lines']} "
        f"kb={snapshot['kb_artifact_count']}"
    )

    # --- Q1 ---------------------------------------------------------------------------
    by_attempt, source_type_counts, total_rows, coverage_table = q1_coverage(registry_path)
    assert coverage_table["distinct_attempts"] == sum(1 for _ in by_attempt), "attempt map drift"
    print(
        f"[Q1] attempts={coverage_table['distinct_attempts']} "
        f"confidence={coverage_table['attempt_confidence']} "
        f"paired={coverage_table['confidence+status']} "
        f"verified={coverage_table['phase_test_verified']} "
        f"verified+conf={coverage_table['phase_test_verified+confidence']}"
    )

    # --- Q2 ---------------------------------------------------------------------------
    (
        confidence_values,
        status_values,
        paired,
        model_values,
        cost_values,
        verified_values,
        observed_at,
        missing,
    ) = q2_calibration(root, by_attempt)
    bins = confidence_bins(paired)
    strata_model, below_model = stratum_calibration(paired, model_values)
    disc = discriminant(paired)
    miss = missingness_by_outcome(status_values, confidence_values)
    print(
        f"[Q2] confidence-present rate: ok={miss['ok']['confidence_present_rate']} "
        f"failed={miss['failed']['confidence_present_rate']} "
        f"rd={miss['risk_difference_ok_minus_failed']} "
        f"rr={miss['risk_ratio_ok_over_failed']}"
    )
    print(
        f"[Q2] conf={len(confidence_values)} status={len(status_values)} "
        f"paired={len(paired)} verified={len(verified_values)} missing={missing}"
    )
    print(
        f"[Q2] AUC incl0.0={disc['including_0.0']['auc']:.4f} "
        f"excl0.0={disc['excluding_0.0']['auc']:.4f} "
        f"rho_excl0.0={disc['excluding_0.0']['spearman_rho']}"
    )

    # --- Q2b --------------------------------------------------------------------------
    ledger = q2_ledger_calibration(snapshot["workflows_glob"])
    kb_fields = q2c_kb_structured_fields(root)
    print(
        f"[Q2b] ledger attempts={ledger['n_attempt_rows']} "
        f"conf={ledger['coverage']['confidence']} first_pass={ledger['coverage']['first_pass']} "
        f"accepted={ledger['coverage']['accepted']} "
        f"test_exec={ledger['coverage']['test_executed_success']}"
    )
    print(f"[Q2c] kb structured non-null={kb_fields['non_null']}")

    # --- Q3 ---------------------------------------------------------------------------
    esc = q3_escalation(snapshot["workflows_glob"])
    print(
        f"[Q3] ledgers={esc['n_ledgers']} attempts={esc['n_attempt_rows']} "
        f"esc_from={esc['escalation_from']} esc_to={esc['escalation_to']} "
        f"parent={esc['parent_attempt_id']} retries={esc['retries_attempt_number_gt_1']}"
    )

    # --- Q4 ---------------------------------------------------------------------------
    prior = q4_prior_baseline(
        os.path.join(root, "experiments", "results", "cap_cascade_retrospective.json")
    )
    print(f"[Q4] prior baseline cpvo={prior.get('baseline_cost_per_verified_outcome')}")

    # --- Q5 ---------------------------------------------------------------------------
    parquet = q5_parquet_columns([root, repo_root])
    print(f"[Q5] studied fields present in parquet: {parquet['studied_fields_present']}")

    # --- Q6 ---------------------------------------------------------------------------
    power = q6_power_inputs(paired, cost_values)
    print(
        f"[Q6] spread={power['separation']['p_ok_spread']} "
        f"non_monotone={power['separation']['non_monotone_where_mass']} "
        f"frac_1.0={power['confidence_point_masses']['fraction_exactly_1.0']}"
    )

    # --- raw per-attempt rows (small; lets an adversary recompute any aggregate) --------
    per_attempt = [
        {
            "attempt_key": k,
            "confidence": c,
            "status": s,
            "model": model_values.get(k),
            "cost_usd": cost_values.get(k),
            "observed_at": observed_at.get(k),
            "test_verified": verified_values.get(k),
        }
        for k, (c, s) in sorted(paired.items())
    ]

    result = {
        "schema": "confidence_cascade_retrospective/v1",
        "spec": "confidence_cascade_study@0.1",
        "phase": "execute",
        "snapshot": snapshot,
        "source_type_counts": source_type_counts,
        "total_registry_rows": total_rows,
        "q1_coverage": coverage_table,
        "q2_resolved": {
            "n_confidence": len(confidence_values),
            "n_status": len(status_values),
            "n_paired": len(paired),
            "n_test_verified": len(verified_values),
            "n_test_verified_with_confidence": sum(
                1 for k in verified_values if k in confidence_values
            ),
            "status_breakdown": dict(Counter(status_values.values())),
            "missing_artifacts": missing,
            "calibration_bins": bins,
            "discriminant": disc,
            "missingness_by_outcome": miss,
            "strata_by_model": strata_model,
            "model_strata_below_min": below_model,
        },
        "q2b_ledger": ledger,
        "q2c_kb_structured_fields": kb_fields,
        "q3_escalation": esc,
        "q4_prior_baseline": prior,
        "q5_parquet": parquet,
        "q6_power": power,
        "per_attempt": per_attempt,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    print(f"[out] wrote {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    main()
