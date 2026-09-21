I have read all 24 delivery files (wave1 c01–c16, wave2 c01–c08). Below is the single reconciled report. It is analysis only; no code or state was fetched or changed.

---

# Reconciliation report — the capacity-budget contemplation corpus (24 outputs)

## 0. Method, manifest, and a completeness caveat that matters

**What was read.** All 24 files under `/tmp/cont_run/.instrument/delivery-answers/`: wave1 c01–c16 (16) and wave2 c01–c08 (8). I treat each as complete text per the delivery marker.

**A caveat that changes how wave-2 must be read.** Every wave-2 answer positions itself against a **wave-1 `c17`** and a **"synthesis"** (with proposals `Q-A` / `Q-B`) — e.g. *"What I add beyond wave-1 c17 (Q-B)"* (wave2/c01), *"beyond a named sibling… c04"* (wave2/c02), *"beyond wave-1 c17 (Q-A)"* (wave2/c03), *"the synthesis's law"* (wave2/c08). **`c17` and that synthesis are not among the 24 delivered files.** Therefore: wave-2's account of `c17`/the synthesis is second-hand; I do not attribute content to them beyond what wave-2 states. This delivery is the 24 raw answers, not the prior synthesis passes it replaces.

**Provenance gap.** The manifest supplies lengths and hashes but **no model/lineage labels** for the 24 answers. That is not a formatting nit — item 1 below turns on it: the corpus's agreement cannot be partitioned into independent lineages, so much of its unanimity is *correlated by construction* (same evidence history, same quoted reviewer sentence, and in wave 1 a shared "seven lenses" scaffold that appears in nearly every answer).

**What the corpus is about.** One concrete arc: an AIO session replaces a fixed 200K-token / 80-turn session budget (`DEFAULT_CTX_BUDGET`/`DEFAULT_TURN_BUDGET`) with the *active model's resolved capacity* (~968,000 usable for `deepseek/deepseek-v4-flash`), makes the 80% warning advisory, handles the native-compaction boundary, lands PR #77 after a five-finding review, activates it (broker/consumer reload), and submits the continuation run (`job 1fddc5861ac6` → `run-0da5271bc0cb`) through the native `run_workflow` tool.

---

## 1. What the corpus collectively establishes

### 1.1 The generator: authority divergence (near-unanimous, and independently grounded)

The corpus's central claim, quoted from the controller's review in almost every file: *"sharing one Python helper does not establish one authority if that helper disagrees with OpenCode."* Concretely, the first implementation **re-derived** runtime semantics instead of consuming them:

| Axis | The re-derivation | The runtime's authority |
|---|---|---|
| Limits / config | local `load_runtime_config` + `_config_candidates` + JSONC stripper | `opencode models <provider> --verbose` |
| Token measure | `input+output+reasoning+cache.read+cache.write` | `tokens.total \|\| input+output+cache.read+cache.write` (**no reasoning**) |
| Transient state | "last completed sample = context" | run loop skips `he.summary !== true` |

This is the strongest claim in the corpus, and it is the **least** dependent on prose agreement: it is backed by the controller's five reproduced findings and by commits (`9ae173419`, `d2aef3be3`, `4c3c6cdf0`).

### 1.2 The measured incident chain

- **False trip, measured:** the predecessor continuation was refused at **172,491 tokens / 35 turns**, which is **86% of the old 200K policy but well inside the active model's 968,000 usable** — and the repo default (`deepseek-v4-pro`) is *not* the session model (`deepseek-v4-flash`). Cited in essentially every file.
- **The five review findings** (all reproduced by the controller): (P1) a completed compaction summary's generation usage read as the new context → 975K/`COMPACT` after a successful compaction; (P2) config precedence/partial-merge/JSONC; (P2) `reasoning` in the sum (955K native vs 975K local); (P2) `FINOPS_SESSION_CTX_LIMIT` emitting `COMPACT` at a policy cap; (P2) corrupt-DB CLI crash vs backend `UNJUDGED`.
- **Control-plane gap, measured:** the first `fleet_manager.py restart --service workflow-runner` was claimed, `fleet:commands` and the processing lane drained, **no compose call, no board record, PID 733477 unchanged**; re-issuing through the documented broker seam produced `Restarting infrastructure_workflow-runner_1 … done` and PID 883849. Present in every wave-1 file.
- **Activation and submit:** broker PID 883363 @01:59:12, consumer 883849 @02:02:51; native-tool receipt `1fddc5861ac6`; control-db row `run-0da5271bc0cb` `running`; `p1b_gate_first_viewport` executing under lease `bud_afacee0f57e647b5`; the tool's own maxim *"a queued submit is NOT a running run."*
- **Honesty invariants that held:** `UNJUDGED` never permission; pending-zero samples never overwrite a reading (the Astra finding); the exit-3 control envelope had to stop rendering "no database" as an observed empty packet.

