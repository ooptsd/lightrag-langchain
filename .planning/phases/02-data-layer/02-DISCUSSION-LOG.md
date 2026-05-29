# Phase 2: Data Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 02-data-layer
**Areas discussed:** 数据库驱动 & 连接池, 数据层抽象设计, 表名发现策略, 只读保证机制

---

## 数据库驱动 & 连接池

### Q1: 数据库驱动选择

| Option | Description | Selected |
|--------|-------------|----------|
| asyncpg (推荐) | 跟随 LightRAG 上游选型。二进制协议最快，pgvector register_vector 无缝集成，Apache AGE 兼容已验证 | ✓ |
| psycopg 3 | 更 Pythonic 的 API，同步+异步双模式，与 SQLAlchemy/LangChain 生态更好集成 | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** asyncpg (推荐)
**Notes:** —

### Q2: 连接池管理方式

| Option | Description | Selected |
|--------|-------------|----------|
| 轻量独立连接池 (推荐) | 简单 asyncpg Pool 封装，.env 配置，不含写路径依赖 | ✓ |
| 复用 LightRAG ClientManager | 引入上游 PostgreSQLDB/ClientManager | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 轻量独立连接池 (推荐)
**Notes:** —

### Q3: 连接池配置参数

| Option | Description | Selected |
|--------|-------------|----------|
| .env 可配置 (推荐) | PG_POOL_MIN_SIZE (2) / PG_POOL_MAX_SIZE (10) / PG_POOL_TIMEOUT (30s) | ✓ |
| 硬编码默认值 | 固定合理默认值，KISS | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** .env 可配置 (推荐)
**Notes:** 默认值覆盖大多数场景，高级用户可按需调优

### Q4: 连接池生命周期

| Option | Description | Selected |
|--------|-------------|----------|
| 延迟初始化 + 显式关闭 (推荐) | 首次查询自动初始化，提供 close() 方法 | ✓ |
| 上下文管理器模式 | async context manager 管理生命周期 | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 延迟初始化 + 显式关闭 (推荐)
**Notes:** —

### Q5: Workspace 策略

| Option | Description | Selected |
|--------|-------------|----------|
| 单 workspace (推荐) | PG_WORKSPACE 配置，默认 'default' | ✓ |
| 多 workspace 支持 | 允许查询时指定 workspace | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 单 workspace (推荐)
**Notes:** —

### Q6: 连接错误重试策略

| Option | Description | Selected |
|--------|-------------|----------|
| 简单重试 (推荐) | 瞬态错误重试 3 次，指数退避 | ✓ |
| 不重试，直接抛异常 | 由上层处理 | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 简单重试 (推荐)
**Notes:** 使用 tenacity 或手动实现

### Q7: 连接池依赖注入

| Option | Description | Selected |
|--------|-------------|----------|
| 默认值 + 手动注入 | 开箱即用，但也允许用户注入自定义池 | ✓ |

**User's choice:** 提供默认连接池，也允许用户手动注入（自由文本输入）
**Notes:** 方便在多组件/服务间共享同一个连接池实例

---

## 数据层抽象设计

### Q1: 抽象粒度

| Option | Description | Selected |
|--------|-------------|----------|
| 2 个核心类 (推荐) | PGVectorStore + PGGraphStore | ✓ |
| 4 个独立类 | Entities / Relationships / Chunks / Graph 各自独立 | |
| 1 个统一 DataAccess | 所有查询方法在一个类中 | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 2 个核心类 (推荐)
**Notes:** 向量操作共享 cosine distance 逻辑，图查询独立

### Q2: 返回类型

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic 模型 (推荐) | EntityRecord / RelationshipRecord / ChunkRecord / GraphNode / GraphEdge | ✓ |
| 原始 dict/list | 零转换开销 | |
| TypedDict | 类型提示但无运行时验证 | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** Pydantic 模型 (推荐)
**Notes:** 与 Phase 1 风格一致

### Q3: 向量接口设计

| Option | Description | Selected |
|--------|-------------|----------|
| 接收预计算向量 (推荐) | search(embedding: list[float], top_k: int) | |
| 接收文本 + embedding_fn | search(query: str, top_k: int) | |
| 你决定 | 由规划阶段决定 | ✓ |

**User's choice:** 你决定 → Claude 选择"接收预计算向量"
**Notes:** 保持 Phase 2 纯净，不依赖 LLM/Embedding

### Q4: 文件组织

| Option | Description | Selected |
|--------|-------------|----------|
| 2-3 个文件 (推荐) | data/store.py + graph.py + models.py | |
| 单个 data.py | 跟随 config.py 惯例 | |
| 你决定 | 由规划阶段决定 | ✓ |

**User's choice:** 你决定 → Claude 选择"2-3 文件"
**Notes:** 数据层代码量预计超过 400 行，拆分为 3 个独立可测文件

---

## 表名发现策略

### Q1: 表名发现方式

| Option | Description | Selected |
|--------|-------------|----------|
| 自动发现 + .env 指定 (推荐) | information_schema.tables 匹配 + PG_TABLE_PREFIX 覆盖 | ✓ |
| .env 显式配置每张表名 | 6 个配置项，用户全手动 | |
| 约定优于配置 | 假设无 model_suffix | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 自动发现 + .env 指定 (推荐)
**Notes:** —

### Q2: 多表变体处理

| Option | Description | Selected |
|--------|-------------|----------|
| 优先匹配 (推荐) | 按优先级自动选择 | |
| 要求用户显式指定 | 检测到多个匹配时直接报错 | ✓ |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 要求用户显式指定
**Notes:** 安全优先，避免读取错误的表

### Q3: AGE 图名称发现

| Option | Description | Selected |
|--------|-------------|----------|
| 与 vector 表统一策略 (推荐) | 自动发现 + .env PG_GRAPH_NAME | ✓ |
| 完全由 .env 指定 | 不自动发现 | |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 与 vector 表统一策略 (推荐)
**Notes:** —

---

## 只读保证机制

### Q1: 只读保证方法

| Option | Description | Selected |
|--------|-------------|----------|
| 多层防御 (推荐) | 代码层 + 事务级 + 文档建议只读角色 | |
| 代码层 + 事务级 | asyncpg query() + READ ONLY 事务 | |
| 纯代码层保证 | 只用 query() 不用 execute() | ✓ |
| 你决定 | 由规划阶段决定 | |

**User's choice:** 纯代码层保证
**Notes:** 最简单方案，依赖代码规范

### Q2: 只读验证方式

| Option | Description | Selected |
|--------|-------------|----------|
| 自动化检测测试 (推荐) | SQL 审计脚本验证无写操作关键字 | |
| Code review 作为门禁 | 依赖 review 确保只读 | ✓ |
| 你决定 | 由规划阶段决定 | |

**User's choice:** Code review 作为门禁
**Notes:** —

---

## Claude's Discretion

- **向量接口设计:** 选择接收预计算向量 `list[float]` 而非文本+embedding函数。保持 Phase 2/3 边界清晰
- **文件组织:** 选择 2-3 文件（store.py + graph.py + models.py）而非单文件

## Deferred Ideas

None — 讨论保持在 phase scope 内
