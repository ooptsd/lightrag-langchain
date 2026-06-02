"""PGVectorStore 单元测试 — 向量搜索、表发现、只读强制、池注入和向量参数验证。

所有 psycopg 调用通过 ``mock_pool`` / ``mock_conn`` / ``mock_cursor`` fixtures 进行 mock，
无需真实数据库连接。
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
    """返回 PGVectorStore 类。

    延迟导入 — 在测试体内部调用，不在模块级别，
    以确保 pytest fixtures 已先设置环境变量。
    """
    from lightrag_langchain.data.store import PGVectorStore

    return PGVectorStore


def _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor):
    """配置 mock_pool 使 psycopg connection/cursor 模式正常工作。

    psycopg 模式使用:
    - ``async with pool.connection() as conn:``
    - ``async with conn.cursor() as cur:``
    - ``await cur.execute(sql, (p1, p2, ...))``
    - ``await cur.fetchall()``
    """
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor


# ---------------------------------------------------------------------------
# TestEntitySearch
# ---------------------------------------------------------------------------


class TestEntitySearch:
    """STOR-01: PGVector entities_vdb 向量相似度搜索。"""

    @pytest.mark.asyncio
    async def test_search_entities_returns_entity_records(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """search_entities 返回包含正确字段值的 EntityRecord 列表。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(
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
    async def test_search_entities_empty_result(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """search_entities 在无匹配结果时返回空列表。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        results = await store.search_entities(_EMBEDDING_1024)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_entities_custom_top_k(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """search_entities 将自定义 top_k 传递给 cursor.execute。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024, top_k=10)

        # 验证 execute 被调用，top_k=10 在参数元组中
        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        # 参数元组: (workspace, embedding, closer_than, embedding, top_k)
        # top_k 是第5个参数 (index 4)
        assert call_args[0][1][4] == 10

    @pytest.mark.asyncio
    async def test_search_entities_uses_default_top_k(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """search_entities 在 top_k=None 时使用 settings.query_params.top_k (40)。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)  # top_k 未传递

        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        assert call_args[0][1][4] == 40  # settings 中的默认 top_k


# ---------------------------------------------------------------------------
# TestRelationSearch
# ---------------------------------------------------------------------------


class TestRelationSearch:
    """STOR-02: PGVector relationships_vdb 向量相似度搜索。"""

    @pytest.mark.asyncio
    async def test_search_relationships_returns_relationship_records(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """search_relationships 返回包含正确字段的 RelationshipRecord。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(
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
        self, mock_pool, mock_conn, mock_cursor
    ):
        """relationship 的 keywords 和 weight 为 None（VDB_RELATION 表不含这些列）。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(
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
    """STOR-03: PGVector chunks_vdb 向量相似度搜索。"""

    @pytest.mark.asyncio
    async def test_search_chunks_returns_chunk_records(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """search_chunks 返回包含正确字段值的 ChunkRecord。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(
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
    async def test_search_chunks_full_doc_id_nullable(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """ChunkRecord.full_doc_id 在 DB 返回 NULL 时为 None。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(
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
    """D-05: workspace 参数在所有查询中作为第一个参数传递。"""

    @pytest.mark.asyncio
    async def test_workspace_in_sql_params(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """Workspace 到达 cursor.execute 作为参数元组中的第一个值。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="ws_custom")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        # 参数元组中的第一个值 = workspace
        assert call_args[0][1][0] == "ws_custom"


# ---------------------------------------------------------------------------
# TestTableDiscovery
# ---------------------------------------------------------------------------


class TestTableDiscovery:
    """D-12 / D-13: 从 information_schema 自动发现 PGVector 表。"""

    @pytest.mark.asyncio
    async def test_discover_tables_success(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """_ensure_tables 正确发现并映射三个命名空间。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)

        # _ensure_tables → information_schema 查询
        mock_cursor.fetchall = AsyncMock(
            side_effect=[
                # 第一次调用: information_schema
                [
                    {"table_name": "lightrag_vdb_entity"},
                    {"table_name": "lightrag_vdb_relation"},
                    {"table_name": "lightrag_vdb_chunks"},
                ],
                # 第二次调用: 实际的 _vector_search（将为空）
                [],
            ]
        )

        store = _store_cls()(pool=mock_pool, workspace="default")
        # _tables 为 None — _ensure_tables 将查询
        assert store._tables is None

        tables = await store._ensure_tables()

        assert tables["ENTITY"] == "lightrag_vdb_entity"
        assert tables["RELATION"] == "lightrag_vdb_relation"
        assert tables["CHUNKS"] == "lightrag_vdb_chunks"
        assert store._tables is not None  # 已缓存

    @pytest.mark.asyncio
    async def test_discover_tables_multi_variant_error(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """单个命名空间存在多个后缀变体时抛出 RuntimeError (D-13)。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(
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
    async def test_discover_tables_no_table_error(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """零匹配表时抛出 RuntimeError 并给出指引。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

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
    """D-15: 只读强制 — 仅使用 fetchall()，不使用 execute() 进行写操作。"""

    @pytest.mark.asyncio
    async def test_uses_cursor_pattern(self, mock_pool, mock_conn, mock_cursor):
        """search_entities 调用 cursor.execute 和 cursor.fetchall。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        # 验证使用了 psycopg cursor 模式
        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called()
        # 验证通过 pool.connection() 获取了连接
        mock_pool.connection.assert_called()

    def test_no_write_methods_on_class(self):
        """PGVectorStore 类不暴露任何面向写入的方法名。"""
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
    """D-07: 依赖注入 — 注入的池覆盖模块级池。"""

    @pytest.mark.asyncio
    async def test_uses_injected_pool(self, mock_pool, mock_conn, mock_cursor):
        """PGVectorStore 使用注入的池，而非模块级池。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        # 验证注入了的 pool.connection() 被调用
        mock_pool.connection.assert_called()

    def test_falls_back_to_module_pool(self, mock_pool):
        """pool 属性在未注入池时返回模块级池。"""
        # 对模块级 _pool 进行 patch
        with patch(
            "lightrag_langchain.data.pool._pool", mock_pool
        ):
            store = _store_cls()(pool=None, workspace="default")
            # 属性应返回 patch 后的模块级池
            assert store.pool is mock_pool


# ---------------------------------------------------------------------------
# TestVectorParameters
# ---------------------------------------------------------------------------


class TestVectorParameters:
    """D-10: 预计算向量处理和余弦距离阈值计算。"""

    @pytest.mark.asyncio
    async def test_embedding_passed_as_list(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """embedding 以 float 列表形式传递给 cursor.execute（非生成）。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        # 参数元组: (workspace, closer_than, top_k, embedding)
        # embedding 是第四个参数 (index 3)
        embedding_arg = call_args[0][1][3]
        assert isinstance(embedding_arg, list)
        assert len(embedding_arg) == 1024
        assert all(isinstance(v, float) for v in embedding_arg)

    @pytest.mark.asyncio
    async def test_cosine_threshold_in_sql(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """closer_than = 1.0 - cosine_threshold 作为第二个参数传递。"""
        _wire_pool_for_psycopg(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall = AsyncMock(return_value=[])

        store = _store_cls()(pool=mock_pool, workspace="default")
        store._tables = {"ENTITY": "lightrag_vdb_entity"}

        await store.search_entities(_EMBEDDING_1024)

        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        # 参数元组: (workspace, embedding, closer_than, embedding, top_k)
        # closer_than 是第3个参数 (index 2)
        closer_than = call_args[0][1][2]
        # 默认 cosine_threshold = 0.2 → closer_than = 0.8
        assert closer_than == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# TestAsyncpgRemoved
# ---------------------------------------------------------------------------


class TestAsyncpgRemoved:
    """验证 store.py 中 asyncpg 导入和 acquire_with_retry 引用已完全移除。"""

    def test_no_asyncpg_imports(self):
        """store.py 不应包含任何 asyncpg 导入。"""
        import ast

        with open("src/lightrag_langchain/data/store.py") as f:
            source = f.read()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert "asyncpg" not in imports, f"store.py still imports asyncpg: {imports}"

    def test_no_acquire_with_retry_reference(self):
        """store.py 源代码不应引用 acquire_with_retry。"""
        with open("src/lightrag_langchain/data/store.py") as f:
            source = f.read()
        assert "acquire_with_retry" not in source, (
            "store.py should not reference acquire_with_retry"
        )
