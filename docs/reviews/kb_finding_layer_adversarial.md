---
status: accepted
kind: adversarial_review
spec: kb_finding_layer
phase: k7_adversarial
author_model: deepseek/deepseek-v4-pro
author_under_review: deepseek/deepseek-v4-flash
generated_at: 2026-09-03T19:30:00Z
---

# kb_finding_layer k7 — INDEPENDENT adversarial review: the finding layer is real

**Verdict: PASS (merge-ready).** Reviewer: `deepseek/deepseek-v4-pro` (a DIFFERENT model and
session from the `deepseek-v4-flash` author). This review FALSIFIES, not certifies. Every claim
below was re-derived against the actual wave code (`/tmp/wt_wave4` at `146c37b94`) and the LIVE
KB (Neo4j `bolt://localhost:7687`, Chroma `knowledge_chunks_v1`, Redis 6380) — none asserted.
The core claim — **retrieval answers findings questions with findings** — held under independent
probe. Three findings are recorded (all RECORD-level accepted limitations / pre-existing drift,
none falsifying a claim); none required an on-branch fix.

---

## 1. Attack results, in mandate order

| # | Claim | Independent probe | Result |
|---|---|---|---|
| k1 | DEFAULT run emits a scoped, enriched finding (not just tests claiming it) | Real witness run `run-8e4b45836b21` (ledger committed), phase `witness_phase` ok, cost $0.0040, commit `7b1941ff1`; durable artifact `030f9574…json` carries `status ok, test_executed_success None → ADVISORY [H], cost, commit, conclusion`; registry row `self-wt_wave4_witness` present; retrievable at rank 2. Emit gate `_finding_emit_enabled` defaults ON; clean-tree adoption (k6 fix) verified in code + `_git_head`/`_git_commit` both exist. | **PASS** |
| k2 | Backfilled records are REAL, with content | `control_db_evidence` artifact `6961dcfb…` has `verdict not`, `spec_sha a358cde6…`, `findings 5`, `residuals 6`, conclusion `Verdict: FAIL — merge-blocked…`. `engine_gaps_followups` carries the split-run (F5) closure + the `17-spec shift` residual. 164 `wave:` records committed; deterministic dry-run reproduces 164. | **PASS** |
| k3 | Original probe returns findings above code (run myself) | 2026-09-02 probe re-run: **60 selected, `{'finding': 41, 'code': 19}`, `control_db_evidence` finding at rank 4, top-5 all findings** — was `{'code': 21, '': 40}`, top-6 all code. Code-shaped query: top-3 all `code` (code stays first). | **PASS** |
| k4 | Untyped records gone from top-K; graph leg resolved or honestly documented | Probe mix has zero `""` candidates; `untyped_excluded=0` (resolver/cross-leg typing populated them, not silent drops). Graph leg `graph_paths {}` documented-down honestly; `test_versioned_graph` (42 passed) proves the leg returns depth≥1 paths when edges exist in a scoped corpus. | **PASS** |
| k5 | Narrator fires on a real shift | Pure derivation + full emit path (real artifact + registry row, rerun-safe) unit-verified (173 new tests green). **Not yet observed on a live shift** — see F2. | **PASS (code) / see F2** |
| cross | Quality gates + parity suite green | Parity (`test_workflow_executor_parity`) green; 173 new + 122 workflow-runner tests green. **3 pre-existing publication-count gates red** — see F3. | **PARTIAL / see F3** |

---

## 2. The finding layer is REAL — re-verification evidence (reproducible)

```bash
# (a) original 2026-09-02 probe, re-run independently from the wave src
cd /tmp/wt_wave4 && python3 - <<'EOF'
import sys; sys.path.insert(0, 'src')
from agentic_dynamics.knowledge.augment import default_retrieve_fn
r = default_retrieve_fn()
a = r("control database per-phase evidence recording findings",
      repository_id="", acl_scope="",
      phase_objective="determine what the control_db_evidence wave concluded")
print(len(a.selected_evidence),
      {s: sum(1 for c in a.selected_evidence if getattr(c,'source_type','')==s)
       for s in {getattr(c,'source_type','') for c in a.selected_evidence}},
      [getattr(c,'text','')[:40] for c in a.selected_evidence[:5]])
EOF
# -> 60 {'finding': 41, 'code': 19}
#    ['wave control_room_ui_implement -> verdict no…',
#     'wave control_room_live_board -> verdict clea…',
#     'wave control_db_followups -> verdict clean,…',
#     'wave control_db_evidence -> verdict not, spec…',   # rank 4 — the k2 backfill
#     'wave control_room_posthoc_visibility -> ver…']

# (b) witness finding at rank 2 of the witness probe shape (top-5 all findings)
# (c) code-shaped query keeps code first: top-3 all code (mix {'code': 23, 'finding': 40})
```

The `'flat, not rich'` verdict is **inverted, measured with the identical query + phase
objective the 2026-09-02 probe used**. The k2-backfilled `control_db_evidence` finding returns
at rank 4 of 60 in a top-5 that is entirely findings; the witness finding returns at rank 2.

---

