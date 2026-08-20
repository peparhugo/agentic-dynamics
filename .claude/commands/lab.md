---
description: Run a specific lab book analysis
---

Run a specific lab book analysis. Load the "lab-books" skill for the current list (19 active labs).

First, load the "lab-books" skill. Then:

1. If a lab name is specified ($ARGUMENTS), run it:
   `python scripts/lab_$ARGUMENTS.py`

2. If no lab specified, list available labs and ask which to run.

3. Ensure prerequisites exist: `_results_summary.json`, `inventory.json`.
   If not, suggest running `/analyze` or `/pipeline` first.

Report: lab output path, key findings summary.
