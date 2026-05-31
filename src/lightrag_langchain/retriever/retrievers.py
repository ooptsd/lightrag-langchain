"""LightRAG query-mode retriever subclasses (D-07).

This module provides six :class:`LightRAGBaseRetriever` subclasses, one per
LightRAG query mode.  Each retriever:

1. Generates a query embedding via the shared ``_generate_query_embedding`` helper.
2. Calls the corresponding Phase 4 async strategy function.
3. Converts the returned :class:`QueryResult` into ``list[Document]`` with
   upstream-compatible JSON ``page_content`` (D-04) and structured ``metadata`` (D-05).

All strategy imports are **lazy** (inside method bodies) to keep the module
safe to import without a .env file or database connection.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.documents import Document

from lightrag_langchain.retriever.base import LightRAGBaseRetriever
from lightrag_langchain.retriever.utils import (
    build_graph_lookups,
    chunk_to_document,
    entity_to_document,
    graph_triple_to_document,
    relation_to_document,
)

if TYPE_CHECKING:
    from lightrag_langchain.config import EmbeddingConfig
    from lightrag_langchain.data.graph import PGGraphStore
    from lightrag_langchain.data.models import (
        ChunkRecord,
        EntityRecord,
        GraphEdge,
        GraphNode,
        RelationshipRecord,
    )
    from lightrag_langchain.data.store import PGVectorStore
    from lightrag_langchain.query.results import GraphTriple, QueryResult

logger = logging.getLogger(__name__)


# ===========================================================================
# Retriever 1 — Naive: pure vector chunk search (RETR-01 naive mode)
# ===========================================================================


class NaiveRetriever(LightRAGBaseRetriever):
    """LangChain retriever for LightRAG **naive** query mode.

    Performs pure vector similarity search on the chunks_vdb table.
    No graph traversal — returns chunk Documents only.

    RETR-01 (naive mode).  ``graph_store`` is not used (always ``None``).
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """Async naive retrieval: embed query → vector search chunks → convert."""
        embedding = self._generate_query_embedding(query)

        from lightrag_langchain.query.strategies import naive_strategy

        result = await naive_strategy(
            embedding,
            vector_store=self.vector_store,
            chunk_top_k=self.chunk_top_k,
        )

        if not result.chunks:
            self._logger.warning(
                "NaiveRetriever: no chunks found for query %r", query[:120]
            )

        return [
            chunk_to_document(c, retrieval_mode="naive") for c in result.chunks
        ]


# ===========================================================================
# Retriever 2 — Local: entity vector search + graph expansion (RETR-01 local)
# ===========================================================================


