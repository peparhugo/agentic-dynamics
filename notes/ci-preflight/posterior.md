# Posterior — local CI preflight (`agentic-dynamics validate preflight`)

**Loop:** POSTERIOR phase of `workflows/repository/world_model_loop.yaml` (prior → execute →
posterior). **Task:** ONE local command running the five gates `.github/workflows/pytest.yml`
runs on every push (ruff · generated surfaces · docs drift · fast path · deterministic suite),
one PASS/FAIL line per gate, non-zero exit if any gate fails.
**Branch:** `feature/ci-preflight` @ `79bbba749` (prior `f2f6bcaa1`; `main` @ `11bae5110`).
**Inputs read:** `notes/world_model.md`, `notes/plan.md`, `notes/deviations.md`, the run's two
commits, and the code they touch. **Date:** 2026-09-21.
**Evidence discipline:** every claim below cites a file/line, a commit, a KB record, or a command
output; nothing is from memory.

---

## 0. What the posterior actually re-measured (method)

The posterior does not trust the deviations note — it re-ran the claims. Commands and results:

| Claim under test | Command | Result |
|---|---|---|
| The inherited shell is a fleet cell | `env \| grep FINOPS` | `FINOPS_CELL_ID=wf_world_model_loop_deepseek_deepseek_v4_flash` |
| All five gates green | `python3 scripts/ci_preflight.py --only lint/surfaces/docs-drift` then `--only fast-path` then `--only full-suite` | 3 PASS, then `PASS fast-path (34.2s)`, then `4581 passed, 32 skipped in 110.35s` → `PASS full-suite (111.0s)`; exit 0 each |
| G2 is real, not cosmetic | `pytest tests/test_control_room_build_contract.py` (raw) vs `env -u FINOPS_CELL_ID …` | raw: **2 failed, 21 passed**; scrubbed: **23 passed** |
| G3/G4 repaired | `pytest tests/test_ci_preflight.py test_cli_resolution.py test_agent_config_semantic.py test_script_classification.py -q` | **117 passed** |
| CLI resolution in-tree | `PYTHONPATH=src python3 -c "cli._resolve(['validate','preflight'])"` | `('ci_preflight.py', [])` |
| The bare console script is NOT this checkout | `/home/drseuss/.local/bin/agentic-dynamics validate preflight --list` | `unknown command validate preflight --list` |
| The two guard tests are fast-excluded | `pytest test_cli_resolution.py test_agent_config_semantic.py test_ci_preflight.py -m fast --collect-only` | `no tests collected (115 deselected)` |
| KB recall for this task | `python3 scripts/kb_read.py --query "CI preflight local gates parity one command" --scope agentic-dynamics` | 1 hit: `e6222c1ca0de8ead \| finding \| design:world-model-loop` |

**Verdict on the world model's hypotheses.** H1 (the five gates are the blocking subset) holds.
H2 (hermetic testability) holds, but only after a seam the plan did not name (§V4). H3 holds, and
is *sharpened*: the failures this task repaired were invisible to the fast path
(`-m fast` collects **zero** of the three guard modules) — only the full-suite gate caught them.

---

## 1. VIOLATIONS — where reality differed from the world model

### V1 — The world model labelled G2 "not real"; it is the load-bearing condition of the deliverable.
- **Model said:** `notes/world_model.md:153-155` — the two `test_control_room_build_contract`
  failures are "**Harness-environment (not real, 2)**", and `:108` frames G2 as an open question
  ("Decide whether the preflight scrubs…").
