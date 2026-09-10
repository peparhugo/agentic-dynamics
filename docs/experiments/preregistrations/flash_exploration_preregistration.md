---
status: accepted
---

# flash_exploration — pre-registration

**Status: accepted · PRE-REGISTERED — committed BEFORE any build phase or cell runs.**
**Design (p0 research artifact):** `docs/experiments/designs/flash_exploration_design.md`
SHA256 `8eb31bbf894b54c718cda7a58b398280901e4e2d9471988a3ba4adf71f2037d8` (status
`proposed` until its `p0_research_verify` phase re-verifies every claim).
**Build spec:** `workflows/repository/flash_exploration_build.yaml` SHA256
`c0a86f09603d4fe0a03cb9362827a9996ff3c4ca8ac8188750b93fcc6506349e`.
**Base:** `feature/flash-exploration` at `bd5c530e2ee05f359eb759695af985a6cc7410ce`.
**Models (pinned):** author/subject `deepseek/deepseek-v4-flash`; build adversary
`openai/gpt-5.6-terra`.
**Ladder specs (to be pinned):** `flash_ladder_bare.yaml` / `flash_ladder_kb.yaml` — authored
after the build wave and pinned by SHA256 in a dated **addendum** to this file committed BEFORE
the first cell runs. The addendum may PIN, never redefine, §4.

> **The registration rule:** nothing in §0–§5 may be redefined after this commit. A deviation —
> a redefined margin, a dropped cell, a reseeded assignment, a post-hoc relabelled condition — is
> a **FAILED finding**, not a limitation.

## 0. Pinned machinery facts the wave depends on

All read at the pinned SHAs in design §0; `p0_research_verify` must confirm or correct them
before implementation (see design G-research).

1. **The commit hard-gate.** `retrieval.freshness_multiplier` excludes SOURCE/MEASURED/DERIVED
   on a mismatched non-empty `commit_sha` (`retrieval.py:548-554`), mirrored in the Chroma
   `where` (`retrieval.py:1726-1735`) and the lexical Cypher (`graph.py:1388-1392`). The change:
   **only SOURCE stays hard-gated.**
2. **Patterns are not projected.** 6 pattern facts, 0 `source_type="pattern"` artifacts, 0
   `pattern-content=` registry rows; the only shipped `rag_augment` spec lacks
   `pattern_projection: true` (gate at `retrieval.py:1297-1313`).
3. **Pattern churn.** `pattern.py:229` uses the caller's HEAD as `validity_window`; the
   fingerprint (`fact_ingestion.py:99-115`) does not exclude it → every commit supersedes every
   pattern fact. The fix: an evidence-stable digest.
4. **Augmentation is phase-only** (`workflow_runner.py:3022-3031`, `:3317-3345`), with the
   constructor failure text still unpersisted (`augment.py:205` → not in
   `PhaseResult.to_dict()`); the ladder must read `fallback_mode` from the ledger and treat
   `no_rag` KB cells as **condition-failed**, not as KB evidence.
5. **No diversity instrument**; `run.py` collides rep/variant artifacts and strips the solution
   (`run.py:404,460,507`).

## 1. Question and hypotheses

**Question.** Does `deepseek/deepseek-v4-flash`'s design behaviour move under (H1) divergence
framing, (H2) a larger thinking budget, or (H3) retrieval augmentation with the accumulated
knowledge base — measured as portfolio diversity across independent attempts, paired with
independently tested quality?

- **H1 (framing):** C1 raises mean pairwise composite diversity vs C0 (ΔD ≥ 0) without lowering
  quality (`Q_C1 ≥ Q_C0`).
- **H2 (thinking):** C2 shifts quality in either direction (two-sided); no diversity direction
  is predicted.
- **H3 (KB):** C3 raises quality (`Q_C3 ≥ Q_C0`) and does not raise diversity (ΔD ≤ 0
  predicted — retrieved patterns converge behaviour).
- **H0:** all conditions measure flat within the registered margin; recorded as a null with the
  instrument's sensitivity noted (not as evidence that creativity is immutable).

## 2. Build wave (before any cell)

