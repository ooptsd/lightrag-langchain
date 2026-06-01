"""LightRAG 查询模式 Retriever 子类 (D-07)。

本模块提供六个 :class:`LightRAGBaseRetriever` 子类，每个对应一种 LightRAG 查询模式。
每个 Retriever：

1. 通过共享的 ``_generate_query_embedding`` 辅助方法生成查询 embedding。
2. 调用相应的 Phase 4 异步策略函数。
3. 将返回的 :class:`QueryResult` 转换为 ``list[Document]``，包含上游兼容的 JSON ``page_content`` (D-04)
   和结构化 ``metadata`` (D-05)。

所有策略导入均为**延迟导入**（在方法体内部），确保模块在无需 .env 文件或数据库连接时也能安全导入。
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
    """LightRAG **naive** 查询模式的 LangChain Retriever。

    在 chunks_vdb 表上执行纯向量相似度搜索。
    不进行图遍历 — 仅返回 chunk Document。

    RETR-01 (naive mode)。``graph_store`` 不使用（始终为 ``None``）。

    Example:
        ```python
        from lightrag_langchain.retriever import NaiveRetriever

        retriever = NaiveRetriever(
            vector_store=vector_store,
            embedding_config=settings.embedding,
        )
        docs = await retriever.ainvoke("your query")
        ```
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """异步 naive 检索：embed query → 向量搜索 chunks → 转换。"""
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
    """LightRAG **local** 查询模式的 LangChain Retriever。

    在 entities_vdb 中搜索 top-K 实体，扩展到 AGE 图中发现边/邻居，
    返回 entity + GraphTriple Document。

    RETR-01 (local mode)。需要同时 ``vector_store`` 和 ``graph_store``。

    Example:
        ```python
        from lightrag_langchain.retriever import LocalRetriever

        retriever = LocalRetriever(
            vector_store=vector_store,
            embedding_config=settings.embedding,
            graph_store=graph_store,
        )
        docs = await retriever.ainvoke("your query")
        ```
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """异步 local 检索：embed → 实体搜索 → 图扩展 → 转换。"""
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
    """LightRAG **global** 查询模式的 LangChain Retriever。

    在 relationships_vdb 中搜索 top-K 关系，批量从 AGE 图中检索边数据，
    返回 relation + GraphTriple Document。

    RETR-01 (global mode)。需要同时 ``vector_store`` 和 ``graph_store``。

    Example:
        ```python
        from lightrag_langchain.retriever import GlobalRetriever

        retriever = GlobalRetriever(
            vector_store=vector_store,
            embedding_config=settings.embedding,
            graph_store=graph_store,
        )
        docs = await retriever.ainvoke("your query")
        ```
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """异步 global 检索：embed → 关系搜索 → 丰富 → 转换。"""
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
    """LightRAG **hybrid** 查询模式的 LangChain Retriever。

    并行运行 local 和 global 策略，然后轮询合并 entities 和 relations。
    返回 entity + relation + GraphTriple Document。

    RETR-01 (hybrid mode)。需要同时 ``vector_store`` 和 ``graph_store``。

    Example:
        ```python
        from lightrag_langchain.retriever import HybridRetriever

        retriever = HybridRetriever(
            vector_store=vector_store,
            embedding_config=settings.embedding,
            graph_store=graph_store,
        )
        docs = await retriever.ainvoke("your query")
        ```
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """异步 hybrid 检索：embed → 并行 local+global → 合并 → 转换。"""
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
    """LightRAG **mix** 查询模式的 LangChain Retriever。

    并行运行 hybrid 策略和 chunk 向量搜索，通过轮询将实体伪块与文本块合并。
    返回 entity + relation + chunk + GraphTriple Document。

    RETR-01 (mix mode)。需要同时 ``vector_store`` 和 ``graph_store``。

    Example:
        ```python
        from lightrag_langchain.retriever import MixRetriever

        retriever = MixRetriever(
            vector_store=vector_store,
            embedding_config=settings.embedding,
            graph_store=graph_store,
        )
        docs = await retriever.ainvoke("your query")
        ```
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """异步 mix 检索：embed → mix 策略 → 转换全部四种类型。"""
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
    """LightRAG **bypass** 查询模式的 LangChain Retriever。

    不进行检索 — 返回空的 ``list[Document]``。无 embedding 生成、无策略调用、
    无数据库 I/O。

    RETR-01 (bypass mode)。``vector_store`` 和 ``graph_store`` 不使用。

    Example:
        ```python
        from lightrag_langchain.retriever import BypassRetriever

        retriever = BypassRetriever(
            vector_store=vector_store,
            embedding_config=settings.embedding,
        )
        docs = await retriever.ainvoke("your query")  # 始终返回 []
        ```
    """

    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """异步 bypass — 返回空列表。无 I/O。"""
        return []

    def _get_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """同步 bypass — 返回空列表。跳过 ``asyncio.run`` 开销。"""
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
