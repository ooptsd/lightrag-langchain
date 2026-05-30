# Phase 3: LLM Integration - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning

<domain>
## Phase Boundary

本 phase 交付 LLM、Embedding、Reranker 三个服务的可切换集成层 + LLM 关键词提取 + Token 预算控制工具。通过 .env 配置的 binding/host/api_key/model 驱动，支持任意 OpenAI 兼容 API 的 provider 切换。

Scope: ChatOpenAI/OpenAIEmbeddings 兼容接口创建、多 Reranker 后端切换（aliyun/cohere/jina）、LLM 结构化关键词提取、Token 预算计算与截断。
Out of scope: 查询策略逻辑（Phase 4）、LangChain Retriever 接口（Phase 5）、端到端 QA Chain 拼装（Phase 6）、数据层访问（Phase 2）。

Requirements: LLM-01, LLM-02, LLM-03, LLM-04, LLM-05
</domain>

<decisions>
## Implementation Decisions

### LLM/Embedding 服务封装
- **D-01:** Thin factory 函数 — `create_llm(config: LlmConfig) → ChatOpenAI` 和 `create_embedding(config: EmbeddingConfig) → OpenAIEmbeddings`，直接映射 config 字段到 LangChain 构造参数。provider 切换由 LangChain 原生支持
- **D-02:** 延迟初始化 — factory 返回 lazily-initialized proxy（`__getattr__` 模式），与 config.py settings 和 data/__init__.py 的 PGVectorStore/PGGraphStore 行为一致。import llm module 不触发 LLM 连接
- **D-03:** 配置来源 — 严格从 LlmConfig / EmbeddingConfig 读取参数（temperature, max_tokens 等），factory 不提供 override 参数。下游如需不同参数，直接操作 ChatOpenAI 实例
- **D-04:** 文件位置 — `src/lightrag_langchain/llm.py`，包含两个 factory 函数

### Reranker 多后端接口
- **D-05:** 接口方式 — Factory + Protocol：`create_reranker(config: RerankerConfig) → Reranker` (typing.Protocol)，根据 RERANK_BINDING 返回对应实现
- **D-06:** LangChain 集成 — 双层接口：底层 raw `async rerank(query: str, documents: list[str]) → list[dict]`（provider 无关，标准化为 [{index, score}]）；顶层 `LightRAGReranker(BaseDocumentCompressor)` 封装 Document ↔ str 转换，可直接用于 LangChain ContextualCompressionRetriever
- **D-07:** HTTP 客户端 — httpx（LangChain 生态标准，自带连接池/超时），不引入 aiohttp 额外依赖
- **D-08:** 重试策略 — 与 Phase 2 pool.py 一致：3 retries, exponential backoff 1s→2s→4s, tenacity。不重试 4xx 客户端错误
- **D-09:** 文件位置 — `src/lightrag_langchain/reranker.py`

### Keyword Extraction
- **D-10:** 实现方式 — LangChain `llm.with_structured_output(KeywordsSchema)` + Pydantic model（`high_level_keywords: list[str]`, `low_level_keywords: list[str]`）。类型安全、LangChain 惯用
- **D-11:** Prompt 模板 — 复用上游 LightRAG `lightrag/prompt.py` 的 `keywords_extraction` prompt 模板 + `keywords_extraction_examples`（角色/目标/指令/示例），解析方式改为 structured output
- **D-12:** 缓存 — 不支持缓存。Phase 3 只做提取，缓存由 Phase 6 QA Chain 通过 LangChain cache 机制处理
- **D-13:** 语言配置 — 通过 .env `KEYWORD_LANGUAGE` 配置，默认 `"Chinese"`，填入上游 prompt 模板的 `{language}` 占位符
- **D-14:** 回退策略 — 不提供 json_repair 回退。依赖 LLM provider 的 structured output（JSON mode）能力，不支持的 provider 快速报错
- **D-15:** 文件位置 — `src/lightrag_langchain/keywords.py`

