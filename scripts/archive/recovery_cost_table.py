"""Recovery cost by perturbation type — processes existing DB data.

Extracts baseline cost, perturbed cost, and recovery cost for each
operator×strength combination from the opencode session database.
"""

import sqlite3
from collections import defaultdict
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.measurement.perturb import perturbation_class_for

DB = Path.home() / ".local/share/opencode/opencode.db"


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''
        SELECT json_extract(s.model, '$.providerID') as prov,
               s.cost, s.tokens_input, s.tokens_output, s.tokens_reasoning,
               s.tokens_cache_write, s.title
        FROM session s WHERE s.cost > 0
        AND s.title LIKE '%REST API%' OR s.title LIKE '%task manager%'
        OR s.title LIKE '%URL shortener%' OR s.title LIKE '%collaboration%'
        ORDER BY prov, s.time_created
    ''')
    rows = c.fetchall()

    # Classify each session
    baselines = {"deepseek": [], "anthropic": []}
    perturbed = defaultdict(lambda: {"deepseek": [], "anthropic": []})

    for prov, cost, ti, to, tr, cw, title in rows:
        cost, ti, to, tr, cw = (cost or 0), (ti or 0), (to or 0), (tr or 0), (cw or 0)
        title_lower = (title or "").lower()

        # Detect perturbation
        op = None
        for candidate in ["remove_critical_constraint", "inject_alien_vocab",
                          "inject_phantom_success", "invert_constraint", "shift_framing",
                          "inject_false_premise", "inject_competing_goal"]:
            if candidate.replace("_", " ") in title_lower:
                op = candidate
                break

        if op is None:
            # Baseline (no perturbation keyword in title)
            baselines[prov].append(cost)
        else:
            perturbed[op][prov].append(cost)

    # Compute recovery costs
    print("| Perturbation | Class | DeepSeek Baseline | DeepSeek Perturbed | Recovery $ | Claude Baseline | Claude Perturbed | Recovery $ | Factor |")
    print("|-------------|-------|-----------------|-------------------|------------|----------------|------------------|------------|--------|")

    for op_name in sorted(perturbed.keys()):
        cls = perturbation_class_for(op_name)
        ds_base = sum(baselines["deepseek"]) / max(len(baselines["deepseek"]), 1)
        cl_base = sum(baselines["anthropic"]) / max(len(baselines["anthropic"]), 1)

        ds_costs = perturbed[op_name]["deepseek"]
        cl_costs = perturbed[op_name]["anthropic"]

        if ds_costs:
            ds_pert = sum(ds_costs) / len(ds_costs)
            ds_rec = max(0, ds_pert - ds_base)
        else:
            ds_pert, ds_rec = 0, 0

        if cl_costs:
            cl_pert = sum(cl_costs) / len(cl_costs)
            cl_rec = max(0, cl_pert - cl_base)
        else:
            cl_pert, cl_rec = 0, 0

        factor = cl_rec / max(ds_rec, 0.000001) if ds_rec > 0 else float('inf')

        print(f"| {op_name} | {cls} | ${ds_base:.4f} | ${ds_pert:.4f} | ${ds_rec:.4f} | ${cl_base:.4f} | ${cl_pert:.4f} | ${cl_rec:.4f} | {factor:.0f}× |")

    conn.close()


if __name__ == "__main__":
    main()