### 1.3 The KB anchors the corpus leans on
`7948b8ace287e881` (no instruction arm improved accepted outcomes; baseline cost-minimal; cache 95.5–97.9%), `6ef9bf9b6ef3b53a` (goals ride argv, newlines refused; untracked specs never reach run clones), `c50f37cfff42523b` (frozen row-level snapshots refused to fork / lost auxiliary rows; native `opencode export/import` preserved sessions; fork ≈ $0.004735, cache 47%→90%).

**What it does *not* establish (stated by the corpus itself):** that the new policy is *behaviorally* safe (capacity vs. compliance), that the 80% ratio is calibrated, or that contemplation/fan-out carries independent signal. Those are exactly the conflicts below.

---

## 2. Conflicts kept visible (named pairs; not averaged)

**C1 — How much of the five is mechanically recoverable? `wave1/c01`+`wave2/c02` vs `wave2/c05`(+`c07`).**
- `wave2/c01`: "exactly three of the five are recoverable differentially" (F1 only model-vs-model via a transcribed guard), and "F4, F5 — no… no authority output exists to diff."
- `wave2/c02`: predicts **P1 is not recoverable** — "the completed-summary overflow skip exists only in the runtime's run loop, invisible to any configuration or metadata diff."
- `wave2/c05`: ≥4/6 mechanizable at ≤$0.05/finding, with D1 mechanism = "drive a forked session through compaction."
- `wave1/c07` (RADAR): would have caught **all five** pre-merge.
The disagreement is real and load-bearing: if F1 needs an *induced live compaction* (and `wave1/c13`/`c09` report `time_compacting IS NOT NULL` returning empty on this host), then `c05`'s cost/specificity claim is unmeasured and `c07`'s "all five" is aspirational.

**C2 — Is the 80% advisory safe? `wave2/c03` vs `wave1/c13`+`wave1/c02`.**
`c03`'s entry claim is "f does not predict acceptance below the native boundary → advisory safe," but its own Lens A says the existing data are structurally unusable (work-progress endogeneity / conditioning on a collider; disjoint exposure/outcome stores; join gap) and its decision rule **defaults to KEEP as a policy choice, not a measurement**. `c13` (B6): ratio is **ASSUMED**, "only its referent changed (200K → 968K)." `c02`: "no dose–response calibration, only a hunch." Conflict kept: the corpus establishes the advisory is *policy*, not that it is *safe*.

**C3 — Is the apparatus insurance or overbuilt? `wave1/c11` vs `wave2/c07`+`wave1/c12`.**
`c11`'s leading claim: the system is "misclassified and misallocated" — a safety-and-audit system billing itself as measurement-driven control; the overbuilt layer is telemetry→**normative stopping rules** (which produced `f987cde9`, the 172,491 refusal, and four of five findings); the underbuilt piece is "a single authoritative runtime oracle plus a cheap override." `wave2/c07` wants **more** structure (required artifacts, maxima, brakes). `wave1/c12` wants a **host-effect interlock** (more guard). `wave1/c08` says route attention through *existing* surfaces, do not add prose. Unresolved by argument; `c11` states the counter-position (insurance) itself.

