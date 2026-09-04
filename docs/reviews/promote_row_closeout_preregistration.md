---
status: accepted
kind: preregistration
spec: promote_row_closeout
phase: p0_pin_defect
generated_at: 2026-09-04T14:22:12Z
---

# Preregistration — `promote_row_closeout` (p0_pin_defect)

**The house pin convention.** This document is written BEFORE any implementation phase of the
wave executes (`a1_close_row_on_success`, `a2_stale_candidate_guard`, `g9_adversarial`,
`g10_test_gate`). Its purpose is twofold, and both halves are load-bearing:

1. **Anchor the run to exact bytes.** A workflow spec is a mutable file. Recording the spec's
   SHA256 makes the mandate immutable *by reference*: any divergence is detectable by re-running
   one command.
2. **Verify the premises, do not assert them.** The three defect edges this wave closes are
   stated as current-state claims in the spec's `question`/`context.finding` block (authored
   2026-09-04 from the session-close record of `2026-09-04-aio-graph-leg-closeout`): (1) ROW
   LEFT OPEN — promote.py's success path performs no control-db transition; (2) EVIDENCE ON
   MAIN — commit `3e40537e2` is tree-identical to `f0c612516` and the two graph_leg_closeout
   control rows were cancelled by hand (actor `controller-close-out`); (3) NO STALE GUARD —
   `promote --dry-run` does not refuse a candidate whose tree equals base head. This phase
   re-derives each edge against the actual repository at the pin, and records the commands that
   produced the evidence, so a reader can reproduce every finding without trusting this
   document. **An edge that does not hold is a FAILED finding.** THREE attempts max per claim,
   then record the deviation and FAIL — never loop.

No claim below was accepted on the spec's authority. Every edge was verified against the code
at the worktree HEAD and the machine-local control state at the main checkout. All three edges
**PASS** — each reproduced the spec's current-state claim with measured evidence. The evidence
is quoted so the adversarial phase (g9) can re-run every probe.

---

## 1. The pin

| Field | Value |
|---|---|
| Spec path | `workflows/repository/promote_row_closeout.yaml` |
| Spec **SHA256** | `7be05e606b94fe179026f736cae10b3808bdd9b29c0eb339a324e41ae2d036b3` |
| Spec size | 12,032 bytes |
| Worktree HEAD (git sha) | `752ba96b9b0e18d873f0c518474d7ecf7c7542cf` |
| HEAD subject | `spec: promote_row_closeout — promote closes its own control row + stale-candidate guard (task-card phases)` |
| HEAD committed | 2026-09-04 16:17:34 +0200 |
| Worktree | `/tmp/wt_promote_row_closeout` — branch `feature/promote-row-closeout` (git worktree of the main checkout; common dir `/home/drseuss/ai-finops-framework/.git`) |
| Main checkout | `/home/drseuss/ai-finops-framework` — branch `main`, HEAD `35e4c3e9fc1e7f4c62dda2e13f0f00e04b146c7c` |
| main ↔ worktree | `git diff --stat main...HEAD` = `workflows/repository/promote_row_closeout.yaml` ONLY (+230). `scripts/promote.py` is byte-identical to main's, so edge 1 verifies the behavior main's promoter will keep until a1 edits it. |
| Working tree | clean (`git status`: nothing to commit) |
| Control db | `/home/drseuss/ai-finops-framework/experiments/results/control/control.db` present (machine-local, gitignored) — the run_transitions/promotions reads in §2.2 |
| Pinned at | 2026-09-04T14:22:12Z |

Reproduce the pin — these are the EXACT bytes the wave executes:

```bash
sha256sum workflows/repository/promote_row_closeout.yaml
# 7be05e606b94fe179026f736cae10b3808bdd9b29c0eb339a324e41ae2d036b3
git rev-parse HEAD          # (in the worktree)
# 752ba96b9b0e18d873f0c518474d7ecf7c7542cf
```

If either value differs when `a1_close_row_on_success` (or `g9_adversarial`) runs, the spec was
edited mid-run and the mandate this document pins is no longer the mandate being executed — a
reportable finding in itself.

**Spec shape at the pin** — five phases (three `kind: agent` in `implementation` scope +
`g9_adversarial` on `openai/gpt-5.6-terra` + `g10_test_gate`). Single factor: `model =
deepseek/deepseek-v4-flash`. Stop budget $6.00, `max_attempts: 1`.

