# Unit 4B — retrieval delivery proof (2026-09-18)

**Acceptance:** approved relevant repository knowledge reaches the exact isolated prepared worker
context (private coordinator records excluded; unavailable and empty distinguished; research
isolation retained).

**Demonstration:** `flash_ladder_kb` run `run-75e8319533fb` through the ordinary fleet path —
request key `aio-explicit:flash_ladder_kb:unit4b-retrieval-demo-3`, base `9da3687ef89c`,
model `deepseek/deepseek-v4-flash`, candidate `136d1c2fcc22`.

**What the worker received:** the exact prepared-step prompt
(`prepared_step_generate.a1.json`; its `prompt_sha256` verifies) carries the Evidence block with
citation `[K:3c4d382ea67744ba…@121126dfbcd65a…:workload:skill/flash-ladder/taskman#pattern]` — a
public (`acl_scope: public`), repository-scoped (`agentic-dynamics`) DERIVED pattern, revision
`121126dfb…`.

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

**Phase outcome (separate rail):** the phase's commit was refused (`COMMIT_PREFIX`) because the
commit-msg hook silently fails to install when a run clone has no `.git/hooks/` directory (the
runner writes the hook without creating the directory; the P0-4 strict gate default then fails a
plain-message commit at the finish line). The delivery evidence above is from the same phase and
is unaffected; the rail is repaired on this branch.

Machine-readable twin: `evidence.json`.