### 模块组织 & Token 预算
- **D-16:** 文件总数 — 4 文件：`llm.py` + `reranker.py` + `keywords.py` + `token_budget.py`。每个文件 80–150 行，小而专注
- **D-17:** Token 预算位置 — 独立 `token_budget.py`：纯计算工具函数（`truncate_entities_by_tokens()` / `truncate_relations_by_tokens()` / `compute_chunk_token_budget()` → remaining_tokens）。Phase 4/6 调用这些函数实现上下文拼装
- **D-18:** Tokenizer — tiktoken（LangChain 依赖，与上游 LightRAG 的 TiktokenTokenizer 一致，支持 gpt-4o/gpt-4o-mini 编码）
- **D-19:** Token 预算接口 — 同步纯函数 + async wrapper。核心计算不涉及 I/O，异步 wrapper 适配 Phase 4/6 的 async pipeline
- **D-20:** Token 参数来源 — 从 `QueryParamsConfig` 读取 `max_entity_tokens` / `max_relation_tokens` / `max_total_tokens`（Phase 1 已定义且包含 token budget invariant D-08）

### Claude's Discretion
- `create_embedding()` 遵循与 `create_llm()` 相同的 lazy `__getattr__` 模式（D-02）
- Token 预算函数切分：3 个截断函数（entities/relations/chunks）+ 1 个剩余容量计算函数。遵循单一职责原则
- `__init__.py` 使用与 `data/__init__.py` 相同的 `__getattr__` lazy import 模式，避免 import 时触发 Settings 实例化
- LLM / Embedding / Reranker 的 `__repr__` / `__str__` 不暴露 SecretStr 值，延续 Phase 1 安全约定（config.py L:38 注释）
- Reranker 的 raw method 签名统一为 `async rerank(query: str, documents: list[str], top_n: int | None = None) → list[dict[str, Any]]`，返回 `[{"index": int, "relevance_score": float}, ...]`
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 需求与范围
- `.planning/ROADMAP.md` §Phase 3 — Goal, 5 项 success criteria, 依赖关系 (Phase 1), requirement 映射 (LLM-01..05)
- `.planning/REQUIREMENTS.md` §LLM — LLM-01 到 LLM-05 详细规范（ChatOpenAI 兼容、Embedding 兼容、多 Reranker、关键词提取、Token 预算）
- `.planning/PROJECT.md` — Key Decisions 表、Constraints 节（Python>=3.12, Langchain>=1.2.3, LLM/Embedding/Reranker 中立, .env 全配置）

### 上游 LightRAG 源码（LLM 集成参考）
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/rerank.py` — **Reranker 关键参考**：`generic_rerank_api()` (L:182-365) 统一 rerank 入口；`cohere_rerank()` (L:368-432) / `jina_rerank()` (L:435-472) / `ali_rerank()` (L:475-512) 三个 thin adapter；`chunk_documents_for_rerank()` (L:22-113) 文档切分；`aggregate_chunk_scores()` (L:116-171) 分数聚合
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py` §keywords_extraction — **关键词提取 Prompt**：`PROMPTS["keywords_extraction"]` (L:325-349) 完整 prompt 模板（角色/目标/指令/约束/输出格式）；`PROMPTS["keywords_extraction_examples"]` (L:351-376) 3 个中文示例
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py` — `extract_keywords_only()` (L:3204-3289) 关键词提取完整流程；`get_keywords_from_query()` (L:3172-3201) 预提供关键词检查；token budget 截断逻辑 (L:3601-3749) — `truncate_list_by_token_size` 使用方式
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py` — `truncate_list_by_token_size()` 实现，`TiktokenTokenizer` 类

### Phase 1 上下文（配置依赖）
- `.planning/phases/01-configuration/01-CONTEXT.md` — 项目结构约定（src-layout, hatchling, pytest, ruff, Pydantic SecretStr, 延迟单例, frozen=True）
- `src/lightrag_langchain/config.py` — Phase 1 实现：`LlmConfig` / `EmbeddingConfig` / `RerankerConfig` / `QueryParamsConfig` 完整字段定义；`Settings` 单例模式；`__getattr__` lazy init；categorized error formatting

