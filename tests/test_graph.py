"""Comprehensive unit test suite for PGGraphStore (AGE graph query layer).

Covers:
- Node retrieval: get_node, get_nodes_batch
- Edge retrieval: get_edge, get_edges_batch
- Neighbor traversal: get_node_edges
- agtype parsing (::vertex / ::edge suffix stripping)
- Dollar-quote generation (collision avoidance)
- Read-only enforcement (fetch vs execute)
- Graph name resolution from workspace
- Cypher parameterization safety ($1::agtype, no string interpolation)

All asyncpg calls are mocked — no real database connection is made.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.models import GraphEdge, GraphNode

# ---------------------------------------------------------------------------
# Auto-use fixture: env vars for Settings instantiation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """Set required env vars so ``settings`` can be instantiated.

    Some tests (graph name resolution) access ``settings.pg.workspace`` via
    the PGGraphStore constructor.  This fixture ensures Settings can load
    even though most graph tests inject a ``graph_name`` directly.
    """
    required_vars = {
        "pg__host": "localhost",
        "pg__port": "5432",
        "pg__user": "test",
        "pg__password": "secret",
        "pg__database": "testdb",
        "llm__binding": "openai",
        "llm__binding_host": "https://api.openai.com/v1",
        "llm__binding_api_key": "sk-test",
        "llm__model": "gpt-4o-mini",
        "embedding__binding": "openai",
        "embedding__binding_host": "https://api.openai.com/v1",
        "embedding__binding_api_key": "sk-emb",
        "embedding__model": "text-embedding-3-small",
    }
    for k, v in required_vars.items():
        monkeypatch.setenv(k, v)

    # Reset cached Settings singleton so it picks up monkeypatched env vars
    import lightrag_langchain.config as cfg

    cfg._settings = None


# ---------------------------------------------------------------------------
# Helper: wire mocks for acquire_with_retry (direct acquire, not context mgr)
# ---------------------------------------------------------------------------


def _wire_mocks(mock_pool, mock_conn):
    """Configure mock_pool for ``acquire_with_retry`` usage.

    ``acquire_with_retry`` calls ``await pool.acquire()`` directly (not
    ``async with pool.acquire() as conn``), so we replace the fixture's
    context-manager setup with a direct AsyncMock returning ``mock_conn``.
    """
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_pool.release = AsyncMock()


# ===================================================================
# TestGetNode
# ===================================================================


class TestGetNode:
    """``get_node(entity_id)`` — single node retrieval."""

    @pytest.mark.asyncio
    async def test_get_node_returns_graph_node(self, mock_pool, mock_conn):
        """Returns a GraphNode when the entity exists in the AGE graph."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "props": json.dumps(
                    {
                        "entity_type": "Person",
                        "description": "A person entity",
                        "source_id": "doc42",
                    }
                )
            }
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        node = await store.get_node("n1")

        assert node is not None
        assert isinstance(node, GraphNode)
        assert node.entity_id == "n1"
        assert node.entity_type == "Person"
        assert node.description == "A person entity"
        assert node.source_id == "doc42"

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, mock_pool, mock_conn):
        """Returns None when no node with the given entity_id exists."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = []

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        node = await store.get_node("nonexistent")

        assert node is None

    @pytest.mark.asyncio
    async def test_get_node_null_properties(self, mock_pool, mock_conn):
        """Returns None when query returns a row but props are None."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [{"props": ""}]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        node = await store.get_node("n1")

        assert node is None


# ===================================================================
# TestGetNodesBatch
# ===================================================================