## 3. Findings

| # | Attack | Disposition | Reasoning + evidence |
|---|---|---|---|
| F1 | k2 backfill is rerun-safe, but **corpus-sensitive, not content-forever**: `logical_locator=wave:<name>` (and `entity_id`) is stable across `spec_sha` changes, while `knowledge_id` folds `spec_sha`. Re-running against a corpus that advanced (5 wave-2/3 specs got new sha) mints **parallel records with the same `entity_id` and no `supersedes` link** → two `lifecycle_state: current` records per wave. | **RECORD** (accepted limitation) | Reproduced: `python3 scripts/kb_backfill_findings.py --corpus-root /home/drseuss/ai-finops-framework --root /tmp/wt_wave4` emitted `5 new` (fleet_launch_boundary, fleet_launch_boundary_followups, fleet_launch_container_smoke, fleet_launch_smoke, authoring_product_aio) with duplicate `wave:` locators and no supersede chain. The docstring scopes rerun-safety to "unchanged artifacts", so this is documented-by-design; the version-chain consequence (stale "current" twin) is unaddressed. Fix path, if ever wanted: set `record.supersedes` to the prior `knowledge_id` for the same `logical_locator` when a changed sha re-derives. |
| F2 | k5 narrator has **0 live records** in either checkout's registry — it has never fired on a real production shift. The `17-spec shift` (the k5 "here's why" example) predates k5 and is retrievable only as a *residual* inside the `engine_gaps_followups` backfill, not as its own narrated record. | **RECORD** (forward-only by design; not yet observed live) | Verified the full emit path is real (test writes an actual durable artifact + registry row, rerun-safe, Redis-stubbed) and the wiring is correct in `refresh_spec_status` → `emit_index_shift`. The mechanism is forward-only: it narrates the *next* shifting regeneration, and no regeneration has shifted since k5 landed (the witness's synthetic spec was deliberately kept out of `workflows/**`). Not a defect; a completeness gap only for the historical 17-spec shift. |
| F3 | cross — **3 publication/docs-drift gates are RED**, all pre-existing: `test_doc_lifecycle::test_readme_spec_counts_match_index` (README 185 vs index 188), `test_publication_singular_door::test_readme_figures_match_public_statistics` (README 187 vs 188), `test_lab_outputs_canonical::test_site_lab_keys_are_all_contract_bearing` (site reads `D.labs.quality_frontier`, `data.js` does not publish it). | **RECORD** (pre-existing; not a wave regression) | Verified pre-existing at the merge-base (`64d1ded09`): README says 185 while `experiments/specs/index.json` has 188 specs; `quality_frontier` absent from `data.js` at the merge-base too. `git diff 64d1ded09..HEAD -- README.md apps/website/` is **empty** — the wave touched zero bytes of the publication surface; the drift was inherited from the 17-spec shift + wave-2/3 merges. The wave documented this as out-of-scope (k6 §6) but did not fix it. "Quality gates stay green" holds for the wave's OWN suites (parity + 173 new + 122 workflow-runner + guard families minus these 3); these 3 are a merge-readiness note for the controller, not a wave defect. |

All three are RECORD-level: no claim in the mandate was falsified, and none requires an on-branch
code change (F1/F2 are documented design scopes; F3 is a pre-existing controller publication
concern).

---

## 4. Re-stated verdict

| Mandate | Result |
|---|---|
| retrieval answers findings questions with findings | **PASS** — original probe: `{'finding': 41, 'code': 19}`, `control_db_evidence` at rank 4 |
| the finding layer is real (k1 default-on emit, k2 deterministic backfill, k6 witness) | **PASS** — durable artifact + registry row + retrievability, all independently reproduced |
| k3/k4 order + untyped resolution | **PASS** — findings > code for findings queries, code first for code queries, zero untyped in top-K |
| quality gates + parity suite | **PASS with F3 caveat** — parity + wave suites green; 3 pre-existing publication-count gates red |

**Release verdict: merge-ready to main.** The finding layer is real — a phase-objective query
returns the k2-backfilled `control_db_evidence` finding (with verdict, residuals, conclusion) in
its top results, and the witness finding lands and retrieves at rank 2. The three recorded
findings are accepted limitations / pre-existing drift, none falsifying the wave; F3 should be
resolved by the controller at the permanence gate as a pre-existing publication-surface drift,
not as a blocker on this wave.

---

## 5. LOG

```
k7_adversarial: PASS (merge-ready)
findings: F1 RECORD (k2 backfill corpus-sensitivity → parallel records, no supersede chain)
          F2 RECORD (k5 narrator forward-only, 0 live records; 17-spec shift not self-narrated)
          F3 RECORD (3 pre-existing publication/docs-drift gates red — README/index 185/187 vs 188,
                     D.labs.quality_frontier absent; wave touched zero publication bytes)
verification: original probe 60 selected {'finding':41,'code':19}, control_db_evidence at rank 4;
              witness finding at rank 2; code query top-3 code; 173+122+parity tests green;
              tests: 176 passed +1 pre-existing fail (guard families), fast path 543 passed +3 pre-existing fail
```