Run the build spec as committed (8 phases: `p0_research_verify`, `p1_reachability`,
`p2_pattern_repair`, `p3_instrument`, `p4_verify`, `g5_adversarial`, `g6_test_gate`; fork-chained
flash author, terra adversary). Stop: `budget_usd: 12.0`, `max_attempts: 1`.
**No data-plane write (mint) and no ladder cell may run before:** (a) the design is marked
`accepted` (all §0 claims CONFIRMED), (b) `g5_adversarial` records either a clean sweep with
re-verification or findings that are fixed and re-verified, (c) `g6_test_gate` passes.

## 3. Data-plane act (separate from the build; required before cells)

After the build wave's candidate commit is known (call it `B`):

1. Mint + project patterns from the worktree at `B`:
   `python3 scripts/kb_produce_facts.py --reducer pattern/v1` (writes the live artifact dir and
   registry; XADDs to the stream). Expected: ≤6 one-time supersessions (the window value
   changed) and exactly 6 projection records.
2. **Convergence check:** a second `--dry-run` emits 0 supersessions and 0 projections.
3. **Cross-commit reachability probe** at a commit `X ≠ B`: in-process `retrieve()` with
   `pattern_projection=True` returns ≥1 `pattern` (`recovers_under_*`) and ≥1 `finding`;
   `pattern_projection=False` returns no pattern. If the probe fails, **STOP** — no cell runs.
4. Record the probe outputs + `B` in the campaign ledger
   (`experiments/results/flash_ladder/`). The ladder base SHA is `B`; every cell worktree is
   created from `B`, recorded before its run.

## 4. The ladder (registered before any cell)

**Task (pinned contract; exact prompt text pinned in the addendum):** implement a pure-Python,
stdlib-only package `taskman` with this behavioural contract — unique string ids;
`add_task(title, *, priority=3, tags=None, depends_on=None, due_at=None)`; `get_task`,
`update_task`, `delete_task` (delete refuses with `ValueError` while other tasks depend on it);
statuses `todo/doing/done` with `set_status`; `list_tasks(*, status=None, priority=None,
tag=None)` in a deterministic order (priority desc, then `created_at`, then id); `ready_tasks()`
= not-done tasks whose dependencies are all done, same deterministic order; dependency cycles
refused with `ValueError` leaving state unchanged; JSON `save(path)` / `TaskManager.load(path)`
round-trip; unknown ids raise `KeyError`; `priority ∉ 1..5` and unparseable `due_at` raise
`ValueError`. Anything else (data structures, modules, error messages) is the agent's design.
The contract tests live at `tests/flash_ladder/taskman_contract_test.py` on `B`; the prompt
forbids modifying test files.

**Conditions × reps = 12 cells (assignment table, in this order):**

| cell | condition | spec | invocation |
|---|---|---|---|
| C0-r1..r3 | neutral brief | `flash_ladder_bare.yaml` | default (`--thinking-effort high`, budget 0) |
| C1-r1..r3 | brief + divergence framing (enumerate ≥3 materially different designs; implement one) | `flash_ladder_bare.yaml` | default |
| C2-r1..r3 | neutral brief | `flash_ladder_bare.yaml` | `--thinking-budget-tokens 32000` |
| C3-r1..r3 | neutral brief, KB-augmented | `flash_ladder_kb.yaml` | `rag_augment: true`, `rag: {repository_id: agentic-dynamics, acl_scope: agentic-dynamics, pattern_projection: true}` |

Each cell: a fresh worktree at `B`, one `run_workflow` invocation, phases `generate` (agent) →
`g_test` (test phase, the contract file). Cell validity: the test file is byte-identical to
`B`'s (the scorer restores the pristine file from `B` and re-runs it — the in-run test phase is
a signal, the pristine re-run is the quality read). An invalid cell is re-run once; a second
invalidity is recorded and the cell is excluded (with its reason) from aggregates.

**Metrics (all computed by the scorer from immutable artifacts only):**

- `D_c` — primary: mean pairwise composite (`0.4·arch + 0.3·struct + 0.3·novelty`, the basin
  weights) across the valid attempts of condition c; `mean_novelty` and `distinct_fraction`
  (threshold 0.5) secondary.
