# Phase 5: Retriever Interfaces - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

本 phase 交付 6 个 LangChain `BaseRetriever` 子类（NaiveRetriever, LocalRetriever, GlobalRetriever, HybridRetriever, MixRetriever, BypassRetriever），每个封装一种 LightRAG 查询模式。Retriever 负责：接收用户查询文本 → 生成 query embedding → 调用 Phase 4 策略函数 → 将 QueryResult 转换为 `List[Document]`（page_content 为上游 LightRAG 兼容的 JSON 序列化 + metadata 保留结构化引用）。

Scope: 6 个 BaseRetriever 子类、共享基类（embedding 生成、async→sync 桥接、错误处理）、QueryResult→Document 转换、sync `invoke` + async `ainvoke`。
Out of scope: 端到端 QA Chain（Phase 6）、Reranker 集成（Phase 6）、Token 预算控制（Phase 6）、关键词提取（Phase 3 已提供）。

Requirements: RETR-01, RETR-02, RETR-03
</domain>

<decisions>
## Implementation Decisions

### 依赖注入模式

- **D-01:** 构造函数注入 — 每个 Retriever 构造函数接收 `vector_store: PGVectorStore`、`graph_store: PGGraphStore | None`（naive/bypass 不需要 graph）、`embedding_config: EmbeddingConfig`。匹配 Phase 2 D-07 的 DI pool 模式，最直接、最可测试。
- **D-02:** Embedding 延迟初始化 — Retriever 接收 `EmbeddingConfig`，内部首次使用时通过 `create_embedding(config)` 创建。匹配 Phase 2 pool.py 和 Phase 3 lazy proxy 的延迟模式，import 不触发网络连接。
- **D-03:** top_k / chunk_top_k 在构造时设置 — 作为 Retriever 的 Pydantic 字段（可选，默认 None = 使用 Settings 全局值）。匹配 LangChain BaseRetriever 惯例，实例自身持有搜索参数。

### Document 内容格式

- **D-04:** page_content 使用 JSON 对象序列化 — 每个数据记录用 `json.dumps()` 序列化为一行 JSON，字段匹配上游 LightRAG `convert_to_user_format()` 输出：
  - Entity: `{"entity_name": ..., "entity_type": ..., "description": ..., "source_id": ..., "file_path": ...}`
  - Relationship: `{"src_id": ..., "tgt_id": ..., "description": ..., "keywords": ..., "weight": ..., "source_id": ..., "file_path": ...}`
  - Chunk: `{"reference_id": ..., "content": ..., "file_path": ..., "chunk_id": ...}`
  - 格式匹配上游 `kg_query_context` 模板，方便 Phase 6 直接拼装 LLM 上下文。
- **D-05:** metadata 保留 GraphTriple 结构化格式 — 公共字段（source_id, file_path, retrieval_mode）+ 类型特定字段。GraphTriple 的三元组结构（src_entity, relation, tgt_entity）完整保留在 metadata 中供下游程序化访问。Chunks 的 metadata 仅保留 chunk_id、chunk_order_index 等标量字段。

### 类层次与代码共享

- **D-06:** 共享基类 `LightRAGBaseRetriever(BaseRetriever)` — 封装：embedding 生成（D-02）、`asyncio.run` 同步桥接（匹配 LightRAGReranker 模式）、公共错误处理、Logger。子类只需实现 `_get_relevant_documents()` 和 `_aget_relevant_documents()`，各自处理模式特定的策略调用 + QueryResult→Document 转换。
- **D-07:** 6 个子类各自实现模式特定逻辑 — `NaiveRetriever` 只处理 chunks；`LocalRetriever` 处理 entities + graph_triples；`GlobalRetriever` 处理 relations + graph_triples；`HybridRetriever` 处理 entities + relations + graph_triples；`MixRetriever` 处理全部 4 种类型；`BypassRetriever` 返回空列表。

### 模块文件组织

