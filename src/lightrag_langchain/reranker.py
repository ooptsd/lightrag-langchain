"""Multi-backend reranker adapter, factory, and LangChain compressor.

Provides a typing.Protocol-based ``Reranker`` interface, three thin HTTP adapter
functions (``ali_rerank``, ``cohere_rerank``, ``jina_rerank``), a
``create_reranker()`` factory dispatcher, and a ``LightRAGReranker``
BaseDocumentCompressor wrapper for LangChain pipeline integration.

Usage::

    from lightrag_langchain.config import RerankerConfig
    from lightrag_langchain.reranker import create_reranker, LightRAGReranker

    reranker = create_reranker(config.reranker)
    compressor = LightRAGReranker(reranker, top_n=5)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

import httpx
from langchain_core.documents import BaseDocumentCompressor, Document
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from lightrag_langchain.config import RerankerConfig

# ---------------------------------------------------------------------------
# httpx logging suppression — prevent API key leakage in debug logs (T-03-03-01)
# ---------------------------------------------------------------------------

logging.getLogger("httpx").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Retry predicate — 5xx & transport errors retry; 4xx fail fast
# ---------------------------------------------------------------------------


def _is_retryable(exc: BaseException) -> bool:
    """Retry only on 5xx HTTP errors and transport-level errors.

    4xx errors propagate immediately — they indicate client-side mistakes
    (bad API key, invalid model name, etc.) that retrying won't fix.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, httpx.TransportError):
        return True
    return False


# ---------------------------------------------------------------------------
# Reranker Protocol (D-05)
# ---------------------------------------------------------------------------


