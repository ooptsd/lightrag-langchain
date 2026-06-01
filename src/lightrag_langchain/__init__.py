"""lightrag-langchain — LangChain-based query layer for LightRAG knowledge graphs.

All Phase 3+ factory/utility functions are exposed via lazy ``__getattr__``
so that ``import lightrag_langchain`` does NOT trigger:
- Settings singleton instantiation (no .env file required at import time)
- Any LangChain imports (ChatOpenAI, OpenAIEmbeddings, BaseDocumentCompressor)
- Any tiktoken imports
- Any httpx imports

Phase 5 retriever classes (NaiveRetriever, LocalRetriever, GlobalRetriever,
HybridRetriever, MixRetriever, BypassRetriever) are also exposed via lazy
``__getattr__``.

Phase 6 chain classes (NaiveChain, LocalChain, GlobalChain, HybridChain,
MixChain, BypassChain) are also exposed via lazy ``__getattr__``.

Data-layer models (EntityRecord, RelationshipRecord, ChunkRecord, GraphNode,
GraphEdge, PGVectorStore, PGGraphStore) remain accessible via
``from lightrag_langchain.data import ...`` and are NOT re-exported here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lightrag_langchain.llm import create_embedding, create_llm
    from lightrag_langchain.reranker import LightRAGReranker, create_reranker
    from lightrag_langchain.keywords import KeywordsSchema, extract_keywords
    from lightrag_langchain.token_budget import (
        compute_chunk_token_budget,
        truncate_entities_by_tokens,
        truncate_relations_by_tokens,
    )
    from lightrag_langchain.retriever.retrievers import (
        BypassRetriever,
        GlobalRetriever,
        HybridRetriever,
        LocalRetriever,
        MixRetriever,
        NaiveRetriever,
    )
    from lightrag_langchain.chain.chains import (
        BypassChain,
        GlobalChain,
        HybridChain,
        LocalChain,
        MixChain,
        NaiveChain,
    )


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

    # -- Retrievers (retriever/retrievers.py) ----------------------------------
    if name == "NaiveRetriever":
        from lightrag_langchain.retriever.retrievers import NaiveRetriever

        return NaiveRetriever
    if name == "LocalRetriever":
        from lightrag_langchain.retriever.retrievers import LocalRetriever

        return LocalRetriever
    if name == "GlobalRetriever":
        from lightrag_langchain.retriever.retrievers import GlobalRetriever

        return GlobalRetriever
    if name == "HybridRetriever":
        from lightrag_langchain.retriever.retrievers import HybridRetriever

        return HybridRetriever
    if name == "MixRetriever":
        from lightrag_langchain.retriever.retrievers import MixRetriever

        return MixRetriever
    if name == "BypassRetriever":
        from lightrag_langchain.retriever.retrievers import BypassRetriever

        return BypassRetriever

    # -- Chains (chain/chains.py) ----------------------------------------------
    if name == "NaiveChain":
        from lightrag_langchain.chain.chains import NaiveChain

        return NaiveChain
    if name == "LocalChain":
        from lightrag_langchain.chain.chains import LocalChain

        return LocalChain
    if name == "GlobalChain":
        from lightrag_langchain.chain.chains import GlobalChain

        return GlobalChain
    if name == "HybridChain":
        from lightrag_langchain.chain.chains import HybridChain

        return HybridChain
    if name == "MixChain":
        from lightrag_langchain.chain.chains import MixChain

        return MixChain
    if name == "BypassChain":
        from lightrag_langchain.chain.chains import BypassChain

        return BypassChain

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
