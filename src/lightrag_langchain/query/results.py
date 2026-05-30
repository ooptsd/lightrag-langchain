"""Pydantic result models for LightRAG query strategy outputs.

These frozen Pydantic BaseModel subclasses represent the structured
intermediate results returned by each of the 6 LightRAG query strategies.
QueryResult is the single-union type (D-02) that carries all possible
retrieved data; each strategy fills only its relevant fields.

Mapping to strategies:
- naive: ``chunks`` only
- local: ``entities`` + ``graph_triples``
- global: ``relations`` + ``graph_triples``
- hybrid: ``entities`` + ``relations`` + ``graph_triples``
- mix: ``entities`` + ``relations`` + ``chunks`` + ``graph_triples``
- bypass: all fields empty (no retrieval)

All models use ``model_config = ConfigDict(frozen=True)``, matching the
pattern established in :file:`data/models.py`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)

# ---------------------------------------------------------------------------
# Model 1 — Graph triple representing (entity, relation, entity)
# ---------------------------------------------------------------------------


class GraphTriple(BaseModel):
    """A single (src_entity, relation, tgt_entity) triple from graph traversal.

    Represents one hop discovered during local / global / hybrid / mix
    graph expansion.  Each field carries the FULL properties of the
    corresponding node or edge, so downstream consumers (Phase 5/6) have
    all available context without additional database lookups.
    """

    model_config = ConfigDict(frozen=True)

    src_entity: GraphNode
    """The source entity node with full properties (entity_id, entity_type, description, source_id)."""

    relation: GraphEdge
    """The directed edge with full properties (description, keywords, weight, source_id, target_id)."""

    tgt_entity: GraphNode
    """The target entity node with full properties (entity_id, entity_type, description, source_id)."""


# ---------------------------------------------------------------------------
# Model 2 — Structured intermediate result from query strategies
# ---------------------------------------------------------------------------


class QueryResult(BaseModel):
    """Structured intermediate result returned by all 6 query strategies (D-01, D-02).

    The single-union-type design uses one model with all possible fields.
    Each strategy fills only the fields relevant to its retrieval path;
    unused fields remain as empty lists.

    Field strategy mapping
    -----------------------
    - ``entities``: populated by local / hybrid / mix (entity vector search)
    - ``relations``: populated by global / hybrid / mix (relation vector search)
    - ``chunks``: populated by naive / mix (chunk vector search)
    - ``graph_triples``: populated by local / global / hybrid / mix (graph expansion)
    """

    model_config = ConfigDict(frozen=True)

    entities: list[EntityRecord] = []
    """Entity records matching query embedding (entities_vdb vector search)."""

    relations: list[RelationshipRecord] = []
    """Relationship records matching query embedding (relationships_vdb vector search)."""

    chunks: list[ChunkRecord] = []
    """Chunk records matching query embedding (chunks_vdb vector search)."""

    graph_triples: list[GraphTriple] = []
    """(src, relation, tgt) triples discovered during graph expansion."""