class TestGetNodesBatch:
    """``get_nodes_batch(node_ids)`` — batch node retrieval."""

    @pytest.mark.asyncio
    async def test_get_nodes_batch_returns_dict(self, mock_pool, mock_conn):
        """Returns a dict mapping entity_id -> GraphNode for found nodes."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "node_id": '"n1"',
                "properties": json.dumps(
                    {"entity_type": "Person", "description": "Desc 1", "source_id": "s1"}
                ),
            },
            {
                "node_id": '"n2"',
                "properties": json.dumps(
                    {
                        "entity_type": "Organization",
                        "description": "Desc 2",
                        "source_id": "s2",
                    }
                ),
            },
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        result = await store.get_nodes_batch(["n1", "n2"])

        assert isinstance(result, dict)
        assert len(result) == 2
        assert "n1" in result
        assert "n2" in result
        assert result["n1"].entity_type == "Person"
        assert result["n2"].entity_type == "Organization"
        assert isinstance(result["n1"], GraphNode)
        assert isinstance(result["n2"], GraphNode)

    @pytest.mark.asyncio
    async def test_get_nodes_batch_empty_input(self, mock_pool, mock_conn):
        """Returns empty dict without any database call when node_ids is empty."""
        _wire_mocks(mock_pool, mock_conn)

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        result = await store.get_nodes_batch([])

        assert result == {}
        # No database call should have been made
        mock_conn.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_nodes_batch_partial_match(self, mock_pool, mock_conn):
        """Only found nodes appear in result; missing nodes are silently omitted."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "node_id": '"n1"',
                "properties": json.dumps(
                    {"entity_type": "Person", "description": "Only one", "source_id": "s1"}
                ),
            }
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        result = await store.get_nodes_batch(["n1", "n2"])

        assert len(result) == 1
        assert "n1" in result
        assert "n2" not in result

    @pytest.mark.asyncio
    async def test_get_nodes_batch_strips_quotes(self, mock_pool, mock_conn):
        """Node IDs returned by AGE with surrounding double-quotes are stripped."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "node_id": '"entity-with-quotes"',
                "properties": json.dumps(
                    {"entity_type": "Thing", "description": "", "source_id": ""}
                ),
            }
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        result = await store.get_nodes_batch(["entity-with-quotes"])

        assert "entity-with-quotes" in result
        # The key should NOT have quotes
        assert '"entity-with-quotes"' not in result


# ===================================================================
# TestGetEdge
# ===================================================================


class TestGetEdge:
    """``get_edge(src, tgt)`` — single edge retrieval."""

    @pytest.mark.asyncio
    async def test_get_edge_returns_graph_edge(self, mock_pool, mock_conn):
        """Returns a GraphEdge when a directed edge exists between two entities."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "props": json.dumps(
                    {
                        "description": "works at",
                        "keywords": "employer",
                        "weight": 0.9,
                    }
                )
            }
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        edge = await store.get_edge("a", "b")

        assert edge is not None
        assert isinstance(edge, GraphEdge)
        assert edge.source_id == "a"
        assert edge.target_id == "b"
        assert edge.description == "works at"
        assert edge.keywords == "employer"
        assert edge.weight == 0.9

    @pytest.mark.asyncio
    async def test_get_edge_not_found(self, mock_pool, mock_conn):
        """Returns None when no edge exists from src to tgt."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = []

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        edge = await store.get_edge("a", "c")

        assert edge is None

    @pytest.mark.asyncio
    async def test_get_edge_null_props_returns_none(self, mock_pool, mock_conn):
        """Returns None when query returns a row but props cannot be parsed."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [{"props": ""}]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        edge = await store.get_edge("a", "b")

        assert edge is None

    @pytest.mark.asyncio
    async def test_get_edge_optional_fields_none(self, mock_pool, mock_conn):
        """Edge optional fields (description, keywords, weight) may be None."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {"props": json.dumps({"description": "linked"})}
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        edge = await store.get_edge("x", "y")

        assert edge is not None
        assert edge.description == "linked"
        assert edge.keywords is None
        assert edge.weight is None


# ===================================================================
# TestGetEdgesBatch
# ===================================================================


class TestGetEdgesBatch:
    """``get_edges_batch(pairs)`` — batch edge retrieval."""

    @pytest.mark.asyncio
    async def test_get_edges_batch_empty_input(self, mock_pool, mock_conn):
        """Returns empty dict without any database call when pairs is empty."""
        _wire_mocks(mock_pool, mock_conn)

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        result = await store.get_edges_batch([])

        assert result == {}
        mock_conn.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_edges_batch_small_sequential(self, mock_pool, mock_conn):
        """Small batch (<=10 pairs) uses sequential get_edge calls."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "props": json.dumps(
                    {"description": "related", "keywords": "kw", "weight": 0.5}
                )
            }
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        pairs = [{"src": "a", "tgt": "b"}, {"src": "c", "tgt": "d"}]
        result = await store.get_edges_batch(pairs)

        assert len(result) == 2
        assert ("a", "b") in result
        assert ("c", "d") in result
        assert result[("a", "b")].source_id == "a"
        assert result[("c", "d")].target_id == "d"

    @pytest.mark.asyncio
    async def test_get_edges_batch_large_unwind(self, mock_pool, mock_conn):
        """Large batch (>10 pairs) uses UNWIND Cypher query."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "source_id": "a",
                "target_id": "b",
                "props": json.dumps(
                    {"description": "edge-1", "keywords": "k1", "weight": 1.0}
                ),
            },
            {
                "source_id": "c",
                "target_id": "d",
                "props": json.dumps(
                    {"description": "edge-2", "keywords": "k2", "weight": 2.0}
                ),
            },
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        pairs = [{"src": f"e{i}", "tgt": f"f{i}"} for i in range(15)]
        result = await store.get_edges_batch(pairs)

        assert len(result) == 2
        assert ("a", "b") in result
        assert ("c", "d") in result


# ===================================================================
# TestGetNodeEdges
# ===================================================================


class TestGetNodeEdges:
    """``get_node_edges(node_id)`` — neighbor traversal."""

    @pytest.mark.asyncio
    async def test_get_node_edges_returns_neighbors(self, mock_pool, mock_conn):
        """Returns list of (source_id, connected_id) tuples for neighbors."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {"source_id": "n1", "connected_id": "n2"},
            {"source_id": "n1", "connected_id": "n3"},
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        edges = await store.get_node_edges("n1")

        assert isinstance(edges, list)
        assert len(edges) == 2
        assert edges[0] == ("n1", "n2")
        assert edges[1] == ("n1", "n3")

    @pytest.mark.asyncio
    async def test_get_node_edges_no_neighbors(self, mock_pool, mock_conn):
        """Returns empty list when the node has no connected neighbors."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {"source_id": "n1", "connected_id": None}
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        edges = await store.get_node_edges("n1")

        assert edges == []

    @pytest.mark.asyncio
    async def test_get_node_edges_empty_result(self, mock_pool, mock_conn):
        """Returns empty list when OPTIONAL MATCH finds nothing at all."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = []

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        edges = await store.get_node_edges("isolated_node")

        assert edges == []


