"""Apache AGE graph query layer for lightrag-langchain.

Provides ``PGGraphStore`` — a read-only interface to the LightRAG knowledge
graph stored in an Apache AGE graph under a ``base`` node label and
``DIRECTED`` edge label.

Query methods:
- ``get_node(entity_id)`` → ``GraphNode | None``
- ``get_nodes_batch(entity_ids)`` → ``dict[str, GraphNode]``
- ``get_edge(src, tgt)`` → ``GraphEdge | None``
- ``get_edges_batch(pairs)`` → ``dict[tuple[str,str], GraphEdge]``
- ``get_node_edges(entity_id)`` → ``list[tuple[str,str]]``

All Cypher queries use ``$1::agtype`` parameterisation with ``json.dumps()`` —
no string interpolation of user-supplied values into Cypher (T-02-04-GRAPH-01).

Usage::

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

from lightrag_langchain.config import settings
from lightrag_langchain.data import pool as _pool_module
from lightrag_langchain.data.models import GraphEdge, GraphNode
from lightrag_langchain.data.pool import acquire_with_retry

if TYPE_CHECKING:
    from asyncpg import Pool, Record


# ---------------------------------------------------------------------------
# PGGraphStore
# ---------------------------------------------------------------------------


class PGGraphStore:
    """Read-only query layer for the Apache AGE knowledge graph.

    Parameters
    ----------
    pool:
        asyncpg Pool instance.  When *None* the module-level pool from
        ``data/pool.py`` is used (dependency injection, D-07).
    graph_name:
        Explicit AGE graph name.  When *None* the name is resolved lazily
        from ``workspace`` on first query (D-14).
    workspace:
        LightRAG workspace name used to derive the graph name.  When *None*
        ``settings.pg.workspace`` is used (D-05).
    """

    def __init__(
        self,
        pool: Pool | None = None,
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
    def pool(self) -> Pool:
        """Return the injected pool or fall back to the module-level pool."""
        if self._pool is not None:
            return self._pool
        # Lazy access — __getattr__ raises RuntimeError if pool not initialized
        return _pool_module.pool

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dollar_quote(s: str, tag_prefix: str = "AGE") -> str:
        """Generate a PostgreSQL dollar-quoted string with a collision-free tag.

        Iterates ``AGE1``, ``AGE2``, … until a tag is found that does not
        appear inside *s*, preventing dollar-quote nesting conflicts
        (T-02-04-GRAPH-02).  Falls back to a UUID-based tag if 1000
        attempts are exhausted.
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
        """Parse an AGE ``agtype`` return value.

        AGE may suffix agtype strings with ``::vertex`` or ``::edge`` type
        markers.  This method strips those suffixes before ``json.loads``.
        Returns *None* for empty / whitespace-only / unparseable input
        (T-02-04-GRAPH-06).
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
        """Resolve the AGE graph name from workspace (lazy, cached).

        Resolution rules (D-14):
        - If ``graph_name`` was passed to ``__init__``, use it as-is.
        - If ``workspace`` is ``"default"`` or empty → ``"lightrag_graph"``.
        - Otherwise → ``{sanitized_workspace}_lightrag_graph``, where
          sanitization replaces any non-alphanumeric/underscore character
          with ``"_"``.

        If the resolved name does not exist in the database, auto-detects
        from ``ag_catalog.ag_graph`` (preferring graphs with a ``base`` table).
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
        # When pool is not yet initialised (e.g. in tests), skip DB verification
        # and use the resolved name as-is.
        try:
            async for conn in acquire_with_retry(self.pool):
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM ag_catalog.ag_graph WHERE name = $1)",
                    name,
                )
                if not exists:
                    # Auto-detect: find a graph that has a base table
                    detected: str | None = await conn.fetchval(
                        "SELECT g.name FROM ag_catalog.ag_graph g "
                        "JOIN pg_tables t ON t.schemaname = g.name AND t.tablename = 'base' "
                        "ORDER BY g.name LIMIT 1"
                    )
                    if detected is None:
                        # Fallback: any graph
                        detected = await conn.fetchval(
                            "SELECT name FROM ag_catalog.ag_graph ORDER BY name LIMIT 1"
                        )
                    if detected is not None:
                        name = detected
                break
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
        """Execute a parameterised AGE Cypher query via ``SELECT * FROM cypher()``.

        All Cypher parameters are serialised via ``json.dumps()`` and bound
        as ``$1::agtype``, preventing Cypher injection (T-02-04-GRAPH-01).

        Parameters
        ----------
        cypher:
            The Cypher query string (e.g. ``"MATCH (n) RETURN n"``).
        params:
            Dictionary of Cypher parameter bindings.
        returns:
            The ``AS (…)`` return column list for the ``cypher()`` function.
        """
        graph_name = await self._resolve_graph_name()

        graph_quoted = self._dollar_quote(graph_name)
        cypher_quoted = self._dollar_quote(cypher)

        sql = (
            f"SELECT * FROM cypher({graph_quoted}::name, "
            f"{cypher_quoted}::cstring, $1::agtype) "
            f"AS ({returns})"
        )

        pg_params = json.dumps(params or {}, ensure_ascii=False)

        async for conn in acquire_with_retry(self.pool):
            rows: list[Record] = await conn.fetch(sql, pg_params)
            return [dict(row) for row in rows]

        # Unreachable — acquire_with_retry either yields or raises
        return []  # pragma: no cover

    # ------------------------------------------------------------------
    # Public API — node queries
    # ------------------------------------------------------------------

    async def get_node(self, node_id: str) -> GraphNode | None:
        """Retrieve a single graph node by ``entity_id``.

        Returns *None* if no node with the given ID exists.
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
        """Retrieve multiple graph nodes in a single parameterised query.

        Uses ``UNNEST`` + ``ag_catalog.agtype_access_operator`` for
        efficient batch lookup.  Returns a ``dict`` mapping ``entity_id``
        to ``GraphNode``.  Nodes that do not exist are silently omitted.
        """
        if not node_ids:
            return {}

        graph_name = await self._resolve_graph_name()

        age_schema = settings.pg.age_schema

        sql = f"""
            WITH input(v, ord) AS (
              SELECT v, ord
              FROM unnest($1::text[]) WITH ORDINALITY AS t(v, ord)
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

        async for conn in acquire_with_retry(self.pool):
            rows: list[Record] = await conn.fetch(sql, node_ids)
            break

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
        """Retrieve a single directed edge between two entity nodes.

        Returns *None* if no edge exists from *src* to *tgt*.
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
        """Retrieve multiple directed edges in a single UNWIND Cypher query.

        For small batches (<= 10 pairs) falls back to sequential
        ``get_edge`` calls.  For larger batches uses ``UNWIND $pairs``.

        Returns a ``dict`` mapping ``(source_id, target_id)`` tuples to
        ``GraphEdge``.
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
        """Return all ``(source_id, connected_id)`` neighbour pairs for a node.

        Uses ``OPTIONAL MATCH`` — when a node has no neighbours the result
        is an empty list (not ``[(node_id, None)]``).
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