| # | Phase | kind | scope | notes |
|---|---|---|---|---|
| 0 | `p0_pin_defect` | agent | `implementation` | **this phase** — the preregistration |
| 1 | `a1_close_row_on_success` | agent | `implementation` | promote closes its own control row (`promotable -> merged` via `ControlDB.transition_run`) |
| 2 | `a2_stale_candidate_guard` | agent | `implementation` | promote REFUSES a tree-identical candidate (exit 20, reason names the merged sha) |
| 3 | `g9_adversarial` | agent | `adversarial_readonly` | independent pro reviewer on terra (`requires_deliverable`) |
| 4 | `g10_test_gate` | test | `implementation` | `test_promote.py`, `test_control_db.py`, `test_control_status.py`, `test_workflow_runner.py`, `test_doc_lifecycle.py`, `test_agent_config_render.py`, `test_script_classification.py` |

---

## 2. Verified edges (the three defect claims)

Each edge is stated as the spec's `question`/`context.finding` states it, then **independently
derived** against the repository at `752ba96b9…`. "Method" is the command actually run;
"Evidence" is its actual output. No finding below was accepted on the spec's authority.

### Edge 1 — ROW LEFT OPEN: promote.py's success path performs NO control-db transition → **PASS**

*Method.* Read the success path, then token-grep the whole file for the control-db surface
(`ControlDB`/`transition_run`/`run_transitions`/`control_db`/`control.db`) and for the
`promotions` table a1 will populate:

```bash
sed -n '325,352p' scripts/promote.py        # the post-push success path
python3 - <<'EOF'
import pathlib
for tok in ("transition_run", "ControlDB", "control_db", "run_transitions",
            "control.db", "promotions"):
    n = sum(1 for ln in pathlib.Path("scripts/promote.py").read_text().splitlines() if tok in ln)
    print(tok, n)
EOF
```

*Evidence.* The success path after the push (`push(...)` at `:329`) is:

```
329:    pushed = push(workdir, base, subject, candidate)
330:    print(f"promote: pushed {base} → {pushed[:12]} (squash of {candidate[:12]})")
...
336:    _emit_best_effort(
337:        "promote decision record",
338:        lambda: record_decision(_promote_decision_record(args, ledger, candidate)),
339:    )
...
343:    _emit_best_effort(
344:        "promote act",
345:        lambda: emit_act(...),
352:    )
```

The token grep over the file (`scripts/promote.py`, 458 lines) returns **0 hits for every
token** — `transition_run`, `ControlDB`, `control_db`, `run_transitions`, `control.db`,
`promotions` are each absent from the entire file. promote.py never imports
`agentic_dynamics.control.control_db`; its only emission imports are `control.aio_emission`
(`:156,164` — the a5 decision observation + act actuation) and `knowledge.decision_ingestion`
(`:194` — the s2b decision record). The ledger is READ (`_load_ledger`, `:358`) and never
written.

*Reading.* The claim holds. After the push lands, the ONLY state writes are the three
best-effort knowledge-base emissions — the s2b decision record and the a5 act (the a5 decision
observation precedes the push at `:325-327`) — each swallowing its own failure
(`_emit_best_effort`, `:134-145`). No code path calls `ControlDB.transition_run`, so the run's
control row is untouched by a successful promotion: `promotable` rows stay `promotable` and the
packet keeps advertising them. This is precisely the hole `a1_close_row_on_success` closes.

### Edge 2 — EVIDENCE ON MAIN: `3e40537e2` ≡ `f0c612516` tree-identically; the two rows were cancelled by hand → **PASS**

*Method.*

```bash
git log -1 --format='%H %s' 3e40537e2
git merge-base --is-ancestor 3e40537e2 main && echo "on main"
git log -1 --format='%H %s' f0c612516
git diff --quiet 3e40537e2 f0c612516; echo "diff-quiet exit=$?"
# run_transitions read (control db, read-only):
python3 - <<'EOF'
import sqlite3
con = sqlite3.connect("file:/home/drseuss/ai-finops-framework/"
                      "experiments/results/control/control.db?mode=ro", uri=True)
for r in con.execute("SELECT run_id, from_state, to_state, at, reason, actor "
                     "FROM run_transitions WHERE actor='controller-close-out'"):
    print(r)
print("graph_leg promotions rows:",
      list(con.execute("SELECT p.* FROM promotions p JOIN runs r ON r.run_id=p.run_id "
                       "WHERE r.spec_name LIKE '%graph_leg%'")))
EOF
```

*Evidence.*

