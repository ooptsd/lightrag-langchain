"""LightRAG QA Chain implementations — LangChain-compatible query-to-answer pipelines.

This package provides a shared base class :class:`LightRAGBaseChain` and
six mode-specific chain subclasses (NaiveChain, LocalChain,
GlobalChain, HybridChain, MixChain, BypassChain), each
encapsulating one LightRAG query mode behind a standard ``invoke`` /
``ainvoke`` / ``astream`` interface.

All exports use lazy ``__getattr__`` so that ``import lightrag_langchain.chain``
does NOT trigger:
- Settings singleton instantiation (no .env file required at import time)
- Any LangChain imports (ChatOpenAI)
- Any LLM / keyword extraction call
- Any database connection
- Any network call
"""

from __future__ import annotations

__all__ = [
    "LightRAGBaseChain",
    "NaiveChain",
    "LocalChain",
    "GlobalChain",
    "HybridChain",
    "MixChain",
    "BypassChain",
]


def __getattr__(name: str):
    """Lazy import for chain classes — defers import/construction until
    the exported identifier is actually accessed.

    Pattern matches :file:`lightrag_langchain/retriever/__init__.py`.
    """
    if name == "LightRAGBaseChain":
        from lightrag_langchain.chain.base import LightRAGBaseChain

        return LightRAGBaseChain
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
