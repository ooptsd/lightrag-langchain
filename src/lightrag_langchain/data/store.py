"""PGVectorStore — read-only vector similarity search over LightRAG PGVector tables.

Provides entity, relationship, and chunk vector search backed by the LightRAG
``lightrag_vdb_entity_*``, ``lightrag_vdb_relation_*``, and ``lightrag_vdb_chunks_*``
tables.  Uses asyncpg connection pools from the data layer's pool module, with
automatic table-name discovery via ``information_schema``.

Usage::

    from lightrag_langchain.data.store import PGVectorStore

    store = PGVectorStore()
    entities = await store.search_entities(embedding=[0.1] * 1024)
    relations = await store.search_relationships(embedding=[0.1] * 1024)
    chunks = await store.search_chunks(embedding=[0.1] * 1024)
"""

from __future__ import annotations

from typing import Any

import asyncpg

from lightrag_langchain.config import settings
from lightrag_langchain.data.models import ChunkRecord, EntityRecord, RelationshipRecord
from lightrag_langchain.data.pool import acquire_with_retry


class PGVectorStore:
    """Read-only vector similarity search over LightRAG PGVector tables.

    Searches ``entities_vdb``, ``relationships_vdb``, and ``chunks_vdb`` using
    pgvector's ``<=>`` (cosine distance) operator with workspace filtering (D-05),
    parameterized queries (D-10 / D-15), and connection retry (D-06).

    Table names are auto-discovered from ``information_schema.tables`` at first
    query time (D-12).  Multiple suffix variants for a single namespace raise
    ``RuntimeError`` with actionable guidance (D-13).

    Parameters
    ----------
    pool:
        Optional asyncpg ``Pool`` for dependency injection (D-07).  When *None*
        the module-level singleton pool from ``lightrag_langchain.data.pool`` is
        used.
    workspace:
        Workspace isolation namespace (D-05).  Defaults to
        ``settings.pg.workspace`` when *None*.
    table_prefix:
        Prefix used to discover PGVector tables in ``information_schema``.
        Defaults to ``"lightrag_vdb"``.
    """

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
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
    def pool(self) -> asyncpg.Pool:
        """Return the active connection pool.

        Returns the dependency-injected pool when available (D-07), otherwise
        falls back to the module-level singleton pool.  Raises ``RuntimeError``
        when neither pool is available.
        """
        if self._pool is not None:
            return self._pool

        import lightrag_langchain.data.pool as _pool_mod

        return _pool_mod.pool  # __getattr__ raises RuntimeError if uninitialised

    # ------------------------------------------------------------------
    # Table discovery (D-12, D-13)
    # ------------------------------------------------------------------

    async def _ensure_tables(self) -> dict[str, str]:
        """Discover LightRAG PGVector table names via ``information_schema``.

        Caches the result in ``self._tables`` after the first successful call
        so that subsequent queries avoid the metadata round-trip.

        Returns
        -------
        dict[str, str]
            Mapping of namespace name to full table name, e.g.
            ``{"ENTITY": "lightrag_vdb_entity_text_embedding_v4_1024d", ...}``.

        Raises
        ------
        RuntimeError
            - No table found for a namespace (database not initialised).
            - Multiple suffix variants exist for a single namespace (ambiguity
              requires ``PG_TABLE_SUFFIX`` in ``.env``).
        """
        if self._tables is not None:
            return self._tables

        pattern = self._table_prefix + "%"
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name ILIKE $1
            ORDER BY table_name
        """

        async for conn in acquire_with_retry(self.pool):
            rows = await conn.fetch(sql, pattern)

        # Build namespace → table_name categories from the system-catalog
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
            # Non-matching tables are silently ignored — they belong to
            # other LightRAG subsystems (KV, doc status, etc.).

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
        """Generic parameterised PGVector cosine-distance search.

        Uses ``content_vector <=> $4::vector < $2`` for server-side index-
        accelerated filtering, with ``$1`` (workspace) and ``$3`` (LIMIT).

        ``acquire_with_retry`` handles transient connection errors (D-06).
        Only ``conn.fetch()`` is called — no ``execute()`` (D-15 read-only).
        """
        closer_than = 1.0 - self._cosine_threshold
        sql = (
            f"{select_clause} "
            f"FROM {table_name} "
            f"WHERE workspace = $1 "
            f"AND content_vector <=> $4::vector < $2 "
            f"ORDER BY content_vector <=> $4::vector "
            f"LIMIT $3"
        )

        async for conn in acquire_with_retry(self.pool):
            rows = await conn.fetch(
                sql,
                self._workspace,
                closer_than,
                top_k,
                embedding,
            )

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Public search methods — Entities (STOR-01)
    # ------------------------------------------------------------------

    async def search_entities(
        self,
        embedding: list[float],
        top_k: int | None = None,
    ) -> list[EntityRecord]:
        """Vector similarity search on the LightRAG entities vector table.

        Parameters
        ----------
        embedding:
            Pre-computed embedding vector (D-10).  PGVectorStore does NOT
            generate embeddings — it only receives them.
        top_k:
            Maximum number of results.  Defaults to ``settings.query_params.top_k``.

        Returns
        -------
        list[EntityRecord]
            Ranked entity records, closest match first.
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
        """Vector similarity search on the LightRAG relationships vector table.

        ``keywords`` and ``weight`` are returned as ``None`` because the
        ``lightrag_vdb_relation`` DDL does not contain those columns
        (RESEARCH.md A1).  Real values are available from AGE graph edges
        (Plan 02-04 PGGraphStore).

        Parameters
        ----------
        embedding:
            Pre-computed embedding vector (D-10).
        top_k:
            Maximum number of results.  Defaults to ``settings.query_params.top_k``.

        Returns
        -------
        list[RelationshipRecord]
            Ranked relationship records, closest match first.
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
        """Vector similarity search on the LightRAG chunks vector table.

        Parameters
        ----------
        embedding:
            Pre-computed embedding vector (D-10).
        top_k:
            Maximum number of results.  Defaults to ``settings.query_params.top_k``.

        Returns
        -------
        list[ChunkRecord]
            Ranked chunk records, closest match first.
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
