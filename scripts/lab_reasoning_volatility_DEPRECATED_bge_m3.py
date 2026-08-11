#!/usr/bin/env python3
r"""Lab Book: Reasoning Volatility Score (RVS) — Consecutive-Step Semantic Coherence

Computes trigram overlap distance between consecutive reasoning steps within each
session. Higher RVS = scattered concept-hopping. Lower RVS = focused linear reasoning.

Uses text-level trigram overlap (Jaccard distance) for consistent, deterministic
measurement across all sessions regardless of ChromaDB indexing state.

Output: experiments/results/lab_volatility.json
"""

import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
REPORTS_DIR = ROOT / "experiments" / "results" / "reports"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_volatility.json"


def trigram_distance(text_a: str, text_b: str, n: int = 3) -> float:
    def trigrams(s):
        return {s[i:i + n] for i in range(len(s) - n + 1)}
    ta, tb = trigrams(text_a), trigrams(text_b)
    if not ta or not tb:
        return 1.0
    return 1.0 - len(ta & tb) / len(ta | tb)


def extract_reasoning_steps(jsonl_path: Path) -> list[str]:
    """Extract thinking text from a session.jsonl file, skipping empty/short texts."""
    texts = []
    for line in jsonl_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") == "reasoning":
            text = rec.get("text", "").strip()
            if text and len(text) >= 20:
                texts.append(text)
    return texts


def compute_rvs(thinking_texts: list[str]) -> tuple:
    n = len(thinking_texts)
    if n < 3:
        return None, None

    distances = []
    for i in range(n - 1):
        d = trigram_distance(thinking_texts[i], thinking_texts[i + 1])
        distances.append(d)

    if not distances:
        return None, None

    mean_rvs = sum(distances) / len(distances)
    if len(distances) > 1:
        variance = sum((d - mean_rvs) ** 2 for d in distances) / len(distances)
        rvs_std = math.sqrt(variance)
    else:
        rvs_std = 0.0

    return mean_rvs, rvs_std


def main():
    summary_data = json.loads(SUMMARY_PATH.read_text())
    session_map: dict[str, dict] = {}
    for e in summary_data.get("entries", []):
        wn = e.get("worktree_name", "")
        session_map[wn] = {
            "model": e.get("model", "unknown"),
            "correctness": e.get("correctness", 0),
            "experiment": e.get("experiment", wn),
        }

    session_files = {}
    for d in sorted(REPORTS_DIR.iterdir()):
        if d.is_dir() and (d / "session.jsonl").exists():
            session_files[d.name] = d / "session.jsonl"

    print(f"Found {len(session_files)} session directories")

    all_sessions = []
    by_model: dict[str, list[float]] = defaultdict(list)
    by_correctness: dict[str, list[float]] = defaultdict(list)
    skipped = 0

    for session_name, jsonl_path in sorted(session_files.items()):
        meta = session_map.get(session_name, {
            "model": "unknown",
            "correctness": 0,
            "experiment": session_name,
        })

        thinking_texts = extract_reasoning_steps(jsonl_path)
        if len(thinking_texts) < 3:
            skipped += 1
            continue

        rvs, rvs_std = compute_rvs(thinking_texts)
        if rvs is None:
            skipped += 1
            continue

        c = meta.get("correctness", 0)
        if not isinstance(c, (int, float)):
            c = 0

        session_record = {
            "session": session_name,
            "model": meta["model"],
            "rvs": round(rvs, 6),
            "rvs_std": round(rvs_std, 6),
            "steps": len(thinking_texts),
            "correctness": c,
        }
        all_sessions.append(session_record)
        by_model[meta["model"]].append(rvs)

        if c > 0.9:
            by_correctness["high (>0.9)"].append(rvs)
        elif c >= 0.7:
            by_correctness["mid (0.7-0.9)"].append(rvs)
        else:
            by_correctness["low (<0.7)"].append(rvs)

    print(f"  Skipped (<3 steps): {skipped}")
    print(f"  Valid sessions: {len(all_sessions)}")

    model_aggregates = {}
    for model_id, rvs_list in sorted(by_model.items()):
        n = len(rvs_list)
        if n == 0:
            continue
        mean_rvs = sum(rvs_list) / n
        sorted_rvs = sorted(rvs_list)
        median_rvs = sorted_rvs[n // 2] if n % 2 else (sorted_rvs[n // 2 - 1] + sorted_rvs[n // 2]) / 2
        variance = sum((x - mean_rvs) ** 2 for x in rvs_list) / n
        std_rvs = math.sqrt(variance)
        model_aggregates[model_id] = {
            "mean_rvs": round(mean_rvs, 6),
            "median_rvs": round(median_rvs, 6),
            "rvs_std": round(std_rvs, 6),
            "n_sessions": n,
        }

    correctness_buckets = {}
    for bucket, rvs_list in by_correctness.items():
        n = len(rvs_list)
        if n == 0:
            continue
        correctness_buckets[bucket] = {
            "mean_rvs": round(sum(rvs_list) / n, 6),
            "n": n,
        }

    output = {
        "metric": "reasoning_volatility_score",
        "description": "Mean trigram overlap distance between consecutive reasoning steps — measures semantic coherence within a session",
        "computation": {
            "method": "Trigram Jaccard distance between consecutive reasoning step texts. Same metric across all sessions for consistency.",
            "total_sessions_indexed": len(session_files),
            "valid_sessions": len(all_sessions),
            "skipped_insufficient_steps": skipped,
        },
        "by_model": model_aggregates,
        "by_correctness_bucket": correctness_buckets,
        "sessions": sorted(all_sessions, key=lambda s: s["session"]),
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\nWrote {OUTPUT_PATH}")

    label_map = {
        "deepseek/deepseek-v4-pro": "DeepSeek v4 Pro",
        "anthropic/claude-fable-5": "Claude Fable 5",
        "openai/gpt-5": "GPT-5",
        "openai/gpt-5-mini": "GPT-5-mini",
        "openai/gpt-5-nano": "GPT-5-nano",
        "openai/gpt-5.5": "GPT-5.5",
        "openai/gpt-5.6": "GPT-5.6",
        "openai/gpt-5.6-fast": "GPT-5.6-fast",
    }
    print("\n=== Per-Model RVS ===")
    for model_id, agg in model_aggregates.items():
        label = label_map.get(model_id, model_id)
        print(f"  {label:20s} n={agg['n_sessions']:3d}  mean={agg['mean_rvs']:.4f}  median={agg['median_rvs']:.4f}  std={agg['rvs_std']:.4f}")

    print("\n=== Correctness Buckets ===")
    for bucket, agg in correctness_buckets.items():
        print(f"  {bucket:20s} n={agg['n']:3d}  mean_rvs={agg['mean_rvs']:.4f}")


if __name__ == "__main__":
    main()