**C4 — Does the wave carry independent signal at all? `wave2/c06`+`wave2/c07`+`wave2/c08` vs the wave-1 corpus's self-justifying synthesis.**
`c06`: cross-lineage agreement counts only if it exceeds the **within-lineage floor** (`ICS > 0`); "more arms … only raise the floor." `c07`: a wave with no independently checkable artifact is "net cost at any positive spend." `c08` applies its own lint to the wave and to itself: the wave's value metric ("17/17 phases, cache tokens, answers retained") is a substitution — proxy = artifact volume, criterion = decisions changed — and the law's evidence base is the same corpus being linted (circular). Meanwhile many wave-1 answers treat the synthesis as durable value. This is the corpus **partly undermining its own epistemic product** — which is itself the most honest thing in it.

**C5 — Code identity / reload: verified or unguarded? `wave1/c08` vs `wave1/c12`.**
`c08`: the live submit *is* the behavioral version probe (pre-merge it refused; post-reload it was accepted). `c12`: the activation boundary is the largest residual hole — remote branch protection has **no required review** (`reviewDecision: ""`), services read the **local `main` checkout**, and `git merge --ff-only` + `systemctl --user restart` succeeded with no interactive human. Compatible facts, opposed risk postures.

**C6 — The explicit fork named by `wave1/c06`.** Recurrence vs attribution: either the attempt chain (`f344c4b99162 → f52d829af58e → 1c341d58af27 → b787b0d16d6c → dfa259243059 → 0da5271bc0cb`) is a loop that an **Attempt-Recurrence Interlock** should have flagged, or those are genuinely distinct experiments and the missing instrument is an **attributed outcome-quality ledger**. `c06` provides the discriminating replay; it is not run here.

**C7 — Was the capacity policy causal? `wave1/c04` vs `wave1/c13`/`c11`/`c16`.**
`c04`'s honest correction: the accepted policy "didn't create the outcome; it changed *who* could initiate it" — the predecessor close record (`control-room-instrument-cont-submit`) already planned a **fresh-session** submit. The others read the policy change as converting a refusal into a receipt. Both true at different levels; keep visible.

**C8 — Historical record inconsistency (minor, but unexplained).** `wave1/c03`/`c15`: the capsule observed `WARN (turns 37, context 185657)` while a fresh read said `OK (turns 5, 30,518)` — a capsule-TTL/turn-count discrepancy with no reconciliation in the corpus.

**C9 — A branch correcting its own supplied premise.** `wave2/c04`'s entry claim that "submits are the only act with a record" is falsified **by its own analysis**: cancel/promote/publish already leave durable records; the true gap is the four compose acts, and only restart/scale/drain have *none*.

---

## 3. Claims separated by class and support

### 3.A Measured observations (artifact/reproduction exists)
| # | Claim | Support class |
|---|---|---|
| M1 | Five review defects reproduced by the controller; fixes landed (`9ae173419`,`d2aef3be3`,`4c3c6cdf0`) | single independent review pass, n=1 |
| M2 | 172,491 was refused under the old 200K policy; 968,000 is the resolved usable limit; session model ≠ repo default | host DB + CLI + journal (`limits_source: opencode-cli`) |
| M3 | `ruff check .` caught F401 in `core/__init__.py` after per-file lint passed (`bc87e60af`) | CI artifact |
| M4 | The swallowed restart (queue drained, no compose/board record, PID unchanged); seam re-issue worked | direct inspection (PID/journal/compose log) |
| M5 | Submit accepted (`1fddc5861ac6`), run row `run-0da5271bc0cb` `running`, `p1b` cell leased | control DB + process |
| M6 | The compaction summary is created zero-valued, then filled by the generation call; run loop guards `he.summary !== true`; overflow sum excludes `reasoning` | extracted from installed binary **1.18.15** (pinned, not live-observed) |
| M7 | No native compaction observed on this host (`time_compacting` null for every session) | null result |
| M8 | Full suite 4,521 passed / 12 failures attributed (8 on `main`, 3 pristine worktree, 1 live-Neo4j) | differential execution |
| M9 | KB findings `7948b8a`, `6ef9bf9b`, `c50f37cf` as cited | prior KB artifacts, not re-verified here |

