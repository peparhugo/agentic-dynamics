---
status: accepted
---
# CAP I5 Gate Scan — R1-R11 requires/produces gate over the committed spec corpus

**Spec:** `workflows/repository/cap_gate_scan.yaml`
**Date:** 2026-08-24 · **Model:** anthropic/claude-sonnet-5 · **Branch:** `feature/cap-gate_scan`
**Gate under test:** `agentic_dynamics.control.context_compiler.validate_spec_fact_contracts`
(real `FACT_PREDICATES`/`REDUCERS`/`experiments/contexts/*.yaml`, refusals R1-R11) composed with
`agentic_dynamics.experiment.compile_experiment.compile_spec`'s classic requires/produces +
structural gate.

---

## 0. Method

Every check below was **executed**, not asserted.

1. **Corpus enumeration.** Loaded `experiments/specs/index.json` (`n_specs: 94`) and resolved each
   entry's `spec_path` against disk. Independently cross-checked (adversarial phase, §3) by
   re-globbing `experiments/definitions/*.yaml` (non-recursive — `configs/` is a different schema,
   not `ExperimentSpec`) + `workflows/**/*.yaml` (recursive) directly from the filesystem, bypassing
   the index entirely.
2. **Per-spec scan.** For every spec: `ExperimentSpec.from_yaml(path)`, then (a)
   `compile_experiment.compile_spec(spec)` — the classic requires/produces + structural gate
   (tier-1, skips R1-R11 by construction: `experiment` may not import `control.facts`/
   `control.reducers`), and (b) `control.context_compiler.validate_spec_fact_contracts(spec)` — the
   real I5 gate, which threads the real `FACT_PREDICATES` (29 predicates), `REDUCERS` (5 reducer
   versions), and every loaded `experiments/contexts/*.yaml` contract through
   `experiment_spec.validate_spec`. (b) is a strict superset of (a): both are recorded for every
   spec so a refusal's origin (classic vs. R1-R11) is traceable.
3. **Gate-mechanics sanity check.** Before trusting a zero-refusal scan, the gate was proven live
   against a deliberately broken spec (a control rule with `requires: ["nonexistent_field"]` and
   another with `requires_facts: ["nonexistent_predicate"]`) — see §2.1. It correctly refused both
   (one classic error, one `(R1)` error), ruling out a silently-broken scan harness.
4. **Registry integrity.** Beyond per-spec refusals, checked the registries themselves for phantom
   producers: every `FACT_PREDICATES[*].produced_by` entry resolves in `REDUCERS`, every
   `REDUCERS[*].produces` entry is a declared predicate, and every reducer's `consumes` chain
   bottoms out at a producing reducer (the R3 reduction-ladder check, applied registry-wide instead
   of only through a spec that happens to reference it).
5. **Index-drift check.** Derived a fresh index **in-memory only** (`spec_status.collect_entries`
   + `build_index`, never the `spec_status.py --json` CLI form without `--dry-run` — that form
   writes both artifacts for real; see the correction note in §2.3) and diffed the fields
   derivable purely from the committed spec YAMLs (`name`, `version`, `spec_path`,
   `artifact_kind`, `repeatable`, `supersedes`, `superseded_by`) against the committed index.

---

## 1. Summary — PASS/FAIL

| # | Check | Status | Evidence |
|---|---|---|---|
| **G1** | Every committed spec resolves and loads (`spec_path` exists, YAML parses into `ExperimentSpec`) | **PASS** | §2 — 94/94 loaded, 0 load errors |
| **G2** | Classic requires/produces + structural gate (`compile_spec`) — 0 refusals | **PASS** | §2 — 94/94 |
| **G3** | Real R1-R11 fact-contracts gate (`validate_spec_fact_contracts`) — 0 refusals | **PASS** | §2 — 94/94 |
| **G4** | Registry integrity: no phantom producers, complete reduction ladder | **PASS** | §2.2 — 29 predicates / 5 reducers, 0 issues |
| **G5** | Contract integrity: every loaded invariant's `on_missing` is `halt`/`escalate` (R11) | **PASS** | §2.2 — 1 contract (`route_next_job/v1`), 2 invariants, both `halt` |
| **G6** | Index matches disk for every spec-YAML-derived field (no drift in name/path/supersession) | **PASS** | §2.3 |
| **G7** | Adversarial re-scan (independent enumeration, fresh process) reproduces 0 refusals | **PASS** | §3 |

**Overall: PASS — 94/94 specs, zero refusals, nothing to fix or record as BLOCKED.**

This is a **real, verified finding, not a scan gap**: §2.1 proves the harness catches genuine
refusals, and the result is independently corroborated by a pre-existing repo test,
`tests/test_context_plane_contracts.py::test_committed_spec_corpus_gains_zero_new_refusals_from_the_i5_gate`,
which asserts exactly this invariant (`validate_spec_fact_contracts(spec) == validate_spec(spec)`
for every spec in the corpus) and already passes on `main`.

