"""Shared base class for all LightRAG LangChain retrievers (D-06).

Provides the :class:`LightRAGBaseRetriever` abstract base class that encapsulates:
- Embedding generation via lazy :meth:`embedding` property (D-02)
- Async-to-sync bridge using :func:`asyncio.run` (matches LightRAGReranker pattern)
- Shared error handling and logger
- Pydantic field validation (D-01, D-03)

Subclass responsibility is limited to :meth:`_aget_relevant_documents` and
any mode-specific helper methods.  No strategy-specific or conversion logic
lives in the base class.
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
    """Abstract base class for all LightRAG query-mode retrievers.

    Encapsulates shared infrastructure (embedding generation, async bridge,
    error handling) so that each mode-specific subclass only needs to
    implement ``_aget_relevant_documents`` with its own strategy call and
    Document conversion logic (D-06).

    Parameters
    ----------
    vector_store:
        PGVectorStore instance for vector similarity search (D-01).
    embedding_config:
        EmbeddingConfig used to create the embedding model lazily (D-02).
    graph_store:
        PGGraphStore instance for graph lookups.  Optional — naive and
        bypass modes do not require it (default ``None``).
    top_k:
        Override global top_k.  When ``None`` the retriever uses the
        Settings-level default (D-03).
    chunk_top_k:
        Override global chunk_top_k.  When ``None`` the retriever uses the
        Settings-level default (D-03).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vector_store: PGVectorStore
    """PGVectorStore for vector similarity search (D-01 constructor injection)."""

    embedding_config: EmbeddingConfig
    """Embedding provider config; consumed by the lazy ``embedding`` property (D-02)."""

    graph_store: PGGraphStore | None = None
    """PGGraphStore for graph lookups; optional (naive/bypass don't need it)."""

    top_k: int | None = None
    """Override for global top_k; ``None`` means use Settings default (D-03)."""

    chunk_top_k: int | None = None
    """Override for chunk_top_k; ``None`` means use Settings default (D-03)."""

    # ------------------------------------------------------------------
    # Private attributes
    # ------------------------------------------------------------------

    _embedding: OpenAIEmbeddings | None = PrivateAttr(default=None)
    """Lazy-initialized embedding model (D-02)."""

    _logger: logging.Logger = PrivateAttr(
        default_factory=lambda: logging.getLogger(__name__)
    )
    """Per-instance logger for warnings and errors."""

    # ------------------------------------------------------------------
    # Embedding (lazy init, D-02)
    # ------------------------------------------------------------------

    @property
    def embedding(self) -> OpenAIEmbeddings:
        """Return the OpenAIEmbeddings instance, creating it on first access.

        Uses :func:`create_embedding(self.embedding_config)` which returns a
        ``_LazyEmbedding`` proxy — actual ``OpenAIEmbeddings`` construction is
        deferred until the first attribute access on the returned object.
        No network call at import time (D-02).
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
        """Synchronous path — uses ``asyncio.run`` to bridge to the async
        implementation.

        Matches :class:`LightRAGReranker.compress_documents` pattern
        (:file:`reranker.py` line 357).
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
        """Async retrieval — subclasses override with mode-specific logic.

        Each implementation should:
        1. Generate the query embedding via :meth:`_generate_query_embedding`
        2. Call its mode-specific Phase 4 strategy function
        3. Convert the returned :class:`QueryResult` into ``list[Document]``
        """

    # ------------------------------------------------------------------
    # Helper: query embedding
    # ------------------------------------------------------------------

    def _generate_query_embedding(self, query: str) -> list[float]:
        """Encode *query* into a dense vector via the embedding model.

        Returns
        -------
        list[float]
            Embedding vector suitable for pgvector ``<=>`` cosine distance
            searches and Phase 4 strategy function calls.
        """
        return self.embedding.embed_query(query)
