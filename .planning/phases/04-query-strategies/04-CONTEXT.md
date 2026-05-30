# Phase 4: Query Strategies - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning

<domain>
## Phase Boundary

本 phase 交付全部 6 种 LightRAG 查询模式（naive / local / global / hybrid / mix / bypass）的检索策略实现。每种模式调用 Phase 2 数据层（PGVectorStore + PGGraphStore）和 Phase 3 的 embedding 服务，产出结构化中间结果供 Phase 5 Retriever 消费。

Scope: 6 种查询模式的检索逻辑、图遍历编排（local/global/hybrid/mix）、结果合并算法（hybrid round-robin、mix）、空检索模式（bypass）。
Out of scope: LangChain BaseRetriever 接口（Phase 5）、端到端 QA Chain（Phase 6）、Reranker 重排序（Phase 5/6）、Keyword Extraction（Phase 3 已提供）、Token Budget 截断（Phase 3 已提供，Phase 6 拼装时调用）。

Requirements: QUERY-01, QUERY-02, QUERY-03, QUERY-04, QUERY-05, QUERY-06
</domain>

<decisions>
## Implementation Decisions

### 结果格式与接口契约

- **D-01:** 返回格式 — **结构化中间表示**。6 种模式返回强类型 Pydantic 模型 `QueryResult`，包含检索到的原始数据（entities / relations / chunks / graph triples）。Phase 4 只管检索逻辑，Phase 5 Retriever 负责转换为 LangChain Document，Phase 6 Chain 负责上下文拼装和 token 预算控制。
- **D-02:** 类型设计 — **单一联合类型**。一个 `QueryResult` 模型包含所有可能的字段（entities, relations, chunks, graph_triples），各模式只填充自己相关的字段，未使用的字段为默认空值。简单直接，避免过度抽象。
- **D-03:** Embedding 定位 — **接收预计算向量**。每个查询策略方法接收 `query_embedding: list[float]` 参数，内部不做 embedding 生成。延续 Phase 2 D-10 设计（PGVectorStore.search_entities/relationships/chunks 均接收预计算向量），保持策略层纯检索逻辑。
- **D-04:** 图结果表示 — **三元组扁平化**。图遍历结果（节点+边+邻居）展开为 `(entity, relation, entity)` 三元组列表，每个三元组包含源节点、边、目标节点的完整属性。匹配上游 LightRAG 的上下文组装方式，方便 Phase 6 直接序列化给 LLM。

### Claude's Discretion

- **模块组织**: 遵循 Phase 2/3 渐进拆分模式（单文件→2-3 文件→适当拆分）。6 种查询模式作为策略函数或类，集中在一个 `query.py` 模块中，或按逻辑分组为 `query/strategies.py` + `query/results.py`。具体文件数量由计划阶段根据代码量决定。
- **Reranker 定位**: Reranker 不在 Phase 4 范围内。用户选择"结构化中间表示"明确了 Phase 4 职责边界——产出原始检索结果。Reranker 由 Phase 5 Retriever 或 Phase 6 Chain 在结果消费侧应用。
- **Naive 模式 KG_CHUNK_PICK_METHOD**: VECTOR 模式（默认）使用 pgvector `<=>` cosine distance 排序选 top chunks。WEIGHT 模式需要研究上游 LightRAG 行为——可能基于 chunks_vdb 表的特定字段排序，或需要从其他表获取权重信息。由 Phase Researcher 确认并在 PLAN.md 中记录实现方案。
- **Hybrid/Mix 合并算法**: Hybrid 的 round-robin 交错合并和 Mix 的 chunk 融合策略遵循上游 LightRAG 行为。由 Phase Researcher 读取上游源码确认具体实现细节。
- **Bypass 模式**: 直接返回空的 QueryResult（所有字段为空列表），不做任何数据库查询。Phase 6 Chain 检测到空结果时跳过上下文组装，直接 LLM 生成。
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 需求与范围
- `.planning/ROADMAP.md` §Phase 4 — Goal, 6 项 success criteria, 依赖关系 (Phase 2 + Phase 3), requirement 映射 (QUERY-01..06)
- `.planning/REQUIREMENTS.md` §QUERY — QUERY-01 到 QUERY-06 详细规范（6 种查询模式的检索策略描述）
- `.planning/PROJECT.md` — Key Decisions 表、Constraints 节、LightRAG 六种查询模式概述

