"""PGGraphStore (AGE 图查询层) 的完整单元测试套件。

覆盖:
- 节点检索: get_node, get_nodes_batch
- 边检索: get_edge, get_edges_batch
- 邻居遍历: get_node_edges
- agtype 解析 (::vertex / ::edge 后缀去除)
- Dollar-quote 生成 (冲突避免)
- 只读强制 (psycopg cursor 模式)
- 图名称从 workspace 解析
- Cypher 参数化安全 ($entity_id，无字符串插值)

所有 psycopg 调用均被 mock —— 无真实数据库连接。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from lightrag_langchain.data.models import GraphEdge, GraphNode


def _graph_cls():
    """返回 PGGraphStore 类。

    延迟导入 — 在测试体内部调用，确保 Settings 在 pytest fixtures
    已设置环境变量后再实例化。
    """
    from lightrag_langchain.data.graph import PGGraphStore

    return PGGraphStore

# ---------------------------------------------------------------------------
# Auto-use fixture: Settings 实例化所需的环境变量
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """设置所需环境变量，使 ``settings`` 可以实例化。

    某些测试（如图名称解析）通过 PGGraphStore 构造函数访问
    ``settings.pg.workspace``。此 fixture 确保 Settings 能加载，
    即使大多数图测试直接注入 ``graph_name``。
    """
    required_vars = {
        "lightrag_pg__host": "localhost",
        "lightrag_pg__port": "5432",
        "lightrag_pg__user": "test",
        "lightrag_pg__password": "secret",
        "lightrag_pg__database": "testdb",
        "lightrag_llm__binding": "openai",
        "lightrag_llm__binding_host": "https://api.openai.com/v1",
        "lightrag_llm__binding_api_key": "sk-test",
        "lightrag_llm__model": "gpt-4o-mini",
        "lightrag_embedding__binding": "openai",
        "lightrag_embedding__binding_host": "https://api.openai.com/v1",
        "lightrag_embedding__binding_api_key": "sk-emb",
        "lightrag_embedding__model": "text-embedding-3-small",
    }
    for k, v in required_vars.items():
        monkeypatch.setenv(k, v)

    # 重置缓存的 Settings 单例使其使用 monkeypatched 的环境变量
    import lightrag_langchain.config as cfg

    cfg._settings = None


# ---------------------------------------------------------------------------
# Helper: 为 psycopg connection/cursor 模式配置 mock
# ---------------------------------------------------------------------------


def _wire_mocks(mock_pool, mock_conn, mock_cursor):
    """为 psycopg connection/cursor 模式配置 mock_pool。

    psycopg 模式使用:
    - ``async with pool.connection() as conn:``
    - ``async with conn.cursor() as cur:``
    - ``await cur.execute(sql, (p1,))``
    - ``await cur.fetchall()``
    """
    mock_pool.connection.return_value.__aenter__.return_value = mock_conn
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor


# ===================================================================
# TestGetNode
# ===================================================================


class TestGetNode:
    """``get_node(entity_id)`` — 单个节点检索。"""

    @pytest.mark.asyncio
    async def test_get_node_returns_graph_node(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当实体存在于 AGE 图中时返回 GraphNode。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
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

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        node = await store.get_node("n1")

        assert node is not None
        assert isinstance(node, GraphNode)
        assert node.entity_id == "n1"
        assert node.entity_type == "Person"
        assert node.description == "A person entity"
        assert node.source_id == "doc42"

    @pytest.mark.asyncio
    async def test_get_node_not_found(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当不存在具有给定 entity_id 的节点时返回 None。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = []

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        node = await store.get_node("nonexistent")

        assert node is None

    @pytest.mark.asyncio
    async def test_get_node_null_properties(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当查询返回行但 props 为空时返回 None。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [{"props": ""}]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        node = await store.get_node("n1")

        assert node is None


# ===================================================================
# TestGetNodesBatch
# ===================================================================


class TestGetNodesBatch:
    """``get_nodes_batch(node_ids)`` — 批量节点检索。"""

    @pytest.mark.asyncio
    async def test_get_nodes_batch_returns_dict(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """返回将 entity_id 映射到 GraphNode 的 dict。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
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

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
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
    async def test_get_nodes_batch_empty_input(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当 node_ids 为空时返回空 dict，不进行任何数据库调用。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        result = await store.get_nodes_batch([])

        assert result == {}
        # 不应进行任何数据库调用
        mock_cursor.fetchall.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_nodes_batch_partial_match(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """仅找到的节点出现在结果中；缺失节点被静默省略。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
            {
                "node_id": '"n1"',
                "properties": json.dumps(
                    {"entity_type": "Person", "description": "Only one", "source_id": "s1"}
                ),
            }
        ]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        result = await store.get_nodes_batch(["n1", "n2"])

        assert len(result) == 1
        assert "n1" in result
        assert "n2" not in result

    @pytest.mark.asyncio
    async def test_get_nodes_batch_strips_quotes(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """AGE 返回的带双引号节点 ID 应被去除引号。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
            {
                "node_id": '"entity-with-quotes"',
                "properties": json.dumps(
                    {"entity_type": "Thing", "description": "", "source_id": ""}
                ),
            }
        ]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        result = await store.get_nodes_batch(["entity-with-quotes"])

        assert "entity-with-quotes" in result
        # key 不应包含引号
        assert '"entity-with-quotes"' not in result


# ===================================================================
# TestGetEdge
# ===================================================================


class TestGetEdge:
    """``get_edge(src, tgt)`` — 单个边检索。"""

    @pytest.mark.asyncio
    async def test_get_edge_returns_graph_edge(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当两个实体之间存在有向边时返回 GraphEdge。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
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

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        edge = await store.get_edge("a", "b")

        assert edge is not None
        assert isinstance(edge, GraphEdge)
        assert edge.source_id == "a"
        assert edge.target_id == "b"
        assert edge.description == "works at"
        assert edge.keywords == "employer"
        assert edge.weight == 0.9

    @pytest.mark.asyncio
    async def test_get_edge_not_found(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当不存在从 src 到 tgt 的边时返回 None。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = []

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        edge = await store.get_edge("a", "c")

        assert edge is None

    @pytest.mark.asyncio
    async def test_get_edge_null_props_returns_none(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当查询返回行但 props 无法解析时返回 None。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [{"props": ""}]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        edge = await store.get_edge("a", "b")

        assert edge is None

    @pytest.mark.asyncio
    async def test_get_edge_optional_fields_none(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """边的可选字段 (description, keywords, weight) 可以为 None。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
            {"props": json.dumps({"description": "linked"})}
        ]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        edge = await store.get_edge("x", "y")

        assert edge is not None
        assert edge.description == "linked"
        assert edge.keywords is None
        assert edge.weight is None


# ===================================================================
# TestGetEdgesBatch
# ===================================================================


class TestGetEdgesBatch:
    """``get_edges_batch(pairs)`` — 批量边检索。"""

    @pytest.mark.asyncio
    async def test_get_edges_batch_empty_input(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当 pairs 为空时返回空 dict，不进行任何数据库调用。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        result = await store.get_edges_batch([])

        assert result == {}
        mock_cursor.fetchall.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_edges_batch_small_sequential(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """小批量 (<=10 pairs) 使用顺序 get_edge 调用。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
            {
                "props": json.dumps(
                    {"description": "related", "keywords": "kw", "weight": 0.5}
                )
            }
        ]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        pairs = [{"src": "a", "tgt": "b"}, {"src": "c", "tgt": "d"}]
        result = await store.get_edges_batch(pairs)

        assert len(result) == 2
        assert ("a", "b") in result
        assert ("c", "d") in result
        assert result[("a", "b")].source_id == "a"
        assert result[("c", "d")].target_id == "d"

    @pytest.mark.asyncio
    async def test_get_edges_batch_large_unwind(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """大批量 (>10 pairs) 使用 UNWIND Cypher 查询。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
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

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        pairs = [{"src": f"e{i}", "tgt": f"f{i}"} for i in range(15)]
        result = await store.get_edges_batch(pairs)

        assert len(result) == 2
        assert ("a", "b") in result
        assert ("c", "d") in result


# ===================================================================
# TestGetNodeEdges
# ===================================================================


class TestGetNodeEdges:
    """``get_node_edges(node_id)`` — 邻居遍历。"""

    @pytest.mark.asyncio
    async def test_get_node_edges_returns_neighbors(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """返回邻居的 (source_id, connected_id) 元组列表。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
            {"source_id": "n1", "connected_id": "n2"},
            {"source_id": "n1", "connected_id": "n3"},
        ]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        edges = await store.get_node_edges("n1")

        assert isinstance(edges, list)
        assert len(edges) == 2
        assert edges[0] == ("n1", "n2")
        assert edges[1] == ("n1", "n3")

    @pytest.mark.asyncio
    async def test_get_node_edges_no_neighbors(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当节点无已连接的邻居时返回空列表。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
            {"source_id": "n1", "connected_id": None}
        ]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        edges = await store.get_node_edges("n1")

        assert edges == []

    @pytest.mark.asyncio
    async def test_get_node_edges_empty_result(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """当 OPTIONAL MATCH 完全找不到任何内容时返回空列表。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = []

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        edges = await store.get_node_edges("isolated_node")

        assert edges == []


# ===================================================================
# TestAgtypeParsing
# ===================================================================


class TestAgtypeParsing:
    """``_parse_agtype(value)`` — AGE agtype 返回值解析。"""

    def test_parse_agtype_plain_json(self):
        """纯 JSON 字符串（无类型后缀）直接解析。"""
        result = _graph_cls()._parse_agtype('{"key": "val"}')
        assert result == {"key": "val"}

    def test_parse_agtype_vertex_suffix(self):
        """``::vertex`` 后缀在 JSON 解析前被去除。"""
        result = _graph_cls()._parse_agtype('{"entity_type": "Person"}::vertex')
        assert result == {"entity_type": "Person"}

    def test_parse_agtype_edge_suffix(self):
        """``::edge`` 后缀在 JSON 解析前被去除。"""
        result = _graph_cls()._parse_agtype('{"weight": 0.9}::edge')
        assert result == {"weight": 0.9}

    def test_parse_agtype_empty_string(self):
        """空字符串返回 None。"""
        result = _graph_cls()._parse_agtype("")
        assert result is None

    def test_parse_agtype_whitespace_only(self):
        """仅包含空白字符的字符串返回 None。"""
        result = _graph_cls()._parse_agtype("   ")
        assert result is None

    def test_parse_agtype_invalid_json(self):
        """无法解析的 JSON（去除后缀后）返回 None。"""
        result = _graph_cls()._parse_agtype("not valid json::vertex")
        assert result is None

    def test_parse_agtype_none_input(self):
        """None 输入返回 None。"""
        result = _graph_cls()._parse_agtype(None)
        assert result is None

    def test_parse_agtype_non_string_input(self):
        """非字符串输入（如 int）返回 None。"""
        result = _graph_cls()._parse_agtype(42)
        assert result is None

    def test_parse_agtype_multiple_colons(self):
        """仅最后的 ``::`` 被视为类型后缀分隔符。"""
        result = _graph_cls()._parse_agtype(
            '{"url": "http://example.com"}::vertex'
        )
        assert result == {"url": "http://example.com"}


# ===================================================================
# TestDollarQuote
# ===================================================================


class TestDollarQuote:
    """``_dollar_quote(s)`` — PostgreSQL dollar-quote 生成。"""

    def test_dollar_quote_generates_wrapper(self):
        """生成带 ``$AGE1$`` 标签的 dollar-quoted 字符串。"""
        result = _graph_cls()._dollar_quote("hello")
        assert result.startswith("$AGE1$")
        assert result.endswith("$AGE1$")
        assert "hello" in result
        assert result == "$AGE1$hello$AGE1$"

    def test_dollar_quote_avoids_collision(self):
        """当内容包含 ``$AGE1$`` 时，使用下一个标签 (``$AGE2$``)。"""
        result = _graph_cls()._dollar_quote("$AGE1$content$AGE1$")
        # 不应使用 AGE1（会冲突）；改用 AGE2
        assert "$AGE2$" in result
        assert "content" in result
        assert result == "$AGE2$$AGE1$content$AGE1$$AGE2$"

    def test_dollar_quote_empty_string(self):
        """空字符串被包装: ``$AGE1$$AGE1$``。"""
        result = _graph_cls()._dollar_quote("")
        assert result == "$AGE1$$AGE1$"

    def test_dollar_quote_custom_tag_prefix(self):
        """自定义 ``tag_prefix`` 被尊重。"""
        result = _graph_cls()._dollar_quote("hello", tag_prefix="CUSTOM")
        assert result.startswith("$CUSTOM1$")
        assert result == "$CUSTOM1$hello$CUSTOM1$"


# ===================================================================
# TestReadOnly
# ===================================================================


class TestReadOnly:
    """D-15: 强制只读 — 使用 psycopg cursor 模式。"""

    @pytest.mark.asyncio
    async def test_uses_cursor_pattern(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """所有图查询使用 cursor.execute + cursor.fetchall。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
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

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        await store.get_node("x")

        # verify cursor pattern was used
        mock_cursor.execute.assert_called()
        mock_cursor.fetchall.assert_called()


# ===================================================================
# TestGraphNameResolution
# ===================================================================


class TestGraphNameResolution:
    """``_resolve_graph_name()`` — 从 workspace 派生图名称。"""

    @pytest.mark.asyncio
    async def test_graph_name_default_workspace(self, monkeypatch):
        """默认 workspace ``"default"`` 解析为 ``"lightrag_graph"``。"""
        monkeypatch.setenv("lightrag_pg__workspace", "default")
        import lightrag_langchain.config as cfg

        cfg._settings = None

        store = _graph_cls()(workspace="default")
        name = await store._resolve_graph_name()
        assert name == "lightrag_graph"

    @pytest.mark.asyncio
    async def test_graph_name_custom_workspace(self, monkeypatch):
        """自定义 workspace 将清理后的名称追加到 ``lightrag_graph``。"""
        monkeypatch.setenv("lightrag_pg__workspace", "my_project")
        import lightrag_langchain.config as cfg

        cfg._settings = None

        store = _graph_cls()(workspace="my_project")
        name = await store._resolve_graph_name()
        assert "my_project" in name
        assert name.endswith("_lightrag_graph")
        assert name == "my_project_lightrag_graph"

    @pytest.mark.asyncio
    async def test_graph_name_sanitizes_special_chars(self, monkeypatch):
        """workspace 中的非字母数字字符被替换为 ``_``。"""
        monkeypatch.setenv("lightrag_pg__workspace", "my-project")
        import lightrag_langchain.config as cfg

        cfg._settings = None

        store = _graph_cls()(workspace="my-project")
        name = await store._resolve_graph_name()
        assert name == "my_project_lightrag_graph"

    @pytest.mark.asyncio
    async def test_graph_name_explicit_override(self):
        """显式 ``graph_name`` 参数绕过 workspace 解析。"""
        store = _graph_cls()(graph_name="custom_graph")
        name = await store._resolve_graph_name()
        assert name == "custom_graph"

    @pytest.mark.asyncio
    async def test_graph_name_cached(self):
        """解析结果被缓存 — 第二次调用返回相同值。"""
        store = _graph_cls()(workspace="default")
        name1 = await store._resolve_graph_name()
        name2 = await store._resolve_graph_name()
        assert name1 == name2
        assert store._graph_name_resolved == "lightrag_graph"


# ===================================================================
# TestCypherParameterization
# ===================================================================


class TestCypherParameterization:
    """T-02-04-GRAPH-01: 参数化 Cypher — 无字符串插值。"""

    @pytest.mark.asyncio
    async def test_params_use_json_dumps(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """传递给 cursor.execute() 的 params 是用于 %s::agtype 的 JSON 序列化。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
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

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        await store.get_node("entity-123")

        # execute() 的第二个参数应为包含 entity_id 的 JSON 字符串
        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        pg_param = call_args[0][1][0]  # 元组中的第一个参数
        assert isinstance(pg_param, str)
        parsed = json.loads(pg_param)
        assert parsed["entity_id"] == "entity-123"

    @pytest.mark.asyncio
    async def test_no_cypher_string_interpolation(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """entity_id 值不会被插值到 Cypher 字符串中。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
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

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        await store.get_node("malicious'; DROP TABLE--")

        # 传递给 cursor.execute() 的 Cypher 字符串应包含参数
        # 占位符 $entity_id，而非插值后的实际值
        call_args = mock_cursor.execute.call_args
        sql_text = call_args[0][0]  # 第一个位置参数 (SQL 字符串)
        assert "$entity_id" in sql_text
        assert "malicious" not in sql_text
        assert "DROP TABLE" not in sql_text

    @pytest.mark.asyncio
    async def test_get_edge_params_use_json_dumps(
        self, mock_pool, mock_conn, mock_cursor
    ):
        """边查询也使用 json.dumps() 参数化。"""
        _wire_mocks(mock_pool, mock_conn, mock_cursor)
        mock_cursor.fetchall.return_value = [
            {"props": json.dumps({"description": "edge", "keywords": "k", "weight": 1.0})}
        ]

        store = _graph_cls()(pool=mock_pool, graph_name="test_graph")
        await store.get_edge("src-node", "tgt-node")

        call_args = mock_cursor.execute.call_args
        pg_param = call_args[0][1][0]
        parsed = json.loads(pg_param)
        assert parsed["src"] == "src-node"
        assert parsed["tgt"] == "tgt-node"


# ===================================================================
# TestAsyncpgRemoved
# ===================================================================


class TestAsyncpgRemoved:
    """验证 graph.py 中 asyncpg 导入和 acquire_with_retry 引用已完全移除。"""

    def test_no_asyncpg_imports(self):
        """graph.py 不应包含任何 asyncpg 导入。"""
        import ast

        with open("src/lightrag_langchain/data/graph.py") as f:
            source = f.read()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert "asyncpg" not in imports, f"graph.py still imports asyncpg: {imports}"

    def test_no_acquire_with_retry_reference(self):
        """graph.py 源代码不应引用 acquire_with_retry。"""
        with open("src/lightrag_langchain/data/graph.py") as f:
            source = f.read()
        assert "acquire_with_retry" not in source, (
            "graph.py should not reference acquire_with_retry"
        )
