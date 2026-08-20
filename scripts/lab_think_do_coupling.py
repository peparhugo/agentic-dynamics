#!/usr/bin/env python3
"""Lab Book: Think-Do Coupling Index

For each step in each session, measure similarity between the model's
thinking (reasoning + narration) and the tool call + observation that follows.
High coupling = the model thinks about what it actually does.
Low coupling = narration and action are disconnected.

Output: experiments/results/lab_coupling.json
"""

import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from agentic_dynamics.core.constants import MODEL_LABELS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
REPORTS_DIR = ROOT / "experiments" / "results" / "reports"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_coupling.json"


def serialize_tool_input(inp):
    """Serialize tool input for embedding, handling dict/list/string."""
    if isinstance(inp, str):
        return inp
    if isinstance(inp, (dict, list)):
        return json.dumps(inp, sort_keys=True, default=str)
    return str(inp)


def load_session_pairs(session_path):
    """Extract (thinking, action) pairs from a session.jsonl file.
    Each thinking is the reasoning+text preceding a tool call within the same step.
    Action = tool_name + serialized state.input + state.output.
    """
    pairs = []
    with open(session_path) as f:
        current_thinking = []
        in_step = False
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            t = d.get("type")

            if t == "step-start":
                in_step = True
                current_thinking = []
            elif t == "step-finish":
                in_step = False
            elif t in ("reasoning", "text") and in_step:
                txt = d.get("text", "").strip()
                if txt:
                    current_thinking.append(txt)
            elif t == "tool" and in_step:
                tool_name = d.get("tool", "")
                state = d.get("state", {})
                tool_input = serialize_tool_input(state.get("input", ""))
                tool_output = str(state.get("output", ""))
                if not tool_output.strip():
                    # Some tools use metadata.output
                    meta = state.get("metadata", {})
                    if isinstance(meta, dict):
                        tool_output = str(meta.get("output", ""))
                action_text = f"{tool_name} {tool_input} {tool_output}".strip()

                thinking_text = " ".join(current_thinking).strip()
                if thinking_text and action_text:
                    pairs.append((thinking_text, action_text))

    return pairs


