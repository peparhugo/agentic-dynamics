#!/usr/bin/env python3
"""Analyze session.jsonl transcripts from experiment worktrees.

Parses complete model interaction traces to extract step-level operational
metrics that are COMPARABLE ACROSS ALL MODELS:

  - Total tokens and cost per session (from step-finish events)
  - Step count: how many iterations to complete work
  - Tool call composition: read/write/bash ratios
  - Git snapshots: code evolution tracking

Per-session metrics like thinking_density and code_density are kept in
the per-transcript output for inspection but are NOT aggregated across
models because different architectures emit different event types:
  - DeepSeek emits "reasoning" events (GRPO latent reasoning surfaced as text)
  - Claude emits "text" events (chain-of-thought embedded in output tokens)
  - These are fundamentally different and not comparable cross-model.

The worktree analysis (analyze_worktrees.py) handles proper cross-model
cost efficiency comparison through narration_penalty and thinking_ratio.

Produces:
    experiments/results/_trajectory_summary.json  — per-transcript metrics
    experiments/results/_trajectory_aggregate.json — per-model comparable aggregates
"""

import json
import sys
import argparse
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "experiments" / "results" / "reports"
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "_trajectory_summary.json"
AGGREGATE_PATH = ROOT / "experiments" / "results" / "_trajectory_aggregate.json"


def build_model_map():
    """Build mappings from worktree name → {model, operator, experiment}."""
    model_map = {}
    op_map = {}
    exp_map = {}
    if SUMMARY_PATH.exists():
        data = json.loads(SUMMARY_PATH.read_text())
        for entry in data.get("entries", []):
            wt_name = entry.get("worktree_name", "")
            model = entry.get("model", "unknown")
            operator = entry.get("operator", "unknown")
            experiment = entry.get("experiment", "unknown")
            if wt_name and model:
                model_map[wt_name] = model
            if wt_name and operator:
                op_map[wt_name] = operator
            if wt_name and experiment:
                exp_map[wt_name] = experiment
    return model_map, op_map, exp_map