- **Reality:** the variable is set in *every* fleet/AIO shell (measured: this session's `env`),
  and without the scrub the branch's own `full-suite` gate is **red** — the acceptance criterion
  the model itself set (`notes/plan.md:135`, "Reports `5 passed`"). The failures are real in the
  environment the preflight is actually run from; "not real" reads as "can be ignored", which is
  wrong.
- **Evidence:** raw vs scrubbed pytest above; `scripts/ci_preflight.py:274-287` (`_child_env`
  scrub) and `tests/test_ci_preflight.py:211-232` (the scrub is asserted); `notes/deviations.md:72-73`.
- **Consequence:** the scrub is not environment hygiene bolted on — it is a correctness
  requirement of the runner. The next model must state the condition, not the anecdote.

### V2 — "Reachable as `agentic-dynamics validate preflight`" was false for the bare binary.
- **Model said:** `notes/world_model.md:1`, `:47-55`, and `notes/plan.md:125` treat the installed
  console script as the in-tree CLI; §2.2 inspects `src/agentic_dynamics/cli.py` and assumes it is
  what `agentic-dynamics` runs.
- **Reality:** `/home/drseuss/.local/bin/agentic-dynamics` imports `agentic_dynamics` from a
  **different checkout** (`/home/drseuss/ai-finops-framework/src/…`) and prints `unknown command
  validate preflight`. In-tree resolution works (`cli._resolve` → `("ci_preflight.py", [])`).
- **Evidence:** command outputs above; `notes/deviations.md:49-61` (D4).
- **Consequence:** the world model omitted a one-command check (`which agentic-dynamics`) that
  would have caught a host-level assumption at prior time. Every CLI-touching task must check it.

### V3 — The plan's named test seam could not satisfy the plan's own acceptance #4.
- **Model/plan said:** `notes/plan.md:55-59` — the seam is `run_gate(...)` and `run_preflight(...)`,
  and acceptance #4 requires the unit suite green "**without** spawning a real gate … or creating
  a worktree".
- **Reality:** `run_preflight` renders the repo HEAD and the ruff version, so calling it would
  shell out to real `git`/`ruff`, violating acceptance #4. A new pure function
  `evaluate_preflight(...) -> PreflightReport` (plus `build_report`/`render_summary`) was required.
- **Evidence:** `scripts/ci_preflight.py:321-352` (`evaluate_preflight`), `:456-485`
  (`run_preflight` = evaluate + render), `:355-387` (the real metadata probes);
  `notes/deviations.md:13-25` (D1).
- **Consequence:** the world model's H2 ("injectable process execution") was right in spirit but
  the *plan* conflated process injection with metadata-probe injection. The next plan should state
  the seam at the granularity the acceptance tests actually need.

### V4 — The execute commit altered more than the deviation record admits.
- **Plan/model said:** `notes/plan.md:74` — `tests/test_agent_config_semantic.py` change is
  "`_CLI` separator `\s+` → `[^\S\n]+`" (explicitly "1-char semantic"); `notes/deviations.md:70-71`
  records only that separator change for G4.
- **Reality:** the execute commit `79bbba749` also **reformatted `_check_paths`** — a multi-line
  `if (...)` collapsed to one line, with **no behavioural change** — at
  `tests/test_agent_config_semantic.py:183-185`. This second hunk is not recorded anywhere.
- **Evidence:** `git diff f2f6bcaa1..79bbba749 -- tests/test_agent_config_semantic.py` (two hunks);
  the file today at `:183-185`; `notes/deviations.md` has no entry for it.
- **Consequence:** the deviations artifact — the very thing this loop exists to make honest —
  under-reports its own diff. A reviewer diffing the plan against the commit tree finds a change
  the record denies. Minor in blast radius, material to the loop's contract.

### V5 — A line anchor in the world model was already stale on the branch it described.
- **Model said:** `notes/world_model.md:52` — "the `validate` group currently reads
  `session|tests|prereq|preexisting|render` (`cli.py:232` region)".
- **Reality:** the pre-edit `_HELP` validate line sat at `cli.py:236` (the edit hunk header is
  `@@ -233,7 +240,7 @@`, i.e. the old line was in that window, the new at 240). The model's anchor
  was off; note that `notes/` is outside the `anchor_integrity` axis' scan scope
  (`scripts/scan_docs_drift.py:52`), so this class of drift is unchecked by construction.
- **Evidence:** `git diff f2f6bcaa1..79bbba749 -- src/agentic_dynamics/cli.py`; `notes/deviations.md`
  does not mention it.
- **Consequence:** low severity, but it is the loop's own artifacts drifting from the code — a
  world model that cannot be anchor-checked will accumulate this. Worth a prior-phase habit
  (grep the line before citing it), not a new rail.

---

## 2. UNKNOWNS DISCOVERED — what we did not know at prior time

### N1 — "Run the full suite locally" is under-defined in a fleet shell; the clean-shell semantics are the missing half.
The prior model knew `FINOPS_CELL_ID` existed (`notes/world_model.md:108`) and that `cell_scope()`
honours it (`src/agentic_dynamics/runtime/workflow_runner.py`'s `cell_scope`, cited there), but it
did not know the variable is present in **every** AIO/fleet cell, nor that the raw suite is
therefore red by default in exactly the environment the preflight is meant to serve. The
non-obvious fact the next model must carry: *a local preflight is a claim about a CLEAN shell, so
it must construct that shell, not inherit one.* The runner does (`scripts/ci_preflight.py:39-45,
274-287`), but nothing at prior time said the scrub was mandatory.

### N2 — The docs-drift scanner has seven axes; `scripts/CONTEXT.md` documents six.
`scripts/scan_docs_drift.py:43` ("THE SEVEN AXES") and `:104-114` (the `AXES` tuple, ending
`"fast_path"`) enumerate **seven** axes; `scripts/CONTEXT.md:224` says the scanner works "across
six axes" and omits `fast_path`. This is a pre-existing prose drift on `main` too
(`git show main:scripts/scan_docs_drift.py` already has seven; `git show main:scripts/CONTEXT.md`
already says six). It is invisible to the CI gate because CI only runs
`--check spec_lifecycle` (`.github/workflows/pytest.yml:81`). **The scanner does not check its own
documentation's axis count** — a self-referential blind spot the next model should know exists.

### N3 — The guards that catch CLI/generator drift are NOT in the fast path.
`pytest -m fast` collects **zero** of `tests/test_cli_resolution.py`,
`tests/test_agent_config_semantic.py`, `tests/test_ci_preflight.py` (measured: 115 deselected), and
`tests/test_ci_preflight.py` explicitly cannot be fast-marked because importing `ci_preflight`
pulls in `subprocess` (`tests/test_ci_preflight.py:9-11`;
`tests/test_fast_path_gate.py:32` `FORBIDDEN_IN_FAST`). Consequence for the next model: a
"run `test_fast.sh` before pushing" habit does **not** reproduce CI's CLI/parity checks — the
full-suite gate is the one that matters, and it is ~110s. This is precisely why the preflight
exists, and it should be stated in its docstring/onboarding.

### N4 — `--json -` is not a clean machine stream.
The plan's two requirements collide: gates stream to inherited stdout by default
(`notes/plan.md:51`) while `--json -` also writes to stdout. The deviations record this (D3,
`notes/deviations.md:39-47`) and the script documents it, but at **prior time it was unknown** —
the model's file/interface table (`notes/plan.md:47-48`) lists `--json <path|->` with no caveat.
The next model should assume "observable stream + structured stdout" need an explicit split (a
file path, or `--json` implies `--quiet`).

### N5 — The KB has no record of the task itself; recall is design-only.
`kb_read.py --query "CI preflight local gates parity one command" --scope agentic-dynamics` returns
exactly one hit, `e6222c1ca0de8ead | finding | design:world-model-loop` — the loop's own design
note. There is **no** prior finding/decision/session about CI parity, the five gates, or the
`pipeline ci` disjointness. So the prior phase's model was necessarily derived from code, and the
next model must not expect KB recall to reduce the search for repository-infrastructure tasks.
(The read verb itself works — this is a coverage gap, not a retrieval failure.)

### N6 — A maintained script reaches the CLI without a `Primary Entry Points` row.
`scripts/CONTEXT.md` gained only `maintained: ci_preflight.py` (inside the machine-parsed
`<!-- scripts-classification -->` block, `scripts/CONTEXT.md:33` region) to satisfy
`tests/test_script_classification.py`. The file's human-facing "Primary Entry Points" table has no
`ci_preflight.py` row, so a reader browsing the manifest learns the script exists but not what it
does or when to run it. The classification guard does not require the table row. The next model
must know that "classified" ≠ "documented".

---

## 3. UPDATES — the concrete update set

### 3.1 KB findings to emit

1. **`phase-finding/v1` for this run (automatic, scope `agentic-dynamics`).**
   The workflow runs with `rag.emit_self: true` (`workflows/repository/world_model_loop.yaml:19-24`),
   so this report is emitted by the runtime after the phase commits. Content it should carry,
   [M]-tagged: the five-gate preflight exists at `scripts/ci_preflight.py`, is reachable as
   `validate preflight` in-tree, and was end-to-end green (`5 passed`, exit 0) on `79bbba749`.
2. **A cross-suite hazard finding — "`FINOPS_CELL_ID` rewrites the KB cell scope inside the
   deterministic suite."** [M] Evidence: the raw/scrubbed pytest pair above; `cell_scope()`'s env
   override; `scripts/ci_preflight.py:274-287`. Consumer: any suite runner, worker, or agent that
   runs `pytest tests/` from a fleet shell. This is the single highest-value record the loop
   produced.
3. **A docs-drift self-coverage finding — "the scanner's own doc says six axes; the code has
   seven."** [M] Evidence: `scripts/scan_docs_drift.py:43,104-114` vs `scripts/CONTEXT.md:224`;
   the CI gate only checks `spec_lifecycle`. Consumer: the docs-drift rail's next iteration
   (either fix the prose or add an axis that checks the scanner's documented surface).

Suggested retrieval keys so a future prior finds them: `ci preflight`, `local CI parity`,
`FINOPS_CELL_ID cell scope`, `docs-drift axes`.

### 3.2 Skills / knowledge / conventions to record

- **Convention (CLI additions are a three-file edit):** a new `agentic-dynamics` verb requires
  (a) `src/agentic_dynamics/cli.py` `_COMMANDS` **and** `_HELP`, (b) the hand-authored
  `DOCUMENTED_RESOLUTIONS` table in `tests/test_cli_resolution.py`, and (c) the CLI tree in
  `agent_config/mental-model.md` followed by `python3 scripts/_gen_instructions.py`. G3 is the
  proof: `knowledge read` was added to (a) and (b)'s source but not to the table, and the guard
  went red (`notes/world_model.md:109`; repaired at `tests/test_cli_resolution.py:87-89`).
  Candidate home: the `run-workflow`/`instrument` skill, or a short section in
  `scripts/CONTEXT.md`.
- **Convention (fast-path membership):** a test module that imports `subprocess` (or any
  `FORBIDDEN_IN_FAST` token) **must not** carry `@pytest.mark.fast` unless it declares
  `# fast-safe`; `tests/test_fast_path_gate.py:32,104` enforces it. Corollary discovered: the
  preflight's own unit test therefore adds coverage to the full suite only (N3).
- **Convention (clean-shell measurement):** any command whose job is to predict CI must construct
  the CI shell (scrub harness-only variables) rather than inherit the caller's; `--no-clean-env`
  is the documented escape hatch. `scripts/ci_preflight.py:39-45`.
- **Skill/knowledge candidate:** a one-page "local CI parity" entry (either a `knowledge-reader`
  sibling skill or a `scripts/CONTEXT.md` Primary Entry Points row) that says: run
  `agentic-dynamics validate preflight` before a push; `--only`/`--skip` for iteration; the bare
  global binary is not this checkout. Per the design's own rule
  (`docs/designs/proposed/world_model_loop.md:51-54`), a *skill* must ride the normal promotion
  gate — so this phase proposes the content and location but does not mint a generated surface.

### 3.3 What should change in the next loop's prior phase

1. **Separate raw from scrubbed measurement.** When the task touches the test suite, run the raw
   command *and* the clean-shell command and diff the failure sets; classify each failure as
   real vs harness-env *before* writing the model (this loop had to discover that in execute).
2. **Check host-level resolution for any CLI claim.** `which <binary>` + `PYTHONPATH=src …` before
   asserting a command is reachable (V2). Prefer in-tree `cli._resolve` as the evidence form.
3. **Do not cite a line anchor without re-grepping it** (V5); `notes/` is not anchor-checked.
4. **Test the plan's named interfaces against the acceptance criteria on paper** (V3): if an
   acceptance test needs injection the plan's signature cannot provide, name the extra seam in the
   plan, not in execute.
5. **Prose-vs-code counts are a drift class of their own** (N2): reconcile a doc's stated
   "N of X" against the code's enumeration during the prior read.
6. **Expect thin KB recall for repository-infrastructure work** (N5) and budget the prior phase
   for code-derived modelling accordingly.

### 3.4 Derived / design artifacts to update (proposals, not actions here)

- `docs/designs/proposed/world_model_loop.md:43` still lists *"local CI parity … partial — no
  one-command preflight"*; the "Smallest next steps" bullet at `:61-63` is now **done**. The row
  should read *built (`scripts/ci_preflight.py`, `validate preflight`)* and the design should carry
  this loop's result (the pilot's first posterior). Owner: a normal permanence-gated change, not
  this phase.
- `scripts/CONTEXT.md` — two small gaps: its "Primary Entry Points" table has no `ci_preflight.py`
  row (N6), and its `scan_docs_drift.py` row says "six axes" where the code has seven (N2). Both
  are documentation edits on `main` and belong to a docs-drift remediation, not the posterior.

---

## 4. One-line close

The deliverable met its contract (all five gates independently re-verified green; exit 0/1/2 as
specified), but the model that produced it mis-scored its own biggest hazard (V1), assumed an
entry point that does not resolve on this host (V2), under-specified the seam its acceptance
required (V3), and its deviation record under-reports its own diff (V4); the durable lessons are
the clean-shell requirement for every CI-predicting command, the three-file edit rule for a new
CLI verb, and the fact that the guards protecting CLI/generator parity live only in the slow
suite.
