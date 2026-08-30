---
status: accepted
---
# OpenCode Tools → Claude Code Skills Scope

Scope doc for reframing `.opencode/tools/*.ts` (25 files) as Claude Code skills that
shell to the same underlying `scripts/*.py` CLIs / `admin/server.py` endpoints, without
duplicating what the existing ported skills (`analyze`, `instrument`, `lab-books`) and
commands (`analyze`, `lab`, `new-exp`, `pipeline`, `run-exp`) already cover.

**This is not a reversal of `docs/architecture/current/claude_code_port.md`'s D1** ("no `.mcp.json`, no
MCP server for the 25 tools" — reaffirmed in that doc's §3 item 1). D1 rejected
*MCP as the porting mechanism*. This doc proposes *skills* — the same file-based
mechanism already used for `analyze`/`instrument`/`lab-books` — for the subset of the
25 tools whose knowledge (exact flags, safety gates, Redis lifecycle, background-job
contracts) isn't yet folded into any `.claude/` file. Every fact below was pulled by
reading `.opencode/tools/*.ts` and the `scripts/*.py` / `admin/server.py` source
directly this pass — none carried over from the existing skills' prose without
re-verification against the script's actual `argparse`/`sys.argv` parsing.

## 1. Final disposition table

25 tools, verified against source. All 25 are accounted for below (9 net-new, 10
fold-into, 6 skip — see §3 item 1 for the one hypothesis contradiction this resolves).

