"""Unit tests for PGVectorStore — vector search, table discovery, read-only
enforcement, pool injection, and vector parameter validation.

All asyncpg calls are mocked via the ``mock_pool`` / ``mock_conn`` fixtures
from conftest.py.  No real database connection is required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lightrag_langchain.data.models import ChunkRecord, EntityRecord, RelationshipRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMBEDDING_1024: list[float] = [0.1] * 1024


def _store_cls():
    """Return the PGVectorStore class.

    Lazy import — called inside test bodies, not at module level — so that
    Settings is not instantiated until pytest fixtures have monkeypatched
    the environment variables.
    """
    from lightrag_langchain.data.store import PGVectorStore

    return PGVectorStore


def _wire_pool_for_acquire_with_retry(mock_pool, mock_conn):
    """Configure mock_pool so acquire_with_retry works correctly.

    acquire_with_retry calls ``conn = await pool.acquire()`` (a coroutine),
    then yields the connection.  It does NOT use ``async with pool.acquire()``
    as a context manager.  This helper overrides the default conftest context-
    manager setup on ``acquire``.
    """
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_pool.release = AsyncMock()


# ---------------------------------------------------------------------------
# TestEntitySearch
# ---------------------------------------------------------------------------


class TestEntitySearch:
    """STOR-01: PGVector entities_vdb vector similarity search."""

    @pytest.mark.asyncio
    async def test_search_entities_returns_entity_records(self, mock_pool, mock_conn):
        """search_entities returns a list of EntityRecord with correct field values."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "entity_name": "E1",
                    "content": "content about E1",
                    "source_id": "abc123",
                    "file_path": "/doc/a.md",
                    "created_at": 1717000000,
                }
            ]
        )

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        results = await store.search_entities(_EMBEDDING_1024)

        assert isinstance(results, list)
        assert len(results) == 1
        rec = results[0]
        assert isinstance(rec, EntityRecord)
        assert rec.entity_name == "E1"
        assert rec.content == "content about E1"
        assert rec.source_id == "abc123"
        assert rec.file_path == "/doc/a.md"
        assert rec.created_at == 1717000000

    @pytest.mark.asyncio
    async def test_search_entities_empty_result(self, mock_pool, mock_conn):
        """search_entities returns empty list when no matching results exist."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        results = await store.search_entities(_EMBEDDING_1024)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_entities_custom_top_k(self, mock_pool, mock_conn):
        """search_entities passes custom top_k through to conn.fetch."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024, top_k=10)

        # Verify fetch was called with top_k=10 as the $3 parameter
        call_args = mock_conn.fetch.call_args
        assert call_args is not None
        # $3 is at position index 2 (0-based: $1, $2, $3, $4)
        assert call_args[0][3] == 10  # $3 = LIMIT

    @pytest.mark.asyncio
    async def test_search_entities_uses_default_top_k(self, mock_pool, mock_conn):
        """search_entities uses settings.query_params.top_k (40) when top_k=None."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)  # top_k not passed

        call_args = mock_conn.fetch.call_args
        assert call_args is not None
        assert call_args[0][3] == 40  # default top_k from settings


# ---------------------------------------------------------------------------
# TestRelationSearch
# ---------------------------------------------------------------------------


class TestRelationSearch:
    """STOR-02: PGVector relationships_vdb vector similarity search."""

    @pytest.mark.asyncio
    async def test_search_relationships_returns_relationship_records(
        self, mock_pool, mock_conn
    ):
        """search_relationships returns RelationshipRecord with correct fields."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "src_id": "s1",
                    "tgt_id": "t1",
                    "content": "relates to",
                    "keywords": None,
                    "weight": None,
                    "created_at": 1717000000,
                }
            ]
        )

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"RELATION": "lightrag_vdb_relation"}

        results = await store.search_relationships(_EMBEDDING_1024)

        assert len(results) == 1
        rec = results[0]
        assert isinstance(rec, RelationshipRecord)
        assert rec.src_id == "s1"
        assert rec.tgt_id == "t1"
        assert rec.content == "relates to"
        assert rec.created_at == 1717000000

    @pytest.mark.asyncio
    async def test_search_relationships_keywords_weight_null(
        self, mock_pool, mock_conn
    ):
        """relationship keywords and weight are None (VDB_RELATION lacks these cols)."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "src_id": "s1",
                    "tgt_id": "t1",
                    "content": "relates to",
                    "keywords": None,
                    "weight": None,
                    "created_at": 1717000000,
                }
            ]
        )

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"RELATION": "lightrag_vdb_relation"}

        results = await store.search_relationships(_EMBEDDING_1024)
        rec = results[0]
        assert rec.keywords is None
        assert rec.weight is None


# ---------------------------------------------------------------------------
# TestChunkSearch
# ---------------------------------------------------------------------------


class TestChunkSearch:
    """STOR-03: PGVector chunks_vdb vector similarity search."""

    @pytest.mark.asyncio
    async def test_search_chunks_returns_chunk_records(self, mock_pool, mock_conn):
        """search_chunks returns ChunkRecord with correct field values."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "chunk_id": "chunk-001",
                    "content": "chunk content here",
                    "full_doc_id": "doc-42",
                    "chunk_order_index": 0,
                    "file_path": "/data/doc.pdf",
                }
            ]
        )

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"CHUNKS": "lightrag_vdb_chunks"}

        results = await store.search_chunks(_EMBEDDING_1024)

        assert len(results) == 1
        rec = results[0]
        assert isinstance(rec, ChunkRecord)
        assert rec.chunk_id == "chunk-001"
        assert rec.content == "chunk content here"
        assert rec.full_doc_id == "doc-42"
        assert rec.chunk_order_index == 0
        assert rec.file_path == "/data/doc.pdf"

    @pytest.mark.asyncio
    async def test_search_chunks_full_doc_id_nullable(self, mock_pool, mock_conn):
        """ChunkRecord.full_doc_id is None when DB returns NULL."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "chunk_id": "chunk-002",
                    "content": "some text",
                    "full_doc_id": None,
                    "chunk_order_index": 1,
                    "file_path": "",
                }
            ]
        )

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"CHUNKS": "lightrag_vdb_chunks"}

        results = await store.search_chunks(_EMBEDDING_1024)
        assert results[0].full_doc_id is None


# ---------------------------------------------------------------------------
# TestWorkspaceFilter
# ---------------------------------------------------------------------------


class TestWorkspaceFilter:
    """D-05: workspace parameter passed as $1 in all queries."""

    @pytest.mark.asyncio
    async def test_workspace_in_sql_params(self, mock_pool, mock_conn):
        """Workspace reaches conn.fetch as the first positional argument ($1)."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="ws_custom")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        call_args = mock_conn.fetch.call_args
        assert call_args is not None
        # $1 = workspace (index 0)
        assert call_args[0][1] == "ws_custom"