- `Q_c` — valid attempts whose **pristine** contract test suite passes (0..3).
- medians of cost USD and output tokens per condition (from the cell ledgers); `fallback_mode`
  recorded per C3 cell.
- Bootstrap percentile CIs (10k resamples over attempts within condition) are reported but are
  **descriptive only** at n=3.

**Decision rule (registered):**

1. Compute ΔD_c = D_c − D_C0 and ΔQ_c = Q_c − Q_C0 for c ∈ {C1,C2,C3}.
2. **Escalate** (confirmatory grid, n=8, top-2 conditions = C0 and the condition with the
   largest |ΔD| or |ΔQ|, same specs, addendum-pinned) if any |ΔD_c| ≥ 0.10 or any |ΔQ_c| ≥ 1.
3. Otherwise declare the effects **flat within the registered margin**; the finding is the null
   plus the instrument's observed spread — no policy claim.
4. The `adapt` directive (coordinate descent, `highest_uncertainty`) names the factor the
   confirmatory grid should move first; it authors no policy arm in this wave.

**Stop:** ladder budget US$ 15.00; halt on any admission denial, on a failed §3 probe, or on the
build adversary's "must fix" verdict. Test failures are data, not errors.

## 5. Adversarial requirement (before any claim)

1. The build's `g5_adversarial` (terra) — falsify the three fixes (design §3 G-adversary).
2. A **score review** before any ladder number is published: an independent adversarial pass
   over the scorer's output — recalculate `D_c`/`Q_c` from the raw commits, attack cell
   validity, the pristine-test restoration, and the §4 decision rule's arithmetic; at least 3
   findings or a clean sweep with re-verification. A bare PASS is a failed review.
3. No result leaves this branch (website, policy, prose) before both reviews and the controller's
   permanence decision.

## 6. Deviation policy

Any post-commit change to §4 (a condition, a rep, a metric definition, the margin, the task
contract, a dropped cell) is recorded as a deviation in the verdict document with its reason,
and the affected comparison is reported as **exploratory**, never as the registered result.

## 7. Build continuation addendum (2026-09-10)

Two containerized-platform constraints were hit while executing §2 and repaired/worked around
**before any §4 cell runs**; the §4 ladder commitments are unchanged.

1. **Run-clone bookkeeping (fixed).** The orchestrator's post-phase gates/commits read the host
   worktree while sibling cells commit into the run's private clone, so `p4_verify` failed
   `NO_CHANGES` with an empty `pre_head` although its 728-line deliverable was committed in the
   clone. Repaired in `src/agentic_dynamics/runtime/workflow_runner.py` (post-phase git
   operations and the commit-msg hook now resolve the run clone from `FINOPS_RUN_CLONE` when
   containerized) with a regression test; commit `5035f849c`.
2. **Adversarial scope (spec correction).** `adversarial_readonly` binds the run clone
   READ-ONLY (`scripts/fleet/spawn_wrapper.py:138-139`), so a containerized adversarial phase
   cannot deliver its finding doc; the original spec's `g5_adversarial` scope is corrected to
   `implementation` in the continuation spec (prompt unchanged). The pinned original spec is
   **not** edited.

**Continuation spec:** `workflows/repository/flash_exploration_build_resume.yaml` SHA256
`d09a175ab37233e1f2286c6670b718f2028d1db07ea031df85b446cdc10df22c` — phases `g5_adversarial`,
`g6_test_gate`, dispatched against branch HEAD `5035f849c`. The p0–p4 evidence is the harvested
chain on the branch plus the original run's ledger; the continuation's ledger covers g5/g6. No
§4 metric, condition, rep, margin, or decision rule changes.

## 8. Second continuation addendum + evidence-class contract (2026-09-10)

The second adversarial review (`docs/reviews/flash_exploration_adversarial.md`, against
`f481c8d4e`) returned FAIL with findings F1–F5; both remediation rounds are recorded in
`docs/reviews/flash_exploration_remediation.md` (round 1: F3/F4/F2a/F5-F6; round 2: F1
comment-stripping, F2/F4 scorer seam, F3 host-side probe runner + artifact, F5 corrections).