def find_session_jsonls():
    found = []
    if not REPORTS_DIR.exists():
        return found
    for d in sorted(REPORTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        sj = d / "session.jsonl"
        if sj.exists():
            found.append((d.name, sj))
    return found


def parse_session_jsonl(path):
    result = {
        "total_tokens": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_reasoning_tokens": 0,
        "total_cache_read": 0,
        "total_cache_write": 0,
        "total_cost": 0.0,
        "reasoning_chars": 0,
        "tool_content_chars": 0,
        "thinking_density": 0.0,
        "code_density": 0.0,
        "step_count": 0,
        "max_step_tokens": 0,
        "read_calls": 0,
        "write_calls": 0,
        "bash_calls": 0,
        "other_calls": 0,
        "tool_call_counts": Counter(),
        "tool_call_sequence": [],
        "git_snapshots": 0,
        "parse_errors": 0,
    }

    try:
        with open(path) as f:
            first_text_skipped = False
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    result["parse_errors"] += 1
                    continue

                etype = event.get("type", "")

                if etype == "reasoning":
                    text = event.get("text", "")
                    if text:
                        result["reasoning_chars"] += len(text)

                elif etype == "text":
                    if not first_text_skipped:
                        first_text_skipped = True
                        continue
                    text = event.get("text", "")
                    if text:
                        result["reasoning_chars"] += len(text)

                elif etype == "tool":
                    tool = event.get("tool", "unknown")
                    result["tool_call_counts"][tool] += 1
                    result["tool_call_sequence"].append(tool)
                    if tool in ("read", "Read"):
                        result["read_calls"] += 1
                    elif tool in ("write", "Write", "edit", "Edit"):
                        result["write_calls"] += 1
                        state = event.get("state", {})
                        inp = state.get("input", {})
                        if isinstance(inp, dict):
                            content = inp.get("content", "")
                            if isinstance(content, str):
                                result["tool_content_chars"] += len(content)
                    elif tool in ("bash", "Bash", "execute", "Execute"):
                        result["bash_calls"] += 1
                    else:
                        result["other_calls"] += 1

                elif etype == "step-finish":
                    result["step_count"] += 1
                    tokens = event.get("tokens", {})
                    if isinstance(tokens, dict):
                        inp = tokens.get("input", 0) or tokens.get("prompt_tokens", 0) or 0
                        out = tokens.get("output", 0) or tokens.get("completion_tokens", 0) or 0
                        reason = tokens.get("reasoning", 0) or 0
                        cache = tokens.get("cache", {})
                        cr = (cache.get("read", 0) if isinstance(cache, dict) else 0) or 0
                        cw = (cache.get("write", 0) if isinstance(cache, dict) else 0) or 0
                        total_field = tokens.get("total", 0) or 0

                        result["total_input_tokens"] += inp
                        result["total_output_tokens"] += out
                        result["total_reasoning_tokens"] += reason
                        result["total_cache_read"] += cr
                        result["total_cache_write"] += cw

                        step_total = total_field if total_field > 0 else (inp + out + reason)
                        result["total_tokens"] += step_total
                        if step_total > result["max_step_tokens"]:
                            result["max_step_tokens"] = step_total
                    cost = event.get("cost", 0) or 0
                    result["total_cost"] += float(cost) if cost else 0
                    if event.get("snapshot", ""):
                        result["git_snapshots"] += 1

                elif etype == "step-start":
                    if event.get("snapshot", ""):
                        result["git_snapshots"] += 1

    except Exception:
        result["parse_errors"] += 1

    if result["total_output_tokens"] > 0:
        result["thinking_density"] = round(
            result["reasoning_chars"] / result["total_output_tokens"], 4)
        result["code_density"] = round(
            result["tool_content_chars"] / result["total_output_tokens"], 4)

    total_tc = sum(result["tool_call_counts"].values())
    if total_tc > 0:
        result["read_pct"] = round(result["read_calls"] / total_tc * 100, 1)
        result["write_pct"] = round(result["write_calls"] / total_tc * 100, 1)
        result["bash_pct"] = round(result["bash_calls"] / total_tc * 100, 1)

    return result


def analyze_all(limit=0, model_filter=None):
    jsonls = find_session_jsonls()
    print(f"Found {len(jsonls)} session.jsonl files")

    model_map, op_map, exp_map = build_model_map()
    if model_map:
        print(f"  Model map: {len(model_map)} worktree names → models")

    if model_filter:
        jsonls = [j for j in jsonls if model_filter.lower() in j[0].lower()]
        print(f"  Filtered to {len(jsonls)} matching model '{model_filter}'")

    if limit > 0:
        jsonls = jsonls[:limit]
        print(f"  Limited to {limit}")

    results = []
    by_model = defaultdict(list)
    by_task_model = defaultdict(list)

    for i, (name, path) in enumerate(jsonls):
        parsed = parse_session_jsonl(path)
        parsed["report_name"] = name
        parsed["detected_model"] = model_map.get(name, "unknown")
        parsed["detected_operator"] = op_map.get(name, "unknown")
        exp_name = exp_map.get(name, "")
        task_type = "baseline" if exp_name == "baseline" else (
            exp_name.rsplit("_s", 1)[0] if "_s" in exp_name else
            exp_name.rsplit("_r", 1)[0] if "_r" in exp_name else exp_name
        )
        if exp_name.startswith("exp_"):
            task_type = "perturbed"
        parsed["task_type"] = task_type
        results.append(parsed)
        by_model[parsed["detected_model"]].append(parsed)
        by_task_model[f"{task_type}|{parsed['detected_model']}"].append(parsed)
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(jsonls)}...")

    print(f"\nProcessed {len(results)} transcripts")

    model_aggregates = {}
    for model_id, entries in by_model.items():
        agg = {
            "count": len(entries),
            "avg_steps": 0,
            "avg_tokens_per_session": 0,
            "avg_output_tokens": 0,
            "avg_input_tokens": 0,
            "avg_reasoning_tokens": 0,
            "avg_cache_read": 0,
            "avg_cache_write": 0,
            "avg_cost_per_session": 0,
            "avg_git_snapshots": 0,
            "avg_max_step_tokens": 0,
            "avg_read_pct": 0,
            "avg_write_pct": 0,
            "avg_bash_pct": 0,
            "total_parse_errors": 0,
            "tool_call_distribution": Counter(),
        }
        if entries:
            n = len(entries)
            agg["avg_steps"] = round(sum(e["step_count"] for e in entries) / n, 1)
            agg["avg_tokens_per_session"] = round(sum(e["total_tokens"] for e in entries) / n)
            agg["avg_output_tokens"] = round(sum(e["total_output_tokens"] for e in entries) / n)
            agg["avg_input_tokens"] = round(sum(e["total_input_tokens"] for e in entries) / n)
            agg["avg_reasoning_tokens"] = round(sum(e["total_reasoning_tokens"] for e in entries) / n)
            agg["avg_cache_read"] = round(sum(e["total_cache_read"] for e in entries) / n)
            agg["avg_cache_write"] = round(sum(e["total_cache_write"] for e in entries) / n)
            agg["avg_cost_per_session"] = round(sum(e["total_cost"] for e in entries) / n, 6)
            agg["avg_git_snapshots"] = round(sum(e["git_snapshots"] for e in entries) / n, 1)
            agg["avg_max_step_tokens"] = round(sum(e["max_step_tokens"] for e in entries) / n)
            agg["avg_read_pct"] = round(sum(e.get("read_pct", 0) for e in entries) / n, 1)
            agg["avg_write_pct"] = round(sum(e.get("write_pct", 0) for e in entries) / n, 1)
            agg["avg_bash_pct"] = round(sum(e.get("bash_pct", 0) for e in entries) / n, 1)
            agg["total_parse_errors"] = sum(e["parse_errors"] for e in entries)
            for e in entries:
                agg["tool_call_distribution"].update(e["tool_call_counts"])
        model_aggregates[model_id] = agg

    task_model_aggregates = {}
    for key, entries in by_task_model.items():
        if len(entries) == 0:
            continue
        parts = key.split("|", 1)
        task_type, model_id = parts[0], parts[1] if len(parts) > 1 else "?"
        n = len(entries)
        task_model_aggregates[key] = {
            "task_type": task_type,
            "model": model_id,
            "count": n,
            "avg_total_tokens": round(sum(e["total_tokens"] for e in entries) / n),
            "avg_output_tokens": round(sum(e["total_output_tokens"] for e in entries) / n),
            "avg_cache_read": round(sum(e["total_cache_read"] for e in entries) / n),
            "avg_cache_write": round(sum(e["total_cache_write"] for e in entries) / n),
            "avg_cost": round(sum(e["total_cost"] for e in entries) / n, 6),
            "avg_steps": round(sum(e["step_count"] for e in entries) / n, 1),
            "avg_read_pct": round(sum(e.get("read_pct", 0) for e in entries) / n, 1),
            "avg_write_pct": round(sum(e.get("write_pct", 0) for e in entries) / n, 1),
        }

    total_tc_all = Counter()
    for r in results:
        total_tc_all.update(r["tool_call_counts"])

    return {
        "_meta": {
            "total_transcripts_analyzed": len(results),
            "total_models": len(by_model),
            "note": "thinking_density and code_density are per-transcript only — not comparable across models. Use worktree analysis (narration_penalty, thinking_ratio) for cross-model cost efficiency comparison.",
        },
        "per_transcript": results,
        "by_model": {k: v for k, v in model_aggregates.items()},
        "by_task_model": task_model_aggregates,
        "global": {
            "avg_steps": round(sum(r["step_count"] for r in results) / max(len(results), 1), 1),
            "avg_tokens": round(sum(r["total_tokens"] for r in results) / max(len(results), 1)),
            "avg_cost": round(sum(r["total_cost"] for r in results) / max(len(results), 1), 6),
            "tool_call_distribution": dict(total_tc_all.most_common(20)),
            "total_parse_errors": sum(r["parse_errors"] for r in results),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze session.jsonl experiment transcripts")
    parser.add_argument("--limit", type=int, default=0, help="Max transcripts to process")
    parser.add_argument("--model", help="Filter by model name (e.g. deepseek, claude)")
    parser.add_argument("--dry-run", action="store_true", help="Print instead of writing")
    args = parser.parse_args()

    summary = analyze_all(limit=args.limit, model_filter=args.model)

    if args.dry_run:
        print("\n--- DRY RUN ---")
        print(f"Models: {list(summary['by_model'].keys())}")
        print(f"Global avg steps: {summary['global']['avg_steps']}")
        print(f"Global avg tokens: {summary['global']['avg_tokens']}")
        print(f"Global avg cost: ${summary['global']['avg_cost']:.6f}")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary["per_transcript"], indent=2, default=str))
    AGGREGATE_PATH.write_text(json.dumps({
        "_meta": summary["_meta"],
        "by_model": summary["by_model"],
        "by_task_model": summary["by_task_model"],
        "global": summary["global"],
    }, indent=2, default=str))
    print(f"\nWrote per-transcript data to {OUTPUT_PATH}")
    print(f"Wrote aggregate data to {AGGREGATE_PATH}")


if __name__ == "__main__":
    main()