| Tool | Disposition | Reason |
|---|---|---|
| `compile_experiment.ts` | **NET-NEW** → `run-workflow` skill | No CLI script wraps `compile_experiment.py` (confirmed: no `__main__`/`argparse` in the module) — the tool itself is the only documented invocation of `validate_rules`/`compile_spec`. Neither `instrument` nor `analyze` skill mentions it. |
| `run_workflow.ts` | **NET-NEW** → `run-workflow` skill | Wraps `scripts/run_workflow.py`, the *execute* phase of the same spec→DAG pipeline `compile_experiment.ts` validates/compiles. No existing skill documents `run_workflow.py`'s 11 flags or the git-worktree/commit-per-phase contract. |
| `control_room.ts` | **NET-NEW** → `control-room` skill | Talks HTTP to a running `admin/server.py`, not `Bun.$` to a script — a different invocation shape than every fold-into candidate. Not mentioned in any existing skill. Read-only GET boundary is safety-relevant and worth its own file (see §2). |
| `supervisor.ts` | **NET-NEW** → `control-room` skill | Same flag-only/observe-never-steer boundary as `control_room.ts` (explicit in both files' own comments); wraps `scripts/supervise.py`, undocumented elsewhere. Grouped with `control_room.ts` because both exist specifically to guard the same architectural boundary (`admin/server.py`'s POST steer/interrupt routes), not because they share an invocation shape. |
| `enqueue.ts` | **NET-NEW** → `queue` skill | Wraps `scripts/enqueue.py` (Redis `story_jobs` queue fill). Not documented in any existing skill beyond one bare example line in `AGENTS.md`'s Commands block. |
| `worker.ts` | **NET-NEW** → `queue` skill | Wraps `scripts/worker.py` process lifecycle (start/status/stop via `pgrep`/`pkill`, not script flags). Same Redis lifecycle as `enqueue.ts`/`monitor.ts` — one skill, not three. |
| `monitor.ts` | **NET-NEW** → `queue` skill | Wraps `scripts/monitor.py`. `AGENTS.md` lists the bare command but no skill documents `--watch`/`--clear`/`--json` or the interactive-only/destructive gates the tool enforces. |
| `dashboard.ts` | **NET-NEW** → `queue` skill (folded into the `monitor.py` doc, not a separate example) | Functionally `monitor(json:true)` — verified: `dashboard.ts` runs exactly `python3 scripts/monitor.py --json`, a strict subset of what `monitor.ts` already exposes. No new script knowledge; still net-new *content* since neither exists in any skill today, but the skill should present one canonical `--json` example, not duplicate it under two names. |
| `review.ts` | **NET-NEW** → `review` skill | Fans out to 5 distinct scripts (`review_all.py`, `review_stories.py`, `trigger_reviews.py`, `enqueue_reviews.py`, `finalize_reviews.py`) with 3 different invocation shapes (sync subprocess, backgrounded `&`, plain run). None of the 5 appears in any existing skill or command. |
| `run_experiment.ts` | **FOLD** → `instrument` skill | `instrument` skill already documents `scripts/run.py` extensively — but with a **wrong flag** (see §3 item 5). Folding means correcting the existing doc, not just appending. |
| `run_story.ts` | **FOLD** → `instrument` skill | `instrument` skill already has a "Multi-Session Stories" section for `run_story.py` with 4 of 15 flags shown; folding adds the other 11 (`--codebase`, `--worktree-root`, `--results-dir`, `--output-limit`, `--no-standardize`, etc.) verified in §2 is N/A here since this is fold-into, but flags are listed in §3 for completeness. |
| `batch.ts` | **FOLD** → `instrument` skill | `instrument` skill's "Batch & Parallel Runners" section already has the bare `python scripts/batch_run.py` line; folding adds the tool's clarification that it's a **fixed 13-config subset** (`scripts/batch_run.py:CONFIGS`), not all 34 configs — a distinction the current skill prose doesn't make and a real footgun (a reader could assume `batch_run.py` covers the full matrix). |
| `sweep.ts` | **FOLD** → `instrument` skill | Same section, same gap: `python scripts/sweep_parallel.py` is listed but the "16 cells = 4 models × 2 silent modes × 2 operators" shape isn't spelled out. |
| `analyze_worktrees.ts` | **FOLD** → `analyze` skill | Already extensively documented (flags: `--worktree`, `--limit`, `--dry-run`, `--no-tests`) — but incompletely: `--baseline`, `--no-sonar`, `--sonar-url`/`-user`/`-password`/`-timeout`, `--tests`, `--timeout` are real flags (confirmed in `scripts/analyze_worktrees.py:1031-1043`) absent from the skill. The *tool* itself (`args: {}`) exposes none of these — folding should go straight from script source, not through the tool. |
| `analyze_trajectories.ts` | **FOLD** → `analyze` skill | Already documented, flags match (`--limit`, `--model`, `--dry-run`) — no gap, but tool's 1:1 flag mapping worth preserving as a skill example block. |
| `sync_data.ts` | **FOLD** → `analyze` skill | **Missing entirely** from the `analyze` skill today (confirmed: no mention of `sync_data.py` in `.claude/skills/analyze/SKILL.md`) despite `AGENTS.md`'s Commands block listing `python scripts/sync_data.py` as a required pre-`build_data.py` step ("story results -> parquet (before build_data)"). Real gap, not redundant. |
| `build_data.ts` | **FOLD** → `analyze` skill | Already documented (`python scripts/build_data.py`) but the `--dry-run` flag (confirmed `scripts/build_data.py:1168`) isn't shown. |
| `validate_session.ts` | **FOLD** → `analyze` skill | Already documented with the `--worktree` example — but that flag **does not exist** on `validate_session.py` (see §3 item 6); the real flags are `--workdir`, `--session-id`, `--model`. |
| `run_lab.ts` | **FOLD** → `lab-books` skill | `lab-books` skill already documents the `python scripts/lab_<name>.py` pattern for all 19 labs — but the tool's `max_steps`/`--max-steps` arg is fictional (see §3 item 4); folding must NOT carry that flag forward. |
| `pipeline.ts` | **SKIP** | Fully covered by the `pipeline` command (`.claude/commands/pipeline.md`) plus `AGENTS.md`'s Commands block (`python scripts/pipeline.py --plan <name>`). The tool's `action`/`plan` enum values (`ci`/`deploy`/`full_matrix`/`cross_models`/`feature`/`ship_features`, `run`/`dry_run`/`graph`/`status`/`reset`/`check_deps`) are richer than the command doc shows, but that's an edit to `pipeline.md`, not a new skill. |
| `inventory.ts` | **SKIP** | Fully covered — `analyze` skill has a dedicated "inventory.py (392L) — Data Registry CLI" section with all 5 actions (`refresh`/`list`/`stats`/`report`/`worktrees`) and both flags (`-v`, `-a` on `worktrees`). |
| `backfill.ts` | **SKIP** | Covered — `analyze` skill's "Data Maintenance Scripts" section lists `python scripts/backfill_artifacts.py` with the right script name. Flags (`--dry-run`, `--sessions-only`, `--worktree`) aren't itemized there but this is a single-purpose maintenance script, not worth a dedicated skill section — a doc quality nit for `analyze/SKILL.md`, not a scope gap. |
| `archive_worktrees.ts` | **SKIP** | Git-history archival of `/tmp/exp_*`/`story_*` worktrees into `refs/experiments/*` — a one-off maintenance operation with its own dry-run-by-default safety model, not part of the instrument→analyze→lab-books cycle any existing skill maps to. Trivial enough (3 args, single script-free `execSync`/`readdirSync` implementation, no `scripts/*.py` backing it at all — it's pure TS) that it doesn't need script-CLI knowledge folded anywhere; a reader can read the tool source directly. |
| `generate_manifest.ts` | **SKIP** | Zero-flag, single-purpose (`python scripts/generate_manifest.py`, confirmed no args). Not part of any skill's core loop; low value to document beyond the one-line `scripts/CONTEXT.md` entry that should already list it. |
| `list_stories.ts` | **SKIP** | Trivial (`python3 scripts/run_story.py --list`) and already redundant: the `instrument` skill's "BUILTIN_STORIES dict keys" section names and describes all 3 built-in stories directly. Folding would duplicate that, not add to it. **Resolves a contradiction in the starting hypothesis** — see §3 item 1. |

## 2. Net-new skills — exact CLI invocations (verified against source)

Four new skill directories: `.claude/skills/run-workflow/`, `.claude/skills/control-room/`,
`.claude/skills/queue/`, `.claude/skills/review/`.

### 2.1 `run-workflow` skill

**`compile_experiment.py`** has no CLI — confirmed no `if __name__ == "__main__"` or
`argparse` anywhere in `src/instrument/compile_experiment.py`. `compile_experiment.ts`'s
own comment states this explicitly:

> `// CONVENTION BREAK: compile_experiment.py has no CLI (no argparse / __main__) — it's a
> pure library, and no scripts/*.py wraps it. Every other tool in this directory shells
> to a scripts/*.py file; this one shells to an inline python3 -c snippet instead.`

The skill's invocation must reproduce that inline snippet, calling functions confirmed
present at these exact signatures:

```
src/instrument/experiment_spec.py:359:  def load_spec(path: Path) -> ExperimentSpec
src/instrument/experiment_spec.py:367:  def validate_rules(spec: ExperimentSpec) -> list[str]
src/instrument/compile_experiment.py:87: def compile_spec(spec: ExperimentSpec) -> DAG
src/instrument/compile_experiment.py:37: class SpecError(ValueError)
src/instrument/compile_experiment.py:55: class DAG:  # .names() -> list[str], .edges: list[tuple],
                                          #            .feedback: list[tuple], .topological_order() -> list[str]
```

Exact invocation (validate mode — the requires/produces gate only):
```bash
python3 -c "
import sys, json
from pathlib import Path
sys.path.insert(0, 'src')
from instrument.experiment_spec import load_spec, validate_rules
from instrument.compile_experiment import compile_spec, SpecError

spec_path, mode = sys.argv[1], sys.argv[2]
spec = load_spec(Path(spec_path))

if mode == 'validate':
    errors = validate_rules(spec)
    print(json.dumps({'valid': not errors, 'errors': errors}))
    sys.exit(1 if errors else 0)
else:
    try:
        dag = compile_spec(spec)
    except SpecError as e:
        print(json.dumps({'valid': False, 'errors': e.errors}))
        sys.exit(1)
    print(json.dumps({'valid': True, 'phases': dag.names(), 'edges': dag.edges,
                       'feedback': dag.feedback, 'topological_order': dag.topological_order()}))
" experiments/specs/workflow_step_routing.yaml validate
```
Swap the final positional arg to `compile` for the DAG-building mode. Exit code 1 on
either a validation error list or a `SpecError`.

**`run_workflow.py`** — confirmed full flag set, `scripts/run_workflow.py:27-39`:
```
ap.add_argument("--spec", required=True, help="path to an ExperimentSpec YAML")
ap.add_argument("--goal", required=True, help="feature/task prompt (substituted for {goal})")
ap.add_argument("--model", required=True, help="provider/model id")
ap.add_argument("--workdir", required=True, help="git worktree to run in")
ap.add_argument("--backend", default=None, help="opencode | claude_cli (default: auto)")
ap.add_argument("--thinking-effort", default="high")
ap.add_argument("--thinking-budget-tokens", type=int, default=0)
ap.add_argument("--output-token-limit", type=int, default=0)
ap.add_argument("--timeout", type=int, default=1800, help="per-phase timeout (s)")
ap.add_argument("--no-commit", action="store_true", help="do not commit after phases")
ap.add_argument("--resume", action="store_true",
                help="skip phases that already have a [workflow] <phase> commit")
```
`--spec`/`--goal`/`--model`/`--workdir` are **required** — no positional fallback, unlike
`run.py`'s `config` (see §3 item 5). Example:
```bash
python3 scripts/run_workflow.py \
  --spec experiments/specs/workflow_step_routing.yaml \
  --goal "Add rate limiting to the API" \
  --model deepseek/deepseek-v4-pro \
  --workdir /tmp/wf_abc123 \
  --thinking-effort high --timeout 1800
```
Runs `validate_spec`/`compile_spec` internally via `load_spec` + `run_workflow()` from
`instrument.workflow_runner` (confirmed import at `scripts/run_workflow.py:23-24`) — so
this script implicitly re-validates the spec each call; a prior `compile_experiment`
`validate` pass is a fast-fail convenience, not a hard prerequisite.

### 2.2 `control-room` skill

**`control_room.ts`** — read-only GET against a running `admin/server.py`. All 6 endpoint
values confirmed to exist as `@app.get(...)` routes, not `POST`:
```
admin/server.py:738  @app.get("/api/matrix")
admin/server.py:779  @app.get("/api/status")           # SSE — see hazard note below
admin/server.py:805  @app.get("/api/flags")
admin/server.py:860  @app.get("/api/routing")
admin/server.py:903  @app.get("/api/design-sessions")
admin/server.py:1094 @app.get("/api/claude-agents")
```
Port confirmed: `admin/server.py:1365`, `port = int(os.environ.get("FINOPS_PORT", "8000"))`.

Exact invocation:
```bash
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/matrix"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/flags"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/routing"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/design-sessions"
curl -s "http://127.0.0.1:${FINOPS_PORT:-8000}/api/claude-agents"
```
**Do not curl `/api/status` this way** — see §3 item 2; it is a server-sent-events
stream that never closes on its own, unlike the other 5 (confirmed plain `jsonify`
endpoints).

**SECURITY CONSTRAINT — must carry over verbatim into the skill** (quoted from
`control_room.ts`'s own header comment, restated because it is the entire reason this
tool exists as a separate file rather than "just curl the API"):
> Never wrap a POST route here (`/api/flags/<id>/steer`, `/api/flags/<id>/interrupt`,
> `/api/design-sessions/<id>/interrupt`, `/api/claude-agents` create/stop/respawn/rm/steer)
> — those are the human-operator control surface, and exposing them as an agent-callable
> tool would let a session steer or interrupt itself or a peer session through the one
> channel the architecture deliberately keeps flag-only.

**`supervisor.ts`** → `scripts/supervise.py`. Confirmed flags, `scripts/supervise.py:348-350`:
```
ap.add_argument("--once", action="store_true", help="run one assessment pass and exit")
ap.add_argument("--location", default=str(ROOT), help="repo location for the monitor session")
```
Exact invocation:
```bash
python3 scripts/supervise.py --once --location "$(pwd)"
```
Same header-comment boundary as `control_room.ts` (quoted directly in `supervisor.ts`):
> `src/instrument/supervisor.py` deliberately has no OpenCode client dependency "so
> observation can't become control" — never add a mode, flag, or follow-up tool here
> that lets an agent steer or interrupt a session.

**Prerequisite not stated in `supervisor.ts`** (a gap the skill should add): `supervise.py`
instantiates `OpenCodeClient(BASE_URL)` where `BASE_URL = os.environ.get("OPENCODE_BASE_URL",
"http://127.0.0.1:4096")` (`scripts/supervise.py:34`) — it needs a running opencode server
to create the flash monitor session, independent of whether the caller is Claude Code or
opencode. The skill must say so; a Claude Code agent running this cold will get a connection
error, not a helpful message.

### 2.3 `queue` skill

**`enqueue.py`** — manual `sys.argv` parse, confirmed `scripts/enqueue.py:143-152`:
```python
dry_run = "--dry-run" in sys.argv
clear = "--clear" in sys.argv
missing_only = "--missing-only" in sys.argv
interleave = "--interleave" in sys.argv
# --model VALUE read via sys.argv.index("--model") + 1
```
`MODEL` default: `os.environ.get("FINOPS_MODEL", "deepseek/deepseek-v4-pro")`
(`scripts/enqueue.py:34`). Redis target: `127.0.0.1:${FINOPS_REDIS_PORT:-6380}`,
db `${FINOPS_REDIS_DB:-1}` (`scripts/enqueue.py:41-42`).
```bash
python3 scripts/enqueue.py                                    # fill queue, default model
python3 scripts/enqueue.py --model anthropic/claude-sonnet-5   # target a specific model
python3 scripts/enqueue.py --missing-only                      # skip cells with a saved result
python3 scripts/enqueue.py --interleave                        # round-robin across providers
python3 scripts/enqueue.py --dry-run                           # print the plan only
python3 scripts/enqueue.py --clear                             # reset the queue (destructive)
```
`enqueue.ts`'s own safety gate (preserve in the skill): it refuses to run `--clear`
unless `--dry-run` is *also* passed, returning a warning instead — i.e. the tool-level
contract is "see the dry-run plan before you're allowed to clear," even though the raw
script accepts `--clear` standalone.

**`worker.py`** — zero CLI flags (confirmed: no `add_argument`/`sys.argv` in the file;
`main()` just loops on `BRPOP`). Env vars: `FINOPS_REDIS_HOST` (default `127.0.0.1`),
`FINOPS_REDIS_PORT` (default `6380`), `FINOPS_REDIS_DB` (default `1`) —
`scripts/worker.py:22-24`.
```bash
python3 scripts/worker.py &                    # start (background); auto-exits after 2 min idle
pgrep -f "scripts/worker.py"                    # status
pkill -f "scripts/worker.py"                    # stop all
```
Lifecycle (start/status/stop) is process-management via `pgrep`/`pkill` on the command
line pattern `scripts/worker.py`, not a script flag — confirmed matches `worker.ts`
exactly (`Bun.$`python3 scripts/worker.py &``, `pgrep -f "scripts/worker.py"`,
`pkill -f "scripts/worker.py"`).

**`monitor.py`** — manual `sys.argv` parse, confirmed `scripts/monitor.py:114-116`:
```python
watch = "--watch" in sys.argv
clear = "--clear" in sys.argv
json_out = "--json" in sys.argv
```
```bash
python3 scripts/monitor.py             # human-readable status snapshot
python3 scripts/monitor.py --json      # machine-readable (this is what dashboard.ts always runs)
python3 scripts/monitor.py --watch     # live 5s-refresh loop — needs an interactive terminal
python3 scripts/monitor.py --clear     # deletes story_jobs/story_status/story_results — destructive
```
`monitor.ts` itself refuses to run `--watch` (returns "requires an interactive terminal,
run it manually") and refuses `--clear` (returns "run monitor.py --clear manually") —
both are intentional guardrails to preserve in the skill, not gaps to fill.

`dashboard.ts` (folded in, not a separate script): exactly `python3 scripts/monitor.py --json`
— present it as the canonical `--json` example above, not a second script.

### 2.4 `review` skill

**`review_all.py`** — confirmed `scripts/review_all.py:119-122`:
```python
parser.add_argument("--workers", type=int, default=6)
parser.add_argument("--story", default="", help="Substring filter on story name")
parser.add_argument("--dry-run", action="store_true")
```
```bash
python3 scripts/review_all.py                              # all stories, 6 workers, ThreadPoolExecutor
python3 scripts/review_all.py --workers 3 --story task_manager --dry-run
```

**`review_stories.py`** — manual parse, confirmed `scripts/review_stories.py:20`:
```python
dry_run = "--dry-run" in sys.argv
```
```bash
python3 scripts/review_stories.py [--dry-run]   # batch commit + story review, no Redis
```

**`trigger_reviews.py`** — zero CLI flags (confirmed: no `add_argument` anywhere in the
file). Reads `REVIEW_WORKERS` env var, default `4` (`scripts/trigger_reviews.py:26`).
Polls `analysis_jobs`/`analysis_status` Redis keys until drained, then runs
`enqueue_reviews.py` as a blocking subprocess and spawns `REVIEW_WORKERS` detached
`review_worker.py` processes via `nohup ... &` (`scripts/trigger_reviews.py:60-77`).
```bash
python3 scripts/trigger_reviews.py              # default 4 review workers, backgrounded
REVIEW_WORKERS=6 python3 scripts/trigger_reviews.py &
```

**`enqueue_reviews.py`** — manual parse, confirmed `scripts/enqueue_reviews.py:61`:
```python
dry_run = "--dry-run" in sys.argv
```
```bash
python3 scripts/enqueue_reviews.py [--dry-run]   # populate review_jobs queue
```

**`finalize_reviews.py`** — zero CLI flags (confirmed: no `add_argument`/`sys.argv` in
the file).
```bash
python3 scripts/finalize_reviews.py              # merge per-session review files into aggregates
```

## 3. Corrections to the starting hypothesis

1. **`list_stories.ts` appeared in both the FOLD and SKIP lists of the starting
   hypothesis** — a direct contradiction (`FOLD into instrument skill <- ... list_stories.ts`
   and `SKIP ... list_stories.ts` both present). Resolved to **SKIP**: `list_stories.ts` is
   a one-line wrapper (`python3 scripts/run_story.py --list`, confirmed
   `.opencode/tools/list_stories.ts:7`), and the `instrument` skill's existing
   "BUILTIN_STORIES dict keys" section already names and describes all 3 built-in stories.
   Folding it would duplicate, not add, content.

2. **`control_room.ts`'s default endpoint (`status`) is unusable through a plain HTTP
   GET+read.** `/api/status` is a Flask SSE endpoint (`admin/server.py:779-802`) whose
   generator loop (`while True: ... yield ": ping\n\n"`) never terminates on its own — it
   only stops when the client disconnects. `control_room.ts`'s `execute()` does
   `await fetch(url)` then `await res.text()`, which will block until the connection is
   closed by something else — in practice, hang. This isn't a hypothesis gap, it's a bug
   discovered by reading the tool against the live route it targets. The `control-room`
   skill must **not** default its example invocation to `/api/status`; lead with
   `/api/matrix` (confirmed plain `jsonify(...)`, `admin/server.py:738-776`) and, if
   `/api/status` is documented at all, flag it as "use `curl --max-time N` or a real SSE
   client, not a bare GET."

3. **`enqueue.ts` under-exposes `enqueue.py`.** The script's own usage docstring
   (`scripts/enqueue.py:1-19`) and `main()` both support `--interleave` ("weave new cells
   across models/providers... round-robins across models so concurrent workers spread
   across providers instead of hammering one"), but `enqueue.ts`'s `args` schema has no
   `interleave` field and never passes the flag through. The `queue` skill should document
   `--interleave` from the script directly (§2.3), not inherit the tool's omission.

4. **`run_lab.ts`'s `max_steps` → `--max-steps` flag does not exist on any lab script.**
   Verified by grepping every `scripts/lab_*.py` for `add_argument`/`ArgumentParser`: only
   `lab_sonar_quality.py` (`--summary`, `--json`) and `lab_opencode_meta_analysis.py`
   (`--skip-expensive`, `--limit-tasks`, `--all`) parse CLI args at all; neither has
   `--max-steps`, and the other 17 non-deprecated labs take **zero** arguments. Folding
   `run_lab.ts` into the `lab-books` skill must drop `max_steps` entirely rather than
   documenting a flag that would make `argparse` (or the bare script) error out.

5. **`scripts/run.py`'s config argument is positional, not `--config`.** Confirmed
   `scripts/run.py:488`: `parser.add_argument("config", help="YAML config path")` — there
   is no `--config` option registered. `run_experiment.ts` gets this right (positional:
   `` Bun.$`python3 scripts/run.py ${configPath} ${flags}` ``), but **the existing
   `instrument` skill, `AGENTS.md`'s Commands block, and both `new-exp.md`/`run-exp.md`
   commands (on both the opencode and Claude Code sides) all document
   `python scripts/run.py --config experiments/configs/<name>.yaml --model deepseek`** —
   an invocation `argparse` would reject (`unrecognized arguments: --config ...` plus a
   missing-required-positional error). This predates this task and isn't caused by the
   tools-to-skills port, but folding `run_experiment.ts`'s *correct* invocation into the
   `instrument` skill means the fold must **fix** the existing wrong examples in
   `instrument/SKILL.md` (4 occurrences), not add a 5th correct one alongside 4 wrong ones.
   `AGENTS.md` and the two `.md` commands are out of this doc's file scope but should be
   flagged to whoever owns that fix.

6. **`validate_session.ts`'s example flag (`--worktree`) does not exist on the script it
   wraps.** `analyze` skill's existing doc shows `python scripts/validate_session.py
   --worktree /tmp/exp_xyz`, but `scripts/validate_session.py:82-85` registers only
   `--workdir`, `--session-id`, `--model` — no `--worktree`. `validate_session.ts` itself
   gets this right (`args.workdir` → `--workdir`). The fold-in must correct the skill's
   existing example, mirroring correction 5's pattern (tool source was right, prose skill
   was wrong).

7. **`analyze_worktrees.ts` exposes zero of the script's 12 real flags** (`args: {}` in
   the tool, vs. `--worktree`/`--limit`/`--dry-run`/`--baseline`/`--no-tests`/`--no-sonar`/
   `--sonar-url`/`--sonar-user`/`--sonar-password`/`--sonar-timeout`/`--tests`/`--timeout`
   confirmed at `scripts/analyze_worktrees.py:1031-1043`). Not a contradiction to resolve,
   but a reminder for the fold: the `analyze` skill should keep documenting the script's
   real flag surface directly (it partially does today — `--baseline`/`--no-sonar`/
   `--sonar-*`/`--tests`/`--timeout` are the net-new additions) rather than mirroring the
   tool's empty schema.

8. **`dashboard.ts` and `monitor.ts` are the same script with different defaults**, not
   two capabilities. `dashboard.ts` always runs `monitor.py --json`; `monitor.ts` defaults
   to no flags (human-readable) with `action` selecting `--watch`/`--clear` (both refused
   and redirected to manual terminal use). The hypothesis already grouped both under
   `queue`, correctly — flagged here only so the skill author writes one `monitor.py`
   reference section with the `--json` case called out, not two redundant ones.

## 4. Acceptance checklist

Numbered items the build phase can implement against and a verify pass can check off.

1. Four new skill directories exist: `.claude/skills/run-workflow/SKILL.md`,
   `.claude/skills/control-room/SKILL.md`, `.claude/skills/queue/SKILL.md`,
   `.claude/skills/review/SKILL.md`, each with `name`/`description` frontmatter
   following the existing 3 skills' format (no `paths:` — unconditional load is not
   required for these; confirm intended load behavior before setting frontmatter).
2. `run-workflow` skill documents both `compile_experiment`'s inline `python3 -c`
   snippet (validate + compile modes, both positional args) and `run_workflow.py`'s
   11 flags, with `--spec`/`--goal`/`--model`/`--workdir` marked required — verify by
   running `python3 scripts/run_workflow.py --help` and diffing against §2.1.
3. `control-room` skill documents all 6 GET endpoints against a running
   `admin/server.py`, explicitly warns against a bare `curl`/`fetch` on `/api/status`
   (SSE hazard, §3 item 2), and restates the POST-route prohibition verbatim from
   `control_room.ts`'s header comment. Verify: skill text contains the phrase "never
   steer" or equivalent, and lists `/api/matrix` (not `/api/status`) as the primary
   example.
4. `control-room` skill documents `supervise.py`'s `OPENCODE_BASE_URL` prerequisite
   (opencode server must be running) — a gap not present in `supervisor.ts` itself.
   Verify: skill text mentions port 4096 or `OPENCODE_BASE_URL`.
5. `queue` skill documents `enqueue.py`'s `--interleave` flag (missing from
   `enqueue.ts`, §3 item 3) and preserves the tool-level `--clear` requires-`--dry-run`
   safety convention. Verify: skill text contains `--interleave` and a warning about
   `--clear`.
6. `queue` skill presents `monitor.py --json` as the single canonical dashboard
   example (not a duplicated `dashboard.ts` section) and documents `worker.py`'s
   zero-flag `pgrep`/`pkill` lifecycle with the correct env vars
   (`FINOPS_REDIS_HOST`/`_PORT`/`_DB`, defaults `127.0.0.1`/`6380`/`1`).
7. `review` skill documents all 5 backing scripts (`review_all.py`,
   `review_stories.py`, `trigger_reviews.py`, `enqueue_reviews.py`,
   `finalize_reviews.py`) with their real flags per §2.4, and notes
   `trigger_reviews.py`'s two-stage behavior (blocking `enqueue_reviews.py` call, then
   detached `review_worker.py` spawns) since that process-management detail isn't
   obvious from the flag list alone.
8. `instrument` skill's existing `python scripts/run.py --config ...` examples (4
   occurrences in `.claude/skills/instrument/SKILL.md`) are corrected to the positional
   form (`python scripts/run.py experiments/configs/<name>.yaml --model deepseek`) as
   part of folding in `run_experiment.ts` — not left standing alongside new correct
   examples. Verify: `grep -c -- "--config" .claude/skills/instrument/SKILL.md` returns
   `0` after the fold.
9. `analyze` skill's existing `validate_session.py --worktree ...` example is corrected
   to `--workdir` as part of folding in `validate_session.ts`. Verify:
   `grep -- "--worktree" .claude/skills/analyze/SKILL.md` matches only
   `analyze_worktrees.py` usage lines, never `validate_session.py`.
10. `analyze` skill gains a `sync_data.py` section (`sync`/`check`/`query` modes,
    confirmed at `scripts/sync_data.py:263-276`) that does not exist today. Verify:
    `grep sync_data.py .claude/skills/analyze/SKILL.md` returns at least one match.
11. `instrument` skill's `batch_run.py`/`sweep_parallel.py` bullets are updated to state
    the fixed-subset/fixed-cell-count caveats (13-config subset; 16 cells = 4×2×2) rather
    than the bare script names.
12. `lab-books` skill's fold-in of `run_lab.ts` does **not** introduce a `--max-steps`
    flag anywhere (§3 item 4). Verify: `grep -- "--max-steps" .claude/skills/lab-books/SKILL.md`
    returns no matches.
13. The 6 SKIP tools (`pipeline.ts`, `inventory.ts`, `backfill.ts`, `archive_worktrees.ts`,
    `generate_manifest.ts`, `list_stories.ts`) get **no new skill file**; any doc-quality
    nits noted against them in §1 (e.g. `backfill.ts`'s flags not itemized in `analyze`
    skill) are optional follow-ups, not required by this scope.
14. No new skill or fold-in references `.opencode/tools/*.ts` file paths as the source of
    truth for a flag — every flag documented anywhere in the output must cite the
    `scripts/*.py`/`admin/server.py` line verified in this doc or a fresh re-verification,
    per the "tool declared args do NOT always match the script" premise that produced
    corrections 3, 4, 5, 6, 7 above.
15. `docs/architecture/current/claude_code_port.md` is either left unchanged (if its D1 "no MCP" stance is
    considered separate from this skills-based port) or gets a cross-reference added
    noting that this doc's skills satisfy the tool knowledge D1 said didn't need an MCP
    server — a documentation-consistency check, not a functional requirement.