- **D-08:** `retriever/` 包，2-3 文件 — `retriever/base.py`（LightRAGBaseRetriever 基类 + 共享工具函数）、`retriever/retrievers.py`（6 个子类）。可选 `retriever/utils.py` 存放 QueryResult→Document 的转换辅助函数（如转换行数过多）。匹配 Phase 4 `query/results.py` + `query/strategies.py` 的两文件模式。
- **D-09:** `__init__.py` lazy 导出 — 使用 `__getattr__` 模式 lazy import 6 个 Retriever 类，匹配 `data/__init__.py` 和 `query/__init__.py` 的惯例。`import lightrag_langchain.retriever` 不触发 Settings 实例化或网络连接。

### Claude's Discretion

- **基类 vs 子类职责切分**：embedding 生成、async 桥接、错误处理放基类。策略调用 + QueryResult→Document 转换放子类。转换逻辑虽然模式不同，但模式数量有限（最多 4 种转换路径），不需要复杂的策略模式 — 每个子类内部直接实现即可。
- **Document 转换**：实现为内部 helper 函数（每个 retriever 内联或在 `utils.py` 中共用）。Entity/Relation/Chunk 的 JSON 序列化是共通的，提取为共享函数；GraphTriple→Document 的转换因只有 local/global/hybrid/mix 使用，与对应子类内联。
- **BypassRetriever**：直接返回空 `List[Document]`，不做 embedding 生成也不调策略函数。匹配上游 bypass 行为，无依赖。
- **sync 桥接**：使用 `asyncio.run` 桥接同步路径，与 LightRAGReranker 模式一致。不需要 run_in_executor（策略是全 async 的，没有同步版本可用）。
- **Pydantic 字段**：BaseRetriever 继承自 BaseModel，所有构造参数（vector_store, graph_store, embedding_config, top_k, chunk_top_k）声明为 Pydantic 字段，使用 `model_config = ConfigDict(arbitrary_types_allowed=True)` 支持非标准类型。
- **__init__.py 导出**：添加 `__all__` 并注册到顶级 `lightrag_langchain/__init__.py` 的 lazy `__getattr__` 中，与 Phase 3/4 模块一致。
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 需求与范围
- `.planning/ROADMAP.md` §Phase 5 — Goal, 4 项 success criteria, 依赖关系 (Phase 4), requirement 映射 (RETR-01..03)
- `.planning/REQUIREMENTS.md` §RETR — RETR-01 到 RETR-03 详细规范（6 个 BaseRetriever 子类、sync/async、来源 metadata）
- `.planning/PROJECT.md` — Key Decisions 表、Constraints 节、LangChain Retriever + Chain 双层接口决策

