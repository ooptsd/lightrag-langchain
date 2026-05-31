"""Shared pytest fixtures for the lightrag-langchain test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def temp_env_file(tmp_path: Path):
    """Fixture returning a callable that writes key=value pairs to a temporary .env file.

    Usage in tests::

        def test_something(temp_env_file):
            env_path = temp_env_file(PG_HOST="localhost", PG_PORT="5432")
            # env_path points to tmp_path / ".env" with those variables
    """

    def _write(**kwargs: str) -> Path:
        env_path = tmp_path / ".env"
        lines = [f"{key}={value}" for key, value in kwargs.items()]
        env_path.write_text("\n".join(lines) + "\n")
        return env_path

    return _write


@pytest.fixture
def mock_pool():
    """Return an AsyncMock wrapping asyncpg.Pool for unit testing data layer classes.

    Usage::

        async def test_something(mock_pool):
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            store = PGVectorStore(pool=mock_pool)
    """
    from unittest.mock import AsyncMock

    pool = AsyncMock()
    # Simulate async context manager behavior for pool.acquire()
    pool.acquire.return_value.__aenter__ = AsyncMock()
    pool.acquire.return_value.__aexit__ = AsyncMock()
    return pool


@pytest.fixture
def mock_conn():
    """Return an AsyncMock wrapping asyncpg.Connection with configurable fetch().

    Usage::

        async def test_something(mock_pool, mock_conn):
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = [{"col": "val"}]
    """
    from unittest.mock import AsyncMock

    conn = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    return conn


# ---------------------------------------------------------------------------
# Phase 3 fixtures: LLM / Embedding / Reranker / QueryParams / httpx
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_config():
    """Return a LlmConfig instance with test values for LLM integration tests.

    Constructed directly (not via Settings), so tests do not need a real .env file.
    """
    from pydantic import SecretStr

    from lightrag_langchain.config import LlmConfig

    return LlmConfig(
        binding="test_llm",
        binding_host="https://test-llm.example.com/v1",
        binding_api_key=SecretStr("test-llm-key"),
        model="test-model",
    )


@pytest.fixture
def mock_embedding_config():
    """Return an EmbeddingConfig instance with test values for embedding tests.

    Constructed directly (not via Settings), so tests do not need a real .env file.
    """
    from pydantic import SecretStr

    from lightrag_langchain.config import EmbeddingConfig

    return EmbeddingConfig(
        binding="test_emb",
        binding_host="https://test-emb.example.com/v1",
        binding_api_key=SecretStr("test-emb-key"),
        model="test-emb-model",
        dim=1024,
    )


@pytest.fixture
def mock_reranker_config():
    """Return a RerankerConfig instance with test values for reranker tests.

    Constructed directly (not via Settings), so tests do not need a real .env file.
    """
    from pydantic import SecretStr

    from lightrag_langchain.config import RerankerConfig

    return RerankerConfig(
        binding="cohere",
        binding_host="https://api.cohere.com/v2/rerank",
        binding_api_key=SecretStr("test-rerank-key"),
        model="rerank-v3.5",
        min_rerank_score=0.0,
    )


@pytest.fixture
def mock_query_params_config():
    """Return a QueryParamsConfig instance with defaults + keyword_language.

    Token budget invariant: 4000 + 5000 = 9000 < 20000.
    """
    from lightrag_langchain.config import QueryParamsConfig

    return QueryParamsConfig(
        max_entity_tokens=4000,
        max_relation_tokens=5000,
        max_total_tokens=20000,
        keyword_language="Chinese",
    )


@pytest.fixture
def mock_httpx_client():
    """Return an AsyncMock wrapping httpx.AsyncClient for reranker HTTP tests."""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.post = AsyncMock()
    return client


# Phase 5: Retriever test fixtures


@pytest.fixture
def mock_vector_store():
    """Return an AsyncMock wrapping PGVectorStore for retriever unit tests.

    Uses ``spec=PGVectorStore`` so ``isinstance(mock, PGVectorStore)``
    returns True, which satisfies Pydantic v2 field validation.

    Three search methods return empty lists by default; individual tests
    override return_value to provide test data.
    """
    from unittest.mock import AsyncMock

    from lightrag_langchain.data.store import PGVectorStore

    store = AsyncMock(spec=PGVectorStore)
    store.search_entities = AsyncMock(return_value=[])
    store.search_relationships = AsyncMock(return_value=[])
    store.search_chunks = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_graph_store():
    """Return an AsyncMock wrapping PGGraphStore for retriever unit tests.

    Uses ``spec=PGGraphStore`` so ``isinstance(mock, PGGraphStore)``
    returns True, which satisfies Pydantic v2 field validation.

    get_nodes_batch returns dict[str, GraphNode]; get_edges_batch returns
    dict[tuple[str,str], GraphEdge]; get_node_edges returns list[tuple[str,str]].
    All default to empty; tests override as needed.
    """
    from unittest.mock import AsyncMock

    from lightrag_langchain.data.graph import PGGraphStore

    store = AsyncMock(spec=PGGraphStore)
    store.get_node = AsyncMock(return_value=None)
    store.get_nodes_batch = AsyncMock(return_value={})
    store.get_edge = AsyncMock(return_value=None)
    store.get_edges_batch = AsyncMock(return_value={})
    store.get_node_edges = AsyncMock(return_value=[])
    return store


# ---------------------------------------------------------------------------
# Phase 6: Chain test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm():
    """Return an AsyncMock wrapping ChatOpenAI for chain unit tests.

    ``ainvoke`` returns an AIMessage-like mock with ``.content`` attribute.
    ``astream`` is an async generator yielding nothing by default.
    Individual tests override ``return_value`` / ``side_effect`` as needed.
    """
    from unittest.mock import AsyncMock, MagicMock

    llm = AsyncMock()
    # Default ainvoke: returns mock AIMessage with empty content
    mock_response = MagicMock()
    mock_response.content = ""
    llm.ainvoke = AsyncMock(return_value=mock_response)
    # Default astream: empty async generator
    async def _empty_stream(*args, **kwargs):
        return
        yield  # pragma: no cover  -- makes it an async generator
    llm.astream = MagicMock(side_effect=_empty_stream)
    return llm


@pytest.fixture
def mock_retriever():
    """Return an AsyncMock wrapping LightRAGBaseRetriever for chain unit tests.

    Uses ``spec=LightRAGBaseRetriever`` so ``isinstance(mock, LightRAGBaseRetriever)``
    returns True, satisfying Pydantic v2 field validation for LightRAGBaseChain.retriever.

    ``ainvoke`` returns empty list by default; tests override ``return_value``.
    """
    from unittest.mock import AsyncMock

    from lightrag_langchain.retriever.base import LightRAGBaseRetriever

    retriever = AsyncMock(spec=LightRAGBaseRetriever)
    retriever.ainvoke = AsyncMock(return_value=[])
    return retriever


@pytest.fixture
def make_entity_doc():
    """Fixture returning a callable that creates a Document with entity page_content.

    Produces Documents matching :func:`retriever.utils.entity_to_document` JSON format.
    """
    import json

    from langchain_core.documents import Document

    def _make(
        entity_name="e1",
        entity_type="",
        description="",
        source_id="src-1",
        file_path="test/file.txt",
    ):
        obj = {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "description": description,
            "source_id": source_id,
            "file_path": file_path,
        }
        metadata = {
            "source_id": source_id,
            "file_path": file_path,
            "retrieval_mode": "local",
            "document_type": "entity",
            "entity_name": entity_name,
            "entity_type": entity_type,
        }
        return Document(page_content=json.dumps(obj), metadata=metadata)

    return _make


@pytest.fixture
def make_chunk_doc():
    """Fixture returning a callable that creates a Document with chunk page_content.

    Produces Documents matching :func:`retriever.utils.chunk_to_document` JSON format.
    """
    import json

    from langchain_core.documents import Document

    def _make(chunk_id="c1", content="chunk text", file_path="test/file.txt"):
        obj = {
            "reference_id": "",
            "content": content,
            "file_path": file_path,
            "chunk_id": chunk_id,
        }
        metadata = {
            "source_id": "",
            "file_path": file_path,
            "retrieval_mode": "naive",
            "document_type": "chunk",
            "chunk_id": chunk_id,
            "chunk_order_index": 0,
        }
        return Document(page_content=json.dumps(obj), metadata=metadata)

    return _make
