---
name: queue
description: Fill and drain the Redis story_jobs queue (enqueue.py), run BRPOP workers (worker.py), and check queue status (monitor.py, incl. the --json machine-readable dashboard). Use when asked to enqueue story cells, start/stop/check workers, or view the queue dashboard — covers the finops-queue Redis instance on port 6380, not the finops-redis story-agent instance on 6379.
disable-model-invocation: false
user-invocable: false
argument-hint: ""
---

# Queue Skill — Redis story_jobs Lifecycle

Ordering matters: **enqueue → worker → monitor**. Fill the queue first, start worker(s) to
drain it, then check status. All three scripts target the framework's own Redis instance —
`127.0.0.1:${FINOPS_REDIS_PORT:-6380}`, db `${FINOPS_REDIS_DB:-1}` — **never** the
`finops-redis` instance on 6379 that story agents' own Flask/Celery apps use (those call
`flushdb()`/`flushall()` while testing; see `mental-model.md`/`AGENTS.md`'s Redis isolation
note). Never point any of these scripts at 6379.

## 1. `enqueue.py` — fill the queue

Manual `sys.argv` parse, confirmed `scripts/enqueue.py:143-152`:

```
--dry-run        in sys.argv — print the plan only, don't write to Redis
--clear          in sys.argv — reset the queue (destructive)
--missing-only   in sys.argv — skip cells that already have a saved result
--interleave     in sys.argv — round-robin fill across models/providers so concurrent
                  workers spread across providers instead of hammering one
--model VALUE    read via sys.argv.index("--model") + 1
                  default: $FINOPS_MODEL, else "deepseek/deepseek-v4-pro"
```

```bash
python3 scripts/enqueue.py                                    # fill queue, default model
python3 scripts/enqueue.py --model anthropic/claude-sonnet-5   # target a specific model
python3 scripts/enqueue.py --missing-only                      # skip cells with a saved result
python3 scripts/enqueue.py --interleave                        # round-robin across providers
python3 scripts/enqueue.py --dry-run                           # print the plan only
python3 scripts/enqueue.py --clear                             # reset the queue (destructive)
```

**Safety convention: never run `--clear` without checking queue state first.** The
opencode `enqueue.ts` tool's own gate refuses a bare `clear` and tells the caller to pass
`dry_run=true` alongside it "to see what would be removed" — but tracing `scripts/enqueue.py`'s
`main()` shows this doesn't actually work: the `if dry_run:` branch returns *before* the
script ever reaches `if clear:`, so `--dry-run --clear` together just prints the normal
"Would enqueue N cells" plan, not a preview of what `--clear` would delete. There is no
flag that previews a clear. The real safety practice: check current queue contents with
`python scripts/monitor.py` (or `--json`) *before* running `--clear` bare — `--clear` takes
effect immediately and irreversibly once run without `--dry-run`.

## 2. `worker.py` — drain the queue

Zero CLI flags — confirmed no `add_argument`/`sys.argv` parsing in the file; `main()` just
loops on Redis `BRPOP`. Env vars, `scripts/worker.py:22-24`:

```
FINOPS_REDIS_HOST   default: 127.0.0.1
FINOPS_REDIS_PORT   default: 6380
FINOPS_REDIS_DB     default: 1
```

Lifecycle is process management, not script flags:

```bash
python3 scripts/worker.py &      # start (background); auto-exits after 2 min idle
pgrep -f "scripts/worker.py"     # status — list running worker PIDs
pkill -f "scripts/worker.py"     # stop all workers
```

Run N workers in parallel for N-way concurrency (`AGENTS.md`'s Commands block: "worker.py
— BRPOP worker — run N in parallel") — start multiple `python3 scripts/worker.py &`
processes.

## 3. `monitor.py` — check status

Manual `sys.argv` parse, confirmed `scripts/monitor.py:114-116`:

```
--watch    in sys.argv — live 5s-refresh loop, needs an interactive terminal
--clear    in sys.argv — deletes story_jobs/story_status/story_results (destructive)
--json     in sys.argv — machine-readable output
```

```bash
python3 scripts/monitor.py             # human-readable status snapshot
python3 scripts/monitor.py --json      # machine-readable — the canonical dashboard example
python3 scripts/monitor.py --watch     # live loop — run manually in an interactive terminal
python3 scripts/monitor.py --clear     # deletes queue state — destructive, run manually
```

`--json` is the canonical machine-readable dashboard invocation — this is the exact command
to run for "show me the queue dashboard" or any programmatic status check; there is no
separate dashboard script, just `monitor.py --json`.

**Guardrails to preserve, not fill in:** don't run `--watch` from an agent session (it
needs a real interactive terminal — tell the user to run it manually) and don't run
`--clear` automatically (it's destructive — tell the user to run
`python scripts/monitor.py --clear` manually if they want to reset the queue).

## Common gotchas

- Redis isolation: this queue is `finops-queue` on port 6380. `finops-redis` on 6379
  belongs to story agents under test and must never host this queue.
- `--clear` on either `enqueue.py` or `monitor.py` is destructive — always dry-run/confirm
  first, never auto-run it.
- `worker.py` auto-exits after 2 minutes idle — if a worker seems to have "disappeared,"
  that's expected once the queue drains, not a crash.
- `--watch` needs a real terminal — don't attempt to run it from a non-interactive agent
  session; direct the user to run it themselves.
