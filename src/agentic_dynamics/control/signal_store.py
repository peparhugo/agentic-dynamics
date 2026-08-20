"""Signal store: measured per-model signals aggregated from ``_results_summary.json``.

Implements ``docs/routing_next_steps.md`` item 1. The run path has always *accepted* a
``dict[str, ModelSignals]`` (``run_workflow(signals=…)``) and ``step_routing.build_signal_store``
could already build one from ``_results_summary.json`` rows — but nothing in the run path
actually called it, so per-step routing started cold and fell back to ``prev_model`` /
``pool[0]``. This module is the missing link: it loads the measured ``entries``, derives the
two signals that are *not* stored directly, normalizes the model-id mismatch between the
current ``model_pool`` ids and the legacy result ids, and aggregates every dimension through
the NaN/None-aware mean.

Design decisions, per ``docs/routing_next_steps.md`` §1:

- ``load_results`` reads the ``entries`` key directly. It does **not** re-derive from
  ``by_model``, whose keys use the legacy model granularity and would bypass the alias layer.
- ``derive_cache_hit_rate`` / ``derive_constraint_score`` are pure, per-entry functions so the
  derivation is testable in isolation, and they return ``None`` (never ``0.0``) on a zero
  denominator or missing fields — an unmeasured dimension is never fabricated as zero.
- ``MODEL_ALIASES`` maps a *pool* id to the *legacy result* id(s) that feed it (e.g.
  ``openai/gpt-5.6-sol → openai/gpt-5.6``). ``normalize_model_id`` canonicalizes any id (pool
  or legacy) to its pool form, so the store's keys line up with ``workflow.params.model_pool``
  — exactly the ids ``route_step`` looks up. Ids that already match on both sides pass through.
- ``build_signal_store`` applies the derivations + alias normalization *before* grouping, then
  aggregates every dimension through the NaN/None-aware ``_mean_present`` (including
  ``correctness``/``cost`` — ``docs/routing_next_steps.md`` item 5.3), so a sparse entry cannot
  bias a mean by contributing a spurious 0.0.

The load-bearing rule is respected: ``confidence`` and ``edge_case_coverage`` are never read
here. ``edge_case_coverage`` remains ``None`` on every ``ModelSignals`` until it is
instrumented (item 3); the store simply does not touch it.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from agentic_dynamics.control.step_routing import ModelSignals

# Default results path, anchored to the repo root so ``load_results()`` works regardless of
# the caller's working directory (``src/instrument/signal_store.py`` → repo root).
_DEFAULT_RESULTS_PATH: Path = Path(__file__).resolve().parents[3] / "experiments" / "results" / "_results_summary.json"

# ── Model-id aliasing ───────────────────────────────────────────
#
# The spec's ``model_pool`` uses the current ids (openai/gpt-5.6-sol|luna|terra, …), but the
# perturbation corpus in ``_results_summary.json`` recorded the *consolidated* id
# ``openai/gpt-5.6`` before the sol/luna/terra split. Each key is a pool id; each value lists
# the legacy result id(s) that should be folded into it. Ids that already appear identically in
# both the pool and the results (e.g. ``deepseek/deepseek-v4-pro``, ``anthropic/claude-fable-5``)
# need no entry — ``normalize_model_id`` passes them through unchanged.
MODEL_ALIASES: dict[str, list[str]] = {
    "openai/gpt-5.6-sol": ["openai/gpt-5.6"],
}


def load_results(path: Path = _DEFAULT_RESULTS_PATH) -> list[dict[str, Any]]:
    """Read the ``entries`` list from a ``_results_summary.json``-shaped file.

    Only ``entries`` is consumed; ``by_model`` is deliberately ignored because its keys use the
    legacy model granularity and would bypass the alias layer in :func:`build_signal_store`.
    """
    with path.open() as fh:
        doc = json.load(fh)
    entries = doc.get("entries", [])
    return [e for e in entries if isinstance(e, dict)]


def _as_float(value: Any) -> float | None:
    """Coerce ``value`` to a finite float, or ``None`` when missing/NaN/non-numeric."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN check (float('nan') != itself)
        return None
    return f


