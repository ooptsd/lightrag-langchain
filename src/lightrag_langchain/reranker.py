"""多后端 reranker 适配器、工厂函数和 LangChain compressor。

提供基于 typing.Protocol 的 ``Reranker`` 接口、三个轻量级 HTTP 适配器函数
（``ali_rerank``、``cohere_rerank``、``jina_rerank``）、``create_reranker()``
工厂分发函数，以及用于 LangChain pipeline 集成的 ``LightRAGReranker``
BaseDocumentCompressor 包装器。

用法::

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
    """仅在 5xx HTTP 错误和传输层错误时重试。

    4xx 错误立即传播——它们表示客户端错误（错误的 API key、无效的模型名称等），
    重试无法修复。
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
    """用于 reranking 后端的可调用接口。

    所有适配器都实现此协议，以便工厂和 compressor 能够透明地与任何 provider
    一起工作。
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
    """在临时错误上执行带指数退避重试的 HTTP POST。

    在 5xx / 传输错误上最多重试 3 次。4xx 错误立即传播——自定义的
    ``_is_retryable`` 断言仅匹配 5xx 状态码。
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
    """使用阿里云 DashScope API 对文档进行重排序。

    请求格式：嵌套的阿里云结构，包含 ``input`` 和 ``parameters``。
    响应格式：``output.results[...]`` → 标准化为
    ``[{index, relevance_score}]``。
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
    """使用 Cohere API 对文档进行重排序。

    请求格式：标准格式 ``{model, query, documents}``。
    响应格式：``results[...]`` → 标准化为
    ``[{index, relevance_score}]``。
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
    """使用 Jina AI API 对文档进行重排序。

    请求和响应格式与 cohere 相同（标准格式）。
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
    """Cohere 适配器——委托给 ``cohere_rerank()``。"""

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
    """Jina 适配器——委托给 ``jina_rerank()``。"""

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
    """阿里云适配器——委托给 ``ali_rerank()``。"""

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
    """根据配置中的 ``binding`` 字段创建 Reranker 适配器。

    分发表::

        * ``"cohere"`` → ``_CohereReranker``
        * ``"jina"``   → ``_JinaReranker``
        * ``"aliyun"`` / ``"dashscope"`` → ``_AliyunReranker``

    对于任何无法识别的 binding 值，抛出 ``ValueError``。

    Example:
        ```python
        from lightrag_langchain.config import settings
        from lightrag_langchain.reranker import create_reranker

        reranker = create_reranker(settings.reranker)
        print(reranker)
        ```
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
    """将 ``Reranker`` Protocol 实例包装为 LangChain 的
    ``BaseDocumentCompressor``，用于 ``ContextualCompressionRetriever``。

    Parameters
    ----------
    reranker:
        任何满足 ``Reranker`` Protocol 的对象。
    top_n:
        重排序后返回的最大文档数量（转发到底层 reranker 调用）。

    Example:
        ```python
        from lightrag_langchain.config import settings
        from lightrag_langchain.reranker import create_reranker, LightRAGReranker

        reranker = create_reranker(settings.reranker)
        compressor = LightRAGReranker(reranker, top_n=5)
        ```
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
        """同步路径——使用 ``asyncio.run`` 桥接异步 reranker。

        提取每个 Document 的 ``page_content``，调用 reranker，
        将 ``relevance_score`` 附加到 metadata，并按分数降序返回排序后的文档。
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
        """异步路径——直接 await reranker，无需 ``asyncio.run``。"""
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
    """将 relevance_score 附加到文档 metadata 并按降序排序。"""
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
