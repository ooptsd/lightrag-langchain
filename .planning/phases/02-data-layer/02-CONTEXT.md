# Phase 2: Data Layer - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

本 phase 交付一个只读的 PostgreSQL 数据抽象层，封装对 LightRAG 已处理好的 PGVector 向量表和 Apache AGE 图数据库的查询访问。提供两个核心类（PGVectorStore + PGGraphStore），通过 asyncpg 连接池实现高性能异步数据读取。

Scope: entities_vdb / relationships_vdb / chunks_vdb 向量相似度搜索 + AGE 图节点/边查询与遍历。
Out of scope: LLM/Embedding 集成（Phase 3）、查询策略（Phase 4）、LangChain Retriever 接口（Phase 5）。

Requirements: STOR-01, STOR-02, STOR-03, STOR-04
</domain>

<decisions>
## Implementation Decisions

### 数据库驱动 & 连接池
- **D-01:** 数据库驱动使用 **asyncpg**（跟随 LightRAG 上游选型，二进制协议最快，pgvector `register_vector` 无缝集成）
- **D-02:** **轻量独立连接池**（不依赖 LightRAG 的 ClientManager，只封装 asyncpg Pool 的创建/查询/关闭，不含表创建、migration 等写路径逻辑）
- **D-03:** 连接池参数 **.env 可配置**（PG_POOL_MIN_SIZE 默认 2, PG_POOL_MAX_SIZE 默认 10, PG_POOL_TIMEOUT 默认 30s），提供合理默认值覆盖大多数场景
- **D-04:** 连接池生命周期 **延迟初始化 + 显式关闭**（首次查询时自动创建池，提供 `close()` 方法供应用关闭时调用。类似 Phase 1 的 `__getattr__` 延迟单例模式）
- **D-05:** **单 workspace** 策略（通过 .env PG_WORKSPACE 配置，默认 `"default"`。所有查询自动添加 WHERE workspace=$1 过滤）
- **D-06:** **简单重试**（对瞬态连接错误自动重试 3 次，指数退避 1s→2s→4s。不重试查询逻辑错误）
- **D-07:** **连接池依赖注入**（提供默认值开箱即用，也允许用户通过构造函数/工厂方法注入自定义 asyncpg Pool 实例，支持全局共享连接池）

### 数据层抽象设计
- **D-08:** **2 个核心类**：PGVectorStore（统一管理 entities/relationships/chunks 三种向量搜索）+ PGGraphStore（AGE 图查询/遍历）。两者共享底层连接池
- **D-09:** 返回类型使用 **Pydantic 模型**（EntityRecord / RelationshipRecord / ChunkRecord / GraphNode / GraphEdge），与 Phase 1 Pydantic 风格一致，IDE 友好
- **D-10:** 向量搜索接口 **接收预计算向量**（`search_entities(embedding: list[float], top_k: int)`），数据层不做 embedding 生成，保持 Phase 2 纯净，embedding 留给 Phase 3
- **D-11:** 文件组织 **2-3 文件**（`data/store.py` + `data/graph.py` + `data/models.py`），每文件独立可测

### 表名发现策略
- **D-12:** **自动发现 + .env 覆盖**（启动时查询 `information_schema.tables` 匹配 `LIGHTRAG_VDB_*` 模式，.env 提供 PG_TABLE_PREFIX 用于非标准前缀）
- **D-13:** 多表变体时 **报错要求显式指定**（检测到多个 model_suffix 变体时直接报错，让用户在 .env 中明确指定使用哪个）
- **D-14:** AGE 图名称 **与向量表统一策略**（自动发现 + .env PG_GRAPH_NAME 覆盖，检测到多个图时报错）

### 只读保证机制
- **D-15:** **纯代码层保证**（所有查询使用 asyncpg `query()` 方法，不使用 `execute()`。数据层类不暴露任何写方法）
- **D-16:** **Code review 作为门禁**（不编写自动化 SQL 审计测试。依赖 code review 确保只读约束不被违反）

### Claude's Discretion
- **向量接口设计 (D-10):** 选择接收预计算向量（`list[float]`），而非接收文本 + embedding 函数。理由：Phase 2 是纯数据访问层，embedding 生成属于 Phase 3 的 LLM 集成。此设计使 Phase 2 可以不依赖任何 LLM 独立测试和验证
- **文件组织 (D-11):** 选择 2-3 文件而非单文件。理由：数据层代码量预计比 config.py 大（2 个核心类 + 多个 Pydantic 模型 + 连接池管理），单文件会超过 400 行。但不过度拆分——2 个 store 类的代码量在 ~100-200 行/文件是合理的
- **敏感信息处理 (延续 Phase 1 惯例):** PG_PASSWORD 使用 Phase 1 的 SecretStr 模式，日志/错误消息中不包含密码明文
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 需求与范围
- `.planning/ROADMAP.md` §Phase 2 — Goal, 5 项 success criteria, 依赖关系 (Phase 1), requirement 映射 (STOR-01..04)
- `.planning/REQUIREMENTS.md` §STOR — STOR-01 到 STOR-04 详细规范（entities_vdb / relationships_vdb / chunks_vdb / AGE 图数据读取）
- `.planning/PROJECT.md` — Key Decisions 表、Constraints 节（Python>=3.12, 只读, .env 全配置, LLM/Embedding/Reranker 中立）
- `.planning/PROJECT.md` §Context — LightRAG 数据库结构说明

