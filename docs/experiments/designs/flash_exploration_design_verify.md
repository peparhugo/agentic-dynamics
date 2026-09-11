---
status: accepted
---

# flash_exploration — design re-verification (`p0_research_verify`)

**Deliverable of:** `flash_exploration_build.yaml` › `p0_research_verify`.
**Verifies:** `docs/experiments/designs/flash_exploration_design.md` — its §0 pins table and §1
findings F1..F6.
**Base:** `feature/flash-exploration` at `bd5c530e2ee05f359eb759695af985a6cc7410ce` (the design's
stated main HEAD `bd5c530e2`; confirmed an ancestor of HEAD).
**Verified at:** HEAD `824d329681811afcd4071212da3a295ce79bd477`. The three commits after the
design-base commit that sit on this branch (`1bffea30f` design, `464050a66` build workflow,
`824d32968` pre-registration) touch **no** pinned file — proven by
`git diff --stat 1bffea30f HEAD -- <the 10 pins>` returning empty.

**Result: PASS.** All 10 file pins match byte-for-byte; every substantive claim in F1..F6 is
CONFIRMED. Two sub-details were imprecise and are corrected in place in the design
(F4's error-persistence *mechanism*; F6's 2026-09-04 incident *sub-count*). No claim was
REFUTED. The design's frontmatter is therefore flipped `proposed → accepted`.

> **Environment note (live claims).** This checkout (`/repo`) carries the code + tracked
> `experiments/data_manifest.json` but not the runtime data payloads; the live data plane lives at
> `/app/experiments/results` (kb artifacts, `registry_index.jsonl`, `control/control.db`,
> Redis DB 2). The F2/F3/F6 live probes below read that plane. The F3 canonical-corpus dry-run
> needs both halves together, so it was reproduced with a temporary `experiments/results`
> symlink to `/app/experiments/results` (the standard ignored data path), which was removed
> before committing.

---

## 0. Pins (§0) — every recomputed SHA256 equals the table

| Artifact | Design SHA256 | Recomputed | Verdict |
|---|---|---|---|
| `src/agentic_dynamics/knowledge/retrieval.py` | `116a76ef…3715b0` | `116a76efb73f83590c365da8de81063b3c634c23112fb4b8ad4c2889cc3715b0` | CONFIRMED |
| `src/agentic_dynamics/knowledge/graph.py` | `2de561ed…79a449` | `2de561edfb9aa93ac60dc94c916f518ead698dee17dff5fd5e0501d64279a449` | CONFIRMED |
| `src/agentic_dynamics/knowledge/augment.py` | `9b4a8bcf…b6264d` | `9b4a8bcf7cbb4102c56e9334e4c69b6f8af9638bc86781a94179caa885b6264d` | CONFIRMED |
| `src/agentic_dynamics/control/reducers/pattern.py` | `cab1ae1e…7b8a70` | `cab1ae1e0b3ab4f2918116c528949e9d9436b725d10db87c62aed521477b8a70` | CONFIRMED |
| `src/agentic_dynamics/control/fact_ingestion.py` | `eeb720ea…ae6f8f` | `eeb720eac7a954404287c4d388a7fa79366875c2c7bc82a78a06b9accaae6f8f` | CONFIRMED |
| `src/agentic_dynamics/measurement/basin.py` | `bc24affd…92374` | `bc24affdce226c24904892df1e340b6cd6dcad7ac645927f3316c6dcb9092374` | CONFIRMED |
| `src/agentic_dynamics/runtime/workflow_runner.py` | `6be6d072…c3d22` | `6be6d072f660d0ec7152d7208eb2141a9741d48e1550426e65b033bcf2ac3d22` | CONFIRMED |
| `scripts/run.py` | `ea86f1b9…4e9c9` | `ea86f1b9370214bbe8c5ad81ba10e913b6c2cca4e76439b9bd3aac8bd484e9c9` | CONFIRMED |
| `scripts/kb_produce_facts.py` | `79ee6344…8055f8` | `79ee63447eb94ed433ccb19f0d03ffe02dd55dbe55d94dd12f0c7971878055f8` | CONFIRMED |
| `workflows/repository/retrieval_activation_augment_proof.yaml` | `44dd42a0…a43139` | `44dd42a052a9caef8756994a375761d82245587ff346ef68ed61480b69a43139` | CONFIRMED |

