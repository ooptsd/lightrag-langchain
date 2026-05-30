"""Unit tests for reranker adapter, factory, and compressor.

Validates: LLM-03 requirement — multi-backend reranker with
create_reranker dispatch, response normalization, tenacity retry,
and BaseDocumentCompressor integration.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# Factory dispatch tests (import from not-yet-existing module)
# ---------------------------------------------------------------------------


def test_create_reranker_dispatches_cohere(mock_reranker_config):
    """Test 1: create_reranker dispatches to cohere adapter when binding="cohere"."""
    from lightrag_langchain.reranker import create_reranker

    cfg = mock_reranker_config  # binding="cohere", binding_host="https://api.cohere.com/v2/rerank"
    reranker = create_reranker(cfg)

    # Internal adapter should be a cohere adapter using the cohere base URL
    assert reranker._base_url == "https://api.cohere.com/v2/rerank"
    assert reranker._binding == "cohere"


def test_create_reranker_dispatches_jina(mock_reranker_config):
    """Test 2: create_reranker dispatches to jina adapter when binding="jina"."""
    from pydantic import SecretStr

    from lightrag_langchain.config import RerankerConfig
    from lightrag_langchain.reranker import create_reranker

    cfg = RerankerConfig(
        binding="jina",
        binding_host="https://api.jina.ai/v1/rerank",
        binding_api_key=SecretStr("test-rerank-key"),
        model="jina-reranker-v2",
    )
    reranker = create_reranker(cfg)

    assert reranker._base_url == "https://api.jina.ai/v1/rerank"
    assert reranker._binding == "jina"


def test_create_reranker_dispatches_aliyun(mock_reranker_config):
    """Test 3: create_reranker dispatches to aliyun adapter when binding="aliyun"."""
    from pydantic import SecretStr

    from lightrag_langchain.config import RerankerConfig
    from lightrag_langchain.reranker import create_reranker

    cfg = RerankerConfig(
        binding="aliyun",
        binding_host="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        binding_api_key=SecretStr("test-rerank-key"),
        model="gte-rerank-v2",
    )
    reranker = create_reranker(cfg)

    assert (
        reranker._base_url
        == "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    )
    assert reranker._binding == "aliyun"


def test_create_reranker_unknown_binding(mock_reranker_config):
    """Test 4: create_reranker raises ValueError for unknown binding string."""
    from pydantic import SecretStr

    from lightrag_langchain.config import RerankerConfig
    from lightrag_langchain.reranker import create_reranker

    cfg = RerankerConfig(
        binding="unknown_provider",
        binding_host="https://unknown.example.com",
        binding_api_key=SecretStr("test-key"),
        model="test-model",
    )

    with pytest.raises(ValueError, match="unknown_provider"):
        create_reranker(cfg)


# ---------------------------------------------------------------------------
# Response normalization tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ali_rerank_response_normalization():
    """Test 5: aliyun response (output.results[...]) normalizes to [{index, relevance_score}]."""
    from lightrag_langchain.reranker import ali_rerank

    # Mock httpx.AsyncClient.post to return aliyun-format response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "output": {
            "results": [
                {"index": 0, "relevance_score": 0.95},
                {"index": 1, "relevance_score": 0.30},
            ]
        }
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        results = await ali_rerank(
            query="test query",
            documents=["doc1", "doc2"],
            model="gte-rerank-v2",
            base_url="https://test.example.com",
            api_key="test-key",
            top_n=2,
        )

    assert results == [
        {"index": 0, "relevance_score": 0.95},
        {"index": 1, "relevance_score": 0.30},
    ]
    assert len(results) == 2


@pytest.mark.asyncio
async def test_cohere_rerank_response_normalization():
    """Test 6: cohere response (results[...]) normalizes to [{index, relevance_score}]."""
    from lightrag_langchain.reranker import cohere_rerank

    # Mock httpx.AsyncClient.post to return standard-format response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"index": 1, "relevance_score": 0.87},
            {"index": 0, "relevance_score": 0.42},
        ]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        results = await cohere_rerank(
            query="test query",
            documents=["doc_a", "doc_b"],
            model="rerank-v3.5",
            base_url="https://api.cohere.com/v2/rerank",
            api_key="test-key",
        )

    assert results == [
        {"index": 1, "relevance_score": 0.87},
        {"index": 0, "relevance_score": 0.42},
    ]
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Retry behavior tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reranker_retry_on_5xx():
    """Test 7: 5xx errors are retried and eventually succeed."""
    from lightrag_langchain.reranker import cohere_rerank

    # First call raises 503, second call succeeds
    error_response = MagicMock()
    error_response.status_code = 503
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=MagicMock(),
        response=error_response,
    )

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "results": [{"index": 0, "relevance_score": 0.99}]
    }

    mock_post = AsyncMock(side_effect=[httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=MagicMock(),
        response=error_response,
    ), success_response])

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post = mock_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        results = await cohere_rerank(
            query="test query",
            documents=["doc1"],
            model="rerank-v3.5",
            base_url="https://api.cohere.com/v2/rerank",
            api_key="test-key",
        )

    # The call should succeed after retry
    assert results == [{"index": 0, "relevance_score": 0.99}]
    # HTTP post should have been called at least twice (initial + retry)
    assert mock_post.call_count >= 2


@pytest.mark.asyncio
async def test_reranker_no_retry_on_4xx():
    """Test 8: 4xx errors propagate immediately without retry."""
    from lightrag_langchain.reranker import cohere_rerank

    # 400 error — should fail fast, no retry
    error_response = MagicMock()
    error_response.status_code = 400
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400 Bad Request",
        request=MagicMock(),
        response=error_response,
    )

    mock_post = AsyncMock(return_value=error_response)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post = mock_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await cohere_rerank(
                query="test query",
                documents=["doc1"],
                model="rerank-v3.5",
                base_url="https://api.cohere.com/v2/rerank",
                api_key="test-key",
            )

    # Post should have been called exactly once — no retry on 4xx
    assert mock_post.call_count == 1


# ---------------------------------------------------------------------------
# Document compressor integration test
# ---------------------------------------------------------------------------


def test_lightrag_reranker_compressor():
    """Test 9: LightRAGReranker.compress_documents sorts by score and sets metadata."""
    from lightrag_langchain.reranker import LightRAGReranker

    # Mock Reranker (Protocol) returning hardcoded scores
    class MockReranker:
        async def rerank(
            self, query: str, documents: list[str], top_n: int | None = None
        ) -> list[dict[str, Any]]:
            return [
                {"index": 0, "relevance_score": 0.90},
                {"index": 1, "relevance_score": 0.50},
            ]

    mock_reranker = MockReranker()
    compressor = LightRAGReranker(reranker=mock_reranker)

    docs = [
        Document(page_content="Document A content"),
        Document(page_content="Document B content"),
    ]

    result = compressor.compress_documents(documents=docs, query="test query")

    # Should return documents sorted by relevance_score descending
    assert len(result) == 2
    # Highest score (0.90) should be first
    assert result[0].metadata["relevance_score"] == 0.90
    assert result[0].page_content == "Document A content"
    # Lower score (0.50) should be second
    assert result[1].metadata["relevance_score"] == 0.50
    assert result[1].page_content == "Document B content"


# ---------------------------------------------------------------------------
# Protocol signature test
# ---------------------------------------------------------------------------


def test_reranker_async_signature():
    """Test 10: Reranker Protocol has the correct async method signature."""
    from lightrag_langchain.reranker import Reranker

    # Verify rerank is an async method with correct parameters
    sig = inspect.signature(Reranker.rerank)
    params = list(sig.parameters.keys())

    assert "self" in params
    assert "query" in params
    assert "documents" in params
    assert "top_n" in params
    assert len(params) == 4  # self, query, documents, top_n
