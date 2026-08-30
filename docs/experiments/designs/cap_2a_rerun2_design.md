---
status: accepted
---

# cap_2a_rerun2 — design: fixing the verifier's over-prediction (measured, not guessed)

**Status: accepted** · Supersedes: `cap_2a_rerun@0.1` (verdict `docs/experiments/results/cap_2a_rerun.md`)
· Predecessor data: `cap_2a_rerun` p4 score JSON (`experiments/results/cap_2a_rerun_score_20260826T001107Z.json`, SHA256 `59bd15d8…`)

## 1. The measured defect chain (every link is evidence, not speculation)

The rerun produced 3 cells, all with `code_change_risk` minted (`risk_mint_rate=1.0` — the blocker
from campaign 1 is broken) and **0/3 proposals correct** (Wilson [0, 0.5615], descriptive-only).
The failure is systematic over-prediction: every cell's proposal demanded verification or rework
at depth 2–3; every realized outcome was `no_rework`. The chain, link by link:

| # | Link | Evidence |
|---|---|---|
| L1 | `_sonar_evidence` mints `new_critical_count = bugs + vulnerabilities` — **any severity** | `src/agentic_dynamics/runtime/workflow_runner.py` (`_sonar_evidence`, p1 of the rerun); `SonarMetrics` carries **counts only** (`sonar.py:334-336`: `bugs`, `vulnerabilities`, `code_smells`) — no severity dimension exists in the current fetch |
| L2 | `new_sonar_critical_count` fires on MAJOR test-style findings | p3b's `rework` proposal was driven by `python:S1244` ("do not compare floats with `==`") — a MAJOR **bug-type** finding, not a release-blocking defect (rerun p6 limitation 1) |
| L3 | `"new"` is not a delta | the count is the tree's count **at the analyzed revision**, not issues **introduced by the change** — `_sonar_evidence` analyzes only the phase commit; `compute_sonar_diff` (`sonar.py:162`) exists but is unused by the seam |
| L4 | the action tree trusts the inflated term | `verify_proposal.py:196-209`: `new_sonar_critical_count > 0 → rework/depth 3`; otherwise `risk ≥ VERIFY_RISK_THRESHOLD → verify/depth(_risk_depth)` — both fire on L1's inflated counts |
| L5 | `_risk_depth` thresholds (0.15 / 0.3) and `VERIFY_RISK_THRESHOLD` are **"deliberately not fitted to any data"** | `verify_proposal.py:143-151` docstring — the calibration campaign exists to fit them; the rerun produced the first data and the mapping was wrong in the same direction 3/3 times |
| L6 | cells had no realized-rework contrast | all 3 bespoke cells realized `no_rework` — the `rework` branch of the decision tree has **zero calibration data** |

The p6 re-stated verdict: 16 attacks safe, 2 accepted limitations — **severity conflation** (the
root cause of over-prediction, a documented `[P]` decision in the p1 implementation) and
single-agent adjudication. This design fixes the measurement and makes the verifier mapping the
campaign's *output* instead of an unexamined input.

## 2. Root causes → fixes (each fix is explicit, with acceptance tests)

### RC1 — severity conflation: `new_sonar_critical_count` counts ALL bugs+vulnerabilities

**Fix F1a (measurement, reducer v2):** the term is redefined as **severity-filtered AND
change-introduced**:

```
new_sonar_critical_count :=
  |{ i : i ∈ issues(after) ∧ i ∉ issues(before) ∧ i.severity ∈ {BLOCKER, CRITICAL} }|
```

- **Severity filter:** `BLOCKER` + `CRITICAL` only, across all rule types. A MAJOR finding —
  including bug-type rules like `python:S1244` — **never** counts. This is a `[P]` decision
  recorded in the reducer v2 docstring with this design as provenance.
- **Novelty rule:** issue identity is `(rule_key, file_path, line)`. An issue is "new" iff it is
  present in the after analysis and absent in the before analysis (same identity). A
  pre-existing BLOCKER that the change did not touch **never** counts. `compute_sonar_diff`
  (`sonar.py:162`) is the model — but it diffs counts; v2 must diff **issue sets by identity**,
  which requires per-issue records, not measures.

