"""Data layer package — connection pool, data models, vector store, and graph store."""

from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)

__all__ = [
    "EntityRecord",
    "RelationshipRecord",
    "ChunkRecord",
    "GraphNode",
    "GraphEdge",
]


def __getattr__(name: str):
    """Lazy import PGVectorStore and PGGraphStore to avoid triggering Settings
    instantiation at import time (before pytest fixtures can monkeypatch env vars).
    """
    if name == "PGVectorStore":
        from lightrag_langchain.data.store import PGVectorStore

        return PGVectorStore
    if name == "PGGraphStore":
        from lightrag_langchain.data.graph import PGGraphStore

        return PGGraphStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
