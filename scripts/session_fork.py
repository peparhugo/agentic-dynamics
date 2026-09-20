#!/usr/bin/env python3
"""Fan out contemplation prompts from ONE approved aio-control session (in-process forks).

Bounded operator-authorized exception to the fleet-only rule (decision 5d9362133040): the
prompts are ANALYSIS-ONLY contemplations (no actions), run ONE fork at a time against the
session's live store, each in the adapter's own isolated worktree, with per-fork receipts.
The safety clause is prepended to every prompt by the command itself.

Scheduled fan-out: all prompts fork the SAME parent, so the parent prefix stays stable across
siblings — the first sibling pays the cold prefix, later siblings ride the provider cache.
Every fork is recorded (prompt hash, session ids, tokens, cache read/write, cost, latency,
answer) under the output directory; transcript content stays in the store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path.home() / ".local/share/opencode/opencode.db"
DEFAULT_OUT = REPO / "experiments" / "results" / "fork_contemplation"

SAFETY = ("CONTEMPLATION - ANALYSIS ONLY. Do not modify files, run commands, or write code; "
 "answer as text. You are a FORKED aio-control session: the working history above is your "
 "evidence - cite specific moments, decisions, and failures by name.")

METHOD = ("METHOD - MoE leverage: before reconciling, route deliberately across 5-7 DISTINCT "
 "expert lenses this material activates (e.g. control theory, distributed systems, measurement "
 "epistemology, safety engineering, organizational economics, evolutionary dynamics, game "
 "theory). Give each lens an independent short take; keep conflicts visible and name the "
 "discriminating test. Divergence first, synthesis second. Ground every claim in a specific "
 "moment from the context.")

EVIDENCE = ("KNOWN FINDINGS (project knowledge base): 7948b8ace287e881 - prompt-branch pilot: "
 "no instruction arm improved accepted outcomes; baseline cost-minimal; cache 95.5-97.9%. "
 "6ef9bf9b6ef3b53a - fleet transport: goals ride argv (newlines refused); untracked specs never "
 "reach run clones. c50f37cfff42523b - Docker forks: one seed -> four isolated branches, cache "
 "47% cold -> 90% warm, total $0.004735. Frozen real-session snapshots refuse to fork in Docker "
 "(three attempts; directory/project adaptations insufficient) - hence this in-process path.")

SIBLING_ANSWER_CAP = 1500


def sibling_digest(receipts: list[dict]) -> str:
    """The synthesis payload: every PRIOR fork's identity, economics and answer.

    Expanded into any prompt containing ``{{SIBLINGS}}`` — the meta/synthesis pass runs LAST and
    receives the whole fan-out, not just the shared parent context.
    """
    if not receipts:
        return "(no sibling contemplations ran before this pass)"
    lines = ["SIBLING CONTEMPLATIONS (this fan-out, in run order):"]
    for r in receipts:
        answer = str(r.get("answer") or "")
        if len(answer) > SIBLING_ANSWER_CAP:
            answer = answer[:SIBLING_ANSWER_CAP] + " [...truncated]"
        lines.append(
            f"\n### {r['index']:02d} {r['title']}\n"
            f"(fork {r.get('fork_session_id','') or '?'} | {r.get('tokens',0)} tok | "
            f"cache_read {r.get('cache_read_tokens',0)} | ${r.get('cost_usd',0):.5f} | "
            f"{r.get('latency_s',0)}s)\n{answer}"
        )
    return "\n".join(lines)


def expand_placeholders(body: str, receipts: list[dict]) -> str:
    """Replace ``{{SIBLINGS}}`` / ``{{FINDINGS}}`` with the batch's evidence."""
    return body.replace("{{SIBLINGS}}", sibling_digest(receipts)).replace("{{FINDINGS}}", EVIDENCE)


def parse_prompts(text: str) -> list[dict[str, str]]:
    """Split a prompts file on '## <title>' blocks."""
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            current = {"title": m.group(1).strip(), "body": ""}
            blocks.append(current)
        elif current is not None:
            current["body"] += line + "\n"
    return [b for b in blocks if b["body"].strip()]


def session_exists(db: Path, session_id: str) -> bool:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute("select 1 from session where id = ?", (session_id,)).fetchone() is not None
    finally:
        con.close()


