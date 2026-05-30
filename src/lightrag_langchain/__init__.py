"""lightrag-langchain — LangChain-based query layer for LightRAG knowledge graphs.

All Phase 3+ factory/utility functions are exposed via lazy ``__getattr__``
so that ``import lightrag_langchain`` does NOT trigger:
- Settings singleton instantiation (no .env file required at import time)
- Any LangChain imports (ChatOpenAI, OpenAIEmbeddings, BaseDocumentCompressor)
- Any tiktoken imports
- Any httpx imports

Data-layer models (EntityRecord, RelationshipRecord, ChunkRecord, GraphNode,
GraphEdge, PGVectorStore, PGGraphStore) remain accessible via
``from lightrag_langchain.data import ...`` and are NOT re-exported here.
"""

from __future__ import annotations


def __getattr__(name: str):
    """Lazy import for all Phase 3 modules — defers import/construction until
    the exported identifier is actually accessed.

    Pattern matches :file:`data/__init__.py` (L:20-32).
    """
    # -- LLM / Embedding factories (llm.py) -----------------------------------
    if name == "create_llm":
        from lightrag_langchain.llm import create_llm

        return create_llm
    if name == "create_embedding":
        from lightrag_langchain.llm import create_embedding

        return create_embedding

    # -- Reranker (reranker.py) -----------------------------------------------
    if name == "create_reranker":
        from lightrag_langchain.reranker import create_reranker

        return create_reranker
    if name == "LightRAGReranker":
        from lightrag_langchain.reranker import LightRAGReranker

        return LightRAGReranker

    # -- Keywords (keywords.py) -----------------------------------------------
    if name == "KeywordsSchema":
        from lightrag_langchain.keywords import KeywordsSchema

        return KeywordsSchema
    if name == "extract_keywords":
        from lightrag_langchain.keywords import extract_keywords

        return extract_keywords

    # -- Token budget (token_budget.py) ---------------------------------------
    if name == "truncate_entities_by_tokens":
        from lightrag_langchain.token_budget import truncate_entities_by_tokens

        return truncate_entities_by_tokens
    if name == "truncate_relations_by_tokens":
        from lightrag_langchain.token_budget import truncate_relations_by_tokens

        return truncate_relations_by_tokens
    if name == "compute_chunk_token_budget":
        from lightrag_langchain.token_budget import compute_chunk_token_budget

        return compute_chunk_token_budget

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