**Implementation option A — server-native (preferred):** SonarQube's `api/issues/search`
(`severities=BLOCKER,CRITICAL`, `sinceLeakPeriod=true` or a before/after comparison by issue
key) gives per-issue records with `rule, severity, component, line`. The seam fetches issues for
the parent revision and the phase revision and applies the identity rule.

**Implementation option B — client-side diff:** run `run_sonar_analysis` at the phase commit's
**parent** and the commit itself (the seam already materializes both trees —
`_run_change_analysis` computes `before_files`/`after_files`), extending `SonarMetrics` (or the
fetch) to carry per-issue records `(rule, severity, file, line)`, then apply the identity rule.

**The p0_research phase decides A vs B by probing the local server** (see §4) — this design
does not pre-commit; it pins the *semantics* and lets research pin the *transport*.

**Same treatment for the LSP leg:** `new_lsp_error_count` is redefined as diagnostics **errors
introduced by the change** — `run_diagnostics` at parent vs after, identity `(file, line, code)`,
severity-filtered to error-level. (`run_diagnostics` is cheap and runnable on both trees; the
rerun's cells had lsp `unavailable` because pyright is broken on this machine — p0_research also
pins which LSP tool is *actually available* here (mypy is supported by `lsp_diagnostics._parse_mypy`
and is pure-python; the [lsp] extra's pyright pin is broken on this box: its bundled nodeenv node
cannot load `libatomic.so.1`).)

### RC2 — "new" was never a delta

Folded into F1a (both options diff before/after by issue identity). **Acceptance test:**
a change that does not touch a file containing a pre-existing BLOCKER mints
`new_sonar_critical_count = 0`; a change that introduces one BLOCKER mints exactly 1.

### RC3 — the verifier mapping is an unfitted guess

