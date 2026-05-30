"""LightRAG query strategy implementations.

This package provides six query strategies (naive, local, global, hybrid,
mix, bypass) that execute against the LightRAG PostgreSQL knowledge graph.
Each strategy returns a strongly-typed :class:`QueryResult` intermediate
representation (D-01, D-02), which downstream consumers (Phase 5 Retriever,
Phase 6 Chain) convert and assemble.

Models (eagerly imported)
    :class:`QueryResult` — Single-union type with entities, relations,
    chunks, and graph_triples fields; each strategy fills only its relevant
    fields.

    :class:`GraphTriple` — A (src_entity, relation, tgt_entity) triple
    from graph traversal, carrying full node and edge properties.

Strategy functions (lazy, added in Plan 03)
    When accessed, the ``__getattr__`` lazy import mechanism resolves
    strategy function references to ``lightrag_langchain.query.strategies``
    without triggering Settings instantiation at import time.
"""

from __future__ import annotations

from lightrag_langchain.query.results import GraphTriple, QueryResult

__all__ = [
    "QueryResult",
    "GraphTriple",
    "naive_strategy",
    "local_strategy",
    "global_strategy",
    "hybrid_strategy",
    "mix_strategy",
    "bypass_strategy",
]


def __getattr__(name: str):
    """Lazy import for query strategy functions — defers import/construction
    until the exported identifier is actually accessed.

    Pattern matches :file:`lightrag_langchain/__init__.py` (L:18-68) and
    :file:`data/__init__.py` (L:20-32).
    """
    if name == "naive_strategy":
        from lightrag_langchain.query.strategies import naive_strategy

        return naive_strategy
    if name == "local_strategy":
        from lightrag_langchain.query.strategies import local_strategy

        return local_strategy
    if name == "global_strategy":
        from lightrag_langchain.query.strategies import global_strategy

        return global_strategy
    if name == "hybrid_strategy":
        from lightrag_langchain.query.strategies import hybrid_strategy

        return hybrid_strategy
    if name == "mix_strategy":
        from lightrag_langchain.query.strategies import mix_strategy

        return mix_strategy
    if name == "bypass_strategy":
        from lightrag_langchain.query.strategies import bypass_strategy

        return bypass_strategy

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
