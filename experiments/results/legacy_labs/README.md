---
status: accepted
---
# `legacy_labs/` — lab outputs with non-canonical lineage

**These files are historical artifacts. Nothing reads them. Nothing publishes them.**

They live here, one directory away from `experiments/results/lab_*.json`, because of the
semantic-integrity release (`docs/review/semantic_integrity_review.md` P0, item 3):

> Rebuild derived outputs — every active lab + website dataset from current canonical
> records only. […] Verify zero lab outputs carry the retired summary's lineage.

`experiments/results/lab_*.json` is now, by construction, **only** the contract-bearing
outputs of publication-eligible labs — every one of them carrying a `lab_contract` block
whose `input_manifest_sha256` matches the current registry. A stale file sitting beside
them could be mistaken for a current measurement; separating them makes the invariant
checkable (`tests/test_lab_outputs_canonical.py`) instead of merely intended.

Nothing was deleted. Provenance is preserved in full — both the files and their git
history.

## What is in here

**Quarantined labs (11)** — the script still exists in `scripts/`, is classified
`lab_status: quarantined` in `scripts/lab_manifest.json`, and reaches the **retired**
`experiments/results/_results_summary.json` directly or transitively. Running one by hand
(`agentic-dynamics analyze lab <name>`) is still supported; it writes back *here*, not into
the canonical results directory.

```
lab_basin_topology.json          lab_grit_matrix.json          lab_task_routing.json
lab_basin_topology_neo4j.json    lab_opencode_meta_analysis.json  lab_tool_archetypes.json
lab_claude_audit.json            lab_survival_horizon.json
lab_correctness_premium.json     lab_coupling.json  (lab_think_do_coupling.py)
lab_flail_triggers.json
```

**Retired labs (8)** — outputs of the `*_DEPRECATED_bge_m3` scripts deleted in
consolidation Stage 1. No script produces these any more; they are pure history.

```
lab_cascades.json      lab_drift.json                 lab_semantic_clusters.json
lab_cross_model_reasoning.json  lab_reasoning_divergence.json  lab_stability.json
lab_recovery_curves.json        lab_volatility.json
```

## Why they are not canonical

Every file here was computed from `_results_summary.json` — the 144-entry corpus retired
by `docs/data_integrity_findings.md` treatment rule 4 — or from a graph loaded out of it.
None carries a `lab_contract`, so none can state which registry produced it, and none can
be checked for staleness. That is the whole reason they may not publish.

To bring a lab back: re-point it at the registry resolver
(`agentic_dynamics.reporting.canonical_corpus.load_canonical_tables`), have it emit a
contract (`reporting.lab_contract.attach_contract`), then flip its `lab_status` and
`publication_eligible` in `scripts/lab_manifest.json`. The guards do the rest.