# ===================================================================
# TestAgtypeParsing
# ===================================================================


class TestAgtypeParsing:
    """``_parse_agtype(value)`` — AGE agtype return value parsing."""

    def test_parse_agtype_plain_json(self):
        """Plain JSON string (no type suffix) is parsed as-is."""
        result = PGGraphStore._parse_agtype('{"key": "val"}')
        assert result == {"key": "val"}

    def test_parse_agtype_vertex_suffix(self):
        """``::vertex`` suffix is stripped before JSON parsing."""
        result = PGGraphStore._parse_agtype('{"entity_type": "Person"}::vertex')
        assert result == {"entity_type": "Person"}

    def test_parse_agtype_edge_suffix(self):
        """``::edge`` suffix is stripped before JSON parsing."""
        result = PGGraphStore._parse_agtype('{"weight": 0.9}::edge')
        assert result == {"weight": 0.9}

    def test_parse_agtype_empty_string(self):
        """Empty string returns None."""
        result = PGGraphStore._parse_agtype("")
        assert result is None

    def test_parse_agtype_whitespace_only(self):
        """Whitespace-only string returns None."""
        result = PGGraphStore._parse_agtype("   ")
        assert result is None

    def test_parse_agtype_invalid_json(self):
        """Unparseable JSON (even with suffix stripped) returns None."""
        result = PGGraphStore._parse_agtype("not valid json::vertex")
        assert result is None

    def test_parse_agtype_none_input(self):
        """None input returns None."""
        result = PGGraphStore._parse_agtype(None)
        assert result is None

    def test_parse_agtype_non_string_input(self):
        """Non-string input (e.g. int) returns None."""
        result = PGGraphStore._parse_agtype(42)
        assert result is None

    def test_parse_agtype_multiple_colons(self):
        """Only the last ``::`` is treated as the type suffix separator."""
        result = PGGraphStore._parse_agtype(
            '{"url": "http://example.com"}::vertex'
        )
        assert result == {"url": "http://example.com"}


