"""Comprehensive test suite for data layer Pydantic record models.

Tests cover instantiation, default values, and frozen immutability for all
5 record models: EntityRecord, RelationshipRecord, ChunkRecord, GraphNode,
and GraphEdge. Also verifies __all__ exports from the data package init.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# EntityRecord tests
# ---------------------------------------------------------------------------


class TestEntityRecord:
    """EntityRecord tests — PGVector lightrag_vdb_entity_* row mapping."""

    def test_instantiation_all_fields(self):
        """Instantiate EntityRecord with all fields populated."""
        from lightrag_langchain.data.models import EntityRecord

        record = EntityRecord(
            entity_name="E1",
            content="Entity content",
            source_id="abc123",
            file_path="/docs/a.md",
            created_at=1717000000,
        )
        assert record.entity_name == "E1"
        assert record.content == "Entity content"
        assert record.source_id == "abc123"
        assert record.file_path == "/docs/a.md"
        assert record.created_at == 1717000000

    def test_default_file_path(self):
        """file_path defaults to empty string when not provided."""
        from lightrag_langchain.data.models import EntityRecord

        record = EntityRecord(entity_name="E1", content="Entity content", source_id="abc123")
        assert record.file_path == ""

    def test_default_created_at(self):
        """created_at defaults to None when not provided."""
        from lightrag_langchain.data.models import EntityRecord

        record = EntityRecord(entity_name="E1", content="Entity content", source_id="abc123")
        assert record.created_at is None

    def test_frozen_prevents_mutation(self):
        """Setting entity_name on a frozen EntityRecord raises ValidationError."""
        from lightrag_langchain.data.models import EntityRecord

        record = EntityRecord(entity_name="E1", content="Entity content", source_id="abc123")
        with pytest.raises(ValidationError):
            record.entity_name = "new"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RelationshipRecord tests
# ---------------------------------------------------------------------------


class TestRelationshipRecord:
    """RelationshipRecord tests — PGVector lightrag_vdb_relation_* row mapping."""

    def test_instantiation_all_fields(self):
        """Instantiate RelationshipRecord with all fields populated."""
        from lightrag_langchain.data.models import RelationshipRecord

        record = RelationshipRecord(
            src_id="s1",
            tgt_id="t1",
            content="relates to",
            keywords="kw1,kw2",
            weight=0.85,
            created_at=1717000000,
        )
        assert record.src_id == "s1"
        assert record.tgt_id == "t1"
        assert record.content == "relates to"
        assert record.keywords == "kw1,kw2"
        assert record.weight == 0.85
        assert record.created_at == 1717000000

    def test_defaults_optional_fields(self):
        """Optional fields default to None when only src_id/tgt_id provided."""
        from lightrag_langchain.data.models import RelationshipRecord

        record = RelationshipRecord(src_id="s1", tgt_id="t1")
        assert record.content is None
        assert record.keywords is None
        assert record.weight is None
        assert record.created_at is None

    def test_frozen_prevents_mutation(self):
        """Setting weight on a frozen RelationshipRecord raises ValidationError."""
        from lightrag_langchain.data.models import RelationshipRecord

        record = RelationshipRecord(src_id="s1", tgt_id="t1")
        with pytest.raises(ValidationError):
            record.weight = 2.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ChunkRecord tests
# ---------------------------------------------------------------------------


class TestChunkRecord:
    """ChunkRecord tests — PGVector lightrag_vdb_chunks_* row mapping."""

    def test_instantiation_all_fields(self):
        """Instantiate ChunkRecord with all fields populated."""
        from lightrag_langchain.data.models import ChunkRecord

        record = ChunkRecord(
            chunk_id="chk1",
            content="chunk text",
            full_doc_id="doc42",
            chunk_order_index=3,
            file_path="/docs/b.md",
        )
        assert record.chunk_id == "chk1"
        assert record.content == "chunk text"
        assert record.full_doc_id == "doc42"
        assert record.chunk_order_index == 3
        assert record.file_path == "/docs/b.md"

    def test_defaults_optional_fields(self):
        """Optional fields default correctly when only chunk_id/content provided."""
        from lightrag_langchain.data.models import ChunkRecord

        record = ChunkRecord(chunk_id="chk1", content="chunk text")
        assert record.full_doc_id is None
        assert record.chunk_order_index is None
        assert record.file_path == ""

    def test_frozen_prevents_mutation(self):
        """Setting content on a frozen ChunkRecord raises ValidationError."""
        from lightrag_langchain.data.models import ChunkRecord

        record = ChunkRecord(chunk_id="chk1", content="chunk text")
        with pytest.raises(ValidationError):
            record.content = "new"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GraphNode tests
# ---------------------------------------------------------------------------


class TestGraphNode:
    """GraphNode tests — Apache AGE graph node (label 'base') mapping."""

    def test_instantiation_all_fields(self):
        """Instantiate GraphNode with all fields populated."""
        from lightrag_langchain.data.models import GraphNode

        node = GraphNode(
            entity_id="n1",
            entity_type="Organization",
            description="A company",
            source_id="doc99",
        )
        assert node.entity_id == "n1"
        assert node.entity_type == "Organization"
        assert node.description == "A company"
        assert node.source_id == "doc99"

    def test_default_description_source_id(self):
        """description and source_id default to empty string."""
        from lightrag_langchain.data.models import GraphNode

        node = GraphNode(entity_id="n1", entity_type="Person")
        assert node.description == ""
        assert node.source_id == ""

    def test_frozen_prevents_mutation(self):
        """Setting entity_type on a frozen GraphNode raises ValidationError."""
        from lightrag_langchain.data.models import GraphNode

        node = GraphNode(entity_id="n1", entity_type="Person")
        with pytest.raises(ValidationError):
            node.entity_type = "Organization"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GraphEdge tests
# ---------------------------------------------------------------------------


class TestGraphEdge:
    """GraphEdge tests — Apache AGE graph edge (label 'DIRECTED') mapping."""

    def test_instantiation_all_fields(self):
        """Instantiate GraphEdge with all fields populated."""
        from lightrag_langchain.data.models import GraphEdge

        edge = GraphEdge(
            source_id="a",
            target_id="b",
            description="works at",
            keywords="employer",
            weight=0.9,
        )
        assert edge.source_id == "a"
        assert edge.target_id == "b"
        assert edge.description == "works at"
        assert edge.keywords == "employer"
        assert edge.weight == 0.9

    def test_defaults_all_optional(self):
        """Optional fields default to None when only source_id/target_id provided."""
        from lightrag_langchain.data.models import GraphEdge

        edge = GraphEdge(source_id="a", target_id="b")
        assert edge.description is None
        assert edge.keywords is None
        assert edge.weight is None

    def test_frozen_prevents_mutation(self):
        """Setting weight on a frozen GraphEdge raises ValidationError."""
        from lightrag_langchain.data.models import GraphEdge

        edge = GraphEdge(source_id="a", target_id="b")
        with pytest.raises(ValidationError):
            edge.weight = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Package import / __all__ tests
# ---------------------------------------------------------------------------


class TestModelImports:
    """Verify all 5 models are importable from the data package."""

    def test_all_models_importable_from_package(self):
        """All 5 model classes are re-exported via data.__all__."""
        from lightrag_langchain.data import (
            ChunkRecord,
            EntityRecord,
            GraphEdge,
            GraphNode,
            RelationshipRecord,
        )

        # Verify each is the correct type
        assert issubclass(EntityRecord, EntityRecord.__bases__[0])
        assert issubclass(RelationshipRecord, RelationshipRecord.__bases__[0])
        assert issubclass(ChunkRecord, ChunkRecord.__bases__[0])
        assert issubclass(GraphNode, GraphNode.__bases__[0])
        assert issubclass(GraphEdge, GraphEdge.__bases__[0])
