#!/usr/bin/env python3
"""
Compute baseline-vs-perturbed sonar deltas for all entries in _results_summary.json.
Populates: sonar_bugs_delta, sonar_code_smells_delta, sonar_cognitive_complexity_delta,
           sonar_duplication_delta, sonar_maintainability_delta, sonar_security_delta,
           sonar_baseline_bugs, sonar_perturbed_bugs.
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"
SUMMARY_PATH = RESULTS_DIR / "_results_summary.json"

def main():
    with open(SUMMARY_PATH) as f:
        data = json.load(f)

    entries = data["entries"]

    # Index baselines by model (experiment names diverge between baseline/perturbed runs)
    baselines = {}
    for e in entries:
        if e.get("operator") == "baseline":
            key = e.get("model", "")
            baselines[key] = e

    # Compute deltas for perturbed entries with sonar data
    computed = 0
    skipped = 0
    for e in entries:
        if e.get("operator") == "baseline":
            continue
        if not e.get("sonar_analyzed"):
            skipped += 1
            continue

        key = e.get("model", "")
        bl = baselines.get(key)
        if not bl or not bl.get("sonar_analyzed"):
            skipped += 1
            continue

        # Compute deltas directly from flat fields
        e["sonar_baseline_bugs"] = bl.get("sonar_bugs", 0)
        e["sonar_perturbed_bugs"] = e.get("sonar_bugs", 0)
        e["sonar_bugs_delta"] = e["sonar_perturbed_bugs"] - e["sonar_baseline_bugs"]
        e["sonar_vulnerabilities_delta"] = (e.get("sonar_vulnerabilities", 0) or 0) - (bl.get("sonar_vulnerabilities", 0) or 0)
        e["sonar_code_smells_delta"] = (e.get("sonar_code_smells", 0) or 0) - (bl.get("sonar_code_smells", 0) or 0)
        e["sonar_cognitive_complexity_delta"] = (e.get("sonar_cognitive_complexity", 0) or 0) - (bl.get("sonar_cognitive_complexity", 0) or 0)
        e["sonar_duplication_delta"] = round((e.get("sonar_duplicated_lines_density", 0) or 0) - (bl.get("sonar_duplicated_lines_density", 0) or 0), 2)
        e["sonar_complexity_delta"] = e["sonar_cognitive_complexity_delta"]

        # Maintainability rating delta (A=1, B=2, C=3, D=4, E=5, higher = worse)
        rating_map = {"A":1,"B":2,"C":3,"D":4,"E":5}
        bl_rating = rating_map.get(str(bl.get("sonar_maintainability_rating","")).upper(), 0)
        e_rating = rating_map.get(str(e.get("sonar_maintainability_rating","")).upper(), 0)
        e["sonar_maintainability_delta"] = e_rating - bl_rating if bl_rating and e_rating else None

        bl_sec = rating_map.get(str(bl.get("sonar_security_rating","")).upper(), 0)
        e_sec = rating_map.get(str(e.get("sonar_security_rating","")).upper(), 0)
        e["sonar_security_delta"] = e_sec - bl_sec if bl_sec and e_sec else None

        computed += 1

    # Write back
    data["_meta"]["sonar_deltas_computed"] = True
    data["_meta"]["sonar_deltas_computed_at"] = __import__('datetime').datetime.now().isoformat()
    data["_meta"]["sonar_deltas_pairs"] = computed
    data["_meta"]["sonar_deltas_skipped"] = skipped

    with open(SUMMARY_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Sonar deltas computed: {computed} pairs, {skipped} skipped")

    # Report by perturbation class
    from collections import defaultdict
    by_class = defaultdict(lambda: {"bugs":[], "smells":[], "quality_score":[]})
    for e in entries:
        pc = e.get("perturbation_class", "unknown")
        if e.get("sonar_bugs_delta") is not None:
            by_class[pc]["bugs"].append(e["sonar_bugs_delta"])
        if e.get("sonar_code_smells_delta") is not None:
            by_class[pc]["smells"].append(e["sonar_code_smells_delta"])
        if e.get("sonar_quality_score") is not None:
            by_class[pc]["quality_score"].append(e["sonar_quality_score"])

    print("\nAverage sonar impact by perturbation class:")
    for pc in sorted(by_class):
        d = by_class[pc]
        bugs_avg = sum(d["bugs"])/max(len(d["bugs"]),1)
        smells_avg = sum(d["smells"])/max(len(d["smells"]),1)
        qs_avg = sum(d["quality_score"])/max(len(d["quality_score"]),1)
        print(f"  {pc:12s}: bugs_delta={bugs_avg:+.1f}, smells_delta={smells_avg:+.1f}, quality={qs_avg:.3f} (n={len(d['bugs'])})")

if __name__ == "__main__":
    main()