**Fix F2 (the campaign's output, not an input):** `build_verify_proposal` and `_risk_depth` stay
**code-unchanged** this campaign — the v1 mapping is the treatment under test, and changing it
mid-campaign would void the calibration. Instead, p4/p5 must emit the **empirical calibration
table**:

```
per cell: (cell_id, action, depth, scope_size, code_change_risk, sonar/lsp term values,
           realized_outcome, realized_depth, hit)
risk→outcome:  risk buckets [0,0.15) [0.15,0.3) [0.3,∞)  vs  realized rework enum
finding→outcome: new_sonar_critical_count ∈ {0, ≥1}  vs  realized rework enum
```

and the p5 verdict must state the **fitted v2 mapping** (or "n insufficient", with the n
needed): e.g. "the empirical BLOCKER/CRITICAL count threshold above which rework was realized
is T; v2 should map risk r ∈ [a,b) → depth d; the MAJOR-only changes realized no_rework, so v2
maps them to verify-or-continue". The verdict is *prescriptive for the next campaign*, backed by
this campaign's rows.

### RC4 — decision tree trusts the inflated term

Fixed by F1a (the term can no longer inflate). **Acceptance test (regression, must exist before
p2):** a change whose only sonar finding is `python:S1244` (MAJOR, bug-type) mints
`new_sonar_critical_count = 0` and must NOT produce a `rework` proposal.

### RC5 — no realized-rework contrast in the dataset

**Fix F3 (cell design, deterministic stimulus control):** the bespoke cell spec becomes
**three deterministic variants**, one per outcome class:

| variant | stimulus (what the implement phase is told to do) | expected realized class |
|---|---|---|
| `clean` | add a small pure function + test (no defects) | `no_rework` |
| `critical` | add a function containing a **real BLOCKER/CRITICAL defect** (e.g. an unguarded `eval` of user input, or a division by an unvalidated value) + a test | `targeted_rework` |
| `style` | add a function with a MAJOR-style finding only (e.g. float `==` comparison) + test | `no_rework` (or `verification_only`) |

Each variant is a separate cell spec (`cap_2a_cell_clean.yaml`, `cap_2a_cell_critical.yaml`,
`cap_2a_cell_style.yaml`) sharing the same skeleton, so the campaign controls the stimulus
instead of hoping real cells vary. p2/p3 run one of each (min 3 cells, one per class). The
`critical` variant's realized outcome is adjudicated by the independent test_runner + a
post-hoc evaluator that verifies the defect is present (the outcome record is not the model's
narrative).

### RC6 — measurement honesty fallback (must be in the research doc)

If p0_research proves **neither** option A nor B is feasible on this machine (no server issue
API, no scanner to produce fresh analyses, no available LSP tool), the honest fallback is:
the sonar term is **dropped from risk** (weights renormalized over the remaining terms, [P]
change recorded with this design as provenance) AND the campaign measures the *reduced* verifier
+ records the capability gap. What is NOT allowed: redefining the term to the count-only
measure and pretending it is severity-filtered. The research doc states which option holds
before p1 writes code.

## 3. What "working" means — acceptance criteria for the rerun2 verdict

1. `risk_mint_rate = 1.0` on ran cells (carried from the rerun).
2. **Severity conflation is gone (the p6 limitation is fixed):** the regression test of §RC4
   exists and passes; no scored proposal was driven by a MAJOR finding.
3. **Novelty is a real delta:** the §RC2 acceptance test passes; the ledger's
   `new_sonar_critical_count` is the change-introduced BLOCKER/CRITICAL count.
4. **Outcome spread:** the dataset contains ≥ 1 realized `targeted_rework` cell and ≥ 1
   realized `no_rework` cell (the `rework` branch finally has calibration data).
5. **The calibration table is the verdict's core:** p4 JSON carries the §F2 table; p5 states the
   fitted v2 mapping or the exact n needed.
6. The p6 adversarial phase re-attacks severity conflation + novelty first — if either
   regresses, that is a FAILED finding, not an accepted limitation.

## 4. The campaign (`cap_2a_rerun2`) — phases, with the research phase as p0

### p0_research — DEEP RESEARCH BEFORE ANY CODE (the operator's explicit requirement)

A dedicated research phase that runs BEFORE implementation and whose deliverables **gate p1**:

- **R1 — Probe the local SonarQube server (`127.0.0.1:9000`):**
  - authenticate (the scanner env / `SONAR_URL_DEFAULT` credentials) and enumerate: does
    `api/issues/search` exist and return `rule, severity, component, line` per issue? Does it
    support `sinceLeakPeriod` / new-code filtering? Do existing analyses (the fetch-first
    cache) carry issue records, or measures only?
  - determine whether the server can list issues **per analysis** (before vs after revision).
- **R2 — Probe the scanner:** is `sonar-scanner`/`java` obtainable on this machine (apt, docker,
  existing binary)? If not, can a fresh analysis be produced at all? (The rerun's cells were
  `sonar=available` via fetch-first — the server already held analyses; R2 must establish
  whether NEW analyses can be produced for the rerun2 cells, or whether rerun2 must reuse the
  existing analysis shape.)
- **R3 — Probe the LSP tool:** which of `pyright` (broken: `libatomic.so.1`), `mypy`
  (supported by `_parse_mypy`, pure-python) is actually runnable here? Pin the tool.
- **R4 — Read the pinned semantics:** `code_change_facts.py` RISK_WEIGHTS + term definitions,
  `verify_proposal.py` (the v1 mapping is the treatment), `sonar.py` `compute_sonar_diff`,
  the rerun's p4 score JSON rows (the actual fact values per cell — the calibration table's
  first three rows already exist).
- **DELIVER (mandatory, committed before p1 starts):**
  `docs/experiments/designs/cap_2a_rerun2_measurement_design.md` containing, with no placeholders:
  1. the chosen transport (option A server-native, option B client diff, or the §RC6 fallback)
     with the exact API calls / function signatures and their outputs;
  2. the reducer v2 term definitions verbatim (the §F1a semantics), the [P] weight table
     (unchanged, or re-weighted only with this doc as provenance), and the version bump
     (`code_change_facts/v1 → /v2`);
  3. the LSP tool pin and the diagnostics delta rule;
  4. the three cell-variant specs' exact prompts (stimulus per class);
  5. the p4 calibration-table schema (JSON field names).
  **Hard rule: p1 MUST NOT start until the measurement design doc is committed.** If any
  deliverable is impossible (e.g. no server API, no scanner, no LSP tool), the doc states the
  §RC6 fallback and the campaign proceeds with the reduced verifier — recorded, not invented.