---

## 2. G1-G6 — the raw scan (first pass)

### 2.1 Gate-mechanics sanity check

Ran before trusting any zero-refusal result, against a hand-built spec that is not part of the
committed corpus:

```
rules=[
    RuleSpec(name="bad_classic", plane="control", evidence_class="[H]",
             requires=["nonexistent_field"]),
    RuleSpec(name="bad_fact", plane="control", evidence_class="[H]",
             requires_facts=["nonexistent_predicate"]),
]
```

```
compile_spec(spec)  ->  SpecError:
  rule "bad_classic" requires 'nonexistent_field' — not produced by the ledger or any
  measurement rule in this spec. Instrument it first.

validate_spec_fact_contracts(spec)  ->
  rule "bad_classic" requires 'nonexistent_field' — not produced by the ledger or any
  measurement rule in this spec. Instrument it first.
  rule "bad_fact" requires fact 'nonexistent_predicate' — no such predicate is declared.
  Declare it with a producing reducer first. (R1)
```

Both refusal paths fire correctly. The harness is live.

### 2.2 Corpus scan — findings table

| spec | spec_path | rule/contract | refusal text | requires_facts entry |
|---|---|---|---|---|
| *(none)* | | | | |

**0 rows.** All 94 specs in `experiments/specs/index.json` loaded without error and produced
**zero** entries from either `compile_spec` or `validate_spec_fact_contracts`.

Root cause of the zero count (verified, not assumed): as of this branch, **no committed spec
declares a real `requires_facts:` or `decision_type:` key on any rule** —

```
$ grep -rn "requires_facts:" workflows/ experiments/definitions/   # 0 matches
$ grep -rn "decision_type:"  workflows/ experiments/definitions/   # 0 matches
```

(Free-text mentions of the words "requires_facts" / "decision_type" exist in four workflow
prompts — `cap_addendum_implement.yaml`, `cap_implement_repair.yaml`, `cap_addendum_design.yaml`,
`cap_gate_scan.yaml` — but none are YAML keys under a `rules:` entry, so R1-R10 have nothing to
check per-spec.) R1-R10 only fire for a rule that *declares* `requires_facts`/`decision_type`;
since none do, the corpus is structurally incapable of tripping R1-R10 today. R11 is a property of
the *contract*, independent of spec references — checked anyway (below) and clean.

**Registry integrity (G4):**

```
29 predicates in FACT_PREDICATES, 5 reducers in REDUCERS
0 registry-level integrity issues
  (every produced_by resolves in REDUCERS; every reducer.produces is a declared predicate;
   every reducer.consumes entry that names a predicate has a non-empty produced_by — the R3
   reduction ladder is complete registry-wide)
```

**Contract integrity (G5):** `experiments/contexts/` has exactly one committed contract,
`route_next_job/v1`. Both its invariants:

```
invariant 'allowed_models'   on_missing='halt' -> ok
invariant 'max_spend_usd'    on_missing='halt' -> ok
```

satisfy R11 (`on_missing` ∈ `{halt, escalate}`). No `(R11)` refusal is possible today.

### 2.3 Index-drift check (G6)

**Correction recorded in the interest of an honest scan log:** the first attempt at this check ran
`python scripts/spec_status.py --json > /tmp/index_regen.json` **without** `--dry-run`. Per the
script's own argument parser, `--json` is additive to the default action, not a substitute for
`--dry-run` — the command silently **regenerated and overwrote the real, committed**
`experiments/specs/index.json` **and** `experiments/specs/STATUS.md` on disk before printing. The
resulting diff (`git status`) showed 75/94 entries changed — not spec drift, but data loss: this
worktree checkout has no `experiments/results/workflows/` directory (`.gitignore:27` — it is
correctly untracked, local run-artifact output) and no Redis/registry backing it either, so
`collect_entries()` derived `status`/`last_run_at`/`latest_ok`/`latest_model`/`latest_cost_usd`/
`latest_git_sha`/`results_pointer`/`n_runs` as empty for every spec whose run history the committed
index recorded from the environment that produced it (`main`, or wherever those local result files
actually live). Caught immediately via `git diff --stat` before this pass moved on; reverted with
`git restore experiments/specs/index.json experiments/specs/STATUS.md` before anything was
committed. **No data was lost** — this note exists so a future run of this same command in a fresh
worktree does not repeat the mistake.

The check was then redone safely — **in-memory only**, no CLI, no writes — comparing just the
fields a spec's own committed YAML determines (independent of the gitignored run ledger):

