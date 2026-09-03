"""Knowledge — knowledge + augmentation (critique system 4).

Ownership: canonical identity + authority contract (``knowledge``), durable stream transport
(``knowledge_stream``), the record factory, deterministic retrieval, prompt construction, the
RAG seam (``augment``), the Neo4j/Chroma stores (``graph``/``embeddings``), and the ingestion
producers (knowledge/code/quality/policy/story/review/ledger/session/spec).

Knowledge does NOT actuate (rec 8): no module here calls
``actuation_ingestion.derive_actuation_record``, and retrieval never supplies canonical
POLICY-authority facts (enforced by the Stage 1 data-flow tests).
"""

from . import (
    augment,
    code_ingestion,
    decision_ingestion,
    embeddings,
    graph,
    knowledge,
    knowledge_ingestion,
    knowledge_stream,
    ledger_ingestion,
    policy_ingestion,
    prompt_constructor,
    quality_ingestion,
    record_factory,
    retrieval,
    review_ingestion,
    session_ingestion,
    spec_ingestion,
    story_ingestion,
)

__all__ = ['augment', 'code_ingestion', 'decision_ingestion', 'embeddings', 'graph', 'knowledge', 'knowledge_ingestion', 'knowledge_stream', 'ledger_ingestion', 'policy_ingestion', 'prompt_constructor', 'quality_ingestion', 'record_factory', 'retrieval', 'review_ingestion', 'session_ingestion', 'spec_ingestion', 'story_ingestion']