**Evidence command**

```bash
for f in src/agentic_dynamics/knowledge/retrieval.py \
  src/agentic_dynamics/knowledge/graph.py \
  src/agentic_dynamics/knowledge/augment.py \
  src/agentic_dynamics/control/reducers/pattern.py \
  src/agentic_dynamics/control/fact_ingestion.py \
  src/agentic_dynamics/measurement/basin.py \
  src/agentic_dynamics/runtime/workflow_runner.py \
  scripts/run.py scripts/kb_produce_facts.py \
  workflows/repository/retrieval_activation_augment_proof.yaml; do
  sha256sum "$f"
done
```

**Output:** all ten lines matched the design §0 table byte-for-byte (reproduced in the
"Recomputed" column above). No pin is STALE.

---

## 1. Findings F1..F6

### F1 — the commit hard-gate excludes knowledge authorities in a fresh worktree

**Claim.** `freshness_multiplier` returns `None` for `SOURCE | MEASURED | DERIVED` with a
non-empty `commit_sha != current_commit` (`retrieval.py:548-554`); the same hard gate exists in
the Chroma `where` (`retrieval.py:1726-1735`) and the lexical Cypher (`graph.py:1388-1392`,
with `commit=commit_sha` passed from `retrieval.py:1406-1408`); the one `fallback_mode="full"`
proof run injected zero evidence (`selected_evidence_ids: []`).

**Verdict: CONFIRMED.**

**Evidence command / output**

```bash
sed -n '548,554p' src/agentic_dynamics/knowledge/retrieval.py
# if (
#     current_commit
#     and authority in (Authority.SOURCE, Authority.MEASURED, Authority.DERIVED)
#     and commit_sha
#     and commit_sha != current_commit
# ):
#     return None

sed -n '1726,1735p' src/agentic_dynamics/knowledge/retrieval.py
# commit = filters.get("commit_sha")
# if commit:
#     conditions.append({"$or": [{"commit_sha": ""}, {"commit_sha": commit}]})

sed -n '1388,1392p' src/agentic_dynamics/knowledge/graph.py
# if commit:
#     query_str += "WHERE node.commit_sha = $commit OR node.commit_sha IS NULL "

sed -n '1406,1408p' src/agentic_dynamics/knowledge/retrieval.py
# return graph_client.search_knowledge_fulltext(
#     plan.lexical_query, limit=top_k, commit=commit_sha
# )
```

Proof-ledger probe (all five `retrieval_activation_augment_proof` run ledgers, read from
`/app/experiments/results/workflows/...`, the runtime path for
`retrieval_activation_augment_proof/20260901T031548Z.json`):

```bash
for f in <the 5 ledgers>; do <print phases[].fallback_mode, selected_evidence_ids>; done
# 20260901T022559Z.json  fallback=no_rag  evidence=[]
# 20260901T024712Z.json  fallback=no_rag  evidence=[]
# 20260901T031548Z.json  fallback=full    evidence=[]   <-- the one full run injected zero evidence
# 20260901T031939Z.json  fallback=no_rag  evidence=[]
# 20260901T044549Z.json  fallback=no_rag  evidence=[]
```

All three layers filter on `commit_sha` alone (empty or exact match) at their respective
layers, and the fusion-time gate excludes the three knowledge authorities. The `full` run
records `fallback_mode="full"` with `selected_evidence_ids: []` exactly as claimed.

*Note (not a refutation):* the lexical Cypher admits `commit_sha IS NULL`; the substantive
claim — a **non-empty, differing** commit is excluded on all three layers — holds, because
projection/finding records carry the mint-time commit.

### F2 — patterns were never projected, and the proof arm never asked for them

**Claim.** 6 pattern facts; **0** `source_type="pattern"` projection artifacts; **0** registry
`reason` rows starting `pattern-content=`; the only shipped `rag_augment` spec
(`retrieval_activation_augment_proof.yaml:26-33`) omits `rag.pattern_projection: true`; the
retrieval gate admits patterns only under that flag (`retrieval.py:1297-1313`); the projection
landed a week after the last mint.

