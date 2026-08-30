---
status: accepted
---
# Evidence Restructure Verification

## Verdict

**FAIL.** The chronological two-corpus narrative, natural-behavior caveat, anchors, and JavaScript DOM contracts are present. The page is not data-safe because most `data-stat` keys do not resolve, one resolved key injects the wrong corpus count, a newly added provenance label conflicts with `data.js`, and five section kickers do not explicitly identify their Golden Circle role.

Audit basis: `firebase/public/evidence.html` at HEAD compared with HEAD~1, with `firebase/public/data.js` and `firebase/public/app.js` as the runtime data contract.

## Checks

### FAIL: Every `data-stat` key resolves

- `evidence.html` contains 27 unique source-level `data-stat` keys. Only 6 are present in the fixed `statMap` at `app.js:38-63`; 21 are unresolved.
- Resolved keys: `stories_total`, `story_sessions`, `variants`, `story_total_cost`, `reports`, and `sessions`.
- Unresolved keys: the 20 `rollup-{ds,g56,claude,all}-{cost,pass,think,loc,constraint}` keys at `evidence.html:326-330`, plus dynamically emitted `ci95` at `evidence.html:1387-1389`.
- The unresolved rollup fallbacks are not reliably current. For example, DeepSeek fallback values `87%`, `8.2%`, and `700` differ from values exposed in `data.js` (`84%`, `8.7%`, and `706`).
- `data-stat="sessions"` at `evidence.html:362` does resolve, but it replaces the precursor fallback `249` with `summary.sessions_total = 1,097`, which is the story-session total. The binding therefore corrupts the displayed precursor denominator at runtime.

### FAIL: Measured numbers and provenance are unchanged

- No pre-existing measured magnitude was replaced with a different magnitude, and no pre-existing provenance tag was reclassified by the rewrite.
- The strict diff check still fails because new measured/accounting claims and one new `[M]` tag were added. The `[M]` occurrence count changes from 11 at HEAD~1 to 12 at HEAD.
- The new story-cost labels at `evidence.html:114` and `evidence.html:790` describe `story_total_cost` as `[M]`, while the authoritative provenance is `summary._provenance.story_total_cost = "C"` at `data.js:32`.
- The added exact story cost `$288.6909` and approximations `7` and `122` do not alter prior values, but they are additions rather than preserved text. The cost provenance must be corrected to `[C]` before publication.

### PASS: Canvas and table-body IDs remain present

- Shared `app.js` directly references no canvas or tbody IDs.
- The inline JavaScript in `evidence.html` references 5 canvas IDs and 14 tbody IDs. All 19 targets are present.
- Canvas IDs: `gritMatrixChart`, `narrationChart`, `costBarChart`, `locVsCostChart`, and `snowballChart`.
- Tbody IDs: `narration-tbody`, `cost-ranking-tbody`, `ast-metric-body`, `sonar-quality-body`, `token-cost-tbody`, `tool-profile-body`, `rvs-body`, `drift-body`, `recovery-body`, `coupling-body`, `stability-body`, `cascade-body`, `sonar-impact-body`, and `operator-impact-body`.

### PASS: Natural-behavior caveat is explicit and correct

- `evidence.html:805` states: "We never instructed the models how many tests to write."
- The same callout says the difference is "natural, emergent behavior, not a failure to follow instructions" and explicitly distinguishes it from "instruction-following compliance."
- The caveat appears before the model comparison and separates authored tests, executed tests, self-test pass rate, and independent evidence at `evidence.html:807-811`.

### FAIL: Anchors resolve and Golden Circle kickers are explicit

- Anchor subcheck: **PASS.** The one static internal link, `href="#story-models"`, resolves. Shared `app.js` also creates TOC links for 44 identified headings; all 44 generated fragments resolve. Total runtime contract: 45/45 link occurrences resolve.
- Golden Circle subcheck: **FAIL.** The hero and principal narrative transitions explicitly use WHY, HOW, and WHAT, but 5 of 15 `.circle-label` section kickers name none of those roles: `ACT I - SCOPE AND EXPLORATION`, `ACT I - QUALITY AND MODELED EXTENSIONS`, `ACT II - INDEPENDENT MEASUREMENT`, `ACT II - SOLUTION BEHAVIOR`, and `ACT II - LONGITUDINAL EVIDENCE - 5 LINKED SESSIONS`.

### PASS: Chronology and both corpus overviews are present

- The hero ledger presents the archived single-session perturbation corpus first and the current multi-session story corpus second at `evidence.html:94-118`.
- Act I begins with the precursor at `evidence.html:129-133`; the bridge explains the inherited operators and recovery signals at `evidence.html:780-783`; Act II introduces the current story instrument at `evidence.html:786-790`.
- The page keeps the corpus denominators separate: approximately 227 classified runs, 224 game reports, and 201 Grit sessions for the precursor; 221 stories, 1,097 sessions, 7 models, and `$288.6909` for the story corpus.
- The epilogue explicitly discusses both corpora without pooling them into one dataset at `evidence.html:983-988`.

## Test Results

- `python3 -m pytest tests/`: **437 passed, 1 failed**. The failure is `TestResolveCwd.test_root_default`, which hard-codes a checkout basename ending in `ai-finops-framework`; this worktree ends in `feature_evidence-narrative`.
- The path-dependent test passes in a temporary checkout named `ai-finops-framework`.
- A full run in that correctly named checkout reached **437 passed, 1 failed** because the live Ollama-backed `test_analyze_session_from_file` returned an empty model response. That test passed in the original full run and failed on retries, indicating an external-service-dependent test rather than an evidence-page regression.
- Unscoped `python3 -m pytest` is not the project suite: it collects archived generated code under `experiments/results/reports/` and stops during collection with 688 import errors. The documented project scope is `tests/`.

## Summary

The rewrite succeeds as a chronological Golden Circle narrative and correctly frames test-count differences as unguided, emergent model behavior. It should not ship until all 21 orphaned `data-stat` keys are removed or wired, the precursor `sessions` binding is separated from the story total, story-cost provenance is changed from `[M]` to `[C]`, and every section kicker explicitly identifies WHY, HOW, or WHAT.
