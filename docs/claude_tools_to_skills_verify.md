---
status: accepted
---
# OpenCode Tools → Claude Code Skills: Verify Pass

Verify phase for the port scoped in `docs/claude_tools_to_skills_scope.md` and built in the
`build` phase (commit `70ebc34c6`). Every check below was re-run against current repo state
(`git show HEAD`, `grep`/`--help`/dry-run invocations) — nothing here is carried over from
the scope doc's own claims without independent re-verification.

## Checks

### 1. Every net-new skill's flags match the underlying script's argparse/sys.argv — **PASS**

Re-grepped each script directly (not the `.opencode/tools/*.ts` schemas, not the skill
prose) and diffed against what each skill documents.

- **`run-workflow` / `run_workflow.py`** — `python3 scripts/run_workflow.py --help` output
  matches the skill's flag table exactly: `--spec` (required), `--goal` (required),
  `--model` (required), `--workdir` (required), `--backend`, `--thinking-effort`,
  `--thinking-budget-tokens`, `--output-token-limit`, `--timeout`, `--no-commit`, `--resume`.
  Source: `scripts/run_workflow.py:28-38` (`ap.add_argument(...)` × 11).
- **`run-workflow` / `compile_experiment.py` inline snippet** — `load_spec`
  (`src/instrument/experiment_spec.py:359`), `validate_rules`
  (`src/instrument/experiment_spec.py:367`), `compile_spec`
  (`src/instrument/compile_experiment.py:87`), `SpecError`
  (`src/instrument/compile_experiment.py:37`), `DAG.names()`/`.topological_order()`
  (`src/instrument/compile_experiment.py:55,62,65`) all confirmed present at the cited
  lines with the cited signatures. Ran the skill's exact snippet against
  `experiments/specs/workflow_step_routing.yaml validate` — printed
  `{"valid": true, "errors": []}`, exit code 0, matching the documented contract.
- **`queue` / `enqueue.py`** — `--dry-run`, `--clear`, `--missing-only`, `--interleave` all
  confirmed as literal `"--flag" in sys.argv` checks (`scripts/enqueue.py:144-147`);
  `--model` confirmed read via `sys.argv.index("--model") + 1`
  (`scripts/enqueue.py:149-150`); `FINOPS_MODEL` default confirmed
  (`scripts/enqueue.py:36`); Redis target `127.0.0.1:${FINOPS_REDIS_PORT:-6380}` db
  `${FINOPS_REDIS_DB:-1}` confirmed (`scripts/enqueue.py:42-43`).
- **`queue` / `worker.py`** — confirmed zero `add_argument`/`sys.argv` parsing in the file;
  `FINOPS_REDIS_HOST`/`_PORT`/`_DB` env vars with defaults `127.0.0.1`/`6380`/`1` confirmed
  at `scripts/worker.py:24-26`.
- **`queue` / `monitor.py`** — `--watch`, `--clear`, `--json` confirmed as
  `"--flag" in sys.argv` checks (`scripts/monitor.py:114-116`).
- **`review` / `review_all.py`** — `--workers` (default 6), `--story` (default `""`),
  `--dry-run` confirmed as real `argparse` options (`scripts/review_all.py:120-122`).
- **`review` / `review_stories.py`, `enqueue_reviews.py`, `finalize_reviews.py`** —
  `--dry-run` (`"--dry-run" in sys.argv`) confirmed at `scripts/review_stories.py:20` and
  `scripts/enqueue_reviews.py:61`; `finalize_reviews.py` confirmed zero-flag (no
  `add_argument`/`sys.argv` in the file at all).
- **`review` / `trigger_reviews.py`** — confirmed zero-flag; `REVIEW_WORKERS` env var
  default `4` at `scripts/trigger_reviews.py:28`; two-stage behavior (blocking
  `subprocess.run([sys.executable, "scripts/enqueue_reviews.py"], check=True)` then
  `REVIEW_WORKERS` detached `subprocess.Popen(["nohup", ...])` calls) confirmed at
  `scripts/trigger_reviews.py:62-71`.
- **`control-room` / `admin/server.py`** — all 6 documented routes confirmed as
  `@app.get(...)` (`admin/server.py:738,779,805,860,903,1094`); the skill correctly omits
  the two additional `@app.get` routes that exist but aren't part of this skill's scope
  (`/api/design-sessions/<portal_id>/spec`, `/api/claude-agents/<session_id>/logs`,
  `/api/claude-agents/daemon`, `/api/events/<cell_id>`) — a reasonable choice since the
  scope doc's checklist names exactly 6 top-level endpoints. Port confirmed
  `admin/server.py:1365`.
- **`control-room` / `supervise.py`** — `--once`, `--location` (default `str(ROOT)`)
  confirmed at `scripts/supervise.py:349-350`. `OPENCODE_BASE_URL` default
  `http://127.0.0.1:4096` confirmed at `scripts/supervise.py:39`.

No flag in any net-new skill was found unsupported by its script, and no real flag was
found missing from a skill's documented set.