```
3e40537e2c2f0dfe2dfce340d897b7cf08cd78ba [workflow] g9_adversarial — close the graph-leg open threads on feat
IS-ANCESTOR exit=0
f0c612516bd1bd0b34b7f64cf32a87f93cfe9102 [workflow] g9_adversarial — close the graph-leg open threads on feat
diff-quiet exit=0

('run-f822d6ecd88b', 'promotable', 'cancelled', '2026-09-04T14:16:25.829770Z',
 'stale post-promote row: content already merged to main as 3e40537e2 (tree-identical); '
 'promote.py does not close its own rows', 'controller-close-out')
('run-426ca19fe025', 'promotable', 'cancelled', '2026-09-04T14:16:25.831460Z',
 'stale post-promote row: content already merged to main as 3e40537e2 (tree-identical); '
 'promote.py does not close its own rows', 'controller-close-out')
graph_leg promotions rows: []
```

The two cancelled runs in the `runs` table: `run-f822d6ecd88b` (`graph_leg_closeout`,
`candidate_sha` `4adae17e0`, parent of `run-57b8ec179e30`) and `run-426ca19fe025`
(`graph_leg_closeout`, `candidate_sha` `f0c612516`) — both reached `promotable` via the
orchestrator's `workflow run ended (succeeded)` transition (ids 68 and 70) and were cancelled
by hand at `14:16:25Z` with the reason quoted above. `feature/graph-leg-closeout` still exists
and contains `f0c612516`.

*Reading.* The claim holds in full. Commit `3e40537e2` is on `main` (is-ancestor exit 0), its
subject names the graph-leg g9 close-out, and `git diff --quiet` between it and `f0c612516`
exits 0 — the promoted-on-main tree and the feature-branch tip tree are byte-identical. The two
`graph_leg_closeout` runs that carried that content both sat `promotable` AFTER the content was
already on main, until a human (actor `controller-close-out`) cancelled them — the
`run_transitions` rows (ids 71, 72) are the class proof. The `promotions` table (the row-close
destination a1 populates) holds **zero** graph_leg rows — no promotion ever recorded its row.
The two cancellation reasons even name the defect verbatim: *"promote.py does not close its own
rows"*.

### Edge 3 — NO STALE GUARD: `promote --dry-run` against a candidate whose tree equals base head does NOT refuse → **PASS**

*Method.* A synthetic reproduction of the graph-leg shape, built in a scratch repo (no remote,
no push — dry-run writes nothing): base `main` advanced to tree `T`; candidate branch `C` forks
from an OLDER base commit and re-commits exactly tree `T`, so `C` is not an ancestor of `main`,
its tree equals `main` head's tree, and `diff <merge-base>..C` is non-empty (a real promotion
would push a duplicate squash). A ledger bound to `C` (phases `ok` + `commit_hash`) makes the
candidate pass every pre-push gate. Then `promote --dry-run`.

```bash
git -C repo rev-parse 'main^{tree}'           # 24563c9e05a53252b62b4c19557132b56b664f34
git -C repo rev-parse 'stale-candidate^{tree}' # 24563c9e05a53252b62b4c19557132b56b664f34
python3 scripts/promote.py --spec stale_tree_probe --workdir repo \
    --ledger ledger.json --dry-run --operator probe-operator
echo "PROMOTE EXIT=$?"
```

*Evidence.*

```
24563c9e05a53252b62b4c19557132b56b664f34   # main^{tree}
24563c9e05a53252b62b4c19557132b56b664f34   # stale-candidate^{tree}
promote: verified candidate 25cbc386dbf5 (1 phase(s), $0.5000) → main as '[workflow] stale_tree_probe'
promote: dry-run — verified, would squash-merge + push (nothing written)
PROMOTE EXIT=0
```

The candidate's tree hash equals the base head's tree hash exactly, and `promote --dry-run`
declares it **verified** and exits 0 — "would squash-merge + push". (The non-dry-run path would
only later hit the empty-`merge_base..HEAD`-diff refusal at `promote.py:316-318`, which is the
WRONG comparison for the stale case: a re-presented post-promote candidate whose history still
differs from `merge-base` — the graph-leg topology — has a NON-empty `merge_base..HEAD` diff and
would push a duplicate squash, not refuse. The guard a2 adds must compare the candidate tree
against the base HEAD tree, which today no code path does.)

*Reading.* The claim holds. There is no stale-candidate guard today: a candidate whose tree is
already on main (the run is a post-promote leftover) passes `--dry-run` verification with exit 0
and the "would squash-merge + push" plan — exactly the state that stranded the graph-leg rows.

---

## 3. Supporting current-state facts (verified, not mandated)

