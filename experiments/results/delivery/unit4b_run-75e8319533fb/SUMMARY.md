# Unit 4B — retrieval delivery proof (2026-09-18)

**Acceptance:** approved relevant repository knowledge reaches the exact isolated prepared worker
context (private coordinator records excluded; unavailable and empty distinguished; research
isolation retained).

**Demonstration:** `flash_ladder_kb` run `run-75e8319533fb` through the ordinary fleet path —
request key `aio-explicit:flash_ladder_kb:unit4b-retrieval-demo-3`, base `9da3687ef89c`,
model `deepseek/deepseek-v4-flash`, candidate `136d1c2fcc22`.

**What the parent prepared — and how it reached the worker (qualified):** the exact
prepared-step prompt (`prepared_step_generate.a1.json`; its `prompt_sha256` verifies) carries
the Evidence block with citation
`[K:3c4d382ea67744ba…@121126dfbcd65a…:workload:skill/flash-ladder/taskman#pattern]` — a public
(`acl_scope: public`), repository-scoped (`agentic-dynamics`) DERIVED pattern, revision
`121126dfb…`. The worker's own session (`child_session.jsonl`) contains that citation; the
image-version forensics in `IMAGE_AND_PATH.md` establish that, under the code that actually
ran, that prompt can only have come from the parent's prepared payload. **Caveat (review
2026-09-18):** the cell executed the image's baked `run_workflow.py` (pre-`67cd2e988`) because
the broker set no working directory and the command is relative — so the *current*
prepared-child implementation was not exercised. The rerun (post-merge, with the cell-workdir
and hook fixes active, through `g_test`) is the evidence that closes this.

**Recorded revisions:** the ledger's `augmentation_evidence` names the final emitted set only —
`{id, revision, source_type, locator}` — the by-id mapping over the trimmed selection
(commit `f053f1be2`).

**Unavailable ≠ empty:** `retrieval_leg_errors` names the dense leg
(`No module named 'chromadb'`) and the embedding leg (`No module named 'ollama'`) while
`selected_evidence_ids` is non-empty and `fallback_mode` is `lexical_graph_only` — the lexical
leg delivered; the unavailable legs are named, never silently empty.

**Private coordinator records excluded / research isolation:** the evidence id resolves to
`experiments/results/kb/3c4d382e….json` with `acl_scope: public` and
`repository_id: agentic-dynamics`; the spec requested exactly that scope. Coordinator records
carry `acl_scope: org:agentic-dynamics` and are excluded by the retrieval hard pre-filter.

**Phase outcome (separate rails, both repaired on this branch):** the phase's commit was
refused (`COMMIT_PREFIX`) because the commit-msg hook silently fails to install when a run
clone has no `.git/hooks/` directory (the runner writes the hook without creating the
directory; the P0-4 strict gate default then fails a plain-message commit at the finish line).
And the phase emitted engine-path output because the cell ran the image's baked code rather
than the clone's — the broker set no working directory. Both repairs carry tests; the failed
run is preserved here as historical evidence, and the closeout claim stays qualified until the
rerun passes through `g_test`.

Machine-readable twin: `evidence.json`.