### 上游 LightRAG 源码（查询策略关键参考）
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py` — **查询策略核心文件**：6 种查询模式的完整检索流程（naive_search / local_search / global_search / hybrid_search / mix_search / bypass_search），图遍历编排，结果合并算法
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/kg/postgres_impl.py` — PGVector/PGGraph 底层查询实现，SQL 模板，数据格式
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py` — `truncate_list_by_token_size` 实现，TiktokenTokenizer

### Phase 2 上下文（数据层 API）
- `.planning/phases/02-data-layer/02-CONTEXT.md` — PGVectorStore/PGGraphStore 设计决策（DI pool D-07, 预计算向量 D-10, 只读 D-15）
- `src/lightrag_langchain/data/store.py` — PGVectorStore 公开 API: `search_entities()`, `search_relationships()`, `search_chunks()`
- `src/lightrag_langchain/data/graph.py` — PGGraphStore 公开 API: `get_node()`, `get_nodes_batch()`, `get_edge()`, `get_edges_batch()`, `get_node_edges()`
- `src/lightrag_langchain/data/models.py` — EntityRecord, RelationshipRecord, ChunkRecord, GraphNode, GraphEdge

### Phase 3 上下文（LLM/Embedding/Token）
- `.planning/phases/03-llm-integration/03-CONTEXT.md` — LLM/Embedding/Reranker/Keyword/Token Budget 设计决策
- `src/lightrag_langchain/llm.py` — `create_embedding(config)` → OpenAIEmbeddings（向量化查询文本）
- `src/lightrag_langchain/keywords.py` — `extract_keywords()` — Phase 5/6 调用（非 Phase 4）
- `src/lightrag_langchain/token_budget.py` — `truncate_entities_by_tokens()` 等 — Phase 6 调用（非 Phase 4）
- `src/lightrag_langchain/config.py` — `QueryParamsConfig` (top_k, chunk_top_k, cosine_threshold, kg_chunk_pick_method)

### Phase 1 上下文
- `.planning/phases/01-configuration/01-CONTEXT.md` — Pydantic frozen, SecretStr, src-layout, hatchling, pytest, ruff
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **PGVectorStore**: 3 个向量搜索方法（search_entities / search_relationships / search_chunks），接收 `list[float]` 预计算向量，返回 Pydantic frozen 记录列表
- **PGGraphStore**: 5 个图查询方法（get_node / get_nodes_batch / get_edge / get_edges_batch / get_node_edges），参数化 Cypher 查询
- **create_embedding()**: Phase 3 lazy factory，生成 OpenAIEmbeddings 实例用于查询向量化（Phase 5/6 调用后传入策略）
- **QueryParamsConfig**: top_k, chunk_top_k, cosine_threshold, kg_chunk_pick_method 等查询参数从 settings.query_params 读取

### Established Patterns
- **Pydantic frozen 返回类型**: 所有返回数据模型使用 `frozen=True`（data/models.py）
- **DI pool 模式**: PGVectorStore 和 PGGraphStore 支持 `pool: asyncpg.Pool | None = None` 构造参数
- **延迟初始化**: Phase 2/3 的 lazy init 模式 — QueryResult 可以直接 import 不触发连接
- **async/await 全链路**: Phase 2 数据层全异步 — Phase 4 策略方法也应为 async
- **Parameterized queries**: Phase 2 所有 SQL 使用 `$1, $2, ...` 参数化 — Phase 4 不直接写 SQL，通过 store 方法间接调用

### Integration Points
- **Phase 4 → Phase 5**: QueryResult 中间表示 → BaseRetriever.invoke() → List[Document]
- **Phase 5/6 → Phase 4**: 先调 create_embedding() 生成 query_embedding，再传入策略方法
- **Phase 4 → Phase 2**: 策略方法调用 store.search_*() 和 graph.get_*() 方法
- **Phase 6 → Phase 3**: 上下文拼装时调用 token_budget 函数截断 QueryResult 中的数据
</code_context>

<specifics>
## Specific Ideas

- 上游 LightRAG 的 local/global 使用两阶段检索：向量搜索 Top-K → 图扩展获取邻居 → 可能做第二轮向量搜索补充。Phase Researcher 需确认具体流程。
- Hybrid 的 round-robin 交错方式需确认：按结果位置交替（local[0], global[0], local[1], global[1]...）还是有其他优先级规则。
- KG_CHUNK_PICK_METHOD = "WEIGHT" 时，chunks_vdb 表可能没有 weight 列。上游 LightRAG 可能从 chunks 的 metadata 或其他表获取权重。需要研究确认。
- QueryResult 的 graph_triples 字段：每个 triple 需包含 src 节点属性（entity_type, description, source_id）+ edge 属性（description, keywords, weight）+ tgt 节点属性。保留了完整信息供 Phase 5/6 灵活格式化。
</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在 phase scope 内
</deferred>

---

*Phase: 4-Query Strategies*
*Context gathered: 2026-05-30*
