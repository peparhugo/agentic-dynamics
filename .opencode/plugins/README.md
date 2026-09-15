# `.opencode/plugins/` — hand-authored, outside the generator

This directory holds OpenCode project plugins. Like `.opencode/tools/`, it is **hand-authored
and deliberately outside the generated-surface set**: the generator
(`scripts/_gen_instructions.py`, `agent_config/` → `.opencode/` + `.claude/` + the root files)
does not own it, and its freshness check does not cover it. Edit plugin files directly; keep
their tests outside auto-loaded directories (e.g. `tests/opencode/`).

The approved AIO capsule plugin (`aio-context.ts` — automatic identity binding + capsule
injection) lands here; the controller approved its scope on 2026-09-14. The plugin is
convenience + early refusal, **never authority**: the backend (submit contract, admission,
promote gate) refuses independently, and an absent plugin degrades to thinner context +
backend refusals — never to unbound operations proceeding.