**Verdict: CONFIRMED.**

**Evidence command / output**

Live data plane (`/app/experiments/results`):

```bash
cd /app/experiments/results/kb
grep -rl '"extractor_version": "pattern/v1"' . | wc -l   # 6
grep -rl '"source_type": "pattern"' .            | wc -l   # 0
grep -rl '"pattern_payload"' .                   | wc -l   # 0
grep -c 'pattern-content=' ../registry_index.jsonl        # 0
```

- 6 KB artifacts carry `extractor_version="pattern/v1"`, all `source_type="fact"`,
  `authority=DERIVED` (e.g. `logical_locator=workload:pattern/task_manager/baseline#pattern`).
- 0 `source_type="pattern"` artifacts and 0 artifacts carrying a `pattern_payload` key ⇒ the
  projection records were never written.
- 0 registry rows with a `reason` beginning `pattern-content=`. (The full registry is 49,097
  rows; prefix census: 40,201 `fact-content=`, 353 `spec-lifecycle-content=`, 0
  `pattern-content=`.)

Spec + gate:

```bash
sed -n '25,33p' workflows/repository/retrieval_activation_augment_proof.yaml
# rag_augment: true
# rag:
#   repository_id: agentic-dynamics
#   acl_scope: agentic-dynamics           <-- no pattern_projection key

sed -n '1297,1313p' src/agentic_dynamics/knowledge/retrieval.py
# if source_type != "pattern": return True
# return (pattern_projection and authority is Authority.DERIVED
#         and (not evidence_class or evidence_class == "[C]"))
```

Commit archaeology (design claim: projection landed after the last mint):

```bash
git log -1 --format='%ci %s' 523c0bac1   # 2026-09-01 p3_pattern_projection
git log -1 --format='%ci %s' eb2697459   # 2026-09-01 merge retrieval_activation
git log -1 --format='%ci %s' 38ba8d49b   # 2026-08-25 p2_mint_patterns — "first 6 PatternPayload facts"
```

The projection commit is 2026-09-01, seven days after the 2026-08-25 mint; the mint message
itself states "6". Patterns were doubly invisible.

### F3 — pattern minting churns its own facts on every commit

**Claim.** `pattern.py:229` sets `validity_window=inp.source_revision or REVISION_FALLBACK`;
`kb_produce_facts.py:1237` defaults `revision = git_head_sha()`; `fact_fingerprint` excludes
`evidence_ids`/`inputs_digest` but not `value.validity_window` (`fact_ingestion.py:99-115`);
`fact_payload` (`fact_ingestion.py:62-77`) carries no `source_revision`; a dry-run today emits 6
supersedes + 6 projections; the review records this as the mandatory fix
(`docs/reviews/cap_pattern_minting_review.md:39`).

**Verdict: CONFIRMED.**

**Evidence command / output**

```bash
sed -n '229p' src/agentic_dynamics/control/reducers/pattern.py
# validity_window=inp.source_revision or REVISION_FALLBACK,

sed -n '1237p' scripts/kb_produce_facts.py
# revision = args.revision or git_head_sha()

sed -n '99,115p' src/agentic_dynamics/control/fact_ingestion.py
# _PROVENANCE_KEYS = frozenset({"evidence_ids", "inputs_digest"})
# fact_fingerprint: content = {k: v for k, v in payload.items() if k not in _PROVENANCE_KEYS}

sed -n '62,77p' src/agentic_dynamics/control/fact_ingestion.py
# keys: abstraction_level, evidence_ids, expires_at, inputs_digest, predicate, reducer_version,
#       scope_path, subject_id, subject_type, unit, value, value_type
#   -> no source_revision (only ever inside value.validity_window)
```

Because `_PROVENANCE_KEYS` does not include `value`, and `value.validity_window` is the ambient
HEAD at mint time, a new HEAD re-fingerprints every pattern fact with no real change.

Live dry-run at the verified HEAD (with the data plane mounted; note `revision=824d32968181`):

```bash
python3 scripts/kb_produce_facts.py --reducer pattern/v1 --dry-run
# pattern/v1: derived 12 fact record(s) (revision=824d32968181, repository-id='agentic-dynamics')
# dry-run: would emit 12 fact record(s) (limit=none)
#   <5 samples printed: all [fact/supersede] on workload:pattern/...>   (preview caps at 5)
```

