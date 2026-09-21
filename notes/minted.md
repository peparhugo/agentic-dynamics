# Minted — world_model_loop p2_mint (posterior §UPDATES)

Producer: `python3 scripts/kb_produce_skill.py --skill-json notes/skills/<slug>.json`
(`pattern/v1` fact + projection, scope `agentic-dynamics`). Each line names the posterior
candidate, its status, and the durable record ids. A candidate named in §3 with no line here
would be a silent drop; every named candidate is listed.

- test-seam-guard — minted (posterior A2 + C2 + §3C run-workflow skill; fact `f414a1edc48bc21f33624ee58cf1aa88ed5104bf64b437adab3bcc92b5b0dd5c`, projection `31f62f9a6a4b964639f9a3490fa83de14b79f55d3e8c30ed2f167124dd233d39`)
- lazy-import-emit-patch — minted (posterior U3 + §3C run-workflow skill; fact `4437707b8a7592b48e4d6e49f4fdab7b924635c69da40a9c35bb8020e75d8561`, projection `c418501f29d4b6650c53bfab59c42455787c629c5b1bd2496d0cbcacd966f78c`)
- emit-scope-split — minted (posterior §3C run-workflow skill, scope split; fact `49298bd09fc97ac4323951d392581679da8ff9e0f047b00c514cd8adb5a6e642`, projection `127fdf2ea68ac8b43928073a0b080d018eb22ab4346cbccde142ee02aa5aa371`)
- emit-observability — minted (posterior A3 + C3 + §3C doc item "verify the loop's own artifact"; fact `2fcd50e049b3d434fd0af4a3c818ad40773c24d148ed1cdcf8b7a42a62d0d0ab`, projection `eb3c8134546c1e3e0a1d0978d76236f611f04cc086606661ac710fad0e10e9af`)
- symbol-and-line-citations — minted (posterior C1 + §3C doc item "require symbol+line citations"; fact `d7c87d586d9e0c78b2e8b5838f340e580986b4569adb6a2b8637ef140d0b0041`, projection `89bb98413a794d2f95094bca8c27287e69ca4b2ff8ebfd99dfc03ad1669ac23d`)
- channel-corroboration — minted (posterior C4; fact `7940f73646b7f1a7db46c4a7d94f91ca68b7b98b7e13c3f11955dd59672f200b`, projection `8b1cb3273493be151eda2aaadb31f3d924fa609ef7fc70eaa5735345865da679`)
- kb-read-in-worktrees — minted (posterior U1 + §3C doc item "record that KB read is degraded in run worktrees"; fact `908fa9e1fe15a85c4fc3016a7d40c1c2607c51b2bc2b7ebb1e50deaaba5b0ff4`, projection `bedb796db0755c4173ef7795e57618996b4bb74d461f418581c99ad2d2a0e811`)
- docs/designs/proposed/world_model_loop.md amendment — skipped (source-doc edit: a reviewed commit, not a phase side effect; the underlying patterns are minted above as symbol-and-line-citations, emit-observability, and kb-read-in-worktrees)
- run-workflow skill file amendment — skipped (generated agent surface (§GENERATED SURFACES); landing is a reviewed commit, not a phase side effect; the underlying pattern candidates are minted above as test-seam-guard, lazy-import-emit-patch, and emit-scope-split)
- A1 live-KB-leak verification outcome [M] — skipped (one-off measured result of this run, not a transferable procedure; it belongs to the finding producer path — `kb_produce.py`/`kb_backfill_findings.py` — not the skill/pattern producer, which mints procedural patterns)
- §3D next-prior changes 1-4 — skipped (phase process guidance for the next loop turn, not a reusable KB pattern; carried by the posterior itself and by emit-observability / symbol-and-line-citations / kb-read-in-worktrees)

## Policy notes (why support and uncertainty read the way they do)

- `support` counts the real independently observed instances in the cited evidence, never an
  aspiration: 2 for the recurrence classes (emit-observability, symbol-and-line-citations,
  each observed across two consecutive loop runs), 1 for each single-instance pattern.
- `uncertainty` is `null` on every record because every slice is below the `pattern/v1` reducer's
  `MIN_SUPPORT_FOR_UNCERTAINTY = 3`; the coverage invariant forbids fabricating an interval, and
  a null means "not estimable", not zero.
- Artifacts landed in `experiments/results/kb/` (the worktree-resolved `KB_ARTIFACT_DIR`; the
  producer's `_bootstrap` puts `/repo/src` first on `sys.path`), and both pointer events were
  published to `kb:v1:changes` (Redis `finops-queue:6379` db 2, per the container's
  `FINFOPS_REDIS_HOST`/`FINFOPS_KB_DB`). No generated surface was hand-edited.