# ===================================================================
# TestDollarQuote
# ===================================================================


class TestDollarQuote:
    """``_dollar_quote(s)`` — PostgreSQL dollar-quote generation."""

    def test_dollar_quote_generates_wrapper(self):
        """Generates a dollar-quoted string with ``$AGE1$`` tags."""
        result = PGGraphStore._dollar_quote("hello")
        assert result.startswith("$AGE1$")
        assert result.endswith("$AGE1$")
        assert "hello" in result
        assert result == "$AGE1$hello$AGE1$"

    def test_dollar_quote_avoids_collision(self):
        """When content contains ``$AGE1$``, the next tag (``$AGE2$``) is used."""
        result = PGGraphStore._dollar_quote("$AGE1$content$AGE1$")
        # Should NOT use AGE1 (would collide); uses AGE2 instead
        assert "$AGE2$" in result
        assert "content" in result
        assert result == "$AGE2$$AGE1$content$AGE1$$AGE2$"

    def test_dollar_quote_empty_string(self):
        """Empty string is wrapped: ``$AGE1$$AGE1$``."""
        result = PGGraphStore._dollar_quote("")
        assert result == "$AGE1$$AGE1$"

    def test_dollar_quote_custom_tag_prefix(self):
        """Custom ``tag_prefix`` is respected."""
        result = PGGraphStore._dollar_quote("hello", tag_prefix="CUSTOM")
        assert result.startswith("$CUSTOM1$")
        assert result == "$CUSTOM1$hello$CUSTOM1$"


# ===================================================================
# TestReadOnly
# ===================================================================


