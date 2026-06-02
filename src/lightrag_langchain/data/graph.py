"""lightrag-langchain 的 Apache AGE 图查询层。

提供 ``PGGraphStore`` — 对存储在 Apache AGE 图中 LightRAG 知识图谱的只读接口，
使用 ``base`` 节点标签和 ``DIRECTED`` 边标签。

查询方法：
- ``get_node(entity_id)`` → ``GraphNode | None``
- ``get_nodes_batch(entity_ids)`` → ``dict[str, GraphNode]``
- ``get_edge(src, tgt)`` → ``GraphEdge | None``
- ``get_edges_batch(pairs)`` → ``dict[tuple[str,str], GraphEdge]``
- ``get_node_edges(entity_id)`` → ``list[tuple[str,str]]``

所有 Cypher 查询使用 ``%s::agtype`` 参数化配合 ``json.dumps()`` —
不将用户提供的值进行字符串插值到 Cypher 中 (T-02-04-GRAPH-01)。

用法::

    from lightrag_langchain.data.graph import PGGraphStore

    store = PGGraphStore(graph_name="lightrag_graph")
    node = await store.get_node("entity-123")
"""

from __future__ import annotations

import itertools
import json
import re
import uuid
from typing import TYPE_CHECKING

from psycopg_pool import AsyncConnectionPool

from lightrag_langchain.config import settings
from lightrag_langchain.data import pool as _pool_module
from lightrag_langchain.data.models import GraphEdge, GraphNode

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# PGGraphStore
# ---------------------------------------------------------------------------


