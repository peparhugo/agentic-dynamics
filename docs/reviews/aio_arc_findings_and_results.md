---
status: accepted
---

# AIO arc — findings, knowledge, and results (self-contained)

One document for review: everything this arc measured, learned, and decided, with the raw
artifact locations. Contemplation insights are **advisory [H]**; run metrics and KB findings
marked [M] are **measured**.

**Correction (2026-09-20, after the controller's review).** The wave syntheses are corrected
downward: the wave-1 synthesis received the sibling answers only as 4,000-char excerpts; the
wave-2 synthesis received no sibling outputs at all (its prompt never inserted
`{prior_answers}`). Claims that depended on cross-sibling comparison — including "contemplation
should retire itself" — are unsupported and rejected; observed results, hypotheses, proposals
and disagreements are separated in §4.4. Raw answers are unchanged; delivery evidence is in
`docs/reviews/contemplation_waves_1_2_review.md` (top) and §7.

## 1. What ran (all of it)

| run family | run id | state | cost | phases ok/total |
|---|---|---|---|---|
| prompt_branch_pilot | `run-af9ec083ab11` | failed | $0.00000 | 0/1 |
| prompt_branch_pilot | `run-4540498619b6` | failed | $0.00000 | 0/1 |
| prompt_branch_pilot | `run-df7acda12571` | failed | $0.00000 | 0/1 |
| prompt_branch_pilot | `run-bf902e6a32d6` | succeeded | $0.00681 | 2/2 |
| prompt_branch_pilot | `run-e9db01a61378` | succeeded | $0.00822 | 2/2 |
| prompt_branch_pilot | `run-e04164023bcc` | succeeded | $0.01917 | 2/2 |
| prompt_branch_pilot | `run-f8df6608dc37` | succeeded | $0.00886 | 2/2 |
| prompt_branch_pilot | `run-3ba9d83b24c8` | succeeded | $0.00861 | 2/2 |
| prompt_branch_pilot | `run-64698cb7c320` | succeeded | $0.01297 | 2/2 |
| prompt_branch_pilot | `run-e32b49f67c4f` | succeeded | $0.00895 | 2/2 |
| prompt_branch_pilot | `run-c2fadc05bee0` | succeeded | $0.00649 | 2/2 |
| prompt_branch_pilot | `run-a191c092ff6a` | succeeded | $0.00916 | 2/2 |
| prompt_branch_pilot | `run-4d2e7a72af59` | succeeded | $0.01418 | 2/2 |
| prompt_branch_pilot | `run-f52db21658d1` | succeeded | $0.00658 | 2/2 |
| prompt_branch_pilot | `run-323360c14d5f` | succeeded | $0.01082 | 2/2 |
| fork_seed | `run-6d154b6be623` | failed | $0.00000 | 0/1 |
| fork_seed | `run-83fb791595ad` | succeeded | $0.00136 | 1/1 |
| fork_branch | `run-134ec77d949e` | succeeded | $0.00100 | 1/1 |
| fork_branch | `run-33bbbaa6d82c` | succeeded | $0.00055 | 1/1 |
| fork_branch | `run-c8c35a2c61f3` | succeeded | $0.00050 | 1/1 |
| fork_branch | `run-9ca338196f07` | succeeded | $0.00133 | 1/1 |
| fork_branch | `run-b6b70de821e7` | failed | $0.00000 | 0/1 |
| fork_branch | `run-80ded162abfd` | failed | $0.00000 | 0/1 |
| fork_branch | `run-0ddc7957eb7e` | failed | $0.00000 | 0/1 |
| contemplation_fanout | `run-329d9bbce38c` | failed | $0.00000 | 0/1 |
| contemplation_fanout | `run-4a9ca72e6d50` | failed | $0.00000 | 0/1 |
| contemplation_fanout | `run-4d5feb401fd3` | succeeded | $0.14184 | 17/17 |
| contemplation_fanout_v2 | `run-a2dbea18505c` | succeeded | $0.09423 | 9/9 |
| flash_ladder_kb | `run-da068d1f0950` | succeeded | $0.01462 | 2/2 |
| flash_ladder_kb | `run-8b92a26d5744` | succeeded | $0.00926 | 2/2 |
| flash_ladder_kb | `run-6b54a3f2e744` | succeeded | $0.01005 | 2/2 |
| flash_ladder_kb | `run-54d26f46bf9d` | succeeded | $0.01274 | 2/2 |
| flash_ladder_kb | `run-ed08fbe3c885` | succeeded | $0.00597 | 2/2 |
| flash_ladder_kb | `run-b3db75b4a8f8` | succeeded | $0.00977 | 2/2 |
| flash_ladder_kb | `run-e8e35635ab6f` | failed | $0.00000 | 0/1 |
| flash_ladder_kb | `run-75e8319533fb` | failed | $0.00732 | 0/1 |
| flash_ladder_kb | `run-aeb42e0165c2` | succeeded | $0.01064 | 2/2 |

**Headline economics.** Pilot: 12/12 cells accepted, $0.12082 cells + $0.00147 constructor + $0.03130 evaluator; input cache 95.5–97.9%. Curated Docker forks: one seed + four branches, $0.004735, cache 47% cold → 90% warm. Contemplation wave 1: 17/17 ok, $0.14184, **302,080 cache-read tokens per phase**. Wave 2: 9/9 ok, $0.09423, same 302,080/phase. Arc model spend ≈ **$0.50**.

**Cache caveat (2026-09-20).** The 302,080 figure is a measured per-phase cache-READ count —
identical in every phase of both contemplation runs because it is the shared parent prefix
re-read per fork. It is not a hit percentage; the ledger's derived `cache_hit_rate` field
(0.91–0.98 here) is only as good as its denominator. The review cost that matters is attention:
~55k words of answers for the controller to read.

## 2. Findings (knowledge base, verbatim)

### Prompt-branch pilot (measured [M]) — `7948b8ace287e881`

(artifact: local KB store, not carried by this branch)

### Fleet transport notes (measured [M]) — `6ef9bf9b6ef3b53a`

(artifact: local KB store, not carried by this branch)

### Docker conversation forks, first live run (measured [M]) — `c50f37cfff42523b`

(artifact: local KB store, not carried by this branch)

### In-session contemplation fan-out (measured [M]) — `b8c06bc189c15fee`

(artifact: local KB store, not carried by this branch)

## 3. Decisions (knowledge base)

- **6fce165e8b8f** — fleet repair: recreate the workflow-runner consumer after the broker restart orphaned its socket bind
- **f473370083fb** — park prompt_branch_pilot on one P0 spend authorization (campaign cap)
- **2c64311c0ade** — run-inspection slice under the existing campaign; hygiene fix split to its own branch
- **25a38ad74e6c** — cap install prompt_branch_pilot 2.0/1.0 + the frozen A3 constructor
- **11b9c20f57ba** — pilot transport fix: single-line goals re-freeze; retry the spawn-refused cells
- **218ef84380b5** — pilot complete: 12/12 accepted; no justified default change; findings published; reuse demonstrated
- **124671055948** — cap install fork_seed/fork_branch 1.0/1.0 + the fork experiment
- **5d9362133040** — in-process contemplation forks: aio_session cap + fanned prompts (policy exception)

## 4. Results in detail

### 4.1 Prompt-branch pilot (12 cells)

| arm | accepted | total $ | mean $/accepted | tokens | input cache hit | big misses |
|---|---|---|---|---|---|---|
| A0 | 3/3 | 0.01988 | 0.00663 | 50836 | 96.66% | 0 |
| A1 | 3/3 | 0.02765 | 0.00922 | 64480 | 97.86% | 0 |
| A2 | 3/3 | 0.0413 | 0.01377 | 108137 | 97.17% | 0 |
| A3 | 3/3 | 0.03199 | 0.01066 | 102753 | 95.46% | 0 |

All 12 host-reverified; arm-blind evaluator accepted all; **on this one task no instruction
variant showed an improvement — every arm sat at the acceptance ceiling** (ceiling null; not a
"measured disproof" that instruction prose cannot change outcomes — §4.4).

### 4.2 Docker conversation forks (curated seed)

- Seed `run-83fb791595ad` → checkpoint `fork_seed/run-83fb791595ad-seed.a1` ($0.001358).
- Four isolated branches (`run-134ec77d949e`, `run-33bbbaa6d82c`, `run-c8c35a2c61f3`, `run-9ca338196f07`): $0.0005–$0.0013 each; cache read 4,480 → 8,704 tokens (47% → 90% warm); answers + reuse evidence in `experiments/results/fork_experiment/`.
- Frozen REAL-session snapshots refused to fork in Docker (3 attempts); root cause: row-level extraction lost auxiliary data; a native `opencode export/import` round-trip preserves the session (proved). In-process forks of a real aio-control session work via an isolated store.

### 4.3 Contemplation waves 1+2 (24 contemplations + 2 syntheses = 26 outputs)

Both waves ran **in-process** — single `agent_task` workflows whose phases fork ONE approved
aio-control session with fixed-parent `fork_session` (workdir `/tmp/cont_run`); no Docker.

- Wave 1: `run-4d5feb401fd3`, 17/17 ok, $0.14184; wave 2: `run-a2dbea18505c`, 9/9 ok, $0.09423;
  302,080 cache-read tokens per phase (a count — see §1).
- **Delivery (verified 2026-09-20).** The wave-1 synthesis received the sixteen answers
  **bounded to 4,000 chars each** (stored prompt 66,729 chars; full answers 10.5–21.6 KB). The
  wave-2 synthesis received **no sibling outputs** — its prompt never inserted
  `{prior_answers}` — and only the static ≈700-char wave-1 excerpts; it says so itself
  (`wave2/c09.md:53`). Neither run's ledger persists phase responses.
- **Therefore:** the 24 contemplations are the material; the two syntheses are advisory and input-bounded.
  The *adjacent-quantity law* and Q-A/Q-B stand as proposals read through a 4k-char window; the
  wave-2 typed-boundary reconciliation stands as a proposal; the "retire further contemplation"
  conclusion is **rejected** (§4.4). The controller keeps the contemplation experiment.
- **Next (controller-directed, 2026-09-20):** (1) correct this record; (2) repair and verify
  answer delivery before another wave — capture full branch responses, supply them explicitly to
  the synthesis, record which complete outputs it received, and keep the shared parent prefix
  stable with the new evidence appended after it; (3) rerun only the synthesis on the existing
  answers (preserve disagreements; challenge the prompts' assumptions; separate historical-code
  claims from today's behavior); (4) turn one useful finding into a bounded improvement using
  existing machinery — stale next-action state **or** a missing regression check, after
  verifying the gap exists today; (5) evaluate the fork idea fairly — one broad analysis vs
  several focused forks + synthesis on the same starting evidence and a comparable total
  budget, measuring new validated findings, better decisions, misleading recommendations, and
  the controller's reading/rework time. Do not build a generalized prose compiler or another
  governance framework; retain unsuccessful ideas with their evidence and rejection reasons.
- **Fork-instruction direction (2026-09-20):** relax the constraint — forks may use **read-only
  tools to explore and dissect the session** (not edit or fix), and each output is (a) a
  markdown report and (b) a **knowledge emission** via the existing producer path
  (`emit_phase_finding`/`derive_phase_record`; advisory authority for unverified phases). The
  current specs disable this (`rag.emit_self: false`; all phases `research_readonly` with no
  commits, and the emit hook requires `pr.commit_hash`).
- **Repair verified (2026-09-20):** `run-1ec7bb0052f0` (spec `contemplation_synthesis_rerun`,
  $0.0315) delivered all 24 answers complete (355,473 chars) as a workspace-internal file bundle
  + delivery manifest; the synthesis read 24/24 files (transcript-verified) and produced the
  20,223-char reconciliation at `experiments/results/fork_contemplation/synthesis_rerun/answer.md`
  (advisory KB record `fd4a3960…`). Two next-iteration gaps it flagged: prior syntheses cited
  second-hand; no lineage labels in the manifest.
- **Emission verified (2026-09-20, Astra acceptance):** the runner captures a research fork's
  COMPLETE turn from its session store, persists it as a durable report, and emits an advisory
  finding (`phase-report/v1`) whose text IS the report (evidence link = the report file).
  Verified: registry line + mid-report retrieval through the real pipeline + link resolution.

### 4.4 Claim classes (2026-09-20 correction)

*(Citations under `experiments/results/fork_contemplation/`.)*

**Observed (kept).**

- The capacity-gate false trip: a valid session refused at WARN 172,491 against 968,000 usable
  (`ses_f5add1095ffe1ZDEm4YJZJLbwy`; wave1/c01, c03, c05).
- Three config-resolver divergences: `OPENCODE_CONFIG` precedence, partial `output` override
  discarding inherited `context`, JSONC trailing commas (wave1/c01, c02, c03).
- Acceptance ≠ effect: the swallowed `fleet_manager restart` (claimed; queue and processing lane
  empty; no compose call; PID unchanged — wave1/c01, c02, c05, c12); "a queued submit is NOT a
  running run"; the same-spec failing chain (`run-f344c4b99162 → run-f52d829af58e →
  run-b787b0d16d6c → run-dfa259243059 → run-0da5271bc0cb`; wave1/c06, c17).
- The delivery gaps in §4.3 and the fork-transport results (§4.2).
- Historical observation to re-check before building: a binding still instructing "activate,
  then submit" after both had happened (wave1/c15:20).

**Hypotheses (kept as hypotheses, not findings).** The original 25-hour failure was
compliance/looping rather than capacity-bounded (wave1/c11, c13); native compaction fires on a
live session (never observed on this host); a recurrence interlock would have flagged the
failing chain (wave1/c06); control-action receipts would raise restart reliability (wave1/c04,
c07).

**Proposals (status).**

- *Kept direction:* keep the existing task state current after confirmed actions — the first
  fix, not another memory format (wave1/c15:20).
- *Kept direction:* enforce operational constraints where the action happens — the supported
  execution tool enforces the permitted route and gives useful feedback on refusal (wave1/c12).
- *Candidate:* the Q-B differential harness (a differential/mutation test against the runtime,
  re-injecting the controller's findings; re-judge after the synthesis rerun) (wave2/c01,
  wave2/c09).
- *Candidate:* one bounded improvement — stale next-action state **or** a missing regression
  check — after verifying the gap exists today.
- *Rejected:* "contemplation should retire itself / no further waves / narrative waves provably
  ≤ 0" (wave2/c09:96-98) — see the four grounds in `contemplation_waves_1_2_review.md`.
- *Rejected:* "unpromoted questions are dropped, not stored" (wave2/c07:88) — contradicts
  retaining unsuccessful ideas as searchable evidence; retain with evidence and rejection
  reasons, without a backlog obligation.
- *Do not build:* a generalized prose compiler or another governance framework (controller
  direction, 2026-09-20).
- *Needs technical review before implementation:* the context-dose decision rule that hardens on
  `UCB95(−τ_g) > δ` (wave2/c03:216-224) — the upper bound of harm says substantial harm remains
  *possible*, not established; as written it could harden from inconclusive data and recreate
  the unwanted cutoff.

**Open disagreements (kept visible).** Loop rate — every turn vs the plant's time constant
(wave1/c11 vs wave1/c05); single authority vs resilience (wave1/c04, c14 vs wave1/c05, c12);
capacity vs compliance as root cause (wave1/c11, c13 vs the directive); human review's value
(wave1/c08, c09 vs wave2/c05); build breadth (wave1/c09 vs wave1/c07 vs wave2/c01).

## 5. Knowledge learned (consolidated)

- Forks must be transported, not assumed: explicit parent identity; per-cell snapshot copies; refuse on missing/mismatched bytes — never a silent fresh session.
- SQLite snapshots: backup API, standalone, hash finished bytes, atomic publish with unique temps; identity from stable conversation contents, never transient -shm/WAL bookkeeping.
- Read-only scopes cannot host runner writes (transcripts, scratch workdir) — redirect to the state mount.
- Pin checkpoints at submit (latest-aliases move); carry cache/cost child → parent → ledger.
- Cache reuse is a contributing measurement, never proof of better work; binary oracles saturate; cost rankings without quality signals are provisional; cache-read counts are counts, not hit rates.
- Contemplation is kept as an information generator — with its evidence delivered and recorded. The wave-2 claim that "contemplation without a required artifact is a net cost" was a prompt-supplied entry claim (`docs/experiments/contemplation/prompts-v2.md:57-62`), not a measured finding; "provably ≤ 0" is rejected (§4.4). The adjacent-quantity substitution (accepted vs completed; green tests vs correct behavior; available context vs effective reasoning) is a useful failure *pattern*, not a universal law; new requirements, counterexamples and better questions have value before they are executable.

## 6. Named gaps

- **Fork-answer delivery — repaired + verified (2026-09-20).** `final_response` is now persisted on the ledger; the `{prior_answers}` channel delivers complete by default and switches to a workspace-internal file bundle above 100k chars (a single Linux argv arg caps at ~128 KB — measured live: `exit_code=-2` E2BIG on the 355 KB prompt); the delivery manifest (`answers_delivered`) records name/path/chars/sha256/complete. Verification: `run-1ec7bb0052f0` delivered 24/24 complete answers and the synthesis read 24/24 files (transcript-verified). Next-iteration gaps it flagged: prior syntheses cited second-hand; no lineage labels in the manifest.
- Contemplation outputs produce no KB emission today: both specs set `rag.emit_self: false` and all phases are `research_readonly` with no commits (the emit hook requires `pr.commit_hash`). Direction: relax the fork instruction (read-only exploration allowed; no edits) and emit each output as a scoped advisory finding via the existing producer path (§4.3).
- Frozen real-session Docker forks (snapshot transport) remain unproven; the in-process path was used instead.
- Part 2 (capsule reminder, host-worker tool refusals, owned-run cancellation) not implemented.
- Augmentation cost not itemized in the ledger.

## 7. Where the raw artifacts live

- Ledgers: `experiments/results/workflows/<family>/*.json`; control DB + journals: `experiments/results/control/`.
- Checkpoints/receipts: `experiments/results/opencode/{aio_session,fork_seed,fork_branch}/`.
- Experiment dirs: `fork_contemplation/`, `prompt_branch_pilot/`, `fork_experiment/`, `delivery/`.
- Knowledge: `experiments/results/kb/<id>.json` + `registry_index.jsonl` (both retrieval legs).
- Correction evidence (2026-09-20): fork-store prompt (`ses_f4054506cffeBQ8yDRBn29I03T`, 66,729-char user message); `src/agentic_dynamics/runtime/workflow_runner.py:283,356-422,4844-4849`; `wave2/c09.md:53`; KB records `7948b8ace287e881`, `6ef9bf9b6ef3b53a`, `c50f37cfff42523b`, `b8c06bc189c15fee` (local store, not carried by this branch).
