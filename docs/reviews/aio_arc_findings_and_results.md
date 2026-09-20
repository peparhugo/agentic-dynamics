---
status: accepted
---

# AIO arc — findings, knowledge, and results (self-contained)

One document for review: everything this arc measured, learned, and decided, with the raw
artifact locations. Contemplation insights are **advisory [H]**; run metrics and KB findings
marked [M] are **measured**.

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

## 2. Findings (knowledge base, verbatim)

### Prompt-branch pilot (measured [M]) — `7948b8ace287e881`

(artifact missing)

### Fleet transport notes (measured [M]) — `6ef9bf9b6ef3b53a`

(artifact missing)

### Docker conversation forks, first live run (measured [M]) — `c50f37cfff42523b`

(artifact missing)

### In-session contemplation fan-out (measured [M]) — `b8c06bc189c15fee`

(artifact missing)

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

All 12 host-reverified; arm-blind evaluator accepted all; **no instruction variant improved outcomes — baseline stays default** (single task, ceiling effect).

### 4.2 Docker conversation forks (curated seed)

- Seed `run-83fb791595ad` → checkpoint `fork_seed/run-83fb791595ad-seed.a1` ($0.001358).
- Four isolated branches (`run-134ec77d949e`, `run-33bbbaa6d82c`, `run-c8c35a2c61f3`, `run-9ca338196f07`): $0.0005–$0.0013 each; cache read 4,480 → 8,704 tokens (47% → 90% warm); answers + reuse evidence in `experiments/results/fork_experiment/`.
- Frozen REAL-session snapshots refused to fork in Docker (3 attempts); root cause: row-level extraction lost auxiliary data; a native `opencode export/import` round-trip preserves the session (proved). In-process forks of a real aio-control session work via an isolated store.

### 4.3 Contemplation waves 1+2 (26 answers + 2 syntheses)

- Wave 1: **the adjacent-quantity law** — every failure substituted a cheap adjacent quantity for the authority's own output; durable output must be an executable oracle. Q-A (capacity as quality boundary), Q-B (machine reproduction of the controller's oracle); self-scored 1/5 accepted-outcome, 3/5 question-generator.
- Wave 2: resolves prose/mechanism as a **typed boundary**; **wave 3 should be the Q-B differential harness, not another wave**.
- Full texts: `experiments/results/fork_contemplation/wave1/c01..c17.md`, `wave2/c01..c09.md`.

## 5. Knowledge learned (consolidated)

- Forks must be transported, not assumed: explicit parent identity; per-cell snapshot copies; refuse on missing/mismatched bytes — never a silent fresh session.
- SQLite snapshots: backup API, standalone, hash finished bytes, atomic publish with unique temps; identity from stable conversation contents, never transient -shm/WAL bookkeeping.
- Read-only scopes cannot host runner writes (transcripts, scratch workdir) — redirect to the state mount.
- Pin checkpoints at submit (latest-aliases move); carry cache/cost child → parent → ledger.
- Cache reuse is a contributing measurement, never proof of better work; binary oracles saturate; cost rankings without quality signals are provisional.
- Contemplation without a required executable artifact is a net cost: a wave must ship an oracle or a falsifiable question, else it should be a harness.

## 6. Named gaps

- In-process ledgers record `final_response` empty — answers live in session stores; the drawer cannot show them yet.
- Frozen real-session Docker forks (snapshot transport) remain unproven; the in-process path was used instead.
- Part 2 (capsule reminder, host-worker tool refusals, owned-run cancellation) not implemented.
- Augmentation cost not itemized in the ledger.

## 7. Where the raw artifacts live

- Ledgers: `experiments/results/workflows/<family>/*.json`; control DB + journals: `experiments/results/control/`.
- Checkpoints/receipts: `experiments/results/opencode/{aio_session,fork_seed,fork_branch}/`.
- Experiment dirs: `fork_contemplation/`, `prompt_branch_pilot/`, `fork_experiment/`, `delivery/`.
- Knowledge: `experiments/results/kb/<id>.json` + `registry_index.jsonl` (both retrieval legs).