def compute():
    print("Loading _results_summary.json ...")
    summary = json.loads(SUMMARY_PATH.read_text())
    entries = summary.get("entries", [])

    # Build worktree_name -> entry index
    wt_to_entry = {}
    for e in entries:
        wt = e.get("worktree_name", "")
        if wt:
            wt_to_entry[wt] = e

    # Find all session.jsonl files
    session_files = sorted(glob.glob(
        str(REPORTS_DIR / "*/session.jsonl")
    ))
    print(f"Found {len(session_files)} session files")

    # First pass: collect all thinking/action pairs and map to sessions
    session_data = []  # [(session_id, model, correctness, narration_penalty, perturbation_class, tdci_pairs)]
    all_thinking = []
    all_actions = []

    for sf in session_files:
        session_dir = Path(sf).parent.name
        entry = wt_to_entry.get(session_dir, {})

        model = entry.get("model", "unknown")
        correctness = entry.get("correctness")
        narration_penalty = entry.get("narration_penalty", 0)
        perturbation_class = entry.get("perturbation_class", "unknown")

        pairs = load_session_pairs(sf)
        if not pairs:
            continue

        all_thinking.extend(p[0] for p in pairs)
        all_actions.extend(p[1] for p in pairs)
        session_data.append({
            "session": session_dir,
            "model": model,
            "correctness": correctness,
            "narration_penalty": narration_penalty,
            "perturbation_class": perturbation_class,
            "n_pairs": len(pairs),
        })

    print(f"Total sessions with pairs: {len(session_data)}")
    print(f"Total step-pairs: {len(all_thinking)}")

    # Fit global TF-IDF vectorizer on all texts
    print("Fitting TF-IDF vectorizer ...")
    all_texts = all_thinking + all_actions
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),
        max_features=10000,
        sublinear_tf=True,
        max_df=0.9,
        min_df=2,
        stop_words="english",
    )
    all_vectors = vectorizer.fit_transform(all_texts)

    n_pairs = len(all_thinking)
    thinking_vectors = all_vectors[:n_pairs]
    action_vectors = all_vectors[n_pairs:]

    # Compute cosine similarity for each pair
    print("Computing coupling similarities ...")
    # Use efficient batch cosine similarity
    # For each pair, extract row and compute similarity
    # We can do this in chunks for large datasets
    similarities = []
    pair_idx = 0
    for sd in session_data:
        n = sd["n_pairs"]
        session_sims = []
        for i in range(n):
            tv = thinking_vectors[pair_idx + i]
            av = action_vectors[pair_idx + i]
            sim = cosine_similarity(tv, av)[0][0]
            session_sims.append(float(sim))
        sd["tdci"] = float(np.mean(session_sims)) if session_sims else 0.0
        sd["tdci_values"] = session_sims
        similarities.extend(session_sims)
        pair_idx += n

    # Remove intermediate data before serialization
    for sd in session_data:
        sd.pop("n_pairs", None)
        sd.pop("tdci_values", None)

    # Exclude sessions with no correctness or narration_failure
    valid_sessions = [
        s for s in session_data
        if s["correctness"] is not None and s["correctness"] >= 0
    ]

    # Per-model aggregation
    by_model = defaultdict(list)
    for s in valid_sessions:
        m = s["model"]
        by_model[m].append(s)

    by_model_agg = {}
    for model, sessions in sorted(by_model.items()):
        tdciv = [s["tdci"] for s in sessions]
        corrv = [s["correctness"] for s in sessions]
        [s["narration_penalty"] for s in sessions]
        label = MODEL_LABELS.get(model, model)
        by_model_agg[label] = {
            "model_id": model,
            "mean_tdci": round(float(np.mean(tdciv)), 4),
            "median_tdci": round(float(np.median(tdciv)), 4),
            "std_tdci": round(float(np.std(tdciv, ddof=1)), 4) if len(tdciv) > 1 else 0,
            "min_tdci": round(float(np.min(tdciv)), 4),
            "max_tdci": round(float(np.max(tdciv)), 4),
            "n_sessions": len(sessions),
            "tdci_values": [round(v, 4) for v in tdciv],
            "mean_correctness": round(float(np.mean(corrv)), 4),
            "median_correctness": round(float(np.median(corrv)), 4),
        }

    # Per-perturbation-class aggregation
    by_pclass = defaultdict(list)
    for s in valid_sessions:
        pc = s.get("perturbation_class", "unknown")
        by_pclass[pc].append(s)

    by_pclass_agg = {}
    for pclass, sessions in sorted(by_pclass.items()):
        tdciv = [s["tdci"] for s in sessions]
        by_pclass_agg[pclass] = {
            "mean_tdci": round(float(np.mean(tdciv)), 4),
            "median_tdci": round(float(np.median(tdciv)), 4),
            "n_sessions": len(sessions),
        }

    # Per-model × per-perturbation-class
    by_model_pclass = defaultdict(list)
    for s in valid_sessions:
        key = (s["model"], s.get("perturbation_class", "unknown"))
        by_model_pclass[key].append(s)

    by_model_pclass_agg = {}
    for (model, pclass), sessions in sorted(by_model_pclass.items()):
        tdciv = [s["tdci"] for s in sessions]
        label = MODEL_LABELS.get(model, model)
        k = f"{label}|{pclass}"
        by_model_pclass_agg[k] = {
            "mean_tdci": round(float(np.mean(tdciv)), 4),
            "n_sessions": len(sessions),
        }

    # Correlations (using only valid sessions)
    tdciv_all = [s["tdci"] for s in valid_sessions]
    corrv_all = [s["correctness"] for s in valid_sessions]
    narrv_all = [s["narration_penalty"] for s in valid_sessions]

    def pearson_r(x, y):
        if len(x) < 3:
            return 0.0
        np.mean(x)
        np.mean(y)
        sx = np.std(x, ddof=0)
        sy = np.std(y, ddof=0)
        if sx == 0 or sy == 0:
            return 0.0
        return float(np.corrcoef(x, y)[0][1])

    tdci_vs_correctness = round(pearson_r(tdciv_all, corrv_all), 4)
    tdci_vs_narration_penalty = round(pearson_r(tdciv_all, narrv_all), 4)

    output = {
        "metric": "think_do_coupling_index",
        "description": (
            "Cosine similarity between the model's thinking text (reasoning + narration) "
            "and the subsequent tool call (name + input + output). High coupling means "
            "the model's stated reasoning aligns with its actions. Low coupling means "
            "narration is disconnected from the work being done."
        ),
        "methodology": {
            "text_representation": "TF-IDF with ngram_range=(1,3), max_features=10000, sublinear_tf=True",
            "similarity": "cosine similarity between TF-IDF vectors",
            "pairing": "Each tool call is paired with all reasoning+text entries in the same step",
            "session_tdci": "Mean coupling across all step-pairs in the session",
        },
        "by_model": by_model_agg,
        "by_perturbation_class": by_pclass_agg,
        "by_model_perturbation_class": by_model_pclass_agg,
        "tdci_vs_correctness_correlation": tdci_vs_correctness,
        "tdci_vs_narration_penalty_correlation": tdci_vs_narration_penalty,
        "sessions": valid_sessions,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    return output


def main():
    data = compute()

    print("\n=== LAB BOOK: THINK-DO COUPLING INDEX ===\n")

    print("BY MODEL (mean TDCI):")
    print(f"{'Model':<25} {'Mean':>8} {'Median':>8} {'Std':>8} {'N':>5} {'Correct':>8}")
    print("-" * 70)
    for label, d in sorted(data["by_model"].items(), key=lambda x: -x[1]["mean_tdci"]):
        print(f"{label:<25} {d['mean_tdci']:>8.4f} {d['median_tdci']:>8.4f} "
              f"{d['std_tdci']:>8.4f} {d['n_sessions']:>5} {d['mean_correctness']:>7.0%}")

    print("\nBY PERTURBATION CLASS:")
    for pc, d in sorted(data["by_perturbation_class"].items()):
        print(f"  {pc}: mean_tdci={d['mean_tdci']:.4f}, n={d['n_sessions']}")

    print("\nCORRELATIONS:")
    print(f"  TDCI vs Correctness: {data['tdci_vs_correctness_correlation']:+.4f}")
    print(f"  TDCI vs Narration Penalty: {data['tdci_vs_narration_penalty_correlation']:+.4f}")

    print("\nBottom 5 sessions (lowest coupling):")
    bottom = sorted(data["sessions"], key=lambda s: s["tdci"])[:5]
    for s in bottom:
        print(f"  {s['session']}: tdci={s['tdci']:.4f}, model={MODEL_LABELS.get(s['model'], s['model'])}, "
              f"correctness={s['correctness']:.0%}, penalty={s['narration_penalty']}")

    print("\nTop 5 sessions (highest coupling):")
    top = sorted(data["sessions"], key=lambda s: -s["tdci"])[:5]
    for s in top:
        print(f"  {s['session']}: tdci={s['tdci']:.4f}, model={MODEL_LABELS.get(s['model'], s['model'])}, "
              f"correctness={s['correctness']:.0%}, penalty={s['narration_penalty']}")

    print(f"\nOutput: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