# ---------------------------------------------------------------------------
# TestTableDiscovery
# ---------------------------------------------------------------------------


class TestTableDiscovery:
    """D-12 / D-13: auto-discover PGVector tables from information_schema."""

    @pytest.mark.asyncio
    async def test_discover_tables_success(self, mock_pool, mock_conn):
        """_ensure_tables discovers and maps all three namespaces correctly."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)

        # _ensure_tables → information_schema query
        mock_conn.fetch = AsyncMock(
            side_effect=[
                # First call: information_schema
                [
                    {"table_name": "lightrag_vdb_entity"},
                    {"table_name": "lightrag_vdb_relation"},
                    {"table_name": "lightrag_vdb_chunks"},
                ],
                # Second call: the actual _vector_search (will be empty)
                [],
            ]
        )

        store = _store_cls()(pool=mock_pool, workspace="default")
        # _tables is None — _ensure_tables will query
        assert store._tables is None

        tables = await store._ensure_tables()

        assert tables["ENTITY"] == "lightrag_vdb_entity"
        assert tables["RELATION"] == "lightrag_vdb_relation"
        assert tables["CHUNKS"] == "lightrag_vdb_chunks"
        assert store._tables is not None  # cached

    @pytest.mark.asyncio
    async def test_discover_tables_multi_variant_error(self, mock_pool, mock_conn):
        """Multiple suffix variants for one namespace raise RuntimeError (D-13)."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"table_name": "lightrag_vdb_entity"},
                {"table_name": "lightrag_vdb_entity_v2"},
            ]
        )

        store = _store_cls()(pool=mock_pool, workspace="default")

        with pytest.raises(RuntimeError) as exc_info:
            await store._ensure_tables()

        msg = str(exc_info.value)
        assert "lightrag_vdb_entity" in msg
        assert "lightrag_vdb_entity_v2" in msg
        assert "PG_TABLE_SUFFIX" in msg

    @pytest.mark.asyncio
    async def test_discover_tables_no_table_error(self, mock_pool, mock_conn):
        """Zero matching tables raises RuntimeError with guidance."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")

        with pytest.raises(RuntimeError) as exc_info:
            await store._ensure_tables()

        msg = str(exc_info.value)
        assert "No" in msg
        assert "initialised" in msg


# ---------------------------------------------------------------------------
# TestReadOnly
# ---------------------------------------------------------------------------


class TestReadOnly:
    """D-15: read-only enforcement — fetch() only, no execute() or write methods."""

    @pytest.mark.asyncio
    async def test_uses_fetch_not_execute(self, mock_pool, mock_conn):
        """search_entities calls conn.fetch but never conn.execute."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        mock_conn.fetch.assert_called()
        mock_conn.execute.assert_not_called()

    def test_no_write_methods_on_class(self):
        """PGVectorStore class does not expose any write-oriented method names."""
        cls = _store_cls()
        method_names = [
            name
            for name in dir(cls)
            if callable(getattr(cls, name, None))
            and not name.startswith("_")
        ]
        write_methods = {"insert", "update", "delete", "create", "upsert", "execute"}
        found = write_methods & set(method_names)
        assert not found, f"Write methods detected: {found}"