These are not among the three mandated edges, but the later phases depend on them. They were
cheap to verify, so they were verified.

| Assertion | Method | Result |
|---|---|---|
| promote.py at this HEAD == promote.py on main | `git diff main...HEAD --stat` | **PASS** — the branch diff vs main is ONLY `workflows/repository/promote_row_closeout.yaml` (+230); the fix surface (`scripts/promote.py`) is unchanged from main, so a1/a2 edit the live promoter |
| The gate suites exist and cover promote | `ls tests/test_promote.py` | **PASS** — `test_promote.py` exists (the a1/a2 gates); `test_control_db.py`, `test_control_status.py` also present for the g10 list |
| The run rows carry the ledger identity a1 must bind on | `runs.run_id` + ledger `spec_id`/`run_id` fields | **PASS** — the `runs` table keys by `run_id` (`run-426ca19fe025`…); the ledger files under `experiments/results/workflows/graph_leg_closeout/` carry the run's spec identity, the resolution seam `_load_ledger` already uses (`:358-370`) |
| The legitimate transition API exists for a1 | read `src/agentic_dynamics/control/control_db.py` `transition_run` | **PASS** — `transition_run` is the API `approve_workflow.py:73,104` and `control_sweep_zombies.py` already call; the sweep's own docstring confirms it is "the same legitimate API governed by ALLOWED_TRANSITIONS" |

---

## 4. Deviations recorded against the pinned bytes / mandate

None. All three mandated edges hold exactly as stated against the actual repository at
`752ba96b9…`; no claim required more than one reproduction attempt. The only nuance — the
empty-`merge_base..HEAD` refusal at `promote.py:316-318` being the wrong comparison for the
stale class — is noted inside Edge 3's reading as guidance for `a2`, not a falsified edge.

---

## 5. Scope compliance

The phase mandate (p0_pin_defect prompt): write this preregistration carrying the pin + the
three defect edges verified against the actual repo, then commit.

- **Created:** `docs/reviews/promote_row_closeout_preregistration.md` (this file) — the wave's
  pin, in the `/tmp/wt_promote_row_closeout` worktree at the spec-commit tip.
- **Edited:** nothing else. Every verification above is read-only — `sha256sum`, `git rev-parse`,
  `git diff`, `git ls-tree`, `git log`, the read-only SQLite open (`mode=ro`) of the control db,
  and a synthetic dry-run in a throwaway scratch repo under `/tmp/opencode/promote_prereg/`
  (deleted after use — no remote, no push, nothing written by promote). No `_gen_instructions.py`
  render was invoked; no control-db write was made; no model call was made.
- **Not done, deliberately:** the spec's prose was left as authored — repairing its
  `current_state` would edit the very spec whose SHA256 this document pins.

---

## 6. Verdict

| # | Mandate edge (as stated) | Verdict |
|---|---|---|
| 1 | ROW LEFT OPEN — promote.py's success path performs NO control-db transition | **PASS** — post-push steps (`:329-352`) only emit the s2b decision record + a5 act (best-effort KB writes); zero hits for `transition_run`/`ControlDB`/`control_db`/`run_transitions`/`control.db`/`promotions` in the whole file |
| 2 | EVIDENCE ON MAIN — `3e40537e2` tree-identical to `f0c612516`; both rows cancelled by hand (actor `controller-close-out`) | **PASS** — `git diff --quiet` exit 0; run_transitions ids 71/72 cancel `run-f822d6ecd88b` + `run-426ca19fe025` (`promotable → cancelled`, reason: "promote.py does not close its own rows"); zero graph_leg rows in `promotions` |
| 3 | NO STALE GUARD — `promote --dry-run` does not refuse a candidate whose tree equals base head | **PASS** — synthetic stale candidate (tree hash `24563c9e…` == base head) → `verified candidate … would squash-merge + push`, exit 0 |

**Pin verdict: 3/3 edges hold exactly as stated — the defect class is proven against the actual
repo.** promote.py leaves its promoted run rows `promotable` forever (edge 1), the graph-leg
evidence on main shows the class manifesting in production with manual `controller-close-out`
cancellations as the only clean-up (edge 2), and no stale guard refuses a tree-identical
re-promotion today (edge 3). The mandate is anchored: spec SHA256
`7be05e606b94fe179026f736cae10b3808bdd9b29c0eb339a324e41ae2d036b3` at git
`752ba96b9b0e18d873f0c518474d7ecf7c7542cf`. `a1_close_row_on_success` (implementation) may
proceed.