def derive_cache_hit_rate(e: dict[str, Any]) -> float | None:
    """Cache-hit ratio for one entry: ``tokens_cache_read / (tokens_input + tokens_cache_read)``.

    Returns ``None`` on a zero denominator (no input and no cache reads) or when either field is
    missing — an unmeasured dimension must not be reported as a fabricated 0.0 hit rate.
    """
    read = _as_float(e.get("tokens_cache_read"))
    inp = _as_float(e.get("tokens_input"))
    if read is None or inp is None:
        return None
    denom = inp + read
    if denom <= 0:
        return None
    return read / denom


def derive_constraint_score(e: dict[str, Any]) -> float | None:
    """Constraint satisfaction for one entry: ``constraints_met / constraints_total``.

    Returns ``None`` when ``constraints_total`` is 0 or either field is missing, mirroring how
    the ledger marks an unmeasured dimension.
    """
    met = _as_float(e.get("constraints_met"))
    total = _as_float(e.get("constraints_total"))
    if met is None or total is None or total <= 0:
        return None
    return met / total


def normalize_model_id(
    model: str,
    *,
    aliases: dict[str, list[str]] | None = None,
) -> str:
    """Canonicalize a model id to its *pool* form.

    A pool id (a key of ``aliases``) passes through unchanged. A legacy result id listed under
    a pool id resolves to that pool id (the first match in dict order), so entries measured
    under ``openai/gpt-5.6`` land under ``openai/gpt-5.6-sol`` — the id ``route_step`` looks up.
    Any other id (e.g. ``deepseek/deepseek-v4-pro``, which matches on both sides) is returned
    unchanged.
    """
    alias_map = aliases if aliases is not None else MODEL_ALIASES
    if model in alias_map:
        return model
    for pool_id, legacy_ids in alias_map.items():
        if model in legacy_ids:
            return pool_id
    return model


def _mean_present(group: list[dict[str, Any]], field: str) -> float | None:
    """Mean of a signal over entries that carry a finite value; ``None`` when unmeasured.

    ``_results_summary.json`` rows mark an unmeasured dimension with ``NaN`` (see
    ``analyze_worktrees.py``), so NaN — like ``None`` — is skipped rather than averaged in as
    zero. Every aggregated dimension (including ``correctness``/``cost``) routes through here.
    """
    vals: list[float] = []
    for e in group:
        v = e.get(field)
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv != fv:  # NaN check
            continue
        vals.append(fv)
    return (sum(vals) / len(vals)) if vals else None


def build_signal_store(
    entries: list[dict[str, Any]],
    *,
    aliases: dict[str, list[str]] | None = None,
) -> dict[str, ModelSignals]:
    """Aggregate ``_results_summary.json`` entries into per-model ``ModelSignals``.

    Applies the derivations (``cache_hit_rate``, ``constraint_score``) and the model-id alias
    normalization *before* grouping, then averages every dimension with the NaN/None-aware
    :func:`_mean_present`. The returned dict is keyed by **pool** id, so ``route_step`` can look
    up any ``model_pool`` entry directly. ``efficiency`` remains ``correctness / cost`` and is
    only set when both are measured and ``cost > 0``. Models absent from ``entries`` are omitted.
    """
    alias_map = aliases if aliases is not None else MODEL_ALIASES

    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        m = e.get("model")
        if not m:
            continue
        # Enrich with the derived signals and canonicalize the id *before* aggregation, so a
        # legacy-id entry and a pool-id entry describing the same model merge into one group.
        enriched = dict(e)
        ch = derive_cache_hit_rate(e)
        if ch is not None:
            enriched["cache_hit_rate"] = ch
        cs = derive_constraint_score(e)
        if cs is not None:
            enriched["constraint_score"] = cs
        enriched["model"] = normalize_model_id(str(m), aliases=alias_map)
        by_model[enriched["model"]].append(enriched)

    store: dict[str, ModelSignals] = {}
    for m, group in by_model.items():
        correctness = _mean_present(group, "correctness")
        cost = _mean_present(group, "cost")
        store[m] = ModelSignals(
            model=m,
            correctness=correctness,
            cost=cost,
            efficiency=(correctness / cost)
            if (correctness is not None and cost is not None and cost > 0)
            else None,
            cache_hit_rate=_mean_present(group, "cache_hit_rate"),
            constraint_score=_mean_present(group, "constraint_score"),
            code_quality_score=_mean_present(group, "code_quality_score"),
            novelty_score=_mean_present(group, "novelty_score"),
            composite_score=_mean_present(group, "composite_score"),
        )
    return store