class LocalRetriever(LightRAGBaseRetriever):
    """LangChain retriever for LightRAG **local** query mode.

    Searches the entities_vdb for top-K entities, expands into the AGE graph
    to discover edges/neighbors, and returns entity + GraphTriple Documents.

    RETR-01 (local mode).  Requires both ``vector_store`` and ``graph_store``.
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """Async local retrieval: embed → entity search → graph expand → convert."""
        embedding = self._generate_query_embedding(query)

        from lightrag_langchain.query.strategies import local_strategy

        result = await local_strategy(
            embedding,
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            top_k=self.top_k,
        )

        if not result.entities and not result.graph_triples:
            self._logger.warning(
                "LocalRetriever: no results found for query %r", query[:120]
            )

        node_lookup, _edge_lookup = build_graph_lookups(result.graph_triples)

        # Entity Documents — enrich with GraphNode entity_type/description
        entity_docs: list[Document] = []
        for entity in result.entities:
            node = node_lookup.get(entity.entity_name)
            if node is not None:
                doc = entity_to_document(
                    entity,
                    entity_type=node.entity_type,
                    description=node.description,
                    retrieval_mode="local",
                )
            else:
                doc = entity_to_document(entity, retrieval_mode="local")
            entity_docs.append(doc)

        # GraphTriple Documents
        triple_docs = [
            graph_triple_to_document(t, retrieval_mode="local")
            for t in result.graph_triples
        ]

        return entity_docs + triple_docs


# ===========================================================================
# Retriever 3 — Global: relation vector search + entity lookup (RETR-01 global)
# ===========================================================================


class GlobalRetriever(LightRAGBaseRetriever):
    """LangChain retriever for LightRAG **global** query mode.

    Searches the relationships_vdb for top-K relations, batch-retrieves edge
    data from the AGE graph, and returns relation + GraphTriple Documents.

    RETR-01 (global mode).  Requires both ``vector_store`` and ``graph_store``.
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """Async global retrieval: embed → relation search → enrich → convert."""
        embedding = self._generate_query_embedding(query)

        from lightrag_langchain.query.strategies import global_strategy

        result = await global_strategy(
            embedding,
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            top_k=self.top_k,
        )

        if not result.relations and not result.graph_triples:
            self._logger.warning(
                "GlobalRetriever: no results found for query %r", query[:120]
            )

        _node_lookup, edge_lookup = build_graph_lookups(result.graph_triples)

        # Relation Documents — enrich with GraphEdge keywords/weight/source_id
        relation_docs: list[Document] = []
        for relation in result.relations:
            edge = edge_lookup.get((relation.src_id, relation.tgt_id))
            if edge is not None:
                doc = relation_to_document(
                    relation,
                    keywords=edge.keywords or "",
                    weight=edge.weight,
                    source_id=edge.source_id or "",
                    retrieval_mode="global",
                )
            else:
                doc = relation_to_document(relation, retrieval_mode="global")
            relation_docs.append(doc)

        # GraphTriple Documents
        triple_docs = [
            graph_triple_to_document(t, retrieval_mode="global")
            for t in result.graph_triples
        ]

        return relation_docs + triple_docs


# ===========================================================================
# Retriever 4 — Hybrid: parallel local + global (RETR-01 hybrid mode)
# ===========================================================================


