# Phase 02: Data Layer - Research

**Researched:** 2026-05-29
**Domain:** 只读 PostgreSQL 数据抽象层 (PGVector + Apache AGE)
**Confidence:** HIGH

## Summary

Phase 02 构建一个只读的 PostgreSQL 数据抽象层，封装对 LightRAG 已处理好的 PGVector 向量表和 Apache AGE 图数据库的查询访问。两个核心类 (`PGVectorStore` + `PGGraphStore`) 共享一个 asyncpg 连接池，通过 Pydantic 模型返回类型化的查询结果。

上游 LightRAG 的 SQL_TEMPLATES 和 PGGraphStorage 代码提供了完整的参考实现。Phase 2 的核心工作是从中提取只读查询路径（剔除 upsert/delete/migration 逻辑），用 Phase 1 的配置系统驱动连接参数，并以更简洁的接口暴露给下游 Phase 3/4。

**Primary recommendation:** 严格遵循 LightRAG 已验证的 SQL 模板和 AGE Cypher 查询模式 -- 这些查询已经在生产环境中运行。不要重新发明查询逻辑，专注于用 asyncpg 原生 Pool API 替代 LightRAG 的重量级 `ClientManager`/`PostgreSQLDB` 连接管理。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PGVector 向量相似度搜索 (entities/relationships/chunks) | Database / Storage | -- | PGVector `<=>` operator runs server-side; app only sends embedding vector |
| Apache AGE 图节点/边查询与遍历 | Database / Storage | -- | AGE Cypher engine runs server-side; app sends parameterized Cypher queries |
| asyncpg 连接池生命周期管理 | API / Backend | -- | Connection pools are an application-level concern; Phase 2 owns pool creation, lazy init, and close |
| 表名自动发现 (information_schema) | API / Backend | -- | Startup-time metadata query; app logic, not DB configuration |
| Pydantic 记录模型 (EntityRecord, ChunkRecord, etc.) | API / Backend | -- | Data transfer objects; owned by the data layer abstraction |
| 只读保证 (query() vs execute()) | API / Backend | -- | Code-level enforcement; no DB-level read-only user required per D-16 |
| 重试逻辑 (瞬态连接错误) | API / Backend | -- | Application-level resilience; asyncpg pool already handles some network retries |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|-------------|
| asyncpg | 0.31.0 | PostgreSQL 异步驱动 + 连接池 | LightRAG 上游选型，二进制协议最快，pgvector `register_vector` 无缝集成 [VERIFIED: npm registry -- asyncpg PyPI package, slopcheck OK] |
| pgvector (Python) | 0.4.2 | pgvector 类型编解码 (`register_vector`) | 官方 pgvector 扩展的 Python 客户端，asyncpg 集成接口 [VERIFIED: PyPI package, slopcheck OK] |
| pydantic | 2.13.4 | 记录模型 (EntityRecord, etc.) | Phase 1 已锁定，保持一致 [VERIFIED: PyPI -- already in pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | 1.3.0 | 异步测试支持 | 所有数据层测试（asyncpg 是纯异步 API）[VERIFIED: already installed in dev env] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncpg | psycopg3 (async) | psycopg3 也支持异步，但 LightRAG 上游已锁定 asyncpg，跟随上游避免兼容性风险 |
| 手动管理 Connection | asyncpg Pool | Connection 不适合并发场景；Pool 内置连接复用、健康检查、自动重连 |

**Installation:**
```bash
pip install "asyncpg>=0.31,<1.0" "pgvector>=0.4,<1.0"
```

**Version verification:**
```bash
pip index versions asyncpg   # 0.31.0 (latest, 2026-05)
pip index versions pgvector  # 0.4.2 (latest, 2026-05)
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| asyncpg | PyPI | 9 yrs (est.) | High (MagicStack official) | github.com/MagicStack/asyncpg | [OK] | Approved |
| pgvector | PyPI | 3 yrs (est.) | High (official pgvector client) | github.com/pgvector/pgvector | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**No entry points / console_scripts detected** on either package -- clean install profile.

*Both packages are already installed in the project's asdf Python 3.12 environment (asyncpg 0.31.0, pgvector 0.4.2).*

## Architecture Patterns

### System Architecture Diagram

```
                        .env (Phase 1 Config)
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Settings (Phase 1) │
                    │   pg.host/port/user  │
                    │   query_params.cosine_threshold │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Connection Pool    │  ◄── lazy init on first query
                    │   (asyncpg.Pool)     │  ◄── .env: PG_POOL_MIN/MAX_SIZE
                    │   + register_vector  │  ◄── explicit close()
                    └──────┬──────┬────────┘
                           │      │
              ┌────────────▼─┐  ┌─▼──────────────────┐
              │ PGVectorStore │  │   PGGraphStore      │
              │               │  │                     │
              │ search_entities│  │ get_node(id)        │
              │ search_rels   │  │ get_edge(src, tgt)  │
              │ search_chunks │  │ get_node_edges(id)  │
              │               │  │ get_nodes_batch()   │
              │ get_by_id()   │  │ get_edges_batch()   │
              └──────┬────────┘  └─┬───────────────────┘
                     │              │
                     ▼              ▼
        ┌─────────────────┐  ┌──────────────────────┐
        │  PGVector Tables │  │  Apache AGE Graph    │
        │                  │  │                      │
        │ entities_vdb     │  │  {graph_name}.base   │
        │ relationships_vdb│  │  {graph_name}.DIRECTED│
        │ chunks_vdb       │  │                      │
        └─────────────────┘  └──────────────────────┘
                     │              │
                     ▼              ▼
        ┌─────────────────┐  ┌──────────────────────┐
        │  Pydantic Models │  │  Pydantic Models     │
        │  EntityRecord    │  │  GraphNode            │
        │  RelationshipRec │  │  GraphEdge            │
        │  ChunkRecord     │  │                      │
        └─────────────────┘  └──────────────────────┘
```

**Data flow:**
1. Phase 1 Settings 提供连接参数 (PgConfig) 和查询参数 (QueryParamsConfig)
2. Connection pool 在首次查询时延迟创建（复用 Phase 1 `__getattr__` 模式），每个连接注册 pgvector codec
3. `PGVectorStore.search_*()` 接收预计算向量 → 构造参数化 SQL → Pool 执行 → 返回 Pydantic 模型列表
4. `PGGraphStore.get_*()` 构造参数化 Cypher → `SELECT * FROM cypher()` → Pool 执行 → 返回 Pydantic 模型
5. 所有查询通过 workspace 过滤参数隔离数据

### Recommended Project Structure
```
src/lightrag_langchain/
├── __init__.py
├── config.py              # Phase 1 -- 已完成
├── data/
│   ├── __init__.py
│   ├── models.py          # Pydantic 数据模型 (EntityRecord, RelationshipRecord, ...)
│   ├── store.py           # PGVectorStore (entities/chunks/relationships 向量搜索)
│   ├── graph.py           # PGGraphStore (AGE 图节点/边查询与遍历)
│   └── pool.py            # 连接池管理 (lazy init, close, 重试, 依赖注入)
tests/
├── __init__.py
├── conftest.py            # 现有 fixtures 扩展
├── test_config.py         # Phase 1
├── test_models.py         # 数据模型验证测试
├── test_store.py          # PGVectorStore 单元测试 (含 mock DB)
├── test_graph.py          # PGGraphStore 单元测试 (含 mock DB)
└── test_pool.py           # 连接池生命周期测试
```

### Pattern 1: 延迟连接池初始化 (Phase 1 复用)

**What:** 使用 `__getattr__` 模块级单例模式，首次访问时创建连接池。与 Phase 1 `config.py` 的 `settings` 单例模式一致。

**When to use:** 所有需要异步初始化的全局资源（连接池、图存储、向量存储）

**Example:**
```python
# Source: Phase 1 config.py __getattr__ pattern + LightRAG ClientManager pattern
# File: src/lightrag_langchain/data/pool.py

from typing import TYPE_CHECKING
import asyncpg
from pgvector.asyncpg import register_vector
from lightrag_langchain.config import settings

if TYPE_CHECKING:
    from asyncpg import Pool

_pool: "Pool | None" = None

def __getattr__(name: str) -> "Pool":
    global _pool
    if name == "pool":
        if _pool is None:
            raise RuntimeError(
                "Connection pool not initialized. Call init_pool() first."
            )
        return _pool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

async def init_pool() -> "Pool":
    """Lazy-init the connection pool. Idempotent."""
    global _pool
    if _pool is not None:
        return _pool

    pg = settings.pg  # Phase 1 PgConfig
    _pool = await asyncpg.create_pool(
        host=pg.host,
        port=pg.port,
        user=pg.user,
        password=pg.password.get_secret_value(),
        database=pg.database,
        min_size=2,
        max_size=10,
        command_timeout=30.0,
        init=_init_connection,
        server_settings={
            'application_name': 'lightrag_langchain_v1',
        },
    )
    return _pool

async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register pgvector codec on each new pool connection."""
    await register_vector(conn)

async def close_pool() -> None:
    """Explicitly close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
```

### Pattern 2: 参数化 PGVector 向量搜索

**What:** 使用 `<=>` (cosine distance) 运算符 + `::vector` 类型转换进行向量相似度搜索。通过 asyncpg `connection.fetch()` 执行，参数使用 `$1, $2, ...` 占位符。LightRAG 已验证的模式。

**When to use:** 所有 vector similarity search 查询

**Example:**
```python
# Source: LightRAG SQL_TEMPLATES["entities"] (L:6649-6657)
# Adapted for read-only asyncpg Pool API

async def search_entities(
    pool: asyncpg.Pool,
    workspace: str,
    embedding: list[float],
    top_k: int,
    cosine_threshold: float,
    table_name: str,
) -> list[dict]:
    """Vector similarity search on entities_vdb table."""
    closer_than = 1.0 - cosine_threshold  # cosine distance = 1 - similarity
    sql = f"""
        SELECT entity_name,
               content,
               id AS source_id,
               COALESCE(file_path, '') AS file_path,
               create_time,
               update_time
        FROM {table_name}
        WHERE workspace = $1
          AND content_vector <=> $4::vector < $2
        ORDER BY content_vector <=> $4::vector
        LIMIT $3
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, workspace, closer_than, top_k, embedding)
    return [dict(row) for row in rows]
```

### Pattern 3: 参数化 Apache AGE Cypher 查询

**What:** 使用 `SELECT * FROM cypher(graph_name, cypher_query, params::agtype)` 执行图查询。通过 `$_dollar_quote_` 动态生成 dollar-quote 分隔符避免嵌套冲突。参数通过 `json.dumps()` 序列化为 agtype 格式。LightRAG 已验证的模式。

**When to use:** 所有 AGE 图查询（节点查询、边查询、邻居遍历）

**Example:**
```python
# Source: LightRAG PGGraphStorage.get_node_edges() (L:5045-5068) + get_nodes_batch() (L:5353-5431)
# Adapted for read-only

import json

def _dollar_quote(s: str) -> str:
    """Generate a PostgreSQL dollar-quoted string with a unique tag."""
    tag = "$_$"
    while tag in s:
        tag = f"${'_' * (len(tag) - 2)}$"
    return f"{tag}{s}{tag}"

async def get_node(pool, graph_name: str, node_id: str) -> dict | None:
    """Get a single graph node by entity_id."""
    cypher_query = """MATCH (n:base {entity_id: $entity_id})
                      RETURN properties(n) AS props"""
    sql = (
        f"SELECT * FROM cypher({_dollar_quote(graph_name)}::name, "
        f"{_dollar_quote(cypher_query)}::cstring, $1::agtype) "
        f"AS (props agtype)"
    )
    params = {"params": json.dumps({"entity_id": node_id}, ensure_ascii=False)}
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, params["params"])
    if rows:
        props_str = rows[0]["props"]
        # AGE agtype can be returned as string with ::vertex suffix
        # Parse out the JSON portion
        if isinstance(props_str, str):
            content = props_str.split("::")[0] if "::" in props_str else props_str
            return json.loads(content)
    return None
```

### Pattern 4: 表名自动发现 (information_schema)

**What:** 启动时查询 `information_schema.tables` 匹配 `LIGHTRAG_VDB_*` 模式，检测 `{prefix}_{model_suffix}` 变体。多个变体时报错要求显式指定。

**When to use:** `PGVectorStore` / `PGGraphStore` 初始化时

**Example:**
```python
# Source: LightRAG PostgreSQLDB.check_table_exists() (L:1870-1886) + setup_table (L:3000-3089)

async def discover_vector_tables(
    pool: asyncpg.Pool, prefix: str = "LIGHTRAG_VDB"
) -> dict[str, str]:
    """Discover vector table names matching a prefix pattern.
    
    Returns dict mapping namespace (ENTITY/RELATION/CHUNKS) to full table name.
    Raises RuntimeError if multiple suffix variants found for a namespace.
    """
    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name LIKE $1
        ORDER BY table_name
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, f"{prefix}%")
    
    namespaces = {
        "ENTITY": [],
        "RELATION": [],
        "CHUNKS": [],
    }
    for row in rows:
        name = row["table_name"]
        for ns, candidates in [
            ("ENTITY", [f"{prefix}_ENTITY"]),
            ("RELATION", [f"{prefix}_RELATION"]),
            ("CHUNKS", [f"{prefix}_CHUNKS"]),
        ]:
            for candidate in candidates:
                if name.startswith(candidate) and (
                    name == candidate or name.startswith(f"{candidate}_")
                ):
                    namespaces[ns].append(name)
    
    result = {}
    for ns, tables in namespaces.items():
        if len(tables) > 1:
            raise RuntimeError(
                f"Multiple {ns} tables found: {tables}. "
                f"Specify PG_TABLE_SUFFIX in .env to disambiguate."
            )
        elif len(tables) == 1:
            result[ns] = tables[0]
        else:
            raise RuntimeError(
                f"No {ns} table found with prefix '{prefix}'. "
                f"Is the LightRAG database initialized?"
            )
    return result
```

### Anti-Patterns to Avoid

- **裸 `pool.acquire()` 无 `async with`:** 异常时连接不归还，逐步耗尽连接池。务必使用 `async with pool.acquire() as conn:` [CITED: asyncpg docs -- connection pooling best practices]
- **`execute()` 替代 `fetch()`:** asyncpg 的 `execute()` 用于 DML/DDL；只读查询使用 `fetch()`/`fetchrow()`/`fetchval()` [CITED: asyncpg docs]
- **字符串拼接 SQL:** 不参数化 embedding 向量或 node ID -- 容易导致注入或类型转换错误。始终使用 `$1, $2, ...` 参数化 [CITED: LightRAG 实现中使用 `$1::vector` 参数化的实践]
- **在 `_record_to_dict` 中重复解析 JSON:** LightRAG 的 `_record_to_dict` 是通用的，但已知查询返回已知类型时，直接用 `json.loads(props)` 更简洁
- **忽略 `register_vector` 注册:** 不调用 `register_vector(conn)` 会导致 asyncpg 无法正确序列化/反序列化 `vector` 类型 [CITED: pgvector.asyncpg docs]
- **忘记 `$4::vector` 类型转换:** 即使 `register_vector` 已注册，仍需显式 `::vector` cast 以便 PostgreSQL 查询规划器使用 pgvector 索引 [CITED: pgvector docs -- type casting for index usage]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PostgreSQL 连接池 | 手动 Connection 管理 + 自定义池 | `asyncpg.create_pool()` | 内置连接复用、健康检查、自动重连、连接重置回调；LightRAG 上游已经基于此构建 [VERIFIED: LightRAG source + asyncpg docs] |
| pgvector 类型序列化 | 自定义 vector→string→bytea 转换 | `pgvector.asyncpg.register_vector()` | 官方二进制协议编解码器；无需手动序列化 embedding 列表 [VERIFIED: pgvector PyPI docs] |
| AGE Cypher 执行 | 手动拼接 Cypher → SQL 翻译 | `SELECT * FROM cypher(graph, query, params)` | AGE 官方 API；参数化支持通过 `$1::agtype` 传递 JSON 参数 [VERIFIED: Apache AGE docs] |
| 向量距离计算 | Python 端计算 cosine distance | PostgreSQL `<=>` operator | 服务端计算，利用 pgvector 索引（HNSW/IVFFlat），百万级向量仍可亚秒级响应 [CITED: pgvector docs] |
| 连接重试逻辑 | 自定义 tenacity/backoff 重试 | asyncpg Pool 内置重连 + 应用层简单重试 | Pool 已处理连接断开重连；应用层只在 `acquire()` 失败时重试 3 次 [CITED: LightRAG _run_with_retry pattern] |

**Key insight:** LightRAG 的 `postgres_impl.py` 已经完整实现了 PGVector/PGGraph 的读写路径。Phase 2 的核心工作是**提取只读子集 + 简化接口**，而不是重新发明 SQL 查询或图遍历逻辑。参考但不照搬 -- 去掉 ClientManager 全局单例、去掉 migration/DDL、去掉 embedding 生成逻辑。

## Runtime State Inventory

> Phase 02 是纯代码层实现，不涉及 rename/refactor/migration。此节省略。

## Common Pitfalls

### Pitfall 1: asyncpg Pool 连接泄漏

**What goes wrong:** 使用 `conn = await pool.acquire()` 后未释放，或异常路径未调用 `pool.release(conn)`，导致连接池耗尽，所有后续查询挂起。

**Why it happens:** asyncpg Pool 的 `acquire()` 返回一个连接，必须显式释放。与 SQLAlchemy 的自动会话管理不同。

**How to avoid:** 始终使用 `async with pool.acquire() as conn:` 上下文管理器。对于需要 fetch 结果的简单查询，直接使用 `pool.fetch()` / `pool.fetchrow()` 便捷方法。

**Warning signs:** 查询逐渐变慢，最终超时；`pool.get_stats()` 显示 `free` 连接数为 0。

### Pitfall 2: vector 类型隐式转换失败

**What goes wrong:** 传入 Python `list[float]` 作为 `$1` 参数，但 PostgreSQL 无法自动推断 `vector` 类型，报错 `operator does not exist: vector <=> unknown`。

**Why it happens:** 虽然 `register_vector` 注册了编解码器，但 PostgreSQL 的查询规划器仍需要显式类型提示来选择合适的 `<=>` operator overload。

**How to avoid:** 向量参数始终使用显式类型转换：`$1::vector`。这是 LightRAG SQL_TEMPLATES 中 `$4::{vector_cast}` 的设计原因。

**Warning signs:** `UndefinedFunction` 错误，operator `<=>` 不存在。

### Pitfall 3: AGE parameter 格式错误

**What goes wrong:** 传入参数格式不是 `{"params": json.dumps(...)}`，导致 AGE 无法解析参数。

**Why it happens:** AGE 的 `cypher()` 函数第三参数要求是 `agtype` 类型的 map。Python 端需要先 `json.dumps` 序列化，然后作为 `$1::agtype` 传递。

**How to avoid:** 严格按照 LightRAG `PGGraphStorage._query()` 的参数格式：`params = {"params": json.dumps({"entity_id": "..."}, ensure_ascii=False)}`，然后 `conn.fetch(sql, params["params"])`。

**Warning signs:** `agtype` 解析错误，或 Cypher 查询返回空结果（参数未正确绑定）。

### Pitfall 4: 向量维度不匹配静默错误

**What goes wrong:** 生成的 embedding 维度 (如 1024) 与表中 `content_vector` 的维度不匹配，但 `<=>` 操作可能不会立即报错 -- 取决于 pgvector 版本和配置。

**Why it happens:** 不同 embedding 模型产出的维度不同（如 text-embedding-3-small = 1536, text-embedding-v4 = 1024）。如果配置的 `EMBEDDING_DIM` 与实际表不符，查询可能返回错误或空结果。

**How to avoid:** 初始化时验证 `EMBEDDING_DIM` 与表中 content_vector 实际维度一致。但注意：Phase 2 不生成 embedding，只是接收预计算向量。维度校验属于 Phase 3 的职责。Phase 2 可以在发现表时可选地验证维度。

**Warning signs:** 所有向量查询返回 0 结果，但没有 SQL 错误。

### Pitfall 5: 测试中需要 mock asyncpg

**What goes wrong:** 测试需要真实的 PostgreSQL + pgvector + AGE 环境，但 CI 环境可能不可用。

**Why it happens:** asyncpg 是纯异步 API，无法像同步代码那样简单地用 `unittest.mock` 拦截。

**How to avoid:** 使用分层测试策略：单元测试 mock asyncpg Pool/Connection 对象（`unittest.mock.AsyncMock`），集成测试需要真实数据库（fixture 或 docker-compose）。pytest-asyncio 的 `@pytest.mark.asyncio` 和 `pytest-asyncio` fixture 支持创建临时数据库。

**Warning signs:** 测试在本地通过但 CI 失败 -- 缺少 PostgreSQL 服务。

## Code Examples

Verified patterns from official sources:

### 连接池创建 (完整配置)
```python
# Source: asyncpg docs + LightRAG _create_pool_once() (L:419-447) + WebSearch best practices
# File: src/lightrag_langchain/data/pool.py

import asyncpg
from pgvector.asyncpg import register_vector
from lightrag_langchain.config import settings

async def create_pool(
    min_size: int = 2,
    max_size: int = 10,
    command_timeout: float = 30.0,
) -> asyncpg.Pool:
    """Create an asyncpg connection pool with pgvector codec."""
    pg = settings.pg

    async def _init_connection(conn: asyncpg.Connection) -> None:
        await register_vector(conn)

    pool = await asyncpg.create_pool(
        host=pg.host,
        port=pg.port,
        user=pg.user,
        password=pg.password.get_secret_value(),
        database=pg.database,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
        init=_init_connection,
        server_settings={
            'application_name': 'lightrag_langchain',
            'default_transaction_read_only': 'on',  # D-15 只读保证 — 数据库层兜底
        },
    )
    return pool
```

### PGVector 搜索 (三个 namespace)
```python
# Source: LightRAG PGVectorStorage.query() (L:3485-3514) + SQL_TEMPLATES (L:6649-6668)
# Adapted: 使用 Pool.acquire() 替代 PostgreSQLDB.query()

async def _vector_search(
    pool: asyncpg.Pool,
    table_name: str,
    workspace: str,
    embedding: list[float],
    top_k: int,
    cosine_threshold: float,
    select_clause: str,
) -> list[dict]:
    """Generic vector similarity search."""
    closer_than = 1.0 - cosine_threshold
    sql = f"""{select_clause}
        FROM {table_name}
        WHERE workspace = $1
          AND content_vector <=> $4::vector < $2
        ORDER BY content_vector <=> $4::vector
        LIMIT $3"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, workspace, closer_than, top_k, embedding)
    return [dict(row) for row in rows]

# entities: entity_name, content, id AS source_id, file_path
# relationships: source_id AS src_id, target_id AS tgt_id, content
# chunks: content, full_doc_id, chunk_order_index, file_path
```

### AGE 图节点批量查询
```python
# Source: LightRAG PGGraphStorage.get_nodes_batch() (L:5353-5431)
# Key: parameterized agtype via UNNEST + json.dumps

import json

async def get_nodes_batch(
    pool: asyncpg.Pool,
    graph_name: str,
    node_ids: list[str],
) -> dict[str, dict]:
    """Get multiple graph nodes by entity_id."""
    if not node_ids:
        return {}

    sql = f"""
        WITH input(v, ord) AS (
          SELECT v, ord
          FROM unnest($1::text[]) WITH ORDINALITY AS t(v, ord)
        ),
        ids(node_id, ord) AS (
          SELECT (to_json(v)::text)::agtype AS node_id, ord
          FROM input
        )
        SELECT i.node_id::text AS node_id,
               b.properties
        FROM {graph_name}.base AS b
        JOIN ids i
          ON ag_catalog.agtype_access_operator(
               VARIADIC ARRAY[b.properties, '"entity_id"'::agtype]
             ) = i.node_id
        ORDER BY i.ord;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, node_ids)

    result = {}
    for row in rows:
        node_id = row["node_id"]
        props = row["properties"]
        if isinstance(props, str):
            # AGE returns agtype as string; parse JSON
            content = props.split("::")[0] if "::" in props else props
            try:
                props = json.loads(content)
            except json.JSONDecodeError:
                continue
        result[node_id] = props
    return result
```

### 表名发现
```python
# Source: LightRAG check_table_exists() (L:1870-1886) + information_schema

async def discover_tables(
    pool: asyncpg.Pool,
    prefix: str,
) -> list[str]:
    """Discover all tables matching a prefix pattern."""
    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name LIKE $1
        ORDER BY table_name
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, f"{prefix}%")
    return [row["table_name"] for row in rows]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LightRAG PostgreSQLDB.query/execute | 直接使用 asyncpg.Pool.acquire() + fetch | Phase 2 采用 | 更轻量，去掉 2000 行连接管理代码；Pool 内置连接复用 |
| LightRAG ClientManager 全局单例 | 模块级 `get_pool()` 延迟初始化 | Phase 2 采用 | 更简单的生命周期管理；依赖注入仍然可用 |
| SQL 字符串 embedding (string interpolation) | asyncpg `$1, $2` 参数化 + `register_vector` 二进制编码 | LightRAG 已采用 | 避免 SQL 注入风险 + 性能提升（二进制协议） |
| `$$` dollar-quote for AGE queries | 动态生成 unique tag (`$_$` variants) | LightRAG 已采用 | 避免 Cypher 内容中的 `$$` 与 PG dollar-quote 冲突 |

**Deprecated/outdated:**
- **asyncpg `connection.execute()` for read queries:** 使用 `fetch()`/`fetchrow()`/`fetchval()` -- `execute()` 是为 DML/DDL 设计的，Phase 2 是只读的
- **LightRAG ClientManager global state:** Phase 2 使用模块级 pool 单例 + 显式 `close()`，不上全局状态
- **手动 `time.sleep()` 重试:** asyncpg Pool 已内置连接重试；应用层使用 `asyncio.sleep()` 指数退避

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | LightRAG VDB_RELATION 表不含 `keywords`/`weight` 列（这些字段仅存在于 AGE 图边属性中）；STOR-02 的 `keywords`/`weight` 字段需要从 AGE 图边获取或返回 NULL | Standard Stack / SQL Patterns | 中 -- 如果实际 DDL 已扩展包含这些列，Pydantic 模型需调整 |
| A2 | `entity_name` 在 VDB_ENTITY 表中是独立的文本字段（不是从 JSON/二进制解析） | Standard Stack | 低 -- DDL 明确定义为 `VARCHAR(512)` |
| A3 | `file_path` 列在 VDB_ENTITY / VDB_RELATION / VDB_CHUNKS 三张表中都存在且可为 NULL | Standard Stack | 低 -- DDL 都有 `file_path TEXT NULL` 定义 |
| A4 | LightRAG 默认 workspace = `"default"` 对应 AGE 图名 = `"{namespace}"`（不含 `{workspace}_{namespace}` 前缀）；`.env` 中 PG_WORKSPACE 可覆盖 | Architecture | 低 -- 直接来自 CONTEXT.md D-05 和 LightRAG `_get_workspace_graph_name()` |
| A5 | PostgreSQL 数据库已包含 pgvector 和 Apache AGE 扩展，且表已由 LightRAG 初始化创建 | Environment | 高 -- 如果数据库未初始化，所有查询都会失败；需要明确的 error message 告知用户 |

## Open Questions

1. **STOR-02 `keywords`/`weight` 字段来源**
   - What we know: LIGHTRAG_VDB_RELATION 表 DDL 不包含 `keywords` 或 `weight` 列。这些字段存储在 AGE 图边的 properties 中。LightRAG 的 SQL_TEMPLATES 中 `relationships` 查询只返回 `source_id`, `target_id`, `created_at`，不返回 `keywords`/`weight`/`content`。
   - What's unclear: STOR-02 要求 `keywords` 和 `weight` 字段从 PGVector 读取。是需求文档预期有偏差，还是 LightRAG 的 VDB_RELATION 实际存储逻辑与 DDL 不同？
   - Recommendation: Phase 2 实现时，从 VDB_RELATION 表返回 `content` 全文，并从 AGE 图边 properties 中同步查询 `keywords`/`weight`（如果 PHASE2 有图谱访问能力）。或者，如果仅限 PGVector 查询，返回 `keywords=None, weight=None` 并标注为待实现。

2. **STOR-01 `source_id` 字段映射**
   - What we know: VDB_ENTITY 表的 `id` 列是实体的唯一标识。表中没有独立的 `source_id` 列。
   - What's unclear: 需求中的 `source_id` 是指 `id` 列的重命名（即实体自身的标识），还是指原始文档的来源 ID（需要从其他表 join）？
   - Recommendation: 将 `id` 映射为 `source_id`，因为 LightRAG 中 `id` 就是 `entity_name` 的 hash 值，用于标识实体来源。

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.12.13 (asdf) / 3.14.4 (system) | -- |
| asyncpg | Connection pool | Yes (asdf 3.12.13) | 0.31.0 | -- |
| pgvector (Python) | register_vector codec | Yes (asdf 3.12.13) | 0.4.2 | -- |
| pydantic | Data models | Yes | 2.13.4 | -- |
| pydantic-settings | Config integration | Yes | 2.14.1 | -- |
| pytest | Testing | Yes | 9.0.3 | -- |
| pytest-asyncio | Async test support | Yes | 1.3.0 | -- |
| ruff | Lint/format | Yes | 0.15.14 | -- |
| PostgreSQL server | All DB queries | **No** | -- | docker compose / remote PG |
| pgvector extension | Vector search | **No** | -- | Part of PG server setup |
| Apache AGE extension | Graph queries | **No** | -- | Part of PG server setup |
| psql CLI | Manual DB inspection | **No** | -- | pgAdmin / IDE plugin |

**Missing dependencies with no fallback:**
- PostgreSQL server (含 pgvector + Apache AGE 扩展) -- Phase 2 所有数据查询依赖真实 PG 实例。集成测试需要可访问的 LightRAG 数据库。推荐方案：docker compose 启动本地 PG + AGE，或使用远程开发数据库。

**Missing dependencies with fallback:**
- psql CLI -- 使用 Python `asyncpg` 连接 + `SELECT` 查询替代手动检查；或使用 DBeaver/pgAdmin GUI 工具。

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_store.py tests/test_graph.py tests/test_models.py tests/test_pool.py -x -v` |
| Full suite command | `pytest -x -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STOR-01 | PGVector entities_vdb 向量相似度搜索返回 EntityRecord (name, content, source_id, file_path) | unit + integration | `pytest tests/test_store.py::test_search_entities -x` | No -- Wave 0 |
| STOR-02 | PGVector relationships_vdb 向量相似度搜索返回 RelationshipRecord (src_id, tgt_id, content, keywords, weight) | unit + integration | `pytest tests/test_store.py::test_search_relationships -x` | No -- Wave 0 |
| STOR-03 | PGVector chunks_vdb 向量相似度搜索返回 ChunkRecord (content, full_doc_id, chunk_order_index, file_path) | unit + integration | `pytest tests/test_store.py::test_search_chunks -x` | No -- Wave 0 |
| STOR-04 | AGE 图节点查询 (entity_type, description, source_id) + 边查询 (description, keywords, weight) + 邻居遍历 | unit + integration | `pytest tests/test_graph.py -x -v` | No -- Wave 0 |
| D-01..04 | 连接池创建/延迟初始化/参数配置/显式关闭 | unit | `pytest tests/test_pool.py -x -v` | No -- Wave 0 |
| D-05 | workspace 过滤 (所有查询自动 WHERE workspace=$1) | unit + integration | `pytest tests/test_store.py::test_workspace_filter -x` | No -- Wave 0 |
| D-12..14 | 表名自动发现 + 多表变体报错 | unit | `pytest tests/test_store.py::test_table_discovery -x` | No -- Wave 0 |
| D-15 | 只读保证 (query/fetch 不用 execute) | unit (mock 验证) | `pytest tests/test_store.py::test_readonly -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_store.py tests/test_graph.py tests/test_pool.py tests/test_models.py -x --timeout=30`
- **Per wave merge:** `pytest -x -v` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_store.py` -- covers STOR-01, STOR-02, STOR-03 (PGVector 搜索) + workspace filter + 表发现 + 只读验证
- [ ] `tests/test_graph.py` -- covers STOR-04 (AGE 图查询/遍历)
- [ ] `tests/test_models.py` -- covers Pydantic 模型验证 (EntityRecord, RelationshipRecord, ChunkRecord, GraphNode, GraphEdge)
- [ ] `tests/test_pool.py` -- covers 连接池创建/延迟初始化/参数配置/显式关闭
- [ ] `tests/conftest.py` -- 需要扩展：添加 `@pytest.fixture` 提供 mock asyncpg Pool/Connection，或真实数据库 fixture
- [ ] 集成测试数据库 -- 需要 Docker Compose 或 fixture 启动 PG + pgvector + AGE 含测试数据

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | PG 通过用户名/密码认证，Phase 1 已通过 SecretStr 保护 PG_PASSWORD |
| V3 Session Management | No | 连接池管理是内部实现，不涉及用户会话 |
| V4 Access Control | No | 单一 PG 用户访问，不涉及应用层 RBAC |
| V5 Input Validation | **Yes** | Pydantic 模型验证返回数据格式 (EntityRecord, etc.)；asyncpg 参数化查询防止 SQL 注入 |
| V6 Cryptography | No | 传输层加密由 PostgreSQL SSL 配置处理 (Phase 1 PgConfig 可扩展 sslmode 字段) |

### Known Threat Patterns for asyncpg + PostgreSQL

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL 注入 (动态表名 `f"SELECT * FROM {table_name}"`) | Tampering | 表名来自 `information_schema` 查询结果（白名单），不直接接受用户输入；建议额外用正则 `^[a-zA-Z_][a-zA-Z0-9_]*$` 校验 |
| 连接凭证泄露 | Information Disclosure | Phase 1 `SecretStr` 确保日志/错误消息中不泄露密码；连接 URL 中的密码需在连接池创建时转换为参数形式 |
| 只读绕过 (误用 `execute()` 执行 DML) | Elevation of Privilege | D-15 代码层保证：只用 `fetch()`/`fetchrow()`；D-16 code review 门禁；`server_settings={'default_transaction_read_only': 'on'}` 作为数据库层兜底 |
| AGE Cypher 注入 (未转义的 node_id) | Tampering | 使用 `$1::agtype` 参数化传入 node_id (通过 `json.dumps` 序列化)；不将用户输入拼接到 Cypher 字符串中 |
| 向量注入 (恶意构造的 embedding 触发资源消耗) | Denial of Service | `TOP_K` + `COSINE_THRESHOLD` 双重限制结果集大小；`command_timeout` 限制单次查询耗时 |

## Sources

### Primary (HIGH confidence)
- LightRAG `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/kg/postgres_impl.py`:
  - `TABLES` (L:6314-6462): 完整 DDL -- 确认表结构、字段名、类型
  - `SQL_TEMPLATES` (L:6465-6673): entities/relationships/chunks 三种向量查询 SQL（`<=>` + `::vector` 转换模式）
  - `PGVectorStorage.query()` (L:3485-3514): 向量相似度搜索实现
  - `PGGraphStorage._query()` (L:4884-4958): AGE Cypher 查询通用入口 + `_record_to_dict`
  - `PGGraphStorage.get_node_edges()` (L:5045-5068): 图遍历 Cypher (`MATCH (n)-[]-(connected)`)
  - `PGGraphStorage.get_nodes_batch()` (L:5353-5431): 批量节点查询 (UNNEST + parameterized agtype)
  - `PGGraphStorage.get_edges_batch()` (L:5566-5666): 批量边查询 (forward + backward Cypher)
  - `NAMESPACE_TABLE_MAP` (L:6293-6305): namespace to base table name mapping
  - `PostgreSQLDB._create_pool_once()` (L:419-447): pool creation with `register_vector`
  - `PostgreSQLDB.query()` (L:1796-1868): 查询执行 + record conversion 模式
  - `PostgreSQLDB.check_table_exists()` (L:1870-1886): `information_schema.tables` 模式
- Phase 1 `src/lightrag_langchain/config.py`: `PgConfig`, `QueryParamsConfig` -- 连接和查询参数来源
- Phase 1 `tests/conftest.py` + `tests/test_config.py`: 测试模式 (pytest fixtures, TempEnvFile 模式)

### Secondary (MEDIUM confidence)
- asyncpg connection pooling best practices (WebSearch): confirmed `create_pool(min_size, max_size, command_timeout, init, server_settings)` API with read-only configuration [CITED: asyncpg docs via WebSearch]
- pgvector `<=>` operator docs (WebSearch): confirmed cosine distance semantics `1 - cosine_similarity` and `::vector` type cast requirement for index usage [CITED: pgvector DeepWiki]
- Apache AGE Cypher query format docs (WebSearch): confirmed `SELECT * FROM cypher(graph_name, query, params)` syntax and `$_dollar_quote_` escaping pattern [CITED: age.apache.org]

### Tertiary (LOW confidence)
- None -- all critical claims are verified against LightRAG source or official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified via PyPI + slopcheck + LightRAG source
- Architecture: HIGH -- pattern directly extracted from LightRAG reference implementation
- Pitfalls: HIGH -- pitfalls identified from asyncpg docs, LightRAG code patterns, and WebSearch best practices

**Research date:** 2026-05-29
**Valid until:** 2026-07-29 (60 days -- stable PostgreSQL/asyncpg ecosystem)