class TestReadOnly:
    """D-15: enforce read-only — use ``fetch()``, never ``execute()``."""

    @pytest.mark.asyncio
    async def test_uses_fetch_not_execute(self, mock_pool, mock_conn):
        """All graph queries use conn.fetch() — conn.execute() is never called."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "props": json.dumps(
                    {
                        "entity_type": "Person",
                        "description": "Desc",
                        "source_id": "s1",
                    }
                )
            }
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        await store.get_node("x")

        mock_conn.fetch.assert_called()
        # execute() should never have been called
        if hasattr(mock_conn, "execute"):
            assert mock_conn.execute.call_count == 0


# ===================================================================
# TestGraphNameResolution
# ===================================================================


class TestGraphNameResolution:
    """``_resolve_graph_name()`` — graph name derivation from workspace."""

    @pytest.mark.asyncio
    async def test_graph_name_default_workspace(self, monkeypatch):
        """Default workspace ``"default"`` resolves to ``"lightrag_graph"``."""
        monkeypatch.setenv("pg__workspace", "default")
        import lightrag_langchain.config as cfg

        cfg._settings = None

        store = PGGraphStore(workspace="default")
        name = await store._resolve_graph_name()
        assert name == "lightrag_graph"

    @pytest.mark.asyncio
    async def test_graph_name_custom_workspace(self, monkeypatch):
        """Custom workspace appends sanitized name to ``lightrag_graph``."""
        monkeypatch.setenv("pg__workspace", "my_project")
        import lightrag_langchain.config as cfg

        cfg._settings = None

        store = PGGraphStore(workspace="my_project")
        name = await store._resolve_graph_name()
        assert "my_project" in name
        assert name.endswith("_lightrag_graph")
        assert name == "my_project_lightrag_graph"

    @pytest.mark.asyncio
    async def test_graph_name_sanitizes_special_chars(self, monkeypatch):
        """Non-alphanumeric characters in workspace are replaced with ``_``."""
        monkeypatch.setenv("pg__workspace", "my-project")
        import lightrag_langchain.config as cfg

        cfg._settings = None

        store = PGGraphStore(workspace="my-project")
        name = await store._resolve_graph_name()
        assert name == "my_project_lightrag_graph"

    @pytest.mark.asyncio
    async def test_graph_name_explicit_override(self):
        """Explicit ``graph_name`` parameter bypasses workspace resolution."""
        store = PGGraphStore(graph_name="custom_graph")
        name = await store._resolve_graph_name()
        assert name == "custom_graph"

    @pytest.mark.asyncio
    async def test_graph_name_cached(self):
        """Resolution result is cached — second call returns same value."""
        store = PGGraphStore(workspace="default")
        name1 = await store._resolve_graph_name()
        name2 = await store._resolve_graph_name()
        assert name1 == name2
        assert store._graph_name_resolved == "lightrag_graph"


# ===================================================================
# TestCypherParameterization
# ===================================================================


class TestCypherParameterization:
    """T-02-04-GRAPH-01: parameterised Cypher — no string interpolation."""

    @pytest.mark.asyncio
    async def test_params_use_json_dumps(self, mock_pool, mock_conn):
        """The params passed to conn.fetch() are JSON-serialised for $1::agtype."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "props": json.dumps(
                    {
                        "entity_type": "X",
                        "description": "Y",
                        "source_id": "Z",
                    }
                )
            }
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        await store.get_node("entity-123")

        # The second argument to fetch() should be JSON string with entity_id
        call_args = mock_conn.fetch.call_args
        assert call_args is not None
        pg_param = call_args[0][1]  # second positional arg
        assert isinstance(pg_param, str)
        parsed = json.loads(pg_param)
        assert parsed["entity_id"] == "entity-123"

    @pytest.mark.asyncio
    async def test_no_cypher_string_interpolation(self, mock_pool, mock_conn):
        """The actual entity_id value is NOT interpolated into the Cypher string."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {
                "props": json.dumps(
                    {
                        "entity_type": "X",
                        "description": "Y",
                        "source_id": "Z",
                    }
                )
            }
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        await store.get_node("malicious'; DROP TABLE--")

        # The Cypher string passed to conn.fetch() should contain the parameter
        # placeholder $entity_id, NOT the actual interpolated value
        call_args = mock_conn.fetch.call_args
        sql_text = call_args[0][0]  # first positional arg (SQL string)
        assert "$entity_id" in sql_text
        assert "malicious" not in sql_text
        assert "DROP TABLE" not in sql_text

    @pytest.mark.asyncio
    async def test_get_edge_params_use_json_dumps(self, mock_pool, mock_conn):
        """Edge queries also use json.dumps() parameterization."""
        _wire_mocks(mock_pool, mock_conn)
        mock_conn.fetch.return_value = [
            {"props": json.dumps({"description": "edge", "keywords": "k", "weight": 1.0})}
        ]

        store = PGGraphStore(pool=mock_pool, graph_name="test_graph")
        await store.get_edge("src-node", "tgt-node")

        call_args = mock_conn.fetch.call_args
        pg_param = call_args[0][1]
        parsed = json.loads(pg_param)
        assert parsed["src"] == "src-node"
        assert parsed["tgt"] == "tgt-node"
