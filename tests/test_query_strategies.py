"""Unit tests for QueryResult model, GraphTriple model, and all 6 query strategies.

Tests cover instantiation, default values, frozen immutability, and
required-field validation for QueryResult and GraphTriple.  Strategy
tests use mock store objects to verify retrieval and merge behavior
for all 6 LightRAG query modes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)
from lightrag_langchain.query.results import GraphTriple, QueryResult


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------


def _make_entity(
    name: str = "test-entity",
    content: str = "test content",
) -> EntityRecord:
    """Create a minimal EntityRecord for use in strategy tests."""
    return EntityRecord(
        entity_name=name,
        content=content,
        source_id=f"src-{name}",
        file_path="test/file.txt",
    )


def _make_relation(
    src: str = "a",
    tgt: str = "b",
    content: str = "test relation",
) -> RelationshipRecord:
    """Create a minimal RelationshipRecord for use in strategy tests."""
    return RelationshipRecord(
        src_id=src,
        tgt_id=tgt,
        content=content,
    )


def _make_chunk(
    chunk_id: str = "c1",
    content: str = "chunk text",
) -> ChunkRecord:
    """Create a minimal ChunkRecord for use in strategy tests."""
    return ChunkRecord(
        chunk_id=chunk_id,
        content=content,
        full_doc_id="doc-1",
    )


def _make_graph_node(entity_id: str = "e1") -> GraphNode:
    """Create a minimal GraphNode for use in strategy tests."""
    return GraphNode(
        entity_id=entity_id,
        entity_type="Person",
        description="A test entity",
        source_id=f"src-{entity_id}",
    )


def _make_graph_edge(src: str = "a", tgt: str = "b") -> GraphEdge:
    """Create a minimal GraphEdge for use in strategy tests."""
    return GraphEdge(
        source_id=src,
        target_id=tgt,
        description="test edge",
        keywords="test,example",
        weight=1.0,
    )


# ---------------------------------------------------------------------------
# QueryResult model tests (from Plan 01)
# ---------------------------------------------------------------------------


class TestQueryResultModel:
    """QueryResult model tests — single-union-type frozen Pydantic model (D-01, D-02)."""

    def test_empty_construction(self):
        """QueryResult() constructs with all 4 fields as empty lists."""
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
        result = QueryResult()
        with pytest.raises(ValidationError):
            result.entities = []  # type: ignore[misc]

    def test_fields_populated(self):
        """Construct QueryResult with 1 fake entity, relation, and chunk — verify counts."""
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
# GraphTriple model tests (from Plan 01)
# ---------------------------------------------------------------------------


class TestGraphTripleModel:
    """GraphTriple model tests — (src_entity, relation, tgt_entity) frozen Pydantic model (D-04)."""

    def test_required_fields(self):
        """Constructing GraphTriple without any field raises ValidationError."""
        with pytest.raises(ValidationError):
            GraphTriple()  # type: ignore[call-arg]

    def test_full_construction(self):
        """Construct GraphTriple with real GraphNode + GraphEdge + GraphNode and verify attrs."""
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
        src = GraphNode(entity_id="n1", entity_type="Person")
        edge = GraphEdge(source_id="n1", target_id="n2")
        tgt = GraphNode(entity_id="n2", entity_type="Organization")
        triple = GraphTriple(src_entity=src, relation=edge, tgt_entity=tgt)

        with pytest.raises(ValidationError):
            triple.src_entity = GraphNode(entity_id="x", entity_type="Thing")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Naive strategy tests (QUERY-01)
# ---------------------------------------------------------------------------


class TestNaiveStrategy:
    """Naive mode — chunk vector search (QUERY-01)."""

    @pytest.mark.asyncio
    async def test_naive_returns_chunks(self):
        """naive_strategy returns QueryResult.chunks populated from search_chunks."""
        from lightrag_langchain.query.strategies import naive_strategy

        mock_store = AsyncMock()
        mock_store.search_chunks = AsyncMock(
            return_value=[_make_chunk("c1", "chunk text")]
        )

        with patch("lightrag_langchain.config.settings") as mock_settings:
            mock_settings.query_params.chunk_top_k = 20
            mock_settings.query_params.kg_chunk_pick_method = "VECTOR"

            result = await naive_strategy(
                [0.1] * 10,
                vector_store=mock_store,
                chunk_top_k=20,
            )

        assert len(result.chunks) == 1
        assert result.chunks[0].chunk_id == "c1"
        assert result.chunks[0].content == "chunk text"
        assert len(result.entities) == 0
        assert len(result.relations) == 0
        assert len(result.graph_triples) == 0
        mock_store.search_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_naive_weight_fallback(self):
        """naive_strategy with KG_CHUNK_PICK_METHOD=WEIGHT still calls search_chunks."""
        from lightrag_langchain.query.strategies import naive_strategy

        mock_store = AsyncMock()
        mock_store.search_chunks = AsyncMock(
            return_value=[_make_chunk("c2", "weight test")]
        )

        with patch("lightrag_langchain.config.settings") as mock_settings:
            mock_settings.query_params.chunk_top_k = 20
            mock_settings.query_params.kg_chunk_pick_method = "WEIGHT"

            result = await naive_strategy(
                [0.2] * 10,
                vector_store=mock_store,
                chunk_top_k=20,
            )

        mock_store.search_chunks.assert_called_once()
        assert len(result.chunks) == 1
        assert result.chunks[0].chunk_id == "c2"


# ---------------------------------------------------------------------------
# Local strategy tests (QUERY-02)
# ---------------------------------------------------------------------------


class TestLocalStrategy:
    """Local mode — entity vector search + graph expansion (QUERY-02)."""

    @pytest.mark.asyncio
    async def test_local_returns_entities_and_triples(self):
        """local_strategy returns entities and graph_triples, empty relations/chunks."""
        from lightrag_langchain.query.strategies import local_strategy

        entity = _make_entity("e1", "entity content")
        node = _make_graph_node("e1")
        edge = _make_graph_edge("e1", "e2")
        neighbor_node = _make_graph_node("e2")

        mock_vector = AsyncMock()
        mock_vector.search_entities = AsyncMock(return_value=[entity])

        mock_graph = AsyncMock()
        mock_graph.get_nodes_batch = AsyncMock(return_value={"e1": node})
        mock_graph.get_node_edges = AsyncMock(return_value=[("e1", "e2")])
        mock_graph.get_edges_batch = AsyncMock(return_value={("e1", "e2"): edge})

        with patch("lightrag_langchain.config.settings") as mock_settings:
            mock_settings.query_params.top_k = 40

            # First get_nodes_batch returns the query entity
            # Second get_nodes_batch (neighbor lookup) returns the neighbor
            async def get_nodes_batch_side_effect(ids):
                result = {}
                for eid in ids:
                    if eid == "e1":
                        result[eid] = node
                    elif eid == "e2":
                        result[eid] = neighbor_node
                return result

            mock_graph.get_nodes_batch = AsyncMock(
                side_effect=get_nodes_batch_side_effect
            )

            result = await local_strategy(
                [0.3] * 10,
                vector_store=mock_vector,
                graph_store=mock_graph,
                top_k=40,
            )

        assert len(result.entities) == 1
        assert result.entities[0].entity_name == "e1"
        assert len(result.relations) == 0
        assert len(result.chunks) == 0
        assert len(result.graph_triples) == 1
        triple = result.graph_triples[0]
        assert triple.src_entity.entity_id == "e1"
        assert triple.tgt_entity.entity_id == "e2"
        assert triple.relation.description == "test edge"


# ---------------------------------------------------------------------------
# Global strategy tests (QUERY-03)
# ---------------------------------------------------------------------------


class TestGlobalStrategy:
    """Global mode — relation vector search + entity lookup (QUERY-03)."""

    @pytest.mark.asyncio
    async def test_global_returns_relations_and_triples(self):
        """global_strategy returns relations and graph_triples from edges."""
        from lightrag_langchain.query.strategies import global_strategy

        relation = _make_relation("n1", "n2", "works at")
        entity_node = _make_graph_node("n1")
        target_node = GraphNode(
            entity_id="n2", entity_type="Organization", description="Acme"
        )
        edge = _make_graph_edge("n1", "n2")

        mock_vector = AsyncMock()
        mock_vector.search_relationships = AsyncMock(return_value=[relation])

        mock_graph = AsyncMock()
        mock_graph.get_edges_batch = AsyncMock(
            return_value={("n1", "n2"): edge}
        )
        mock_graph.get_nodes_batch = AsyncMock(
            return_value={"n1": entity_node, "n2": target_node}
        )

        with patch("lightrag_langchain.config.settings") as mock_settings:
            mock_settings.query_params.top_k = 40

            result = await global_strategy(
                [0.4] * 10,
                vector_store=mock_vector,
                graph_store=mock_graph,
                top_k=40,
            )

        assert len(result.relations) == 1
        assert result.relations[0].src_id == "n1"
        assert result.relations[0].tgt_id == "n2"
        assert len(result.graph_triples) == 1
        triple = result.graph_triples[0]
        assert triple.src_entity.entity_id == "n1"
        assert triple.tgt_entity.entity_id == "n2"
        assert triple.relation.description == "test edge"
        assert len(result.entities) == 0
        assert len(result.chunks) == 0


# ---------------------------------------------------------------------------
# Hybrid strategy tests (QUERY-04)
# ---------------------------------------------------------------------------


class TestHybridStrategy:
    """Hybrid mode — parallel local+global + round-robin merge (QUERY-04)."""

    @pytest.mark.asyncio
    async def test_hybrid_merges_local_and_global(self):
        """hybrid_strategy round-robin merges entities from local and relations from global."""
        from lightrag_langchain.query.strategies import hybrid_strategy

        # Local entities
        entity_l1 = _make_entity("e-local", "local entity")
        node_l1 = _make_graph_node("e-local")
        edge_l1 = _make_graph_edge("e-local", "e2")
        node_n = _make_graph_node("e2")

        # Global relations
        relation_g = _make_relation("n1", "n2", "global relation")
        edge_g = _make_graph_edge("n1", "n2")
        node_g1 = _make_graph_node("n1")
        node_g2 = GraphNode(
            entity_id="n2", entity_type="ORG", description="Target"
        )

        mock_vector = AsyncMock()
        mock_vector.search_entities = AsyncMock(return_value=[entity_l1])
        mock_vector.search_relationships = AsyncMock(return_value=[relation_g])

        side_effect_nodes = {
            "e-local": node_l1,
            "e2": node_n,
            "n1": node_g1,
            "n2": node_g2,
        }

        mock_graph = AsyncMock()
        mock_graph.get_nodes_batch = AsyncMock(
            side_effect=lambda ids: {eid: side_effect_nodes[eid] for eid in ids if eid in side_effect_nodes}
        )
        mock_graph.get_node_edges = AsyncMock(return_value=[("e-local", "e2")])
        mock_graph.get_edges_batch = AsyncMock(
            return_value={
                ("e-local", "e2"): edge_l1,
                ("n1", "n2"): edge_g,
            }
        )

        with patch("lightrag_langchain.config.settings") as mock_settings:
            mock_settings.query_params.top_k = 40

            result = await hybrid_strategy(
                [0.5] * 10,
                vector_store=mock_vector,
                graph_store=mock_graph,
                top_k=40,
            )

        # Entities: local entity merged in
        assert len(result.entities) == 1
        assert result.entities[0].entity_name == "e-local"

        # Relations: global relation merged in
        assert len(result.relations) == 1
        assert result.relations[0].src_id == "n1"

        # Graph triples: both local and global merged
        assert len(result.graph_triples) == 2
        triple_ids = {
            (t.src_entity.entity_id, t.tgt_entity.entity_id)
            for t in result.graph_triples
        }
        assert ("e-local", "e2") in triple_ids
        assert ("n1", "n2") in triple_ids

        assert len(result.chunks) == 0


# ---------------------------------------------------------------------------
# Mix strategy tests (QUERY-05)
# ---------------------------------------------------------------------------


class TestMixStrategy:
    """Mix mode — hybrid + chunk search + chunk merge (QUERY-05)."""

    @pytest.mark.asyncio
    async def test_mix_includes_chunks(self):
        """mix_strategy returns QueryResult with chunks populated."""
        from lightrag_langchain.query.strategies import mix_strategy

        # Hybrid data
        entity_l = _make_entity("e-mix", "mix entity")
        node_l = _make_graph_node("e-mix")
        edge_l = _make_graph_edge("e-mix", "e2")
        node_n = _make_graph_node("e2")
        relation_g = _make_relation("n1", "n2", "rel")
        edge_g = _make_graph_edge("n1", "n2")
        node_g1 = _make_graph_node("n1")
        node_g2 = GraphNode(
            entity_id="n2", entity_type="ORG", description="Tgt"
        )

        # Vector chunks from chunk search
        vec_chunk = _make_chunk("vc1", "vector chunk text")

        mock_vector = AsyncMock()
        mock_vector.search_entities = AsyncMock(return_value=[entity_l])
        mock_vector.search_relationships = AsyncMock(return_value=[relation_g])
        mock_vector.search_chunks = AsyncMock(return_value=[vec_chunk])

        side_effect_nodes = {
            "e-mix": node_l,
            "e2": node_n,
            "n1": node_g1,
            "n2": node_g2,
        }

        mock_graph = AsyncMock()
        mock_graph.get_nodes_batch = AsyncMock(
            side_effect=lambda ids: {eid: side_effect_nodes[eid] for eid in ids if eid in side_effect_nodes}
        )
        mock_graph.get_node_edges = AsyncMock(return_value=[("e-mix", "e2")])
        mock_graph.get_edges_batch = AsyncMock(
            return_value={
                ("e-mix", "e2"): edge_l,
                ("n1", "n2"): edge_g,
            }
        )

        with patch("lightrag_langchain.config.settings") as mock_settings:
            mock_settings.query_params.top_k = 40
            mock_settings.query_params.chunk_top_k = 20

            result = await mix_strategy(
                [0.6] * 10,
                vector_store=mock_vector,
                graph_store=mock_graph,
                top_k=40,
                chunk_top_k=20,
            )

        # Entities and relations from hybrid
        assert len(result.entities) == 1
        assert len(result.relations) == 1

        # Chunks: vector chunk + entity pseudo-chunk
        assert len(result.chunks) == 2
        chunk_ids = {c.chunk_id for c in result.chunks}
        assert "vc1" in chunk_ids  # vector chunk
        assert "src-e-mix" in chunk_ids  # entity pseudo-chunk

        # Graph triples
        assert len(result.graph_triples) == 2

        mock_vector.search_chunks.assert_called_once()


# ---------------------------------------------------------------------------
# Bypass strategy tests (QUERY-06)
# ---------------------------------------------------------------------------


class TestBypassStrategy:
    """Bypass mode — no retrieval, empty QueryResult (QUERY-06)."""

    @pytest.mark.asyncio
    async def test_bypass_returns_empty(self):
        """bypass_strategy returns QueryResult with all 4 fields as empty lists."""
        from lightrag_langchain.query.strategies import bypass_strategy

        result = await bypass_strategy()

        assert isinstance(result, QueryResult)
        assert result.entities == []
        assert result.relations == []
        assert result.chunks == []
        assert result.graph_triples == []

    def test_bypass_is_async(self):
        """bypass_strategy is an async function."""
        import inspect

        from lightrag_langchain.query.strategies import bypass_strategy

        assert inspect.iscoroutinefunction(bypass_strategy)