### 上游 LightRAG 源码（数据模型参考）
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/kg/postgres_impl.py` — **关键参考文件**，包含：
  - `TABLES` (L:6314-6462): 完整 DDL 定义 — LIGHTRAG_VDB_ENTITY, LIGHTRAG_VDB_RELATION, LIGHTRAG_VDB_CHUNKS, LIGHTRAG_FULL_ENTITIES, LIGHTRAG_FULL_RELATIONS
  - `SQL_TEMPLATES` (L:6465-6670): 向量查询 SQL（entities/relationships/chunks 三种 namespace 的 cosine distance 搜索）和所有 KV/upsert 操作
  - `NAMESPACE_TABLE_MAP` (L:6294-6301): namespace → 基础表名映射
  - `PGVectorStorage.query()` (L:3485-3514): 向量相似度搜索实现 — `<=>` operator, cosine threshold, top_k 限制
  - `PGVectorStorage.get_by_id()` / `get_by_ids()` (L:3585-3645): 按 ID 获取记录
  - `PGGraphStorage._query()` (L:4884-4958): AGE Cypher 查询通用入口
  - `PGGraphStorage.get_node()` / `get_nodes_batch()` (L:5014-5431): 图节点查询，含 entity_id → 属性映射
  - `PGGraphStorage.get_node_edges()` (L:5045-5068): 图遍历 — `MATCH (n)-[]-(connected)` Cypher 查询
  - `PGGraphStorage.get_edge()` / `get_edges_batch()` (L:5034-5043): 图边查询
  - `PostgreSQLDB` (L:143-1952): 连接管理（asyncpg Pool, query/execute, AGE support）
  - `ClientManager` (L:1952-2194): 全局客户端单例管理

### Phase 1 上下文（决策延续）
- `.planning/phases/01-configuration/01-CONTEXT.md` — 项目结构约定（src-layout, hatchling, pytest, ruff, Pydantic SecretStr, 延迟单例模式, 单文件优先）
- `src/lightrag_langchain/config.py` — Phase 1 实现参考（Settings 单例模式, frozen config, categorized errors, `__getattr__` lazy init）
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 1 config.py**: 延迟单例模式（`__getattr__`）可复用于连接池初始化；SecretStr 可复用于 PG_PASSWORD 处理；frozen settings 可复用于数据层配置
- **LightRAG SQL_TEMPLATES**: entities/relationships/chunks 三种向量查询 SQL 可直接参考（cosine distance `<=>` + threshold + top_k）

### Established Patterns
- **src-layout**: `src/lightrag_langchain/` 下所有新代码
- **单文件优先**: Phase 1 的 config.py（~250 行）是单文件。Phase 2 预计更大，拆分为 2-3 文件
- **Pydantic 优先**: 配置用 pydantic-settings，数据模型用 Pydantic BaseModel，保持一致性
- **延迟初始化**: Phase 1 的 `__getattr__` 模式 → Phase 2 连接池也可用类似延迟创建策略
- **frozen=True**: 配置不可变 → 数据层返回的记录模型也应该考虑不可变

### Integration Points
- **Phase 1 配置系统**: 数据层需要从 `settings.pg` (PgConfig) 读取 PostgreSQL 连接参数；从 `settings.query_params` 读取 cosine_threshold 等查询参数
- **Phase 3 LLM 集成**: 数据层提供向量搜索接口（接受预计算 embedding），Phase 3 调用数据层时传入 embedding
- **Phase 4 查询策略**: 数据层提供原始数据访问，Phase 4 在数据层之上实现 6 种查询模式的检索逻辑
</code_context>

<specifics>
## Specific Ideas

- LightRAG 的 `PGVectorStorage.query()` 返回格式因 namespace 不同而异（entities 返回 entity_name + created_at，relationships 返回 src_id + tgt_id + created_at，chunks 返回 id + content + file_path + created_at）。Phase 2 的 Pydantic 模型应反映这些差异
- LightRAG 使用 `model_suffix` 做表隔离。向量搜索的 `<=>` operator 是 pgvector 扩展的 cosine distance 操作符
- AGE 图查询使用 Cypher → SQL 翻译层。Phase 2 的图查询应该保持参数化（parameterized）以避免注入风险——参考 LightRAG 如何使用 `$1::agtype` 传参
- 连接池依赖注入：用户可在多服务场景下注入共享连接池，避免重复创建
</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在 phase scope 内
</deferred>

---

*Phase: 2-Data Layer*
*Context gathered: 2026-05-29*