Decomposed in-process: the reducer derives **6** facts, `derive_fact_records` returns **6**
(all supersedes — the 6 current pattern entities exist but their fingerprint changed) and
`derive_pattern_projection_records` returns **6** projections ⇒ `12 = 6 + 6`, exactly the
design's "6 supersedes + 6 projections".

Review citation: `docs/reviews/cap_pattern_minting_review.md:39` marks finding #1 **Mandatory
fix** and isolates the cause to `validity_window` / `value` not being in `_PROVENANCE_KEYS` —
matching the design.

### F4 — augmentation is workflow-phase-only; its failures were half-observable

**Claim.** `rag_augment` exists only in `workflow_runner.py` (enablement `:3022-3031`, seam
`:3317-3345`); `run.py`/`run_story.py` have zero references; of five proof runs, four fell back
to `no_rag`; `AugmentationOutcome.error` is not persisted in the run ledger.

**Verdict: CONFIRMED**, with a correction to the cited *mechanism* (see below).

**Evidence command / output**

```bash
git grep -n 'rag_augment' -- '*.py'
# only src/agentic_dynamics/knowledge/augment.py (docstrings) and workflow_runner.py
git grep -c 'rag_augment\|augment_prompt\|AugmentationOutcome' -- scripts/run.py scripts/run_story.py
# (no matches)

sed -n '3022,3031p' src/agentic_dynamics/runtime/workflow_runner.py   # enablement + scope default
sed -n '3317,3345p' src/agentic_dynamics/runtime/workflow_runner.py   # the seam
# 3324: outcome = augment_prompt(...)
# 3337-3345: pr.raw_prompt_hash/.../pr.fallback_mode = outcome.*
#            <-- no pr.error = outcome.error anywhere
```

Five-run fallback tally is in F1's probe (4 × `no_rag`, 1 × `full`). `f76b9acfc` (2026-09-01)
is the constructor-workdir fix (`git show --stat f76b9acfc`) for the swallowed
`FileNotFoundError` that had produced `no_rag`.

**Correction applied.** The design's parenthetical said the error is not persisted because
"`PhaseResult.to_dict()` does not carry it". That is wrong as a mechanism: `PhaseResult`
*defines* an `error` field (`workflow_runner.py:232`) and `to_dict()` *does* serialize it
(`workflow_runner.py:302: "error": self.error`). The real gap is that the RAG seam
(`workflow_runner.py:3337-3345`) never assigns `outcome.error` to `PhaseResult.error`, so the
augmentation error is dropped. The claim's conclusion (not persisted) holds; the mechanism is
corrected in place so the build fixes the assignment rather than adding a field that exists.

### F5 — no diversity instrument; run.py cannot preserve k attempts

**Claim.** `measure_basin_escape` is baseline-vs-perturbed and pure over code strings
(`basin.py:146-168`); `_architecture_divergence`/`_structure_divergence`/`_compute_novelty`
(`basin.py:274-340`) are private and pairwise; no portfolio metric exists; in `scripts/run.py`
artifact/report slugs collide across `seed_variant`/`repetition` (`:460`, `:507`) and
`_save_results` strips `final_response` (`:404`).

**Verdict: CONFIRMED.**

**Evidence command / output**

```bash
sed -n '146,168p' src/agentic_dynamics/measurement/basin.py   # baseline_code/perturbed_code signature
sed -n '274,332p' src/agentic_dynamics/measurement/basin.py   # three private pairwise helpers
git grep -ni 'portfolio\|diversity\|distinct_fraction' -- '*.py'
# only retrieval.py:871 (source-diversity CAP) and a retrieval test -> no portfolio metric
ls src/agentic_dynamics/measurement/diversity.py   # No such file

sed -n '400,405p' scripts/run.py
# 404: "runs": [{k: v for k, v in r.items() if k != "final_response"} for r in runs],
sed -n '459,460p' scripts/run.py
# 460: artifact_dir_name = f"{name}_{model_slug}_{op}_s{s}"   <-- no variant/rep
sed -n '507p' scripts/run.py
# 507: md_path = reports_dir / f"{name}_{model_slug}_{op}_s{s}.md"   <-- no variant/rep
```