class HybridRetriever(LightRAGBaseRetriever):
    """LangChain retriever for LightRAG **hybrid** query mode.

    Runs local and global strategies in parallel, then round-robin merges
    entities and relations.  Returns entity + relation + GraphTriple Documents.

    RETR-01 (hybrid mode).  Requires both ``vector_store`` and ``graph_store``.
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """Async hybrid retrieval: embed → parallel local+global → merge → convert."""
        embedding = self._generate_query_embedding(query)

        from lightrag_langchain.query.strategies import hybrid_strategy

        result = await hybrid_strategy(
            embedding,
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            top_k=self.top_k,
        )

        if (
            not result.entities
            and not result.relations
            and not result.graph_triples
        ):
            self._logger.warning(
                "HybridRetriever: no results found for query %r", query[:120]
            )

        node_lookup, edge_lookup = build_graph_lookups(result.graph_triples)

        # Entity Documents — enrich with GraphNode entity_type/description
        entity_docs: list[Document] = []
        for entity in result.entities:
            node = node_lookup.get(entity.entity_name)
            if node is not None:
                doc = entity_to_document(
                    entity,
                    entity_type=node.entity_type,
                    description=node.description,
                    retrieval_mode="hybrid",
                )
            else:
                doc = entity_to_document(entity, retrieval_mode="hybrid")
            entity_docs.append(doc)

        # Relation Documents — enrich with GraphEdge keywords/weight/source_id
        relation_docs: list[Document] = []
        for relation in result.relations:
            edge = edge_lookup.get((relation.src_id, relation.tgt_id))
            if edge is not None:
                doc = relation_to_document(
                    relation,
                    keywords=edge.keywords or "",
                    weight=edge.weight,
                    source_id=edge.source_id or "",
                    retrieval_mode="hybrid",
                )
            else:
                doc = relation_to_document(relation, retrieval_mode="hybrid")
            relation_docs.append(doc)

        # GraphTriple Documents
        triple_docs = [
            graph_triple_to_document(t, retrieval_mode="hybrid")
            for t in result.graph_triples
        ]

        return entity_docs + relation_docs + triple_docs


# ===========================================================================
# Retriever 5 — Mix: hybrid + chunk search (RETR-01 mix mode)
# ===========================================================================


class MixRetriever(LightRAGBaseRetriever):
    """LangChain retriever for LightRAG **mix** query mode.

    Runs the hybrid strategy and chunk vector search in parallel, merging
    entity pseudo-chunks with text chunks via round-robin.  Returns
    entity + relation + chunk + GraphTriple Documents.

    RETR-01 (mix mode).  Requires both ``vector_store`` and ``graph_store``.
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """Async mix retrieval: embed → mix strategy → convert all four types."""
        embedding = self._generate_query_embedding(query)

        from lightrag_langchain.query.strategies import mix_strategy

        result = await mix_strategy(
            embedding,
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            top_k=self.top_k,
            chunk_top_k=self.chunk_top_k,
        )

        if (
            not result.entities
            and not result.relations
            and not result.chunks
            and not result.graph_triples
        ):
            self._logger.warning(
                "MixRetriever: no results found for query %r", query[:120]
            )

        node_lookup, edge_lookup = build_graph_lookups(result.graph_triples)

        # Entity Documents — enrich with GraphNode entity_type/description
        entity_docs: list[Document] = []
        for entity in result.entities:
            node = node_lookup.get(entity.entity_name)
            if node is not None:
                doc = entity_to_document(
                    entity,
                    entity_type=node.entity_type,
                    description=node.description,
                    retrieval_mode="mix",
                )
            else:
                doc = entity_to_document(entity, retrieval_mode="mix")
            entity_docs.append(doc)

        # Relation Documents — enrich with GraphEdge keywords/weight/source_id
        relation_docs: list[Document] = []
        for relation in result.relations:
            edge = edge_lookup.get((relation.src_id, relation.tgt_id))
            if edge is not None:
                doc = relation_to_document(
                    relation,
                    keywords=edge.keywords or "",
                    weight=edge.weight,
                    source_id=edge.source_id or "",
                    retrieval_mode="mix",
                )
            else:
                doc = relation_to_document(relation, retrieval_mode="mix")
            relation_docs.append(doc)

        # Chunk Documents
        chunk_docs = [
            chunk_to_document(c, retrieval_mode="mix") for c in result.chunks
        ]

        # GraphTriple Documents
        triple_docs = [
            graph_triple_to_document(t, retrieval_mode="mix")
            for t in result.graph_triples
        ]

        return entity_docs + relation_docs + chunk_docs + triple_docs


# ===========================================================================
# Retriever 6 — Bypass: empty result (RETR-01 bypass mode)
# ===========================================================================


class BypassRetriever(LightRAGBaseRetriever):
    """LangChain retriever for LightRAG **bypass** query mode.

    No retrieval — returns an empty ``list[Document]``.  No embedding
    generation, no strategy call, no database I/O.

    RETR-01 (bypass mode).  ``vector_store`` and ``graph_store`` are unused.
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """Async bypass — returns empty list.  No I/O."""
        return []

    def _get_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """Sync bypass — returns empty list.  Skips ``asyncio.run`` overhead."""
        return []


# ------------------------------------------------------------------
# Resolve Pydantic v2 forward references from TYPE_CHECKING imports
# ------------------------------------------------------------------

from lightrag_langchain.data.graph import PGGraphStore  # noqa: E402
from lightrag_langchain.data.store import PGVectorStore  # noqa: E402

for _cls in (
    NaiveRetriever,
    LocalRetriever,
    GlobalRetriever,
    HybridRetriever,
    MixRetriever,
    BypassRetriever,
):
    _cls.model_rebuild()