### Phase 2 上下文（模式延续）
- `.planning/phases/02-data-layer/02-CONTEXT.md` — DI 模式 (D-07 pool 支持外部注入)；Pydantic frozen 返回类型 (D-09)；重试策略 (D-06: 3 retries, 1s→2s→4s)；lazy import in __init__.py (data/__init__.py L:20-32)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **config.py Settings 单例**: `from lightrag_langchain.config import settings` — Phase 3 所有服务从 `settings.llm` / `settings.embedding` / `settings.reranker` / `settings.query_params` 读取配置
- **config.py `__getattr__` lazy init**: llm.py / reranker.py / keywords.py 的 factory 函数可复用此延迟模式（`__getattr__` 或懒加载 proxy）
- **data/__init__.py lazy import**: PGVectorStore/PGGraphStore 的 lazy import 模式可直接应用于 Phase 3 各模块的导出

### Established Patterns
- **src-layout**: `src/lightrag_langchain/` 下所有新代码
- **Pydantic frozen**: 所有返回模型 frozen=True（KeywordsSchema, 与 data/models.py 一致）
- **延迟初始化**: 从 config.py → data/pool.py 一脉相承，Phase 3 延续
- **DI 友好**: Phase 2 pool 支持外部注入，Phase 3 factory 也应支持传入自定义 ChatOpenAI 实例（测试 mock）
- **tenacity 重试**: Phase 2 的 retry 模式（3 retries, exponential backoff, 只重试瞬态错误）直接复用于 reranker HTTP 调用
- **SecretStr 安全**: LLM/Embedding/Reranker 的 API key 使用 SecretStr，`__repr__` 不暴露
- **单文件优先 → 适度拆分**: Phase 1 单文件，Phase 2 拆 2-3 文件，Phase 3 拆 4 文件 — 代码量驱动的渐进拆分

### Integration Points
- **Phase 1 配置系统**: Phase 3 所有服务通过 `settings.llm` / `settings.embedding` / `settings.reranker` / `settings.query_params` 读取配置
- **Phase 2 数据层**: Phase 3 的 embedding 生成结果（向量）传入 Phase 2 的 `PGVectorStore.search_*()` 方法；Phase 3 不直接依赖数据层
- **Phase 4 查询策略**: Phase 4 使用 Phase 3 的 LLM（关键词提取）、Embedding（查询向量化）、Reranker（结果重排序）、Token Budget（上下文截断）
- **Phase 6 QA Chain**: Phase 6 使用 Phase 3 的所有服务 + Phase 2 数据层 + Phase 4 查询策略 + Phase 5 Retriever
</code_context>

<specifics>
## Specific Ideas

- 上游 LightRAG 的 rerank.py `generic_rerank_api` 使用 `aiohttp` + 手动连接管理。本项目改用 `httpx` + LangChain 标准，但保留相同的 response format 适配逻辑（aliyun `output.results` vs. standard `results`）
- 上游 prompt.py 的 `keywords_extraction_examples` 是中文领域（应急管理/三防）的 3 个示例。Phase 3 应保留这些示例原样，下游用户可通过 `KEYWORD_LANGUAGE` 和自定义 prompt 覆盖
- Reranker 的 `BaseDocumentCompressor` 实现需要处理 LangChain Document 的 `page_content` 提取和 score 回写（`document.metadata["relevance_score"]`）
- Token 预算函数应按 entities → relations → chunks 的优先级顺序分配 token（实体优先级最高），剩余 token 全部分配给 chunks，匹配上游 LightRAG 的 `_truncate_context_by_tokens` 逻辑
</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在 phase scope 内
</deferred>

---

*Phase: 3-LLM Integration*
*Context gathered: 2026-05-30*
