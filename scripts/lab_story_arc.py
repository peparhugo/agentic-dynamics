"""
Lab Book: Story Arc — does cost compound across the 5-session story?

Aggregates per-session cost, tokens, and tests across all stories, broken down
by session number (the greenfield -> cross-cutting arc) and by perturbation
condition. This is the Snowball Rule measured directly.

Usage:
    python scripts/lab_story_arc.py

Output:
    experiments/results/lab_story_arc.json
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path("experiments/results/stories")

SESSION_LABELS = {1: "greenfield", 2: "feature", 3: "integration",
                  4: "refactor", 5: "cross_cutting"}


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def _avg(lst):
    return round(sum(lst) / len(lst), 4) if lst else 0.0


def main():
    by_session = defaultdict(lambda: {"cost": [], "tokens": [], "tests": [], "n": 0})
    by_cond_session = defaultdict(lambda: {"cost": [], "n": 0})
    by_model_session = defaultdict(lambda: defaultdict(lambda: {"cost": [], "n": 0}))

    for f in sorted(RESULTS_DIR.glob("*.json")):
        if "log" in f.name or "dvs" in f.name:
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "model" not in d:
            continue
        model = _short_model(d["model"])
        cond = d.get("perturbation_condition", "") or "clean"
        for s in d.get("sessions", []):
            sn = s.get("session_number", 0)
            if not sn:
                continue
            cost = s.get("cost_usd", 0) or 0
            a = s.get("agentic", {}) or {}
            tokens = a.get("total_tokens", 0) or s.get("total_tokens", 0) or 0
            tests = a.get("tests_total", 0) or 0
            by_session[sn]["cost"].append(cost)
            by_session[sn]["tokens"].append(tokens)
            by_session[sn]["tests"].append(tests)
            by_session[sn]["n"] += 1
            by_cond_session[(cond, sn)]["cost"].append(cost)
            by_cond_session[(cond, sn)]["n"] += 1
            by_model_session[model][sn]["cost"].append(cost)
            by_model_session[model][sn]["n"] += 1

    sessions = []
    for sn in sorted(by_session):
        v = by_session[sn]
        sessions.append({
            "session_number": sn,
            "task_type": SESSION_LABELS.get(sn, "?"),
            "n": v["n"],
            "avg_cost": _avg(v["cost"]),
            "avg_tokens": round(_avg(v["tokens"]), 0),
            "avg_tests": round(_avg(v["tests"]), 1),
        })

    # Snowball factor: session 5 cost / session 1 cost.
    s1 = sessions[0]["avg_cost"] if sessions else 0
    s5 = sessions[-1]["avg_cost"] if sessions else 0
    snowball = round(s5 / s1, 2) if s1 else 0.0

    output = {
        "experiment_id": "lab_story_arc",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "snowball_factor": snowball,
            "session1_cost": s1,
            "session5_cost": s5,
        },
        "sessions": sessions,
        "by_condition": {
            f"{cond}_s{sn}": _avg(v["cost"])
            for (cond, sn), v in sorted(by_cond_session.items())
        },
        "by_model": {
            m: {
                str(sn): _avg(v["cost"])
                for sn, v in sorted(sessions_map.items())
            }
            for m, sessions_map in sorted(by_model_session.items())
        },
    }

    out = Path("experiments/results/lab_story_arc.json")
    out.write_text(json.dumps(output, indent=2))
    print(f"Saved: {out}")
    for s in sessions:
        print(f"  session {s['session_number']} ({s['task_type']:14s}) n={s['n']:4d} "
              f"cost=${s['avg_cost']:>7.4f} tokens={s['avg_tokens']:>7.0f} tests={s['avg_tests']}")
    print(f"Snowball factor (S5/S1): {snowball}x")


if __name__ == "__main__":
    main()
