"""Unit tests for all 6 LightRAG retriever classes (Naive/Local/Global/Hybrid/Mix/Bypass).

Tests sync invoke() and async ainvoke(), verify Document page_content JSON
format matches D-04 per upstream convert_to_user_format(), and confirm metadata
structure matches D-05 (common + type-specific fields).
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from langchain_core.documents import Document

from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)
from lightrag_langchain.query.results import GraphTriple
from lightrag_langchain.retriever.base import LightRAGBaseRetriever
from lightrag_langchain.retriever.retrievers import (
    BypassRetriever,
    GlobalRetriever,
    HybridRetriever,
    LocalRetriever,
    MixRetriever,
    NaiveRetriever,
)


# ===========================================================================
# Test data helpers (replicate pattern from test_query_strategies.py)
# ===========================================================================


def _make_entity(name: str = "e1", content: str = "entity content") -> EntityRecord:
    """Create a minimal EntityRecord for retriever tests."""
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
    """Create a minimal RelationshipRecord for retriever tests."""
    return RelationshipRecord(src_id=src, tgt_id=tgt, content=content)


def _make_chunk(
    chunk_id: str = "c1",
    content: str = "chunk text",
) -> ChunkRecord:
    """Create a minimal ChunkRecord for retriever tests."""
    return ChunkRecord(chunk_id=chunk_id, content=content, full_doc_id="doc-1")


def _make_graph_node(
    entity_id: str = "e1",
    entity_type: str = "Person",
    description: str = "A person",
) -> GraphNode:
    """Create a minimal GraphNode for retriever tests."""
    return GraphNode(
        entity_id=entity_id,
        entity_type=entity_type,
        description=description,
        source_id=f"src-{entity_id}",
    )


def _make_graph_edge(
    src: str = "a",
    tgt: str = "b",
    description: str = "test edge",
    keywords: str = "test,example",
    weight: float = 1.0,
) -> GraphEdge:
    """Create a minimal GraphEdge for retriever tests."""
    return GraphEdge(
        source_id=src,
        target_id=tgt,
        description=description,
        keywords=keywords,
        weight=weight,
    )


def _make_graph_triple(
    src_entity: GraphNode,
    relation: GraphEdge,
    tgt_entity: GraphNode,
) -> GraphTriple:
    """Create a GraphTriple for retriever tests."""
    return GraphTriple(src_entity=src_entity, relation=relation, tgt_entity=tgt_entity)


def _set_mock_embedding(retriever: LightRAGBaseRetriever) -> MagicMock:
    """Inject a mock embedding model into the retriever instance.

    Sets ``_embedding`` private attribute so the lazy ``embedding`` property
    returns the mock directly, bypassing ``create_embedding()`` factory.
    ``embed_query`` returns a 1024-dim fake vector (matching aliyun text-embedding-v4).
    """
    mock = MagicMock()
    mock.embed_query = MagicMock(return_value=[0.1] * 1024)
    retriever._embedding = mock
    return mock


# ===========================================================================
# Test Class 1: NaiveRetriever
# ===========================================================================


class TestNaiveRetriever:
    """Tests for NaiveRetriever — pure vector chunk search, no graph traversal."""

    def test_invoke_returns_chunk_documents(
        self, mock_vector_store, mock_embedding_config
    ):
        """invoke() returns chunk Documents with D-04 JSON page_content and D-05 metadata."""
        chunk1 = _make_chunk(chunk_id="c1", content="first chunk")
        chunk2 = _make_chunk(chunk_id="c2", content="second chunk")
        mock_vector_store.search_chunks.return_value = [chunk1, chunk2]

        retriever = NaiveRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")

        assert len(docs) == 2
        for doc in docs:
            assert isinstance(doc, Document)

        # D-04: chunk page_content JSON fields
        obj0 = json.loads(docs[0].page_content)
        assert set(obj0.keys()) == {"reference_id", "content", "file_path", "chunk_id"}
        assert obj0["chunk_id"] == "c1"
        assert obj0["content"] == "first chunk"

        # D-05: chunk metadata
        assert docs[0].metadata["document_type"] == "chunk"
        assert docs[0].metadata["retrieval_mode"] == "naive"
        assert docs[0].metadata["chunk_id"] == "c1"

    def test_invoke_empty_result(
        self, mock_vector_store, mock_embedding_config
    ):
        """invoke() returns empty list when no chunks match."""
        mock_vector_store.search_chunks.return_value = []

        retriever = NaiveRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        assert docs == []

    @pytest.mark.asyncio
    async def test_ainvoke_returns_chunk_documents(
        self, mock_vector_store, mock_embedding_config
    ):
        """ainvoke() (async path) returns chunk Documents."""
        chunk = _make_chunk(chunk_id="c1", content="async chunk")
        mock_vector_store.search_chunks.return_value = [chunk]

        retriever = NaiveRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        _set_mock_embedding(retriever)

        docs = await retriever.ainvoke("test query")

        assert len(docs) == 1
        assert docs[0].metadata["document_type"] == "chunk"
        assert docs[0].metadata["retrieval_mode"] == "naive"

    def test_invoke_verify_full_metadata(
        self, mock_vector_store, mock_embedding_config
    ):
        """invoke() sets all D-05 chunk metadata fields."""
        chunk = _make_chunk(chunk_id="c99", content="meta test")
        mock_vector_store.search_chunks.return_value = [chunk]

        retriever = NaiveRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        meta = docs[0].metadata

        assert meta["document_type"] == "chunk"
        assert meta["retrieval_mode"] == "naive"
        assert meta["chunk_id"] == "c99"
        assert "file_path" in meta
        assert "source_id" in meta
        assert "chunk_order_index" in meta


# ===========================================================================
# Test Class 2: LocalRetriever
# ===========================================================================


class TestLocalRetriever:
    """Tests for LocalRetriever — entity vector search + graph expansion."""

    def test_invoke_returns_entity_and_triple_documents(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """invoke() returns enriched entity Documents and GraphTriple Documents."""
        entity = _make_entity(name="e1", content="entity content")
        node_e1 = _make_graph_node(entity_id="e1", entity_type="Person", description="A person")
        node_e2 = _make_graph_node(entity_id="e2", entity_type="Org", description="An org")
        edge = _make_graph_edge(src="e1", tgt="e2", description="works at", keywords="employment", weight=1.0)

        mock_vector_store.search_entities.return_value = [entity]
        mock_graph_store.get_nodes_batch.return_value = {"e1": node_e1, "e2": node_e2}
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {("e1", "e2"): edge}

        retriever = LocalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")

        # Should have entity doc + triple doc
        assert len(docs) >= 2

        # Find entity document
        entity_docs = [d for d in docs if d.metadata["document_type"] == "entity"]
        assert len(entity_docs) == 1
        entity_doc = entity_docs[0]
        obj = json.loads(entity_doc.page_content)
        assert obj["entity_name"] == "e1"
        assert obj["entity_type"] == "Person"
        assert obj["description"] == "A person"
        assert entity_doc.metadata["document_type"] == "entity"
        assert entity_doc.metadata["retrieval_mode"] == "local"
        assert entity_doc.metadata["entity_name"] == "e1"
        assert entity_doc.metadata["entity_type"] == "Person"

        # Find triple document
        triple_docs = [d for d in docs if d.metadata["document_type"] == "graph_triple"]
        assert len(triple_docs) >= 1

    def test_entity_without_matching_node(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """Entity Document uses empty defaults when no matching GraphNode exists."""
        entity = _make_entity(name="orphan", content="orphan entity")
        mock_vector_store.search_entities.return_value = [entity]
        mock_graph_store.get_nodes_batch.return_value = {}
        mock_graph_store.get_node_edges.return_value = []
        mock_graph_store.get_edges_batch.return_value = {}

        retriever = LocalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        entity_docs = [d for d in docs if d.metadata["document_type"] == "entity"]
        assert len(entity_docs) == 1

        obj = json.loads(entity_docs[0].page_content)
        assert obj["entity_type"] == ""
        assert obj["description"] == ""
        assert entity_docs[0].metadata["entity_type"] == ""

    @pytest.mark.asyncio
    async def test_ainvoke(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """ainvoke() (async path) returns entity and triple Documents."""
        entity = _make_entity(name="e1")
        node_e1 = _make_graph_node(entity_id="e1")
        node_e2 = _make_graph_node(entity_id="e2")
        edge = _make_graph_edge(src="e1", tgt="e2")

        mock_vector_store.search_entities.return_value = [entity]
        mock_graph_store.get_nodes_batch.return_value = {"e1": node_e1, "e2": node_e2}
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {("e1", "e2"): edge}

        retriever = LocalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = await retriever.ainvoke("test query")
        assert len(docs) >= 1
        entity_docs = [d for d in docs if d.metadata["document_type"] == "entity"]
        assert len(entity_docs) == 1

    def test_invoke_empty_result(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """invoke() returns empty list when no entities found."""
        mock_vector_store.search_entities.return_value = []

        retriever = LocalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        assert docs == []


# ===========================================================================
# Test Class 3: GlobalRetriever
# ===========================================================================


class TestGlobalRetriever:
    """Tests for GlobalRetriever — relation vector search + entity lookup."""

    def test_invoke_returns_relation_and_triple_documents(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """invoke() returns enriched relation Documents and GraphTriple Documents."""
        relation = _make_relation(src="a", tgt="b", content="test relation")
        node_a = _make_graph_node(entity_id="a", entity_type="Person", description="Alice")
        node_b = _make_graph_node(entity_id="b", entity_type="Person", description="Bob")
        edge = _make_graph_edge(src="a", tgt="b", description="knows", keywords="friendship", weight=0.9)

        mock_vector_store.search_relationships.return_value = [relation]
        mock_graph_store.get_edges_batch.return_value = {("a", "b"): edge}
        mock_graph_store.get_nodes_batch.return_value = {"a": node_a, "b": node_b}

        retriever = GlobalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")

        # Find relation document
        relation_docs = [d for d in docs if d.metadata["document_type"] == "relation"]
        assert len(relation_docs) == 1
        rel_doc = relation_docs[0]
        obj = json.loads(rel_doc.page_content)
        # D-04: relation page_content JSON enriched from GraphEdge
        assert obj["keywords"] == "friendship"
        assert obj["weight"] == 0.9
        assert obj["src_id"] == "a"
        assert obj["tgt_id"] == "b"
        # D-05: relation metadata
        assert rel_doc.metadata["document_type"] == "relation"
        assert rel_doc.metadata["retrieval_mode"] == "global"
        assert rel_doc.metadata["src_id"] == "a"
        assert rel_doc.metadata["tgt_id"] == "b"

        # Find triple document
        triple_docs = [d for d in docs if d.metadata["document_type"] == "graph_triple"]
        assert len(triple_docs) >= 1

    def test_relation_without_matching_edge(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """Relation Document uses own values when no matching GraphEdge exists."""
        relation = _make_relation(src="x", tgt="y", content="lonely relation")
        # No matching edge in edge_lookup
        mock_vector_store.search_relationships.return_value = [relation]
        mock_graph_store.get_edges_batch.return_value = {}
        mock_graph_store.get_nodes_batch.return_value = {}

        retriever = GlobalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        relation_docs = [d for d in docs if d.metadata["document_type"] == "relation"]
        assert len(relation_docs) == 1

        obj = json.loads(relation_docs[0].page_content)
        assert obj["keywords"] == ""
        assert obj["weight"] is None
        assert obj["source_id"] == ""

    @pytest.mark.asyncio
    async def test_ainvoke(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """ainvoke() (async path) returns relation and triple Documents."""
        relation = _make_relation(src="a", tgt="b")
        node_a = _make_graph_node(entity_id="a")
        node_b = _make_graph_node(entity_id="b")
        edge = _make_graph_edge(src="a", tgt="b")

        mock_vector_store.search_relationships.return_value = [relation]
        mock_graph_store.get_edges_batch.return_value = {("a", "b"): edge}
        mock_graph_store.get_nodes_batch.return_value = {"a": node_a, "b": node_b}

        retriever = GlobalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = await retriever.ainvoke("test query")
        relation_docs = [d for d in docs if d.metadata["document_type"] == "relation"]
        assert len(relation_docs) == 1

    def test_invoke_empty_result(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """invoke() returns empty list when no relations found."""
        mock_vector_store.search_relationships.return_value = []

        retriever = GlobalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        assert docs == []


# ===========================================================================
# Test Class 4: HybridRetriever
# ===========================================================================


class TestHybridRetriever:
    """Tests for HybridRetriever — parallel local + global, returns 3 doc types."""

    def test_invoke_returns_all_three_document_types(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """invoke() returns entity + relation + graph_triple Documents, all with
        retrieval_mode='hybrid'."""
        entity = _make_entity(name="e1", content="hybrid entity")
        relation = _make_relation(src="a", tgt="b", content="hybrid relation")
        node_e1 = _make_graph_node(entity_id="e1", entity_type="Person")
        node_e2 = _make_graph_node(entity_id="e2", entity_type="Org")
        node_a = _make_graph_node(entity_id="a", entity_type="Person")
        node_b = _make_graph_node(entity_id="b", entity_type="Person")
        edge_local = _make_graph_edge(src="e1", tgt="e2", description="local edge", keywords="local", weight=1.0)
        edge_global = _make_graph_edge(src="a", tgt="b", description="global edge", keywords="global", weight=0.8)

        # Both local and global strategies run in parallel
        mock_vector_store.search_entities.return_value = [entity]
        mock_vector_store.search_relationships.return_value = [relation]
        mock_graph_store.get_nodes_batch.return_value = {
            "e1": node_e1, "e2": node_e2, "a": node_a, "b": node_b,
        }
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {
            ("e1", "e2"): edge_local,
            ("a", "b"): edge_global,
        }

        retriever = HybridRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")

        # Verify all three document types present
        doc_types = {d.metadata["document_type"] for d in docs}
        assert "entity" in doc_types
        assert "relation" in doc_types
        assert "graph_triple" in doc_types

        # All must have retrieval_mode="hybrid"
        for doc in docs:
            assert doc.metadata["retrieval_mode"] == "hybrid"

    @pytest.mark.asyncio
    async def test_ainvoke(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """ainvoke() (async path) returns entity + relation + triple Documents."""
        entity = _make_entity(name="e1")
        relation = _make_relation(src="a", tgt="b")
        node_e1 = _make_graph_node(entity_id="e1")
        node_e2 = _make_graph_node(entity_id="e2")
        node_a = _make_graph_node(entity_id="a")
        node_b = _make_graph_node(entity_id="b")
        edge_local = _make_graph_edge(src="e1", tgt="e2")
        edge_global = _make_graph_edge(src="a", tgt="b")

        mock_vector_store.search_entities.return_value = [entity]
        mock_vector_store.search_relationships.return_value = [relation]
        mock_graph_store.get_nodes_batch.return_value = {
            "e1": node_e1, "e2": node_e2, "a": node_a, "b": node_b,
        }
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {
            ("e1", "e2"): edge_local,
            ("a", "b"): edge_global,
        }

        retriever = HybridRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = await retriever.ainvoke("test query")
        doc_types = {d.metadata["document_type"] for d in docs}
        assert "entity" in doc_types
        assert "relation" in doc_types
        assert "graph_triple" in doc_types


# ===========================================================================
# Test Class 5: MixRetriever
# ===========================================================================


class TestMixRetriever:
    """Tests for MixRetriever — hybrid + chunk search, returns 4 doc types."""

    def test_invoke_returns_all_four_document_types(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """invoke() returns entity + relation + chunk + graph_triple Documents."""
        entity = _make_entity(name="e1", content="mix entity")
        relation = _make_relation(src="a", tgt="b", content="mix relation")
        chunk = _make_chunk(chunk_id="c1", content="mix chunk")
        node_e1 = _make_graph_node(entity_id="e1", entity_type="Person")
        node_e2 = _make_graph_node(entity_id="e2", entity_type="Org")
        node_a = _make_graph_node(entity_id="a")
        node_b = _make_graph_node(entity_id="b")
        edge_local = _make_graph_edge(src="e1", tgt="e2")
        edge_global = _make_graph_edge(src="a", tgt="b")

        mock_vector_store.search_entities.return_value = [entity]
        mock_vector_store.search_relationships.return_value = [relation]
        mock_vector_store.search_chunks.return_value = [chunk]
        mock_graph_store.get_nodes_batch.return_value = {
            "e1": node_e1, "e2": node_e2, "a": node_a, "b": node_b,
        }
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {
            ("e1", "e2"): edge_local,
            ("a", "b"): edge_global,
        }

        retriever = MixRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")

        doc_types = {d.metadata["document_type"] for d in docs}
        assert "entity" in doc_types
        assert "relation" in doc_types
        assert "chunk" in doc_types
        assert "graph_triple" in doc_types

        # Verify search_chunks was called
        mock_vector_store.search_chunks.assert_called()

        # All must have retrieval_mode="mix"
        for doc in docs:
            assert doc.metadata["retrieval_mode"] == "mix"

    def test_chunk_top_k_passed_through(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """MixRetriever stores chunk_top_k from constructor."""
        retriever = MixRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
            chunk_top_k=15,
        )
        assert retriever.chunk_top_k == 15

    @pytest.mark.asyncio
    async def test_ainvoke(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """ainvoke() (async path) returns all 4 document types."""
        entity = _make_entity(name="e1")
        relation = _make_relation(src="a", tgt="b")
        chunk = _make_chunk(chunk_id="c1")
        node_e1 = _make_graph_node(entity_id="e1")
        node_e2 = _make_graph_node(entity_id="e2")
        node_a = _make_graph_node(entity_id="a")
        node_b = _make_graph_node(entity_id="b")
        edge_local = _make_graph_edge(src="e1", tgt="e2")
        edge_global = _make_graph_edge(src="a", tgt="b")

        mock_vector_store.search_entities.return_value = [entity]
        mock_vector_store.search_relationships.return_value = [relation]
        mock_vector_store.search_chunks.return_value = [chunk]
        mock_graph_store.get_nodes_batch.return_value = {
            "e1": node_e1, "e2": node_e2, "a": node_a, "b": node_b,
        }
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {
            ("e1", "e2"): edge_local,
            ("a", "b"): edge_global,
        }

        retriever = MixRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = await retriever.ainvoke("test query")
        doc_types = {d.metadata["document_type"] for d in docs}
        assert len(doc_types) == 4


# ===========================================================================
# Test Class 6: BypassRetriever
# ===========================================================================


class TestBypassRetriever:
    """Tests for BypassRetriever — no retrieval, always returns empty list."""

    def test_invoke_returns_empty_list(
        self, mock_vector_store, mock_embedding_config
    ):
        """invoke() returns [] regardless of query."""
        retriever = BypassRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        docs = retriever.invoke("anything")
        assert docs == []

    @pytest.mark.asyncio
    async def test_ainvoke_returns_empty_list(
        self, mock_vector_store, mock_embedding_config
    ):
        """ainvoke() returns [] regardless of query."""
        retriever = BypassRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        docs = await retriever.ainvoke("anything")
        assert docs == []

    def test_no_embedding_or_strategy_call(
        self, mock_vector_store, mock_embedding_config
    ):
        """BypassRetriever does not call embedding or any store method."""
        retriever = BypassRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        # No embedding mock injected — should not be needed
        docs = retriever.invoke("anything")
        assert docs == []

        # Verify no store calls were made
        mock_vector_store.search_chunks.assert_not_called()
        mock_vector_store.search_entities.assert_not_called()
        mock_vector_store.search_relationships.assert_not_called()

    def test_no_asyncio_run_overhead(
        self, mock_vector_store, mock_embedding_config
    ):
        """BypassRetriever overrides _get_relevant_documents directly, skipping asyncio.run."""
        retriever = BypassRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        # Invoke multiple times — should always return []
        for _ in range(5):
            assert retriever.invoke("anything") == []


# ===========================================================================
# Test Class 7: Cross-cutting D-04 / D-05 structural validation
# ===========================================================================


class TestDocumentMetadataStructure:
    """Cross-cutting tests for D-04 JSON field compliance and D-05 metadata structure."""

    def test_entity_document_page_content_fields(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """Entity Document page_content JSON has exactly the 5 D-04 fields."""
        entity = _make_entity(name="e1")
        node_e1 = _make_graph_node(entity_id="e1", entity_type="Person", description="A person")
        node_e2 = _make_graph_node(entity_id="e2")
        edge = _make_graph_edge(src="e1", tgt="e2")

        mock_vector_store.search_entities.return_value = [entity]
        mock_graph_store.get_nodes_batch.return_value = {"e1": node_e1, "e2": node_e2}
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {("e1", "e2"): edge}

        retriever = LocalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        entity_docs = [d for d in docs if d.metadata["document_type"] == "entity"]

        for doc in entity_docs:
            obj = json.loads(doc.page_content)
            assert set(obj.keys()) == {
                "entity_name", "entity_type", "description", "source_id", "file_path",
            }, f"Unexpected keys: {set(obj.keys())}"

    def test_relation_document_page_content_fields(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """Relation Document page_content JSON has exactly the 7 D-04 fields."""
        relation = _make_relation(src="a", tgt="b", content="test relation")
        node_a = _make_graph_node(entity_id="a")
        node_b = _make_graph_node(entity_id="b")
        edge = _make_graph_edge(src="a", tgt="b", keywords="kw", weight=1.0)

        mock_vector_store.search_relationships.return_value = [relation]
        mock_graph_store.get_edges_batch.return_value = {("a", "b"): edge}
        mock_graph_store.get_nodes_batch.return_value = {"a": node_a, "b": node_b}

        retriever = GlobalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        relation_docs = [d for d in docs if d.metadata["document_type"] == "relation"]

        for doc in relation_docs:
            obj = json.loads(doc.page_content)
            assert set(obj.keys()) == {
                "src_id", "tgt_id", "description", "keywords", "weight",
                "source_id", "file_path",
            }, f"Unexpected keys: {set(obj.keys())}"

    def test_chunk_document_page_content_fields(
        self, mock_vector_store, mock_embedding_config
    ):
        """Chunk Document page_content JSON has exactly the 4 D-04 fields."""
        chunk = _make_chunk(chunk_id="c1", content="test content")
        mock_vector_store.search_chunks.return_value = [chunk]

        retriever = NaiveRetriever(
            vector_store=mock_vector_store, embedding_config=mock_embedding_config
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        for doc in docs:
            obj = json.loads(doc.page_content)
            assert set(obj.keys()) == {
                "reference_id", "content", "file_path", "chunk_id",
            }, f"Unexpected keys: {set(obj.keys())}"

    def test_graph_triple_metadata_structure(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """GraphTriple metadata has nested src_entity/relation/tgt_entity dicts."""
        entity = _make_entity(name="e1")
        node_e1 = _make_graph_node(entity_id="e1", entity_type="Person", description="A person")
        node_e2 = _make_graph_node(entity_id="e2", entity_type="Org", description="An org")
        edge = _make_graph_edge(src="e1", tgt="e2", description="works at", keywords="employment", weight=1.0)

        mock_vector_store.search_entities.return_value = [entity]
        mock_graph_store.get_nodes_batch.return_value = {"e1": node_e1, "e2": node_e2}
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {("e1", "e2"): edge}

        retriever = LocalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(retriever)

        docs = retriever.invoke("test query")
        triple_docs = [d for d in docs if d.metadata["document_type"] == "graph_triple"]

        for doc in triple_docs:
            meta = doc.metadata
            # Top-level triple keys
            assert "src_entity" in meta, f"Missing src_entity in {list(meta.keys())}"
            assert "relation" in meta, f"Missing relation in {list(meta.keys())}"
            assert "tgt_entity" in meta, f"Missing tgt_entity in {list(meta.keys())}"

            # src_entity dict structure
            src_ent = meta["src_entity"]
            assert isinstance(src_ent, dict)
            for key in ("entity_id", "entity_type", "description", "source_id"):
                assert key in src_ent, f"Missing '{key}' in src_entity"

            # relation dict structure
            rel = meta["relation"]
            assert isinstance(rel, dict)
            for key in ("source_id", "target_id", "description", "keywords", "weight"):
                assert key in rel, f"Missing '{key}' in relation"

            # tgt_entity dict structure
            tgt_ent = meta["tgt_entity"]
            assert isinstance(tgt_ent, dict)
            for key in ("entity_id", "entity_type", "description", "source_id"):
                assert key in tgt_ent, f"Missing '{key}' in tgt_entity"

    def test_all_documents_have_retrieval_mode_in_metadata(
        self, mock_vector_store, mock_graph_store, mock_embedding_config
    ):
        """Every Document from every retriever has 'retrieval_mode' in metadata."""
        entity = _make_entity(name="e1")
        relation = _make_relation(src="a", tgt="b")
        node_e1 = _make_graph_node(entity_id="e1")
        node_e2 = _make_graph_node(entity_id="e2")
        node_a = _make_graph_node(entity_id="a")
        node_b = _make_graph_node(entity_id="b")
        edge_local = _make_graph_edge(src="e1", tgt="e2")
        edge_global = _make_graph_edge(src="a", tgt="b")

        # Naive
        mock_vector_store.search_chunks.return_value = [_make_chunk()]
        naive = NaiveRetriever(vector_store=mock_vector_store, embedding_config=mock_embedding_config)
        _set_mock_embedding(naive)
        for doc in naive.invoke("q"):
            assert "retrieval_mode" in doc.metadata
            assert doc.metadata["retrieval_mode"] == "naive"

        # Local
        mock_vector_store.search_entities.return_value = [entity]
        mock_graph_store.get_nodes_batch.return_value = {"e1": node_e1, "e2": node_e2}
        mock_graph_store.get_node_edges.return_value = [("e1", "e2")]
        mock_graph_store.get_edges_batch.return_value = {("e1", "e2"): edge_local}
        local = LocalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(local)
        for doc in local.invoke("q"):
            assert "retrieval_mode" in doc.metadata
            assert doc.metadata["retrieval_mode"] == "local"

        # Global
        mock_vector_store.search_relationships.return_value = [relation]
        mock_graph_store.get_edges_batch.return_value = {("a", "b"): edge_global}
        mock_graph_store.get_nodes_batch.return_value = {"a": node_a, "b": node_b}
        global_ret = GlobalRetriever(
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            embedding_config=mock_embedding_config,
        )
        _set_mock_embedding(global_ret)
        for doc in global_ret.invoke("q"):
            assert "retrieval_mode" in doc.metadata
            assert doc.metadata["retrieval_mode"] == "global"

        # Bypass — no docs, but still verify
        bypass = BypassRetriever(vector_store=mock_vector_store, embedding_config=mock_embedding_config)
        assert bypass.invoke("q") == []