class PGGraphStore:
    """Apache AGE 知识图谱的只读查询层。

    Parameters
    ----------
    pool:
        psycopg AsyncConnectionPool 实例。当为 *None* 时，使用 ``data/pool.py`` 的模块级池（依赖注入，D-07）。
    graph_name:
        显式指定的 AGE 图名称。当为 *None* 时，名称在首次查询时从 ``workspace`` 延迟解析 (D-14)。
    workspace:
        用于派生图名称的 LightRAG workspace 名称。当为 *None* 时，使用 ``settings.pg.workspace`` (D-05)。
    """

    def __init__(
        self,
        pool: AsyncConnectionPool | None = None,
        graph_name: str | None = None,
        workspace: str | None = None,
    ) -> None:
        self._pool = pool
        self._workspace = workspace if workspace is not None else settings.pg.workspace
        # None means "resolve lazily"
        self._graph_name_resolved: str | None = graph_name

    # ------------------------------------------------------------------
    # Pool property (D-07 dependency injection)
    # ------------------------------------------------------------------

    @property
    def pool(self) -> AsyncConnectionPool:
        """返回注入的池或回退到模块级池。"""
        if self._pool is not None:
            return self._pool
        # Lazy access — __getattr__ raises RuntimeError if pool not initialized
        return _pool_module.pool

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dollar_quote(s: str, tag_prefix: str = "AGE") -> str:
        """生成带有无冲突标签的 PostgreSQL dollar-quoted 字符串。

        遍历 ``AGE1``、``AGE2``、... 直到找到一个不在 *s* 内出现的标签，
        防止 dollar-quote 嵌套冲突 (T-02-04-GRAPH-02)。
        如果 1000 次尝试耗尽，回退到基于 UUID 的标签。
        """
        content = "" if s is None else str(s)
        for i in itertools.count(1):
            tag = f"{tag_prefix}{i}"
            wrapper = f"${tag}$"
            if wrapper not in content:
                return f"{wrapper}{content}{wrapper}"
            # Safety valve — extremely unlikely to hit in practice
            if i > 1000:
                break
        # Fallback: random UUID tag
        fallback_tag = f"{tag_prefix}_{uuid.uuid4().hex}"
        wrapper = f"${fallback_tag}$"
        return f"{wrapper}{content}{wrapper}"

    @staticmethod
    def _parse_agtype(value: str) -> dict | None:
        """解析 AGE ``agtype`` 返回值。

        AGE 可能在 agtype 字符串后附加 ``::vertex`` 或 ``::edge`` 类型标记。
        此方法在 ``json.loads`` 之前去除这些后缀。
        对于空/仅空白/无法解析的输入返回 *None* (T-02-04-GRAPH-06)。
        """
        if value is None or not isinstance(value, str):
            return None
        stripped = value.strip()
        if not stripped:
            return None
        # Strip agtype suffix — take content before the **last** "::"
        if "::" in stripped:
            content = stripped.rsplit("::", 1)[0]
        else:
            content = stripped
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    async def _resolve_graph_name(self) -> str:
        """从 workspace 解析 AGE 图名称（延迟，缓存）。

        解析规则 (D-14)：
        - 如果 ``graph_name`` 已传入 ``__init__``，直接使用。
        - 如果 ``workspace`` 为 ``"default"`` 或空 → ``"lightrag_graph"``。
        - 否则 → ``{sanitized_workspace}_lightrag_graph``，其中清理操作将任何非字母数字/下划线字符替换为 ``"_"``。

        如果解析的名称在数据库中不存在，则从 ``ag_catalog.ag_graph`` 自动检测
        （优先选择带有 ``base`` 表的图）。
        """
        if self._graph_name_resolved is not None:
            return self._graph_name_resolved

        ws = self._workspace
        if not ws or ws == "default":
            name = "lightrag_graph"
        else:
            sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", ws)
            name = f"{sanitized}_lightrag_graph"

        # Verify the resolved name exists; auto-detect if not.
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT EXISTS(SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s)",
                        (name,),
                    )
                    row = await cur.fetchone()
                    exists = row[0] if row else False

                if not exists:
                    # Auto-detect: find a graph that has a base table
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "SELECT g.name FROM ag_catalog.ag_graph g "
                            "JOIN pg_tables t ON t.schemaname = g.name AND t.tablename = 'base' "
                            "ORDER BY g.name LIMIT 1"
                        )
                        row = await cur.fetchone()
                        detected: str | None = row[0] if row else None

                    if detected is None:
                        # Fallback: any graph
                        async with conn.cursor() as cur:
                            await cur.execute(
                                "SELECT name FROM ag_catalog.ag_graph ORDER BY name LIMIT 1"
                            )
                            row = await cur.fetchone()
                            detected = row[0] if row else None

                    if detected is not None:
                        name = detected
        except RuntimeError:
            # Pool not initialised — use workspace-derived name without
            # DB verification (safe for tests and offline contexts).
            pass

        self._graph_name_resolved = name
        return name

    # ------------------------------------------------------------------
    # Core AGE query wrapper
    # ------------------------------------------------------------------

    async def _query(
        self,
        cypher: str,
        params: dict | None = None,
        returns: str = "result agtype",
    ) -> list[dict]:
        """通过 ``SELECT * FROM cypher()`` 执行参数化的 AGE Cypher 查询。

        所有 Cypher 参数通过 ``json.dumps()`` 序列化并绑定为 ``%s::agtype``，
        防止 Cypher 注入 (T-02-04-GRAPH-01)。

        Parameters
        ----------
        cypher:
            Cypher 查询字符串（例如 ``"MATCH (n) RETURN n"``）。
        params:
            Cypher 参数绑定字典。
        returns:
            ``cypher()`` 函数的 ``AS (…)`` 返回列列表。
        """
        graph_name = await self._resolve_graph_name()

        graph_quoted = self._dollar_quote(graph_name)
        cypher_quoted = self._dollar_quote(cypher)

        sql = (
            f"SELECT * FROM cypher({graph_quoted}::name, "
            f"{cypher_quoted}::cstring, %s::agtype) "
            f"AS ({returns})"
        )

        pg_params = json.dumps(params or {}, ensure_ascii=False)

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (pg_params,))
                rows = await cur.fetchall()
                return [dict(row) for row in rows]

        # Unreachable
        return []  # pragma: no cover

    # ------------------------------------------------------------------
    # Public API — node queries
    # ------------------------------------------------------------------

    async def get_node(self, node_id: str) -> GraphNode | None:
        """通过 ``entity_id`` 检索单个图节点。

        如果不存在具有给定 ID 的节点，则返回 *None*。
        """
        cypher = (
            "MATCH (n:base {entity_id: $entity_id}) "
            "RETURN properties(n) AS props"
        )
        rows = await self._query(
            cypher,
            params={"entity_id": node_id},
            returns="props agtype",
        )

        if not rows:
            return None

        props = self._parse_agtype(rows[0].get("props", ""))
        if props is None:
            return None

        return GraphNode(
            entity_id=node_id,
            entity_type=props.get("entity_type", ""),
            description=props.get("description", ""),
            source_id=props.get("source_id", ""),
        )

    async def get_nodes_batch(self, node_ids: list[str]) -> dict[str, GraphNode]:
        """在单个参数化查询中检索多个图节点。

        使用 ``UNNEST`` + ``ag_catalog.agtype_access_operator`` 进行
        高效的批量查找。返回将 ``entity_id`` 映射到 ``GraphNode`` 的 ``dict``。
        不存在的节点将被静默省略。
        """
        if not node_ids:
            return {}

        graph_name = await self._resolve_graph_name()

        age_schema = settings.pg.age_schema

        sql = f"""
            WITH input(v, ord) AS (
              SELECT v, ord
              FROM unnest(%s::text[]) WITH ORDINALITY AS t(v, ord)
            ),
            ids(node_id, ord) AS (
              SELECT (to_json(v)::text)::{age_schema}.agtype AS node_id, ord
              FROM input
            )
            SELECT i.node_id::text AS node_id,
                   b.properties
            FROM {graph_name}.base AS b
            JOIN ids i
              ON {age_schema}.agtype_access_operator(
                   VARIADIC ARRAY[b.properties, '"entity_id"'::{age_schema}.agtype]
                 ) = i.node_id
            ORDER BY i.ord
        """

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (node_ids,))
                rows = await cur.fetchall()

        result: dict[str, GraphNode] = {}
        for row in rows:
            nid_raw = row["node_id"]
            # AGE may return agtype text with surrounding quotes — strip them
            if isinstance(nid_raw, str):
                nid = nid_raw.strip('"')
            else:
                nid = str(nid_raw)

            props = self._parse_agtype(row["properties"])
            if props is None:
                continue

            result[nid] = GraphNode(
                entity_id=nid,
                entity_type=props.get("entity_type", ""),
                description=props.get("description", ""),
                source_id=props.get("source_id", ""),
            )

        return result

    # ------------------------------------------------------------------
    # Public API — edge queries
    # ------------------------------------------------------------------

    async def get_edge(self, src: str, tgt: str) -> GraphEdge | None:
        """检索两个实体节点之间的单个有向边。

        如果不存在从 *src* 到 *tgt* 的边，则返回 *None*。
        """
        cypher = (
            "MATCH (a:base {entity_id: $src})-[r:DIRECTED]->(b:base {entity_id: $tgt}) "
            "RETURN properties(r) AS props"
        )
        rows = await self._query(
            cypher,
            params={"src": src, "tgt": tgt},
            returns="props agtype",
        )

        if not rows:
            return None

        props = self._parse_agtype(rows[0].get("props", ""))
        if props is None:
            return None

        return GraphEdge(
            source_id=src,
            target_id=tgt,
            description=props.get("description"),
            keywords=props.get("keywords"),
            weight=props.get("weight"),
        )

    async def get_edges_batch(
        self, pairs: list[dict[str, str]]
    ) -> dict[tuple[str, str], GraphEdge]:
        """在单个 UNWIND Cypher 查询中检索多个有向边。

        对于小批量（<= 10 对），回退到顺序 ``get_edge`` 调用。
        对于大批量，使用 ``UNWIND $pairs``。

        返回将 ``(source_id, target_id)`` 元组映射到 ``GraphEdge`` 的 ``dict``。
        """
        if not pairs:
            return {}

        # Small batch — sequential lookups avoid UNWIND overhead
        if len(pairs) <= 10:
            result: dict[tuple[str, str], GraphEdge] = {}
            for pair in pairs:
                edge = await self.get_edge(pair["src"], pair["tgt"])
                if edge is not None:
                    result[(edge.source_id, edge.target_id)] = edge
            return result

        # Large batch — UNWIND Cypher
        cypher = (
            "UNWIND $pairs AS pair "
            "MATCH (a:base {entity_id: pair.src})-[r:DIRECTED]->(b:base {entity_id: pair.tgt}) "
            "RETURN pair.src AS source_id, pair.tgt AS target_id, properties(r) AS props"
        )
        rows = await self._query(
            cypher,
            params={"pairs": pairs},
            returns="source_id text, target_id text, props agtype",
        )

        result = {}
        for row in rows:
            src = row.get("source_id", "")
            tgt = row.get("target_id", "")
            props = self._parse_agtype(row.get("props", ""))

            if props is None:
                continue

            result[(src, tgt)] = GraphEdge(
                source_id=src,
                target_id=tgt,
                description=props.get("description"),
                keywords=props.get("keywords"),
                weight=props.get("weight"),
            )

        return result

    # ------------------------------------------------------------------
    # Public API — neighbor traversal
    # ------------------------------------------------------------------

    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]]:
        """返回节点的所有 ``(source_id, connected_id)`` 邻居对。

        使用 ``OPTIONAL MATCH`` — 当节点没有邻居时，结果为空列表（不是 ``[(node_id, None)]``）。
        """
        cypher = (
            "MATCH (n:base {entity_id: $entity_id}) "
            "OPTIONAL MATCH (n)-[]-(connected:base) "
            "RETURN n.entity_id AS source_id, connected.entity_id AS connected_id"
        )
        rows = await self._query(
            cypher,
            params={"entity_id": node_id},
            returns="source_id text, connected_id text",
        )

        result: list[tuple[str, str]] = []
        for row in rows:
            cid = row.get("connected_id")
            if cid is not None:
                result.append((row["source_id"], cid))
        return result
