---
description: Run a specific lab book analysis
agent: build
subtask: true
---

Run a specific lab book analysis. Load the "lab-books" skill for the current list.

First, load the "lab-books" skill. Then:

1. If a lab name is specified ($ARGUMENTS), run it:
   `python scripts/lab_$ARGUMENTS.py`

2. If no lab specified, list available labs and ask which to run.

3. Ensure prerequisites exist: a refreshed inventory and the canonical registry corpus.
   If not, suggest running `/analyze` or `/pipeline` first.

Report: lab output path, key findings summary.