**The decidable evidence contract** (the reason the earlier reviews could never pass, now
written down): cells run on `fleet-net`; `neo4j` (`infrastructure_kb-neo4j_1`) is on that
network, so the **live lexical probe is reproducible in-cell** at `bolt://neo4j:7687` (never
`localhost`). `chromadb` runs on `infrastructure_ai-infra` and is **not reachable from cells by
network design**, so the **dense live evidence is host-side**: the committed runner
`scripts/probe_retrieval_reachability.py` and its attached output
`docs/reviews/flash_exploration_retrieval_probe.json`. A review verifies the runner's code path
and the artifact's internal consistency; it does not demand in-cell reproduction of a network
boundary. The live DERIVED-pattern query and the second live dry-run (F2b) require the
controller-approved mint and are the first post-mint acts — out of scope for the build review.

**Continuation spec:** `workflows/repository/flash_exploration_build_resume2.yaml` SHA256
`cebc81dcc70694d4e1d290abfe56a7c5d7412d3fe01a3320aa3285f8c383761d` — phases `g5_adversarial`
(corrected review contract, terra) + `g6_test_gate` (six suites, including the new
`test_run_result_shape.py` and `test_portfolio_scorer.py`), dispatched against the branch HEAD
that carries both remediation rounds. No §4 metric, condition, rep, margin, or decision rule
changes; on a clean g5 + g6 the wave proceeds to the one-time pattern mint (AIO data-plane act)
and then the ladder.

## 9. Third continuation addendum (2026-09-10)

The third adversarial review (against `1b7ca911d`) returned FAIL with findings F1–F4
(interior-whitespace gaming in non-Python; omitted/malformed `solution_code` silently unscored;
probe artifact without candidate provenance or per-leg counts; a Probe 5 doc contradiction).
Remediation round 3 closed all four at commit `10c1f3519` (see
`docs/reviews/flash_exploration_remediation.md` §Remediation round 3): canonical/line_form
normalization split, `excluded_invalid_source` accounting, provenance-bound probe artifact with
direct `dense_hits`/`lexical_hits`, and a regenerated Probe 5 transcript.

**Continuation spec:** `workflows/repository/flash_exploration_build_resume3.yaml` SHA256
`05154bbd149e42c931ad238dab521dbdc82cd21288077af669c8f51ad6a5d0a5` — phases `g5_adversarial`
(terra; same decidable evidence classes as §8, plus explicit checks for the round-3 fixes and a
**no-padding** rule: every genuine finding reported, a verified clean sweep a valid outcome) +
`g6_test_gate` (six suites). No §4 metric, condition, rep, margin, or decision rule changes.
On a clean g5 + g6 the wave proceeds to the one-time pattern mint (AIO data-plane act, which
supplies F2b's live DERIVED evidence) and then the ladder.

## 10. Fourth continuation addendum (2026-09-10)

The fourth adversarial review (against `fd97a2ea9`) returned FAIL with findings A1–A3: false
zeros from C preprocessor directives and JS template literals in the non-Python normalizer
(a regression from round 3), graph **expansion** bypassing the SOURCE commit gate (a path the
earlier reachability fix missed), and a non-runnable/stale Probe 5 transcript. Remediation
round 4 closed all three at commit `693ded194` (see
`docs/reviews/flash_exploration_remediation.md` §Remediation round 4): preprocessor-aware,
backtick-aware comment scanning; `freshness_multiplier` applied to every expanded neighbor;
Probe 5 rebuilt as a runnable command + separate output fence, and the probe artifact
regenerated at `693ded194`.

**Continuation spec:** `workflows/repository/flash_exploration_build_resume4.yaml` SHA256
`0949e00da05361901da72abdee4367a683a0b7cbf7d3778427430f4c800031ab` — phases `g5_adversarial`
(terra; same decidable evidence classes as §8–§9, with explicit A1/A2/A3 checks and the
no-padding rule) + `g6_test_gate` (six suites). No §4 metric, condition, rep, margin, or
decision rule changes. On a clean g5 + g6 the wave proceeds to the one-time pattern mint (AIO
data-plane act, supplying F2b) and then the ladder.