`run_experiment` loops `for variant in seed_variants: for rep in range(repetitions)`
(`run.py:121-122`), and the per-run record carries `seed_variant`/`repetition`
(`run.py:298-299`), yet the report artifact directory and markdown slug key only on
`{name}_{model_slug}_{op}_s{s}` — a second variant/rep of the same operator+strength overwrites
the first's artifacts and report. `final_response` is removed from the persisted record. Both
confirmed.

### F6 — hygiene risks on the read path

**Claim.** 36,972 dead letters sit behind `lag=0` watermarks (28,613 from the 2026-09-04
corpus-root incident); `reconcile_missing` is a no-op in v1; the Chroma handler skips `fact`
records and ignores deletes.

**Verdict: CONFIRMED**, with a corrected 2026-09-04 incident sub-count.

**Evidence command / output**

```python
import redis, sqlite3
r = redis.Redis(host="finops-queue", port=6379, db=2, socket_connect_timeout=5)
r.xlen("kb:v1:dead_letter")     # 36972     <-- exact
# XINFO: length 36972, entries-added 36972, max-deleted-entry-id 0-0 (append-only, untrimmed)
con = sqlite3.connect("/app/experiments/results/control/control.db")
# projection_watermarks: chroma/registry/neo4j/ledger all lag_events=0, last_error=''
```

Full-stream bucket by `dead_lettered_at` (all 36,972 entries scanned):

| day | count | | day | count |
|---|---|---|---|---|
| 2026-08-24 | 11 | | 2026-09-02 | 433 |
| 2026-08-26 | 2,629 | | 2026-09-03 | 1,759 |
| 2026-08-30 | 333 | | **2026-09-04** | **28,291** |
| 2026-08-31 | 593 | | 2026-09-08 | 96 |
| 2026-09-01 | 2,775 | | 2026-09-09 | 40 |
| | | | 2026-09-10 | 12 |

The 2026-09-04 bucket is **28,291**, not the design's 28,613 (Δ 322). The total 36,972 is exact,
so this is a mis-grouping in the design, not a shifted total. `reconcile_missing`:

```bash
git grep -n 'reconcile_missing' -- '*.py'
# scripts/kb_worker.py:15 (prose reference), knowledge_stream.py:509 (definition),
# tests/test_knowledge_stream.py (tests) -> no production caller
```

Chroma handler (`scripts/kb_worker.py:359-405`):

```python
if group == "kb-chroma-v1":
    def handler(record):                       # no operation kwarg
        if record.source_type == "fact":
            return                             # facts skipped wholesale
        ...
        store.upsert([record.knowledge_id], [record.text], ...)   # runs on delete too
```

`handler` declares no `operation` parameter, so `process_entry` never passes one and a
`delete` event re-enters `upsert` — deletes are ignored. (The sibling `kb-neo4j-v1` handler
*does* take `operation`, so the gap is Chroma-specific, as the design says.)

**Correction applied.** The design's parenthetical said "28,613 from the 2026-09-04
corpus-root incident"; the scan of all 36,972 entries fixes that bucket at 28,291. The design
now reads 28,291.

---

## 2. Corrections applied to the design (in place)

1. **F4 mechanism** (design §1.F4): reworded the error-persistence parenthetical to name the
   real gap (the RAG seam never assigns `outcome.error` to `PhaseResult.error`) and to note
   that `PhaseResult`/`to_dict()` *do* carry an `error` field. Conclusion unchanged.
2. **F6 sub-count** (design §1.F6): `28,613 → 28,291` for the 2026-09-04 bucket, recomputed from
   all 36,972 live dead letters.
3. **Frontmatter**: `status: proposed → accepted`, with a one-line status note pointing here.

No claim was REFUTED; every claim the build phases depend on is CONFIRMED.

## 3. Disposition

- **G-research: PASS.** All 10 pins match; F1..F6 CONFIRMED with the two sub-detail corrections
  applied in place.
- The design is `status: accepted`; implementation phases (`p1_reachability`,
  `p2_pattern_repair`, `p3_instrument`) may proceed.
- Committed with the design corrections as the `p0_research_verify` deliverable.