```python
from agentic_dynamics.experiment.spec_status import collect_entries, build_index
fresh = build_index(collect_entries(root=Path(".").resolve()))
committed = json.load(open("experiments/specs/index.json"))

PURE = ("name", "version", "spec_path", "artifact_kind", "repeatable", "supersedes", "superseded_by")
an = {s["name"]: {k: s[k] for k in PURE} for s in committed["specs"]}
bn = {s["name"]: {k: s[k] for k in PURE} for s in fresh["specs"]}
print("pure-YAML-derived fields identical for all 94:", an == bn)   # -> True
print("diffs:", [n for n in an if an[n] != bn[n]])                   # -> []
```

Result: **all 94 entries identical** on every field the committed spec YAMLs alone determine — no
spec was added, removed, moved, or resuperseded that the index doesn't already reflect. The only
fields that differ between a from-scratch derivation in this worktree and the committed index are
the **run-history fields**, and only because this worktree lacks the gitignored
`experiments/results/workflows/` ledger the committed index was built against — an environment gap,
not a spec/index drift the gate cares about. **No regeneration was performed or committed this
pass**; the committed index remains authoritative.

---

## 3. G7 — Adversarial re-scan (independent, fresh enumeration)

Re-ran the full gate in a **separate process**, enumerating the corpus **directly from disk**
instead of trusting `experiments/specs/index.json`, per the spec's own instruction to look for
"refusals the first scan missed, fixes that merely silenced the gate, index/spec drift, and
phantom RECORDs":

```python
paths = sorted((REPO / "experiments" / "definitions").glob("*.yaml"))   # non-recursive;
                                                                          # configs/ excluded —
                                                                          # different schema
paths += sorted((REPO / "workflows").rglob("*.yaml"))                   # recursive
```

| Adversarial check | Result |
|---|---|
| File-count parity: independent glob vs. `index.json`'s 94 entries | **94 == 94** — no spec exists on disk that the index misses, and no index entry points at a missing file |
| Silenced-gate check: any rule whose `requires_facts` now references a predicate with a real-looking but unregistered reducer | N/A — 0 specs declare `requires_facts` on a rule (§2.2); nothing to silence |
| Phantom RECORD check: is there any spec this pass could have wrongly marked BLOCKED | N/A — §2 found 0 refusals, so 0 RECORDs were made in the first place; nothing to re-check |
| Full gate re-run over the independently-enumerated 94 files | **0 refusals** — identical to §2 |
| Cross-check against the pre-existing repo test | `pytest tests/test_context_plane_contracts.py::test_committed_spec_corpus_gains_zero_new_refusals_from_the_i5_gate` — **PASS** (see below) |

```
$ pytest tests/test_context_plane_contracts.py -k gains_zero_new_refusals -q
1 passed
```

**Final state: zero refusals, corroborated by three independent methods** (this scan's first
pass, this scan's independent re-enumeration, and the pre-existing committed test suite). No spec
required a fix. No spec required a BLOCKED record.

---

## 4. Log

| Metric | Value |
|---|---|
| Specs in corpus (index) | 94 |
| Specs in corpus (independent disk enumeration) | 94 |
| Load errors | 0 |
| Classic gate (`compile_spec`) refusals | 0 |
| Real R1-R11 gate (`validate_spec_fact_contracts`) refusals | 0 |
| Registry integrity issues | 0 |
| Contract (R11) violations | 0 |
| Index drift (spec-YAML-derived fields) | none — 94/94 identical (§2.3) |
| FIX applied | 0 |
| RECORDed as BLOCKED | 0 |
| Adversarial re-scan refusals found | 0 |

**PASS/FAIL: PASS.** 94/94 specs clear both gates; the corpus needed no changes this pass, so
`experiments/specs/index.json` was left untouched — it already matches a fresh derivation on every
field a spec's own committed YAML determines (§2.3); this worktree simply lacks the gitignored
run-ledger files needed to safely regenerate the run-history fields, so no regeneration was
committed.

### Why this task found nothing to fix (context for future runs)

The I5 gate (R1-R11) is **additive**: it only inspects a rule's `requires_facts`/`decision_type`
fields, which are new, opt-in fields on `RuleSpec` (design §7.1) that no committed spec has adopted
yet. Every spec in the corpus still expresses its information dependencies through the legacy
`requires:` (bare ledger-field names), which the classic gate already validated before I5 shipped.
The I5 gate is therefore currently a no-op over the committed corpus **by construction**, not
because every spec happens to satisfy nontrivial fact contracts — there are no fact contracts in
play yet outside the one demonstration contract (`route_next_job/v1`), and no rule references it.
The next spec that adopts `requires_facts:`/`decision_type:` (e.g. a future routing-policy arm
built against CAP I4's context compiler) will be the first the R1-R10 rows in this gate can
actually refuse — this scan establishes the pre-adoption baseline is clean, so that spec's refusal
(if any) will be attributable to it, not to drift already present in the corpus.