# ---------------------------------------------------------------------------
# TestPoolInjection
# ---------------------------------------------------------------------------


class TestPoolInjection:
    """D-07: dependency injection — injected pool overrides module-level pool."""

    @pytest.mark.asyncio
    async def test_uses_injected_pool(self, mock_pool, mock_conn):
        """PGVectorStore uses the injected pool, not the module-level pool."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        # Verify the injected pool's acquire was called
        mock_pool.acquire.assert_called()

    def test_falls_back_to_module_pool(self, mock_pool):
        """pool property returns the module-level pool when no pool is injected."""
        # Patch the module-level _pool so __getattr__ returns our mock
        with patch(
            "lightrag_langchain.data.pool._pool", mock_pool
        ):
            store = _store_cls()(pool=None, workspace="default")
            # The property should return the patched module-level pool
            assert store.pool is mock_pool


# ---------------------------------------------------------------------------
# TestVectorParameters
# ---------------------------------------------------------------------------


class TestVectorParameters:
    """D-10: pre-computed vector handling and cosine threshold computation."""

    @pytest.mark.asyncio
    async def test_embedding_passed_as_list(self, mock_pool, mock_conn):
        """embedding is passed to conn.fetch as a list of floats (not generated)."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        call_args = mock_conn.fetch.call_args
        assert call_args is not None
        # $4 = embedding (index 4 in 0-based args: $1=sql, $2=ws, $3=closer_than,
        #   $4=top_k, $5=embedding)
        embedding_arg = call_args[0][4]
        assert isinstance(embedding_arg, list)
        assert len(embedding_arg) == 1024
        assert all(isinstance(v, float) for v in embedding_arg)

    @pytest.mark.asyncio
    async def test_cosine_threshold_in_sql(self, mock_pool, mock_conn):
        """closer_than = 1.0 - cosine_threshold is passed as $2 parameter."""
        _wire_pool_for_acquire_with_retry(mock_pool, mock_conn)
        mock_conn.fetch = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        call_args = mock_conn.fetch.call_args
        assert call_args is not None
        # $2 = closer_than (index 2)
        closer_than = call_args[0][2]
        # Default cosine_threshold = 0.2 → closer_than = 0.8
        assert closer_than == pytest.approx(0.8)
