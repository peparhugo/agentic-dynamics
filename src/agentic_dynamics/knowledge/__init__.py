"""Knowledge — knowledge + augmentation (critique system 4).

Ownership: canonical identity + authority contract (``knowledge``), durable stream transport
(``knowledge_stream``), the record factory, deterministic retrieval, prompt construction, the
RAG seam (``augment``), the Neo4j/Chroma stores (``graph``/``embeddings``), and the ingestion
producers (knowledge/code/quality/policy/story/review/ledger/spec).

Knowledge does NOT actuate (rec 8): no module here calls
``actuation_ingestion.derive_actuation_record``, and retrieval never supplies canonical
POLICY-authority facts (enforced by the Stage 1 data-flow tests).
"""
