"""Unit tests for QueryResult model, GraphTriple model, and all 6 query strategies.

Tests cover instantiation, default values, frozen immutability, and
required-field validation for QueryResult and GraphTriple.  Strategy
test classes are stubbed as placeholders (implemented in Plan 02/03).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)

# ---------------------------------------------------------------------------
# QueryResult model tests
# ---------------------------------------------------------------------------


class TestQueryResultModel:
    """QueryResult model tests — single-union-type frozen Pydantic model (D-01, D-02)."""

    def test_empty_construction(self):
        """QueryResult() constructs with all 4 fields as empty lists."""
        from lightrag_langchain.query.results import QueryResult

        result = QueryResult()
        assert result.entities == []
        assert result.relations == []
        assert result.chunks == []
        assert result.graph_triples == []
        assert len(result.entities) == 0
        assert len(result.relations) == 0
        assert len(result.chunks) == 0
        assert len(result.graph_triples) == 0

    def test_frozen_immutable(self):
        """Setting entities on a frozen QueryResult raises ValidationError."""
        from lightrag_langchain.query.results import QueryResult

        result = QueryResult()
        with pytest.raises(ValidationError):
            result.entities = []  # type: ignore[misc]

    def test_fields_populated(self):
        """Construct QueryResult with 1 fake entity, relation, and chunk — verify counts."""
        from lightrag_langchain.query.results import QueryResult

        entity = EntityRecord(
            entity_name="TestEntity",
            content="test entity content",
            source_id="src-1",
        )
        relation = RelationshipRecord(
            src_id="s1",
            tgt_id="t1",
            content="test relation content",
        )
        chunk = ChunkRecord(
            chunk_id="chk-1",
            content="test chunk content",
        )

        result = QueryResult(
            entities=[entity],
            relations=[relation],
            chunks=[chunk],
        )
        assert len(result.entities) == 1
        assert result.entities[0].entity_name == "TestEntity"
        assert len(result.relations) == 1
        assert result.relations[0].src_id == "s1"
        assert len(result.chunks) == 1
        assert result.chunks[0].chunk_id == "chk-1"
        assert len(result.graph_triples) == 0


# ---------------------------------------------------------------------------
# GraphTriple model tests
# ---------------------------------------------------------------------------


class TestGraphTripleModel:
    """GraphTriple model tests — (src_entity, relation, tgt_entity) frozen Pydantic model (D-04)."""

    def test_required_fields(self):
        """Constructing GraphTriple without any field raises ValidationError."""
        from lightrag_langchain.query.results import GraphTriple

        with pytest.raises(ValidationError):
            GraphTriple()  # type: ignore[call-arg]

    def test_full_construction(self):
        """Construct GraphTriple with real GraphNode + GraphEdge + GraphNode and verify attrs."""
        from lightrag_langchain.query.results import GraphTriple

        src = GraphNode(entity_id="n1", entity_type="Person", description="Alice")
        edge = GraphEdge(source_id="n1", target_id="n2", description="works_at")
        tgt = GraphNode(entity_id="n2", entity_type="Organization", description="Acme Inc")

        triple = GraphTriple(src_entity=src, relation=edge, tgt_entity=tgt)
        assert triple.src_entity.entity_id == "n1"
        assert triple.src_entity.entity_type == "Person"
        assert triple.relation.source_id == "n1"
        assert triple.relation.target_id == "n2"
        assert triple.relation.description == "works_at"
        assert triple.tgt_entity.entity_id == "n2"
        assert triple.tgt_entity.entity_type == "Organization"

    def test_frozen_immutable(self):
        """Setting src_entity on a frozen GraphTriple raises ValidationError."""
        from lightrag_langchain.query.results import GraphTriple

        src = GraphNode(entity_id="n1", entity_type="Person")
        edge = GraphEdge(source_id="n1", target_id="n2")
        tgt = GraphNode(entity_id="n2", entity_type="Organization")
        triple = GraphTriple(src_entity=src, relation=edge, tgt_entity=tgt)

        with pytest.raises(ValidationError):
            triple.src_entity = GraphNode(entity_id="x", entity_type="Thing")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Naive strategy placeholder (QUERY-01)
# ---------------------------------------------------------------------------


class TestNaiveStrategy:
    """Naive mode — chunk vector search (QUERY-01)."""

    @pytest.mark.skip(reason="Implemented in Plan 02")
    async def test_placeholder(self):
        pass


# ---------------------------------------------------------------------------
# Local strategy placeholder (QUERY-02)
# ---------------------------------------------------------------------------


class TestLocalStrategy:
    """Local mode — entity vector search + graph expansion (QUERY-02)."""

    @pytest.mark.skip(reason="Implemented in Plan 02")
    async def test_placeholder(self):
        pass


# ---------------------------------------------------------------------------
# Global strategy placeholder (QUERY-03)
# ---------------------------------------------------------------------------


class TestGlobalStrategy:
    """Global mode — relation vector search + entity lookup (QUERY-03)."""

    @pytest.mark.skip(reason="Implemented in Plan 02")
    async def test_placeholder(self):
        pass


# ---------------------------------------------------------------------------
# Hybrid strategy placeholder (QUERY-04)
# ---------------------------------------------------------------------------


class TestHybridStrategy:
    """Hybrid mode — parallel local+global + round-robin merge (QUERY-04)."""

    @pytest.mark.skip(reason="Implemented in Plan 02")
    async def test_placeholder(self):
        pass


# ---------------------------------------------------------------------------
# Mix strategy placeholder (QUERY-05)
# ---------------------------------------------------------------------------


class TestMixStrategy:
    """Mix mode — hybrid + chunk search + chunk merge (QUERY-05)."""

    @pytest.mark.skip(reason="Implemented in Plan 02")
    async def test_placeholder(self):
        pass


# ---------------------------------------------------------------------------
# Bypass strategy placeholder (QUERY-06)
# ---------------------------------------------------------------------------


class TestBypassStrategy:
    """Bypass mode — no retrieval, empty QueryResult (QUERY-06)."""

    @pytest.mark.skip(reason="Implemented in Plan 02")
    async def test_placeholder(self):
        pass