### 3.B Hypotheses (plausible, untested)
- **H1** Capacity-derived policy + native compaction improves continuation outcomes at equal cost (`wave1/c10`). *Not tested.*
- **H2** Below native capacity, context fraction does not predict phase acceptance (`wave2/c03`). *Structurally untestable on existing data per c03's own Lens A.*
- **H3** The 80% advisory is safe (`c03`) / merely assumed (`c13`). *Unfalsified, inherited ratio.*
- **H4** Instruction/prompt changes are near-inert; mechanism dominates (from `7948b8a`). *One small pilot; `c13` argues cache dilution confounds it.*
- **H5** A differential rail recovers the defect class before merge (`c07`,`c05`) vs. only 2–3/5 (`c01`,`c02`). *Directly contested (C1).*
- **H6** Authority consumption is the dominant remedy (`c01`,`c05`,`c08`,`c16`). *Induction over one arc; `c08` self-flags this.*
- **H7** Recurrence (not attribution) is the missing instrument (`wave1/c06`). *Its own falsifier is unrun (C6).*

### 3.C Proposals (specified, not built) — see ranking in §5
Authority differential/conformance suite; control-act terminal receipts; exact-CI pre-push parity + pre-existing-failure baseline; typed `handoff` binding object; Attempt-Recurrence Interlock (ARI); reviewer-calibration benchmark; content-addressed input manifest; host-effect interlock; CAP-BOUNDARY-1 dose–response; contemplation artifact policy; substitution lint.

### 3.D Open questions
- Does the runtime actually compact here, and does the ported guard match it? (No live compaction.)
- What is `run-0da5271bc0cb`'s eventual outcome; does `p1c_contract_gate` stop for approval as predicted?
- Does a same-session resume complete better than a fresh one? (Three prior attempts failed; clean-resume is ASSUMED.)
- Does the cache survive a compaction prefix rewrite (cost forecasts)?
- Can the compaction finding be recovered without *inducing* a real compaction?
- What are the reviewer's POD/specificity (no calibration record anywhere)?
- Is local-`main` activation a real hole in practice?

---

## 4. Historical vs current (mark, do not fetch)

**Historical (as-of the arc):** the five defects and their fixes; `DEFAULT_CTX_BUDGET=200_000`/`DEFAULT_TURN_BUDGET=80`; the pre-clamp `FINOPS_SESSION_CTX_LIMIT`; broker/consumer PIDs 883363/883849; `run-0da5271bc0cb` in `p1b`; the `time_compacting` null result; 4,521/12 suite result; PR #77 merged as `c8acc4d8c`.

**Needs a current-code/state check before being relied on (marked, not fetched):**
- `M-CODE` — does the current tree still (a) consume the runtime CLI first, (b) exclude `reasoning`, (c) skip `summary === true`, (d) clamp the policy cap and return policy `CLOSE`, (e) keep the corrupt-DB boundary? Post-merge this is expected but not verified here.
- `M-CODE` — is the control-action receipt gap still present (`_dispatch_command` ignoring `outcome["ok"]` for non-submits)?
- `M-STATE` — current status of `run-0da5271bc0cb` / `p1c` / `p6g`; current service PIDs/loaded code; whether the six `control_room_*.yaml` remain untracked.
- `M-TEST` — whether the 12 suite failures are unchanged on current `main`/CI.
- `M-KB` — whether the cited KB findings have since been superseded.
- Proposals in §5 are **unbuilt as of the arc** (`M-CODE` if credited later).

---

## 5. Ranked surviving proposals, and the one next artifact

Ranking is by **(checkability, cost, expected value)**; support class is the evidence the proposal rests on, not its elegance.

