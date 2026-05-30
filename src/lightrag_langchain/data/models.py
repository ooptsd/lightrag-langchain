"""Pydantic record models for LightRAG PostgreSQL and Apache AGE query results.

These frozen Pydantic BaseModel subclasses type all data records flowing through
the LightRAG-to-Langchain query layer. Each model maps to a specific LightRAG
database table under the ``lightrag`` / ``lightrag_vdb`` schema.

All models use ``model_config = ConfigDict(frozen=True)`` to enforce immutability
(T-02-01), matching the pattern established in Phase 1's ``config.py``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Model 1 — PGVector entity vector search result (LIGHTRAG_VDB_ENTITY)
# ---------------------------------------------------------------------------


class EntityRecord(BaseModel):
    """A single entity row from the PGVector ``LIGHTRAG_VDB_ENTITY`` table.

    Represents a named entity stored in the vector database.  The ``source_id``
    field is the ``VDB_ENTITY.id`` column (renamed per STOR-01).  ``file_path``
    and ``created_at`` use COALESCE-compatible defaults (DDL allows NULL).
    """

    model_config = ConfigDict(frozen=True)

    entity_name: str
    """The entity name (VARCHAR(512) in DDL)."""

    content: str
    """Full textual content of the entity."""

    source_id: str
    """Entity unique identifier (VDB_ENTITY.id, renamed per STOR-01)."""

    file_path: str = ""
    """Source file path (COALESCE'd from NULL)."""

    created_at: int | None = None
    """Epoch seconds from ``EXTRACT(EPOCH FROM create_time)::BIGINT``."""


# ---------------------------------------------------------------------------
# Model 2 — PGVector relationship vector search result (LIGHTRAG_VDB_RELATION)
# ---------------------------------------------------------------------------


class RelationshipRecord(BaseModel):
    """A single relationship row from the PGVector ``LIGHTRAG_VDB_RELATION`` table.

    The DDL does NOT contain ``keywords`` / ``weight`` columns (see RESEARCH.md
    Open Question 1).  Those fields default to ``None`` for PGVector results;
    real values come from AGE graph edges (Plan 02-04).
    """

    model_config = ConfigDict(frozen=True)

    src_id: str
    """Source entity ID (VDB_RELATION.source_id)."""

    tgt_id: str
    """Target entity ID (VDB_RELATION.target_id)."""

    content: str | None = None
    """Relation textual content."""

    keywords: str | None = None
    """Relation keywords — NULL from VDB_RELATION; real value from AGE edges."""

    weight: float | None = None
    """Relation weight — NULL from VDB_RELATION; real value from AGE edges."""

    created_at: int | None = None
    """Epoch seconds from ``create_time``."""


# ---------------------------------------------------------------------------
# Model 3 — PGVector chunk vector search result (LIGHTRAG_VDB_CHUNKS)
# ---------------------------------------------------------------------------


class ChunkRecord(BaseModel):
    """A single chunk row from the PGVector ``LIGHTRAG_VDB_CHUNKS`` table.

    Maps to the text chunk storage used by LightRAG for naive / mix retrieval.
    ``full_doc_id`` and ``chunk_order_index`` correspond to the document
    relationship and ordering the chunk belongs to.
    """

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    """Chunk identifier (VDB_CHUNKS.id)."""

    content: str
    """Full textual content of the chunk."""

    full_doc_id: str | None = None
    """Parent document identifier (VDB_CHUNKS.full_doc_id)."""

    chunk_order_index: int | None = None
    """Position in document sequence (VDB_CHUNKS.chunk_order_index)."""

    file_path: str = ""
    """Source file path (COALESCE'd from NULL)."""


# ---------------------------------------------------------------------------
# Model 4 — Apache AGE graph node (label "base")
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    """An entity node from the Apache AGE graph under label ``base``.

    Properties (``entity_type``, ``description``, ``source_id``) come from the
    AGE ``properties`` dict.  ``description`` and ``source_id`` may be NULL in
    the database, defaulting to ``""`` here.
    """

    model_config = ConfigDict(frozen=True)

    entity_id: str
    """Node identity from ``properties.entity_id`` on the AGE node."""

    entity_type: str
    """Node type from ``properties.entity_type`` on the AGE node."""

    description: str = ""
    """Entity description from ``properties.description`` (may be NULL in DB)."""

    source_id: str = ""
    """Document source from ``properties.source_id`` (may be NULL in DB)."""


# ---------------------------------------------------------------------------
# Model 5 — Apache AGE graph edge (label "DIRECTED")
# ---------------------------------------------------------------------------


class GraphEdge(BaseModel):
    """A directed edge from the Apache AGE graph under label ``DIRECTED``.

    All optional fields match the AGE ``edge_properties`` dict returned by
    ``get_edges_batch()`` (``description``, ``keywords``, ``weight`` are all
    nullable in the DB).
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    """Source entity ID (src node's entity_id)."""

    target_id: str
    """Target entity ID (tgt node's entity_id)."""

    description: str | None = None
    """Edge description from ``properties.description`` on the AGE edge."""

    keywords: str | None = None
    """Edge keywords from ``properties.keywords`` on the AGE edge."""

    weight: float | None = None
    """Edge weight from ``properties.weight`` on the AGE edge."""
