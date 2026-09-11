# Expert knowledge seed — our tech stacks (2026-09-11)

Authoritative documentation fetched through `scripts/research_fetch.py` (open egress,
controller-approved) for the technologies this repo actually uses. This corpus is the frozen
input to `workflows/repository/stack_knowledge_seed.yaml`: the workflow distils per-stack
skills from these sources (citations required), an independent verifier checks entailment, and
the AIO then emits the accepted skills into the knowledge base through the verified pattern
projection path (`scripts/kb_produce_skill.py`).

- `sources/` — 28 source records (uri, final_url, fetched_at, sha256, title, text).
- `sources_catalog.jsonl` — the append-only catalog (one line per source).
- Fetch seeds: Python, Flask, Celery, SQLite (WAL/lang), Redis (streams/pubsub/locks),
  Neo4j/Cypher, Chroma, Docker/Compose, Playwright, Firebase Hosting, MDN SVG/CSS/WCAG,
  systemd, pytest, DuckDB/Parquet.