class Reranker(Protocol):
    """Callable interface for reranking backends.

    All adapters implement this protocol so the factory and compressor
    can work with any provider transparently.
    """

    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# HTTP POST helper with tenacity retry (D-07, D-08)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception(_is_retryable),
)
async def _post_rerank(
    base_url: str, headers: dict[str, str], payload: dict[str, Any]
) -> dict[str, Any]:
    """Execute an HTTP POST with exponential-backoff retry on transient errors.

    Retries up to 3 times on 5xx / transport errors.  4xx errors propagate
    immediately — the custom ``_is_retryable`` predicate only matches 5xx
    status codes.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(base_url, headers=headers, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Thin adapter functions
# ---------------------------------------------------------------------------


async def ali_rerank(
    query: str,
    documents: list[str],
    model: str,
    base_url: str,
    api_key: str,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Rerank documents using Aliyun DashScope API.

    Request format: nested aliyun structure with ``input`` and ``parameters``.
    Response format: ``output.results[...]`` → normalized to
    ``[{index, relevance_score}]``.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload: dict[str, Any] = {
        "model": model,
        "input": {
            "query": query,
            "documents": documents,
        },
        "parameters": {},
    }
    if top_n is not None:
        payload["parameters"]["top_n"] = top_n

    response = await _post_rerank(base_url, headers, payload)
    results = response.get("output", {}).get("results", [])
    if not isinstance(results, list):
        results = []

    return [
        {"index": r["index"], "relevance_score": r["relevance_score"]}
        for r in results
    ]


async def cohere_rerank(
    query: str,
    documents: list[str],
    model: str,
    base_url: str,
    api_key: str,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Rerank documents using Cohere API.

    Request format: standard ``{model, query, documents}``.
    Response format: ``results[...]`` → normalized to
    ``[{index, relevance_score}]``.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload: dict[str, Any] = {
        "model": model,
        "query": query,
        "documents": documents,
    }
    if top_n is not None:
        payload["top_n"] = top_n

    response = await _post_rerank(base_url, headers, payload)
    results = response.get("results", [])
    if not isinstance(results, list):
        results = []

    return [
        {"index": r["index"], "relevance_score": r["relevance_score"]}
        for r in results
    ]


async def jina_rerank(
    query: str,
    documents: list[str],
    model: str,
    base_url: str,
    api_key: str,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Rerank documents using Jina AI API.

    Request and response format identical to cohere (standard).
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload: dict[str, Any] = {
        "model": model,
        "query": query,
        "documents": documents,
    }
    if top_n is not None:
        payload["top_n"] = top_n

    response = await _post_rerank(base_url, headers, payload)
    results = response.get("results", [])
    if not isinstance(results, list):
        results = []

    return [
        {"index": r["index"], "relevance_score": r["relevance_score"]}
        for r in results
    ]


# ---------------------------------------------------------------------------
# Private adapter classes — thin wrappers storing config, implementing Protocol
# ---------------------------------------------------------------------------


class _CohereReranker:
    """Cohere adapter — delegates to ``cohere_rerank()``."""

    def __init__(self, config: RerankerConfig) -> None:
        self._binding = config.binding
        self._model = config.model
        self._base_url = config.binding_host
        self._api_key = config.binding_api_key

    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> list[dict[str, Any]]:
        return await cohere_rerank(
            query=query,
            documents=documents,
            model=self._model,
            base_url=self._base_url,
            api_key=self._api_key.get_secret_value(),
            top_n=top_n,
        )

    def __repr__(self) -> str:
        return f"Reranker(binding={self._binding!r}, model={self._model!r})"


class _JinaReranker:
    """Jina adapter — delegates to ``jina_rerank()``."""

    def __init__(self, config: RerankerConfig) -> None:
        self._binding = config.binding
        self._model = config.model
        self._base_url = config.binding_host
        self._api_key = config.binding_api_key

    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> list[dict[str, Any]]:
        return await jina_rerank(
            query=query,
            documents=documents,
            model=self._model,
            base_url=self._base_url,
            api_key=self._api_key.get_secret_value(),
            top_n=top_n,
        )

    def __repr__(self) -> str:
        return f"Reranker(binding={self._binding!r}, model={self._model!r})"


class _AliyunReranker:
    """Aliyun adapter — delegates to ``ali_rerank()``."""

    def __init__(self, config: RerankerConfig) -> None:
        self._binding = config.binding
        self._model = config.model
        self._base_url = config.binding_host
        self._api_key = config.binding_api_key

    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> list[dict[str, Any]]:
        return await ali_rerank(
            query=query,
            documents=documents,
            model=self._model,
            base_url=self._base_url,
            api_key=self._api_key.get_secret_value(),
            top_n=top_n,
        )

    def __repr__(self) -> str:
        return f"Reranker(binding={self._binding!r}, model={self._model!r})"


# ---------------------------------------------------------------------------
# Factory (D-05, D-06 raw layer)
# ---------------------------------------------------------------------------


def create_reranker(config: RerankerConfig) -> Reranker:
    """Create a Reranker adapter based on the ``binding`` field in config.

    Dispatch table::

        * ``"cohere"`` → ``_CohereReranker``
        * ``"jina"``   → ``_JinaReranker``
        * ``"aliyun"`` / ``"dashscope"`` → ``_AliyunReranker``

    Raises ``ValueError`` for any unrecognized binding value.
    """
    binding = config.binding.lower()
    if binding == "cohere":
        return _CohereReranker(config)  # type: ignore[return-value]
    if binding == "jina":
        return _JinaReranker(config)  # type: ignore[return-value]
    if binding in ("aliyun", "dashscope"):
        return _AliyunReranker(config)  # type: ignore[return-value]
    raise ValueError(f"Unknown reranker binding: {config.binding}")


# ---------------------------------------------------------------------------
# LangChain BaseDocumentCompressor wrapper (D-06 top layer)
# ---------------------------------------------------------------------------


class LightRAGReranker(BaseDocumentCompressor):
    """Wraps a ``Reranker`` Protocol instance as a LangChain
    ``BaseDocumentCompressor`` for use with ``ContextualCompressionRetriever``.

    Parameters
    ----------
    reranker:
        Any object that satisfies the ``Reranker`` Protocol.
    top_n:
        Maximum number of documents to return after reranking (forwarded to
        the underlying reranker call).
    """

    def __init__(self, reranker: Reranker, top_n: int | None = None) -> None:
        self._reranker = reranker
        self._top_n = top_n

    def compress_documents(
        self,
        documents: list[Document] | tuple[Document, ...],
        query: str,
        **kwargs: Any,
    ) -> list[Document]:
        """Synchronous path — uses ``asyncio.run`` to bridge async reranker.

        Extracts ``page_content`` from each Document, calls the reranker,
        attaches ``relevance_score`` to metadata, and returns documents sorted
        descending by score.
        """
        texts = [doc.page_content for doc in documents]
        scores = asyncio.run(
            self._reranker.rerank(query, texts, self._top_n)
        )
        return _sort_and_attach_scores(documents, scores)

    async def acompress_documents(
        self,
        documents: list[Document] | tuple[Document, ...],
        query: str,
        **kwargs: Any,
    ) -> list[Document]:
        """Async path — directly awaits the reranker without ``asyncio.run``."""
        texts = [doc.page_content for doc in documents]
        scores = await self._reranker.rerank(query, texts, self._top_n)
        return _sort_and_attach_scores(documents, scores)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _sort_and_attach_scores(
    documents: list[Document] | tuple[Document, ...],
    scores: list[dict[str, Any]],
) -> list[Document]:
    """Attach relevance_score to document metadata and sort descending."""
    score_map: dict[int, float] = {
        item["index"]: item["relevance_score"] for item in scores
    }
    scored: list[tuple[float, Document]] = []
    for i, doc in enumerate(documents):
        s = score_map.get(i, 0.0)
        doc.metadata["relevance_score"] = s
        scored.append((s, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored]