def compose(prompt_body: str) -> str:
    return f"{SAFETY}\n\n{METHOD}\n\n{EVIDENCE}\n\nTASK\n{prompt_body.strip()}\n"


def run_fork_batch(*, session_id: str, prompts: list[dict[str, str]], out: Path,
                   model: str, timeout: int, run_agent=None, limit: int = 0) -> list[dict]:
    """Run the fan-out sequentially; return the per-fork receipts."""
    if run_agent is None:
        from agentic_dynamics.adapters.opencode import run_opencode_agentic

        run_agent = run_opencode_agentic
    out.mkdir(parents=True, exist_ok=True)
    receipts: list[dict] = []
    for i, p in enumerate(prompts[: limit or len(prompts)], start=1):
        body = expand_placeholders(p["body"], receipts)
        text = compose(body)
        t0 = time.time()
        r = run_agent(text, model=model, session_id=session_id, fork=True, timeout=timeout)
        rec = {
            "schema": "session-fork/v1",
            "index": i,
            "title": p["title"],
            "prompt_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "parent_session_id": session_id,
            "fork_session_id": getattr(r, "session_id", "") or "",
            "ok": bool(getattr(r, "ok", False)),
            "error": (getattr(r, "error", "") or "")[:300],
            "tokens": getattr(r, "total_tokens", 0) or 0,
            "cache_read_tokens": getattr(r, "cache_read_tokens", 0) or 0,
            "cache_write_tokens": getattr(r, "cache_write_tokens", 0) or 0,
            "cache_hit_rate": getattr(r, "cache_hit_rate", 0.0) or 0.0,
            "cost_usd": getattr(r, "estimated_cost_usd", 0.0) or 0.0,
            "latency_s": round(time.time() - t0, 1),
            "answer": (getattr(r, "final_response", "") or ""),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        receipts.append(rec)
        stem = f"fork-{i:02d}-{re.sub(r'[^a-z0-9]+', '-', p['title'].lower()).strip('-')[:40]}"
        (out / f"{stem}.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        with (out / "forks.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: v for k, v in rec.items() if k != "answer"}) + "\n")
        print(f"[{i:02d}] {p['title'][:44]:44} ok={rec['ok']} tok={rec['tokens']:>6} "
              f"cache_read={rec['cache_read_tokens']:>7} ${rec['cost_usd']:.5f} {rec['latency_s']}s",
              file=sys.stderr)
    return receipts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session", required=True, help="explicit parent aio-control session id")
    ap.add_argument("--prompts-file", required=True, help="markdown file; '## title' blocks")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--model", default="deepseek/deepseek-v4-flash")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not session_exists(Path(args.db), args.session):
        print(f"parent session {args.session} not found in {args.db} - refusing", file=sys.stderr)
        return 2
    prompts = parse_prompts(Path(args.prompts_file).read_text(encoding="utf-8"))
    if not prompts:
        print("no '## ' prompt blocks found - refusing", file=sys.stderr)
        return 2
    print(f"parent {args.session} | {len(prompts)} prompts | model {args.model} | out {args.out}")
    if args.dry_run:
        for i, p in enumerate(prompts, 1):
            print(f"  [{i:02d}] {p['title']} ({len(p['body'])} chars)")
        return 0

    from agentic_dynamics.control.admission import AdmissionRequest, admitted
    from agentic_dynamics.control.lease_registry import LeaseScope, ScopeKind
    from agentic_dynamics.core.cost_provenance import CostSource

    scope = LeaseScope(ScopeKind.CAMPAIGN, "aio_session")
    req = AdmissionRequest(run_id=f"session-fork-{int(time.time())}", model=args.model,
                           worktree_identity="session_fork", result_namespace="session_fork",
                           amount=0.5, cost_source=CostSource.ESTIMATED, hard_cap_usd=1.0,
                           budget_scope=scope, concurrency_scopes=(scope,))
    with admitted(req):
        receipts = run_fork_batch(session_id=args.session, prompts=prompts, out=Path(args.out),
                                  model=args.model, timeout=args.timeout, limit=args.limit)
    total = sum(r["cost_usd"] for r in receipts)
    ok = sum(1 for r in receipts if r["ok"])
    print(json.dumps({"schema": "session-fork-batch/v1", "forks": len(receipts), "ok": ok,
                      "total_cost_usd": round(total, 5), "out": str(args.out)}, indent=2))
    return 0 if ok == len(receipts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
