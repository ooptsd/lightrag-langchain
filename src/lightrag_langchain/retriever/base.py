"""所有 LightRAG LangChain Retriever 的共享基类 (D-06)。

提供 :class:`LightRAGBaseRetriever` 抽象基类，封装了以下功能：
- 通过延迟 :meth:`embedding` 属性生成 Embedding (D-02)
- 使用 :func:`asyncio.run` 的异步到同步桥接（匹配 LightRAGReranker 模式）
- 共享的错误处理和日志记录
- Pydantic 字段验证 (D-01, D-03)

子类职责仅限于 :meth:`_aget_relevant_documents` 和任何模式特定的辅助方法。
基类中不包含策略特定或转换逻辑。
"""

from __future__ import annotations

import abc
import asyncio
import logging
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, PrivateAttr

if TYPE_CHECKING:
    from langchain_openai import OpenAIEmbeddings

    from lightrag_langchain.config import EmbeddingConfig
    from lightrag_langchain.data.graph import PGGraphStore
    from lightrag_langchain.data.store import PGVectorStore


class LightRAGBaseRetriever(BaseRetriever):
    """所有 LightRAG 查询模式 Retriever 的抽象基类。

    封装共享基础设施（embedding 生成、异步桥接、错误处理），使每个模式特定子类
    只需实现 ``_aget_relevant_documents`` 及其自身的策略调用和 Document 转换逻辑 (D-06)。

    Parameters
    ----------
    vector_store:
        用于向量相似度搜索的 PGVectorStore 实例 (D-01)。
    embedding_config:
        用于延迟创建 embedding 模型的 EmbeddingConfig (D-02)。
    graph_store:
        用于图查询的 PGGraphStore 实例。可选 — naive 和 bypass 模式不需要（默认 ``None``）。
    top_k:
        覆盖全局 top_k。当为 ``None`` 时，Retriever 使用 Settings 级别的默认值 (D-03)。
    chunk_top_k:
        覆盖全局 chunk_top_k。当为 ``None`` 时，Retriever 使用 Settings 级别的默认值 (D-03)。

    Example:
        ```python
        from lightrag_langchain.retriever import NaiveRetriever
        from lightrag_langchain.config import settings

        retriever = NaiveRetriever(
            vector_store=vector_store,
            embedding_config=settings.embedding,
        )
        docs = await retriever.ainvoke("your query")
        ```
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vector_store: PGVectorStore
    """用于向量相似度搜索的 PGVectorStore (D-01 构造函数注入)。"""

    embedding_config: EmbeddingConfig
    """Embedding provider 配置；由延迟 ``embedding`` 属性消费 (D-02)。"""

    graph_store: PGGraphStore | None = None
    """用于图查询的 PGGraphStore；可选（naive/bypass 不需要）。"""

    top_k: int | None = None
    """覆盖全局 top_k；``None`` 表示使用 Settings 默认值 (D-03)。"""

    chunk_top_k: int | None = None
    """覆盖 chunk_top_k；``None`` 表示使用 Settings 默认值 (D-03)。"""

    # ------------------------------------------------------------------
    # Private attributes
    # ------------------------------------------------------------------

    _embedding: OpenAIEmbeddings | None = PrivateAttr(default=None)
    """延迟初始化的 embedding 模型 (D-02)。"""

    _logger: logging.Logger = PrivateAttr(
        default_factory=lambda: logging.getLogger(__name__)
    )
    """每个实例的日志记录器，用于警告和错误。"""

    # ------------------------------------------------------------------
    # Embedding (lazy init, D-02)
    # ------------------------------------------------------------------

    @property
    def embedding(self) -> OpenAIEmbeddings:
        """返回 OpenAIEmbeddings 实例，在首次访问时创建。

        使用 :func:`create_embedding(self.embedding_config)`，它返回一个
        ``_LazyEmbedding`` 代理 — 实际的 ``OpenAIEmbeddings`` 构造延迟到
        首次访问返回对象的属性时。导入时无网络调用 (D-02)。
        """
        if self._embedding is None:
            from lightrag_langchain.llm import create_embedding

            self._embedding = create_embedding(self.embedding_config)
        return self._embedding

    # ------------------------------------------------------------------
    # Sync / async bridge
    # ------------------------------------------------------------------

    def _get_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """同步路径 — 使用 ``asyncio.run`` 桥接到异步实现。

        匹配 :class:`LightRAGReranker.compress_documents` 模式
        (:file:`reranker.py` 第 357 行)。
        """
        return asyncio.run(
            self._aget_relevant_documents(query, run_manager=run_manager, **kwargs)
        )

    # ------------------------------------------------------------------
    # Abstract: subclasses MUST override
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def _aget_relevant_documents(
        self, query: str, *, run_manager=None, **kwargs
    ) -> list[Document]:
        """异步检索 — 子类通过模式特定逻辑覆盖。

        每个实现应：
        1. 通过 :meth:`_generate_query_embedding` 生成查询 embedding
        2. 调用其模式特定的 Phase 4 策略函数
        3. 将返回的 :class:`QueryResult` 转换为 ``list[Document]``
        """

    # ------------------------------------------------------------------
    # Helper: query embedding
    # ------------------------------------------------------------------

    def _generate_query_embedding(self, query: str) -> list[float]:
        """通过 embedding 模型将 *query* 编码为稠密向量。

        Returns
        -------
        list[float]
            适用于 pgvector ``<=>`` 余弦距离搜索和 Phase 4 策略函数调用的
            embedding 向量。
        """
        return self.embedding.embed_query(query)


# ------------------------------------------------------------------
# Resolve Pydantic v2 forward references from TYPE_CHECKING imports
# ------------------------------------------------------------------

from langchain_openai import OpenAIEmbeddings  # noqa: E402
from lightrag_langchain.config import EmbeddingConfig  # noqa: E402
from lightrag_langchain.data.graph import PGGraphStore  # noqa: E402
from lightrag_langchain.data.store import PGVectorStore  # noqa: E402

LightRAGBaseRetriever.model_rebuild()
