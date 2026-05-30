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

__all__ = ["QueryResult", "GraphTriple"]


def __getattr__(name: str):
    """Lazy import for query strategy functions — defers import/construction
    until the exported identifier is actually accessed.

    Pattern matches :file:`lightrag_langchain/__init__.py` (L:18-68) and
    :file:`data/__init__.py` (L:20-32).
    """
    # -- Strategy functions (added in Plan 03) --------------------------------

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