### p1_implement_measurement — implement the PINNED doc (no invention)

Implement exactly the measurement design doc: reducer v2 (severity filter + novelty rule),
the seam's before/after analyzer legs (deadline discipline carried from the rerun: sonar/lsp
legs under the 360s envelope), the LSP tool pin. VERIFY: the §RC4 regression test (S1244 →
`new_sonar_critical_count=0`, never rework), the §RC2 novelty test (pre-existing BLOCKER not
counted), the deadline tests, the full affected suite. LIVE PROBE (mandatory): run the `clean`
and `critical` cell variants with `--change-analysis`; the `critical` variant must mint
`new_sonar_critical_count ≥ 1` and the `clean` variant `= 0` (or the fallback state, recorded).
GUARD: without `--change-analysis` byte-identical to merged main.

### p2_measure_one_cell — E4, one cell (the `clean` variant) with the full seam

Same discipline as the rerun (candidate manifest FIRST, fresh worktree, unique FINOPS_CELL_ID,
measured cost, forecast budget labeled FORECAST). Proposals must emit; a refusal here is a p1
defect → fail the phase.

### p3_run_shadow_cells — outcome-spread cells (`critical` + `style` variants)

Run the `critical` and `style` variants (fresh worktrees, proposals recorded BEFORE outcomes,
independent outcomes from the test_runner + post-hoc evaluator, flagged cells, forecast-vs-
actual). The dataset must contain ≥1 realized `targeted_rework` and ≥1 `no_rework`.

### p4_score_hit_rate — fixed v0.2 SEMANTICS + the calibration table

Same scoring semantics verbatim (hard rule: no renegotiation) PLUS the §F2 calibration table
emitted as `calibration` in the score JSON: per-cell rows, risk→outcome buckets, finding→outcome
table, and the risk_mint_rate. Denomination discipline unchanged.

### p5_verdict — the gate + the fitted mapping

2b gate (hit-rate ≥ 0.6, Wilson, descriptive-only under n) PLUS the deliverable the rerun
lacked: **the fitted v2 mapping statement** — the empirical thresholds read off the calibration
table, or the exact n needed to fit them. Compare against the rerun explicitly: over-prediction
must shrink or the numbers say why not.

### p6_adversarial — re-attack the rerun's limitations first

Attack order: (1) severity conflation regressed? (S1244-only change re-triggering rework is a
FAILED finding); (2) novelty rule bypassed? (pre-existing BLOCKER counted as new); (3) the
calibration table's provenance (each row traceable to a p4 JSON field); (4) the rerun's carried
limitations (duplicate-qname CALLS, single-agent adjudication, canonical KB facts on killed
runs); (5) the usual suite (baselines, denominators, applied=false, credentials, hashes). Two
outputs (findings + known-safe), no bare PASS.

## 5. Explicit scope boundaries (what this campaign is NOT doing)

- NOT changing `build_verify_proposal`/`_risk_depth`/`VERIFY_RISK_THRESHOLD` (the v1 mapping is
  the treatment; F2 makes its fit the output).
- NOT reweighting RISK_WEIGHTS except under the §RC6 fallback (and then only with this doc as
  provenance).
- NOT renegotiating the p4 scoring semantics (hard rule carried from the rerun).
- NOT running 2b (the gate must clear first; 2b's randomized prerequisites are unchanged).

## 6. Data lineage

All claims in §1 cite the rerun's committed artifacts: `cap_2a_rerun_score_20260826T001107Z.json`
(SHA256 `59bd15d8…`), `docs/reviews/cap_2a_rerun_adversary.md`, `docs/experiments/results/
cap_2a_rerun.md`. The rerun's p4 JSON also carries the first three calibration-table rows
(risk 0.08/0.24/etc → realized no_rework ×3) — p0_research R4 reads them so rerun2's table
starts with its predecessors, not from zero.