### 上游 LightRAG 源码（上下文格式参考）
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py` — `_build_context_str()` (L:3854-4033) 上下文拼装流程；`convert_to_user_format()` 导入 (L:37)
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py` — `convert_to_user_format()` (L:3168-3289) 实体/关系/块格式化结构、字段名定义
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py` — `kg_query_context` (L:278-306) 知识图谱上下文模板；`naive_query_context` (L:308-323) naive 模式模板

### Phase 4 上下文（查询策略 API）
- `.planning/phases/04-query-strategies/04-CONTEXT.md` — QueryResult 中间表示 (D-01/D-02)、预计算向量 (D-03)、GraphTriple 三元组 (D-04)
- `src/lightrag_langchain/query/strategies.py` — 6 个异步策略函数签名和参数：
  - `naive_strategy(query_embedding, *, vector_store, chunk_top_k=None)`
  - `local_strategy(query_embedding, *, vector_store, graph_store, top_k=None)`
  - `global_strategy(query_embedding, *, vector_store, graph_store, top_k=None)`
  - `hybrid_strategy(query_embedding, *, vector_store, graph_store, top_k=None)`
  - `mix_strategy(query_embedding, *, vector_store, graph_store, top_k=None, chunk_top_k=None)`
  - `bypass_strategy()` — 无参数，返回空 QueryResult
- `src/lightrag_langchain/query/results.py` — QueryResult（entities, relations, chunks, graph_triples）+ GraphTriple 模型定义
- `src/lightrag_langchain/query/__init__.py` — Lazy `__getattr__` 导出模式

### Phase 3 上下文（LLM/Embedding）
- `.planning/phases/03-llm-integration/03-CONTEXT.md` — create_embedding() factory (D-01/D-02)
- `src/lightrag_langchain/llm.py` — `create_embedding(config)` → OpenAIEmbeddings
- `src/lightrag_langchain/reranker.py` — LightRAGReranker sync/async 桥接模式参考（`compress_documents` 用 `asyncio.run`，`acompress_documents` 用 `await`）

### Phase 2 上下文（数据层 API）
- `src/lightrag_langchain/data/store.py` — PGVectorStore 公开方法
- `src/lightrag_langchain/data/graph.py` — PGGraphStore 公开方法
- `src/lightrag_langchain/data/models.py` — EntityRecord, RelationshipRecord, ChunkRecord, GraphNode, GraphEdge 字段定义

### Phase 1 上下文
- `.planning/phases/01-configuration/01-CONTEXT.md` — src-layout, Pydantic frozen, SecretStr, lazy 模式
- `src/lightrag_langchain/config.py` — EmbeddingConfig, QueryParamsConfig 字段定义

### LangChain API 参考
- `langchain_core.retrievers.BaseRetriever` — 需实现 `_get_relevant_documents(query) -> list[Document]`，可选覆盖 `_aget_relevant_documents`
- `langchain_core.documents.Document` — `page_content: str` + `metadata: dict`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **6 个查询策略函数** (`query/strategies.py`)：全异步，接收预计算向量 + vector_store/graph_store，返回 QueryResult。Retriever 直接调用这些函数。
- **create_embedding()** (`llm.py`)：Lazy factory，接收 EmbeddingConfig → 返回 OpenAIEmbeddings。Retriever 内部使用。
- **LightRAGReranker async 桥接模式** (`reranker.py`)：`asyncio.run` 用于 sync 路径，直接 `await` 用于 async 路径。Retriever 基类复用此模式。
- **QueryResult + GraphTriple** (`query/results.py`)：冻结 Pydantic 模型，所有字段含完整数据。Retriever 的转换逻辑消费这些模型。

### Established Patterns
- **Lazy `__getattr__` import**: `data/__init__.py`、`query/__init__.py`、顶级 `__init__.py` 均用此模式。Retriever 包沿用。
- **Pydantic frozen 返回类型**: 所有数据模型 frozen=True。Document 转换是纯函数，不修改输入。
- **async/await 全链路**: Phase 2/3/4 全异步 — Retriever 核心也异步，sync 路径用 `asyncio.run` 桥接。
- **参数化查询**: 所有数据库查询使用 `$1, $2, ...` 参数化 — Retriever 不直接写 SQL，通过 store 方法间接调用。
- **渐进拆分**: Phase 1 单文件 → Phase 2 2-3 文件 → Phase 3 4 文件 → Phase 4 package+2 文件。Phase 5 延续 `retriever/` 包 + 2-3 文件模式。

### Integration Points
- **Phase 5 → Phase 4**: Retriever 调用策略函数（传入 query_embedding + stores），消费 QueryResult
- **Phase 5 → Phase 3**: 使用 create_embedding() 生成查询向量
- **Phase 5 → Phase 2**: 通过 PGVectorStore/PGGraphStore 实例（构造函数注入）间接访问数据库
- **Phase 6 → Phase 5**: Chain 调用 `retriever.invoke(query)` → `List[Document]`，然后自行拼装上下文 + token 预算 + LLM 生成
</code_context>

<specifics>
## Specific Ideas

- 上游 LightRAG 的 `_build_context_str()` 定义了实体/关系/块对 LLM 的最终呈现格式（JSONL + kg_query_context 模板包裹）。Phase 5 的 Document page_content 生成上游兼容的 JSON 记录，Phase 6 的 Chain 负责套用 `kg_query_context` / `naive_query_context` 模板完成拼装。
- upstream `convert_to_user_format()` 是实体/关系/块格式化结构的权威参考 — Retriever 的 JSON 序列化字段必须与此函数的输出字段一致。
- GraphTriple 的三元组信息保留在 metadata 而非 page_content 中，因为上游 LightRAG 的 LLM 上下文不使用三元组格式 — 它直接将图扩展结果展开为实体列表 + 关系列表。Phase 6 可以在 metadata 中按需访问三元组做进一步处理。
- BypassRetriever 不调用任何策略函数，不走 embedding 生成，直接返回空列表 — 最简实现。
</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在 phase scope 内
</deferred>

---

*Phase: 5-Retriever Interfaces*
*Context gathered: 2026-05-31*
