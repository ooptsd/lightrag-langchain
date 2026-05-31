"""LightRAG retriever implementations — LangChain BaseRetriever subclasses.

This package provides a shared base class :class:`LightRAGBaseRetriever` and
six mode-specific retriever subclasses (NaiveRetriever, LocalRetriever,
GlobalRetriever, HybridRetriever, MixRetriever, BypassRetriever), each
encapsulating one LightRAG query mode behind the standard LangChain
``BaseRetriever`` interface.

All exports use lazy ``__getattr__`` so that ``import lightrag_langchain.retriever``
does NOT trigger:
- Settings singleton instantiation (no .env file required at import time)
- Any LangChain imports (BaseRetriever, Document)
- Any database connection
- Any network call
"""

from __future__ import annotations

__all__ = [
    "LightRAGBaseRetriever",
    "NaiveRetriever",
    "LocalRetriever",
    "GlobalRetriever",
    "HybridRetriever",
    "MixRetriever",
    "BypassRetriever",
]


def __getattr__(name: str):
    """Lazy import for retriever classes — defers import/construction until
    the exported identifier is actually accessed.

    Pattern matches :file:`lightrag_langchain/query/__init__.py` and
    :file:`lightrag_langchain/data/__init__.py`.
    """
    if name == "LightRAGBaseRetriever":
        from lightrag_langchain.retriever.base import LightRAGBaseRetriever

        return LightRAGBaseRetriever
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

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