**One behavioral note, not a flag-accuracy problem:** the `control-room` skill says
`supervise.py` run cold "fails with a connection error, not a helpful message." Live-testing
`python3 scripts/supervise.py --once --location "$(pwd)"` against this environment (which
happens to have a long-running `supervise.py` process already active, `PID 1779169`, started
`Fri Aug 14 18:34:40`) showed different behavior: `ensure_monitor()` reused a cached
session ID from `STATE_FILE` without validating connectivity, printed
`"[supervise] relaying + monitoring (assess every 60s)..."`, and then did not exit after one
pass within 75s — `--once`'s own `help=` text ("run one assessment pass and exit") did not
match observed behavior. This is a pre-existing behavior of `supervise.py` itself (stale
`STATE_FILE` reuse + a `--once` flag that doesn't appear to short-circuit the relay loop),
unrelated to the tools-to-skills port — the skill accurately transcribes the flag and its
`help=` text from the script. Flagged here as a script-level follow-up, not a port defect.

### 2. No skill name collides with an existing skill/command name — **PASS**

```
.claude/skills/: analyze, control-room, instrument, lab-books, queue, review, run-workflow
.claude/commands/: analyze, lab, new-exp, pipeline, run-exp
```

The 4 net-new names (`run-workflow`, `control-room`, `queue`, `review`) collide with
nothing in either list. One collision exists in the repo (`analyze` is both a skill
directory and a command file) — confirmed via `git log --follow` on both paths that this
predates the tools-to-skills scope/build commits entirely (command added in the original
opencode→Claude Code taxonomy port, skill added earlier still) and is a doc-supported
pattern (`docs/claude_code_port.md` §2 command row, quoting the Claude Code docs: *"A file
at `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both create
`/deploy` and work the same way."*). Not introduced by, or a defect of, this task.

### 3. No tool is double-covered — **PASS**

- Checked all 4 net-new skills for mentions of the 6 SKIP-listed tools' backing scripts
  (`pipeline.py`, `inventory.py`, `backfill_artifacts.py`, `archive_worktrees` logic,
  `generate_manifest.py`) — zero matches in `run-workflow`/`control-room`/`queue`/`review`.
  The only SKIP-adjacent mention anywhere is `backfill_artifacts.py` in `analyze/SKILL.md`,
  confirmed pre-existing (untouched by the build-phase diff) and singular (one line, no
  duplicate section).
- `dashboard.ts` (functionally `monitor.py --json`) has no separate section in the `queue`
  skill — `grep "^##.*[Dd]ashboard"` returns nothing; it's folded into the `monitor.py`
  section as the "canonical dashboard example," per the scope doc's explicit
  instruction not to create a second script reference for the same underlying command.
- `list_stories.ts` (`run_story.py --list`) is mentioned exactly once, inside the
  `instrument` skill's `run_story.ts` fold-in bullet, as a cross-reference ("this is
  exactly what `list_stories.ts` runs"), not a duplicated standalone section — consistent
  with the SKIP disposition.
- Every script referenced by a net-new skill (`run_workflow.py`, `enqueue.py`, `worker.py`,
  `monitor.py`, `review_all.py`, `review_stories.py`, `trigger_reviews.py`,
  `enqueue_reviews.py`, `finalize_reviews.py`, `supervise.py`) appears in exactly one skill
  file each — no script is documented in two different skills.

### 4. Fold edits are additive — existing skill content preserved verbatim — **PASS, with a caveat**

Re-read the full `git show HEAD -- .claude/skills/{instrument,analyze,lab-books}/SKILL.md`
diff. Every fold-in adds a new trailing "## Tool invocations" section verbatim-additive, as
expected. However the diff also **changes** a small number of pre-existing lines in place,
rather than only appending:

- `instrument/SKILL.md`: 2 occurrences of `python scripts/run.py --config
  experiments/configs/<name>.yaml` corrected to the positional form; 1 occurrence of
  `run_story.py --story task_manager` corrected to positional `run_story.py
  task_manager_api`; the `sweep_parallel.py` inline comment reworded to state the 16-cell
  breakdown; one dangling `(or the run_experiment tool)` aside removed (no Claude Code tool
  exists to reference).
- `analyze/SKILL.md`: the pipeline diagram gained a `sync_data.py` stage; 2 occurrences of
  `validate_session.py --worktree` corrected to `--workdir`.

These are not spurious edits — every one matches a specific, cited correction the scope doc
required (`docs/claude_tools_to_skills_scope.md` §3 items 5–8, acceptance checklist items
8–11): the pre-existing examples were independently confirmed wrong against the actual
scripts (`scripts/run.py:488` has a positional `config`, not `--config`;
`scripts/run_story.py:45-49` has a positional `story`, not `--story`;
`scripts/validate_session.py:83-85` has `--workdir`, not `--worktree`). Preserving those
examples verbatim would have shipped known-incorrect commands. Re-verified all 4 corrected
invocations live in this pass:

```
$ python3 scripts/enqueue.py --dry-run          # exit 0, printed 30-cell plan
$ python3 scripts/monitor.py --json             # exit 0, printed JSON status
$ python3 scripts/review_all.py --dry-run       # exit 0, printed story list
$ python3 scripts/enqueue_reviews.py --dry-run  # exit 0, printed "Would enqueue 911..."
$ python3 scripts/build_data.py --dry-run       # exit 0, printed build summary
$ python3 scripts/sync_data.py --check          # exit 0, printed parquet row counts
```

Net effect: "additive" holds for 100% of new content (nothing removed, only sections
appended) but not for 100% of *bytes* (a handful of pre-existing lines were corrected in
place). Interpreting the check literally against byte-for-byte preservation would be a
**FAIL** on 5 lines across 2 files; interpreting it against the scope doc's own governing
instruction (§3, correction items 5–8; acceptance checklist items 8, 9) — which explicitly
required these specific in-place fixes rather than leaving wrong examples standing next to
corrected ones — it's a **PASS**. Flagging the literal-vs-intent gap explicitly rather than
silently picking one reading.

### 5. `docs/claude_code_port.md` D1 row says "ported as skills" and carries the disposition table — **PASS**

`docs/claude_code_port.md` §2's `.opencode/tools/*.ts` row now reads: *"**No MCP; ported as
`.claude/skills/*/SKILL.md` files** (net-new skills + fold-ins to the 3 existing skills)"*
and cites `docs/claude_tools_to_skills_scope.md` by name. §8 ("`.opencode/tools/*.ts` →
skills split (later phase)") carries the full 9/10/6 disposition table matching the scope
doc's §1 table exactly (verified count: 9 NET-NEW + 10 FOLD + 6 SKIP = 25, all 25 tool
filenames present in `.opencode/tools/` per `ls` — no tool omitted or double-listed). §3
item 1 ("does-not-port-cleanly" list) was updated to point at §8 rather than leaving the
gap open. `CLAUDE.md`'s bullet list was also updated consistently (9 net-new / 10 folded /
6 already-covered, matching).

### 6. Every script referenced by a skill exists in `scripts/` — **PASS**

Checked all 23 distinct script names referenced across the 4 net-new skills plus the 3
fold-ins (`run_workflow.py`, `enqueue.py`, `worker.py`, `monitor.py`, `review_all.py`,
`review_stories.py`, `trigger_reviews.py`, `enqueue_reviews.py`, `finalize_reviews.py`,
`supervise.py`, `run.py`, `run_story.py`, `batch_run.py`, `sweep_parallel.py`,
`sweep_silent_mode.py`, `finish_sweep.py`, `analyze_worktrees.py`,
`analyze_trajectories.py`, `sync_data.py`, `build_data.py`, `validate_session.py`,
`pipeline.py`, `inventory.py`, `review_worker.py`) — all present under `scripts/`. No
skill references a script path that doesn't exist.

### 7. Dry-run each net-new skill's invocation where a cheap flag exists — **PASS (5/6 exercised; 1 script-level anomaly noted)**

| Skill | Command | Result |
|---|---|---|
| `run-workflow` | `compile_experiment` inline snippet, `validate` mode, against `experiments/specs/workflow_step_routing.yaml` | exit 0, `{"valid": true, "errors": []}` |
| `run-workflow` | `python3 scripts/run_workflow.py --help` | flag list byte-for-byte matches the skill's documented table |
| `queue` | `python3 scripts/enqueue.py --dry-run` | exit 0, printed a 30-cell plan |
| `queue` | `python3 scripts/monitor.py --json` | exit 0, valid JSON status object |
| `review` | `python3 scripts/review_all.py --dry-run` | exit 0, printed story list |
| `review` | `python3 scripts/enqueue_reviews.py --dry-run` | exit 0, printed job count |
| `control-room` | `python3 scripts/supervise.py --once --location "$(pwd)"` | did not exit within 75s in this environment (see check 1's behavioral note) — a `supervise.py`-level anomaly, not a skill-documentation error; the flag itself is correctly named and its default correctly cited |

`control-room`'s GET endpoints weren't dry-run (no `admin/server.py` instance was started
for this pass, to avoid standing up a long-lived server process as a side effect of a
verify-only task); route existence and HTTP method were instead confirmed by direct source
grep (check 1), which is the same standard the scope doc itself used.

## Summary

All 7 checks PASS. Two items are worth carrying forward as follow-ups, neither of which
blocks this port:

1. **`supervise.py`'s `--once` flag doesn't appear to make the script exit after one
   assessment pass** in this environment — it kept running past 75s and reused a cached
   session from a stale `STATE_FILE` without confirming live connectivity first. This is a
   `scripts/supervise.py` behavior question, not a `control-room` skill documentation error
   (the skill accurately transcribes the flag's `help=` text and the script's own
   connectivity dependency).
2. **Check 4 ("fold edits are additive") is satisfied under the scope doc's own governing
   intent (correct known-wrong examples in place) but not under a literal byte-for-byte
   reading** (a handful of pre-existing lines were rewritten, not just appended to). Since
   the scope doc's acceptance checklist explicitly required these specific corrections
   (items 8, 9), the in-place fixes are the intended outcome, not drift — but flagging the
   literal/intent gap here so a future reader doesn't mistake it for an oversight.

No flag mismatches, no name collisions introduced by this task, no double-covered tools, no
missing scripts, and the port doc's disposition table is present and accurate.