| Rank | Proposal (source) | Checkability | Cost | Expected value | Support |
|---|---|---|---|---|---|
| 1 | **Differential conformance suite** (w1 c01/c05/c09/c16; w2 c01/c02 R1/c05/c07) | High (pytest, mutation-kill) | Low–Med | **High** | measured findings + authority thesis |
| 2 | **Control-act terminal receipts** (w1 c05#4/c07 L4; w2 c04) | High | Low | High | measured swallowed restart |
| 3 | **Exact-CI pre-push parity + known-failure baseline** (w1 c01#6/c02/c05#3/c09/c13) | High | Low | Med–High | measured F401 miss + repeated re-proof tax |
| 4 | **Typed `handoff` on the binding** (w1 c15; w2 c02 R4) | Med (additive schema) | Low–Med | Med | stale-intent evidence (predecessor's retired 160k quote) |
| 5 | **Attempt-Recurrence Interlock** (w1 c06) | High (pure consumer over `runs`/`step_attempts`) | Low–Med | Med | unused `family_id`/`attempt_no`; chain visible |
| 6 | **Reviewer-calibration benchmark** (w2 c05 §3.2) | Med | Med | Med | no POD/specificity exists (C1) |
| 7 | **Content-addressed input manifest** (w1 c05#2/c06) | Med | Med | Med | `6ef9bf9b` (untracked specs) |
| 8 | **Host-effect interlock** (w1 c12) | Med | Med–High | Med–High | risk map; local-main/activation hole |
| 9 | **CAP-BOUNDARY-1 dose–response** (w1 c10; w2 c03) | High (pre-registered) | Med (~$50) | Med | untested H2/H3 |
| 10 | Contemplation artifact policy (w2 c07) | High mechanically | Low | Low–Med (validity contested, C4) | supplied thesis |
| 11 | Substitution lint (w2 c08) | High mechanically | Low | Low–Med (circular) | self-flagged |

**The single next executable artifact: a differential + transcription conformance suite for the capacity surface, wired so it cannot skip-green.**

*Composition (four oracle classes, mirroring `wave2/c01`'s O1–O4 and `wave2/c05`'s D1–D5):*
1. **Direct authority diff** — `resolve_capacity()` vs a pinned capture of `opencode models <provider> --verbose` over a generated config matrix (global → `OPENCODE_CONFIG` → project; a partial `output`-only override; a trailing-comma JSONC file).
2. **Pinned transcription** — the overflow expression *without* `reasoning` and the run-loop guard `last_assistant.summary !== true`, quoted from the binary with its SHA in the fixture.
3. **Contract invariants** (no runtime output exists) — `policy_limit ≤ native_effective_limit`; `COMPACT` only when `context ≥ native_effective_limit`; corrupt DB → structured `UNJUDGED` in both CLI and gate.
4. **Canaries / negative controls** — the pre-fix revision and an injected mutant must go red; a clean corpus must be green; the **host profile fails** (never skips) when the runtime binary is unavailable, and the CI capture fails loudly on a version mismatch.

*Acceptance test (pre-registered, `c07`-style decision rule):* on the **pre-fix revision** the suite is **RED** and kills mutants for each of the five historical defects (F2/F3 by the authority diff; F1 by the transcription guard; F4/F5 by the invariants/robustness tests); on the **fixed revision** it is **GREEN**; **false positives = 0** on a clean config corpus; and a run with the oracle unavailable is **not green**. Any other outcome (both red, both green, or skip-green) falsifies calibration, not merely sensitivity. Runner-up if only one file may be built: the control-act receipt (rank 2), which closes a *measured* live failure for the least code.

**What stays human, explicitly:** the two findings with no authority output — a policy cap must not speak in the native actuator's voice (F4), and corrupt state must degrade rather than crash (F5) — are **contracts**. A differential suite can hold the line once a human states the property; it cannot discover that the property should exist (`wave2/c01`, `c02`). The residual is ≈1 named contract per review, not 5.

---

## FINDING

Most defensible: (1) the gate's dominant defect class was re-deriving the runtime's authority — config order/merge, the reasoning-inclusive token sum, and reading a compaction summary's generation usage as live context; all five reviewer findings reproduced, and the 172,491 refusal against 968,000 usable was a real false trip. (2) Control-plane restart/scale/drain leave no durable terminal record (the swallowed restart is measured). (3) The next artifact is a differential conformance suite — limits diffed against the runtime CLI plus a pinned transcription of the overflow sum and the `summary !== true` guard, mutation-killed, never skip-green. Falsifier: one session where the shipped gate disagrees with the runtime's overflow/compaction decision, or the suite fails to kill the known post-compaction defect pre-fix.