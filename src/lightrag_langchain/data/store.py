"""PGVectorStore — 基于 LightRAG PGVector 表的只读向量相似度搜索。

提供基于 LightRAG ``lightrag_vdb_entity_*``、``lightrag_vdb_relation_*`` 和 ``lightrag_vdb_chunks_*``
表的 entity、relationship 和 chunk 向量搜索。使用数据层 pool 模块的 psycopg 连接池，
并通过 ``information_schema`` 自动发现表名。

用法::

    from lightrag_langchain.data.store import PGVectorStore

    store = PGVectorStore()
    entities = await store.search_entities(embedding=[0.1] * 1024)
    relations = await store.search_relationships(embedding=[0.1] * 1024)
    chunks = await store.search_chunks(embedding=[0.1] * 1024)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg_pool import AsyncConnectionPool

from lightrag_langchain.config import settings
from lightrag_langchain.data.models import ChunkRecord, EntityRecord, RelationshipRecord

if TYPE_CHECKING:
    pass


class PGVectorStore:
    """基于 LightRAG PGVector 表的只读向量相似度搜索。

    使用 pgvector 的 ``<=>``（余弦距离）运算符搜索 ``entities_vdb``、``relationships_vdb``
    和 ``chunks_vdb``，支持 workspace 过滤 (D-05)、参数化查询 (D-10 / D-15) 和连接重试。

    表名在首次查询时从 ``information_schema.tables`` 自动发现 (D-12)。
    单个命名空间出现多个后缀变体会抛出 ``RuntimeError`` 并给出可操作的指导 (D-13)。

    Parameters
    ----------
    pool:
        可选的 psycopg ``AsyncConnectionPool`` 用于依赖注入 (D-07)。当为 *None* 时，使用
        ``lightrag_langchain.data.pool`` 的模块级单例池。
    workspace:
        Workspace 隔离命名空间 (D-05)。当为 *None* 时默认为 ``settings.pg.workspace``。
    table_prefix:
        用于在 ``information_schema`` 中发现 PGVector 表的前缀。
        默认为 ``"lightrag_vdb"``。
    """

    def __init__(
        self,
        pool: AsyncConnectionPool | None = None,
        workspace: str | None = None,
        table_prefix: str = "lightrag_vdb",
    ) -> None:
        self._pool = pool
        self._workspace = (
            workspace if workspace is not None else settings.pg.workspace
        )
        self._table_prefix = table_prefix
        self._tables: dict[str, str] | None = None
        self._cosine_threshold = settings.query_params.cosine_threshold
        self._default_top_k = settings.query_params.top_k

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def pool(self) -> AsyncConnectionPool:
        """返回活跃连接池。

        当依赖注入的池可用时返回它 (D-07)，否则回退到模块级单例池。
        当两者都不可用时抛出 ``RuntimeError``。
        """
        if self._pool is not None:
            return self._pool

        import lightrag_langchain.data.pool as _pool_mod

        return _pool_mod.pool  # __getattr__ raises RuntimeError if uninitialised

    # ------------------------------------------------------------------
    # Table discovery (D-12, D-13)
    # ------------------------------------------------------------------

    async def _ensure_tables(self) -> dict[str, str]:
        """通过 ``information_schema`` 发现 LightRAG PGVector 表名。

        首次成功调用后将结果缓存在 ``self._tables`` 中，
        以便后续查询避免元数据往返。

        Returns
        -------
        dict[str, str]
            命名空间名到完整表名的映射，例如
            ``{"ENTITY": "lightrag_vdb_entity_text_embedding_v4_1024d", ...}``。

        Raises
        ------
        RuntimeError
            - 未找到某个命名空间的表（数据库未初始化）。
            - 单个命名空间存在多个后缀变体（歧义需要 ``.env`` 中的 ``PG_TABLE_SUFFIX``）。
        """
        if self._tables is not None:
            return self._tables

        pattern = self._table_prefix + "%"
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name ILIKE %s
            ORDER BY table_name
        """

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (pattern,))
                rows = await cur.fetchall()

        # Build namespace -> table_name categories from the system-catalog
        # whitelist (T-02-03-STORE-01: only lightrag_vdb_* prefixed tables).
        prefix = self._table_prefix
        namespaces: dict[str, list[str]] = {
            "ENTITY": [],
            "RELATION": [],
            "CHUNKS": [],
        }

        for row in rows:
            name: str = row["table_name"]
            # ENTITY: exact match or suffix variant (case-insensitive)
            name_lower = name.lower()
            prefix_lower = prefix.lower()
            if name_lower == f"{prefix_lower}_entity" or name_lower.startswith(
                f"{prefix_lower}_entity_"
            ):
                namespaces["ENTITY"].append(name)
            # RELATION: exact match or suffix variant (case-insensitive)
            elif name_lower == f"{prefix_lower}_relation" or name_lower.startswith(
                f"{prefix_lower}_relation_"
            ):
                namespaces["RELATION"].append(name)
            # CHUNKS: exact match or suffix variant (case-insensitive)
            elif name_lower == f"{prefix_lower}_chunks" or name_lower.startswith(
                f"{prefix_lower}_chunks_"
            ):
                namespaces["CHUNKS"].append(name)
            # Non-matching tables are silently ignored

        result: dict[str, str] = {}
        for ns, tables in namespaces.items():
            if len(tables) > 1:
                raise RuntimeError(
                    f"Multiple {ns} vector tables found: {tables!r}. "
                    f"Specify PG_TABLE_SUFFIX in .env to disambiguate."
                )
            if len(tables) == 0:
                raise RuntimeError(
                    f"No {ns} table found with prefix '{prefix}'. "
                    f"Is the LightRAG database initialised?"
                )
            result[ns] = tables[0]

        self._tables = result
        return result

    # ------------------------------------------------------------------
    # Generic vector search (parameterised, read-only)
    # ------------------------------------------------------------------

    async def _vector_search(
        self,
        table_name: str,
        embedding: list[float],
        top_k: int,
        select_clause: str,
    ) -> list[dict[str, Any]]:
        """通用参数化 PGVector 余弦距离搜索。

        使用 ``content_vector <=> %s::vector < %s`` 进行服务器端索引加速过滤，
        配合 ``%s``（workspace）和 ``%s``（LIMIT）。
        """
        closer_than = 1.0 - self._cosine_threshold
        sql = (
            f"{select_clause} "
            f"FROM {table_name} "
            f"WHERE workspace = %s "
            f"AND content_vector <=> %s::vector < %s "
            f"ORDER BY content_vector <=> %s::vector "
            f"LIMIT %s"
        )

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql,
                    (
                        self._workspace,
                        embedding,
                        closer_than,
                        embedding,
                        top_k,
                    ),
                )
                rows = await cur.fetchall()

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Public search methods — Entities (STOR-01)
    # ------------------------------------------------------------------

    async def search_entities(
        self,
        embedding: list[float],
        top_k: int | None = None,
    ) -> list[EntityRecord]:
        """LightRAG 实体向量表上的向量相似度搜索。

        Parameters
        ----------
        embedding:
            预计算的 embedding 向量 (D-10)。PGVectorStore 不生成 embedding — 仅接收它们。
        top_k:
            最大结果数。默认为 ``settings.query_params.top_k``。

        Returns
        -------
        list[EntityRecord]
            排序的实体记录，最接近的匹配排在最前。
        """
        top_k = self._default_top_k if top_k is None else top_k
        await self._ensure_tables()

        select_clause = (
            "SELECT entity_name, content, id AS source_id, "
            "COALESCE(file_path, '') AS file_path, "
            "EXTRACT(EPOCH FROM create_time)::BIGINT AS created_at"
        )
        rows = await self._vector_search(
            self._tables["ENTITY"], embedding, top_k, select_clause  # type: ignore[index]
        )
        return [EntityRecord(**row) for row in rows]

    # ------------------------------------------------------------------
    # Public search methods — Relationships (STOR-02)
    # ------------------------------------------------------------------

    async def search_relationships(
        self,
        embedding: list[float],
        top_k: int | None = None,
    ) -> list[RelationshipRecord]:
        """LightRAG 关系向量表上的向量相似度搜索。

        ``keywords`` 和 ``weight`` 返回为 ``None``，因为 ``lightrag_vdb_relation`` DDL
        不包含这些列（RESEARCH.md A1）。真实值可从 AGE 图边获取
        (Plan 02-04 PGGraphStore)。

        Parameters
        ----------
        embedding:
            预计算的 embedding 向量 (D-10)。
        top_k:
            最大结果数。默认为 ``settings.query_params.top_k``。

        Returns
        -------
        list[RelationshipRecord]
            排序的关系记录，最接近的匹配排在最前。
        """
        top_k = self._default_top_k if top_k is None else top_k
        await self._ensure_tables()

        select_clause = (
            "SELECT source_id AS src_id, target_id AS tgt_id, content, "
            "NULL::text AS keywords, NULL::float8 AS weight, "
            "EXTRACT(EPOCH FROM create_time)::BIGINT AS created_at"
        )
        rows = await self._vector_search(
            self._tables["RELATION"], embedding, top_k, select_clause  # type: ignore[index]
        )
        return [RelationshipRecord(**row) for row in rows]

    # ------------------------------------------------------------------
    # Public search methods — Chunks (STOR-03)
    # ------------------------------------------------------------------

    async def search_chunks(
        self,
        embedding: list[float],
        top_k: int | None = None,
    ) -> list[ChunkRecord]:
        """LightRAG chunks 向量表上的向量相似度搜索。

        Parameters
        ----------
        embedding:
            预计算的 embedding 向量 (D-10)。
        top_k:
            最大结果数。默认为 ``settings.query_params.top_k``。

        Returns
        -------
        list[ChunkRecord]
            排序的 chunk 记录，最接近的匹配排在最前。
        """
        top_k = self._default_top_k if top_k is None else top_k
        await self._ensure_tables()

        select_clause = (
            "SELECT id AS chunk_id, content, full_doc_id, chunk_order_index, "
            "COALESCE(file_path, '') AS file_path"
        )
        rows = await self._vector_search(
            self._tables["CHUNKS"], embedding, top_k, select_clause  # type: ignore[index]
        )
        return [ChunkRecord(**row) for row in rows]
