# Phase 6: QA Chain - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

本 phase 交付端到端 LCEL QA Chain：用户查询 → 关键词提取（LLM）→ Retriever 检索 → 上下文拼装（Token 预算控制）→ LLM 生成 → 带引用来源的最终答案。Chain 支持 `invoke` / `ainvoke` / `astream` 三种调用方式，预提供关键词可跳过 LLM 提取步骤。

Scope: 6 个 Chain 类（NaiveChain / LocalChain / GlobalChain / HybridChain / MixChain / BypassChain）、共享基类 LightRAGBaseChain（关键词提取、Document→dict 转换、上下文拼装、token 截断、LLM 调用、流式管道）、上游 prompt 模板嵌入、引用来源生成、`chain/` 包 + 顶级 `__init__.py` lazy 导出。
Out of scope: Retriever 实现（Phase 5）、查询策略逻辑（Phase 4）、LLM/Embedding/Reranker 服务（Phase 3）、数据层（Phase 2）、配置（Phase 1）。

Requirements: CHAIN-01, CHAIN-02, CHAIN-03
</domain>

<decisions>
## Implementation Decisions

### Chain 架构设计

- **D-01:** 6 个独立 Chain 类 — NaiveChain / LocalChain / GlobalChain / HybridChain / MixChain / BypassChain。每种查询模式一个 Chain 类，用户通过选择使用哪个 Chain 类决定查询模式。每个 Chain 构造函数注入对应的 Retriever 实例（D-04）、ChatOpenAI 实例（LLM）、配置参数（keyword_language）。模式由 Chain 类固化，不在 invoke 时传递。

- **D-02:** 共享基类 `LightRAGBaseChain(BaseModel)` — 封装所有跨模式共享逻辑：关键词提取（调用 Phase 3 `extract_keywords()`）、Document→dict 转换（从 Document.metadata 和 page_content 还原结构化数据）、Token 预算截断（调用 Phase 3 `truncate_entities_by_tokens` / `truncate_relations_by_tokens` / `compute_chunk_token_budget`）、上下文拼装（填入上游 prompt 模板）、LLM 调用、流式管道（`astream` token-by-token + 最后完整 dict）、引用来源生成（file_path 去重 + 自增编号）。子类只需提供 retriever + 选择上下文模板类型（kg_rag / naive_rag / bypass）。

- **D-03:** Chain 输入 — `invoke(query: str, *, system_prompt: str | None = None, hl_keywords: list[str] | None = None, ll_keywords: list[str] | None = None, **kwargs) → dict`。`hl_keywords` / `ll_keywords` 提供时跳过 LLM 关键词提取（CHAIN-03）。`system_prompt` 提供时替换默认上游模板（D-07）。Chain 的输出 dict 结构：`{"answer": str, "sources": list[dict], "keywords": {"high_level": list[str], "low_level": list[str]}, "mode": str}`。

- **D-04:** Retriever 构造函数注入 — Chain 构造函数接收外部创建好的完整 Retriever 实例（`retriever: LightRAGBaseRetriever`），匹配 Phase 5 D-01 构造函数注入模式和项目 DI 惯例。Chain 不关心 Retriever 如何创建，只调用 `retriever.ainvoke(query)` → `list[Document]`。测试 mock 最方便。

- **D-05:** 模块组织 — `chain/` 包：`chain/base.py`（LightRAGBaseChain 基类 + 共享逻辑）、`chain/chains.py`（6 个子类）、`chain/__init__.py`（lazy `__getattr__` export）。匹配 Phase 5 `retriever/` 的两文件 + __init__ 模式。6 个子类加入顶级 `lightrag_langchain/__init__.py` 的 lazy `__getattr__` 中。

- **D-06:** LLM 注入 — Chain 构造函数接收 `llm: ChatOpenAI` 实例（构造函数注入，与 Retriever 对称）。同一 LLM 实例同时用于关键词提取和最终答案生成（匹配上游 LightRAG 行为 — 单一 LLM 实例做所有事情）。Chain 不从 config 内部创建 LLM。

### Prompt 模板定制

- **D-07:** 复用上游 LightRAG prompt 模板 — 知识图谱模式（local/global/hybrid/mix）使用 `PROMPTS["kg_query_context"]` 拼装上下文 + `PROMPTS["rag_response"]` 作为系统提示。naive 模式使用 `PROMPTS["naive_query_context"]` + `PROMPTS["naive_rag_response"]`。bypass 模式无上下文，使用 `PROMPTS["rag_response"]` 系统提示直接回答问题。模板嵌入为模块级常量，匹配 Phase 3 关键词模板嵌入方式。

- **D-08:** system_prompt 整篇替换 — `system_prompt` 参数替换整篇系统提示模板（包括角色、目标、指令、引用格式等全部内容）。为 `None` 时使用上游默认模板。不提供部分覆盖（如仅覆盖 `{user_prompt}` 插值）。调用者可完全控制 LLM 行为。

### 流式输出

- **D-09:** astream 语义 — `astream(query, ...) → AsyncIterator[str | dict]`。先逐 token yield 纯文本 `str` 内容，最后一个 chunk yield 完整结果 `dict`（含 `answer`、`sources`、`keywords`、`mode`）。调用者通过 `isinstance(chunk, dict)` 区分文本流和最终结构化结果。匹配 LangChain `astream_events` / `astream` 的惯用模式。

- **D-10:** sources 在流式前已确定 — 引用来源（reference_list）+ 关键词（keywords）在上下文拼装后、LLM 调用前已计算完成。astream 时这些数据暂存，在流式结束后随最后一个 yield 返回。无需等待 LLM 完成即可确定引用。

### 引用来源生成

- **D-11:** 按 file_path 去重生成 reference_list — 从 Retriever 返回的所有 Document 的 metadata 中提取 file_path（entities/relations 的 file_path 来自 metadata，chunks 的 file_path 来自 page_content JSON 解析或 metadata）。以 file_path 为 key 去重，生成 `[{"reference_id": int, "file_path": str}]` 列表。

- **D-12:** 自增数字 reference_id — `[1]`, `[2]`, `[3]`... 依次编号。匹配上游 LightRAG 行为（`generate_reference_list_from_chunks` 使用顺序编号）。数字简短，在 LLM prompt 中节省 token，LLM 输出引用时也更准确。

### Claude's Discretion

- **Chain 输出 dict 结构**: `{"answer": str, "sources": [{"reference_id": int, "file_path": str}, ...], "keywords": {"high_level": list[str], "low_level": list[str]}, "mode": str}`。sources 是 reference_list，keywords 是提取或预提供的关键词，mode 是 Chain 类对应的查询模式名。
- **bypass 模式**: BypassChain 跳过关键词提取和检索步骤，直接用 `PROMPTS["rag_response"]` 系统提示 + 用户查询调用 LLM。返回空 sources、空 keywords。
- **空结果行为**: retriever 返回空文档列表时，Chain 告知 LLM "无上下文信息"（通过拼装空的 kg_context），由 LLM 自行回应。不提前短路，匹配上游 LightRAG 行为。
- **同一 LLM 实例**: 关键词提取和最终答案生成共用同一个 ChatOpenAI 实例。简化依赖管理，匹配上游 LightRAG 行为。
- **keyword_language**: 从 `settings.query_params.keyword_language` 读取，不暴露为 Chain 参数。下游如需自定义语言，调整 `.env` 或 Settings 单例。
- **Token 预算执行顺序**: entities → relations → chunks（匹配上游优先级）。先截断 entities/relations 列表 → 计算剩余 token → 动态分配 chunks 配额。截断发生在 Document→dict 转换后、拼装 kg_context 模板前。
- **Document→dict 转换**: 共享工具函数，解析 Document.page_content JSON 字符串还原为 dict，从 metadata 补充 fields（entity_type、description、keywords、weight 等）。entities/relations/chunks 各有专用转换函数。这些是纯函数，放在 `base.py` 或独立的 `chain/utils.py` 中。
- **错误处理**: Chain 层不做额外错误恢复 — 信任 Retriever/LLM 自身的错误传播。如果关键词提取失败、LLM 调用失败，异常向上传播给调用者。
- **Pydantic 字段**: LightRAGBaseChain 继承 BaseModel，构造参数（retriever、llm、keyword_language、top_k、chunk_top_k）声明为 Pydantic 字段，使用 `model_config = ConfigDict(arbitrary_types_allowed=True)`。
- **__init__.py lazy export**: 6 个 Chain 类注册到 `lightrag_langchain/__init__.py` 的 `__getattr__` 中，匹配 Phase 3/4/5 的 lazy import 模式。`import lightrag_langchain` 不触发 Settings 实例化或网络连接。
- **Prompt 模板嵌入格式**: 匹配 Phase 3 `keywords.py` 的嵌入方式 — 模块级常量 `RAG_RESPONSE_PROMPT`、`KG_QUERY_CONTEXT_TEMPLATE` 等，从上游 `lightrag/prompt.py` 逐字复制。`{context_data}` 等占位符保留，由 Chain 在调用时通过 `.format()` 填充。
- **Conversation history**: 本 phase 不支持对话历史。Chain 每次 invoke 独立处理，无状态。对话历史管理在 v2 CHAIN-05 中考虑（REQUIREMENTS.md）。上游模板中的"对话历史"指令自然成为 no-op（没有历史内容可引用）。
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 需求与范围
- `.planning/ROADMAP.md` §Phase 6 — Goal, 5 项 success criteria, 依赖关系 (Phase 5 + Phase 3), requirement 映射 (CHAIN-01..03)
- `.planning/REQUIREMENTS.md` §CHAIN — CHAIN-01 到 CHAIN-03 详细规范（完整 LCEL Chain、invoke/ainvoke/astream、预提供关键词）
- `.planning/PROJECT.md` — Key Decisions 表、Constraints 节、LightRAG 六种查询模式概述

### 上游 LightRAG 源码（Prompt 模板 + Chain 流程）
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py` — **Prompt 模板核心文件**:
  - `PROMPTS["rag_response"]` (L:170-222) — 知识图谱 QA 系统提示（角色/目标/指令/引用格式）
  - `PROMPTS["naive_rag_response"]` (L:224-276) — naive 模式系统提示（纯文档片段 QA）
  - `PROMPTS["kg_query_context"]` (L:278-306) — 知识图谱上下文组装模板（entities + relations + chunks + reference_list）
  - `PROMPTS["naive_query_context"]` (L:308-323) — naive 模式上下文模板（chunks + reference_list）
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py` — **Chain 流程参考**:
  - `_build_context_str()` (L:3854-4033) — 完整上下文拼装流程：entities/relations 序列化 → token 计算 → chunk 截断 → reference_list 生成 → kg_context 模板填充
  - `_build_query_context()` (L:4037+) — 4 阶段流程：Search → Truncate → Merge → Build LLM Context

### Phase 5 上下文（Retriever API）
- `.planning/phases/05-retriever-interfaces/05-CONTEXT.md` — Retriever 设计决策（构造函数注入 D-01、Document JSON 格式 D-04、metadata 结构 D-05、基类模式 D-06）
- `src/lightrag_langchain/retriever/base.py` — LightRAGBaseRetriever 公开 API: `_get_relevant_documents(query)`, `_aget_relevant_documents(query)`, `_generate_query_embedding(query)`
- `src/lightrag_langchain/retriever/retrievers.py` — 6 个 Retriever 类及其返回的 Document 类型（entity/relation/chunk/graph_triple）
- `src/lightrag_langchain/retriever/utils.py` — Document 转换函数（entity_to_document / relation_to_document / chunk_to_document / graph_triple_to_document），JSON page_content 格式 + metadata field 定义

### Phase 4 上下文（查询策略 → QueryResult）
- `.planning/phases/04-query-strategies/04-CONTEXT.md` — QueryResult 结构 (D-01/D-02)、GraphTriple 三元组 (D-04)
- `src/lightrag_langchain/query/results.py` — QueryResult（entities / relations / chunks / graph_triples 四个字段）、GraphTriple 模型

### Phase 3 上下文（LLM/Embedding/Keyword/Token）
- `.planning/phases/03-llm-integration/03-CONTEXT.md` — LLM/Embedding/Reranker/Keyword/Token Budget 设计决策
- `src/lightrag_langchain/llm.py` — `create_llm(config)` / `create_embedding(config)` lazy factories
- `src/lightrag_langchain/keywords.py` — `extract_keywords(query, llm, language)` → KeywordsSchema、prompt 模板嵌入方式（模块级常量）
- `src/lightrag_langchain/token_budget.py` — `truncate_entities_by_tokens()` / `truncate_relations_by_tokens()` / `compute_chunk_token_budget()` 及 async wrappers
- `src/lightrag_langchain/config.py` — QueryParamsConfig（max_entity_tokens / max_relation_tokens / max_total_tokens / keyword_language 等）

### Phase 1/2 上下文
- `.planning/phases/01-configuration/01-CONTEXT.md` — src-layout, Pydantic frozen, SecretStr, lazy 模式
- `src/lightrag_langchain/config.py` — Settings 单例、LlmConfig / QueryParamsConfig 完整字段
- `src/lightrag_langchain/data/store.py` / `src/lightrag_langchain/data/graph.py` — PGVectorStore / PGGraphStore 公开 API（间接引用 — Chain 通过 Retriever 间接使用）
- `src/lightrag_langchain/data/models.py` — EntityRecord, RelationshipRecord, ChunkRecord, GraphNode, GraphEdge 字段定义

### LangChain API 参考
- `langchain_core.runnables.Runnable` — invoke / ainvoke / astream 接口契约
- `langchain_core.documents.Document` — page_content: str + metadata: dict
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **6 个 Retriever 类** (`retriever/retrievers.py`): Chain 构造函数注入 Retriever 实例，调用 `retriever.ainvoke(query)` → `list[Document]`。每个 Retriever 的子类型对应一个 Chain 类。
- **extract_keywords()** (`keywords.py`): 异步函数，接收 query + llm + language → KeywordsSchema。Chain 基类中直接调用。关键词模板嵌入方式（模块级字符串常量）复用于 prompt 模板嵌入。
- **token_budget 函数** (`token_budget.py`): truncate_entities/relations 接收 `list[dict]` + max_tokens，返回截断后的 list。compute_chunk_token_budget 计算剩余 token。async wrapper 直接用于 Chain 的异步流。
- **create_llm()** (`llm.py`): Lazy factory → ChatOpenAI 实例。外部传入 Chain 构造函数。
- **Document JSON 格式** (`retriever/utils.py`): 每个 Document 的 page_content 是上游兼容的 JSON 字符串，metadata 含结构化字段。Chain 从这些格式还原数据用于上下文拼装。

### Established Patterns
- **构造函数注入**: Phase 5 Retriever 的 vector_store + graph_store + embedding_config 注入模式 → Phase 6 Chain 的 retriever + llm 注入模式。一致性。
- **Lazy `__getattr__` import**: `data/__init__.py`、`query/__init__.py`、`retriever/__init__.py`、顶级 `__init__.py` 都用此模式。`chain/__init__.py` 沿用。
- **Pydantic frozen + arbitrary_types_allowed**: BaseRetriever 继承 BaseModel 用此配置。LightRAGBaseChain 同样处理。
- **上游模板嵌入**: Phase 3 keywords.py 的 KEYWORDS_EXTRACTION_PROMPT 常量模式 → Phase 6 的 RAG_RESPONSE_PROMPT / KG_QUERY_CONTEXT 常量模式。完全匹配。
- **渐进拆分**: Phase 4 package+2 → Phase 5 package+3 → Phase 6 package+2(+1)。chain/ 包匹配 retriever/ 包结构。
- **async/await 全链路**: 整个调用链 async: extract_keywords → retriever.ainvoke → LLM.ainvoke → astream。sync invoke 桥接用 asyncio.run。
- **纯函数工具**: retriever/utils.py 的 convert 函数是纯函数（无 I/O、无副作用）→ chain 的 Document→dict 转换函数同为此模式。

### Integration Points
- **Phase 6 → Phase 5**: Chain 调用 `retriever.ainvoke(query)` → `list[Document]`，然后从 Document 还原结构化数据
- **Phase 6 → Phase 3 (keywords)**: Chain 基类调用 `extract_keywords(query, self.llm, self.keyword_language)` → KeywordsSchema
- **Phase 6 → Phase 3 (token_budget)**: Chain 基类调用 truncate_*/compute_chunk_budget 做上下文截断
- **Phase 6 → Phase 3 (llm)**: Chain 使用构造函数注入的 ChatOpenAI 实例做 LLM 调用
- **Phase 6 → Phase 1 (config)**: Chain 从 settings.query_params 读取 max_entity_tokens / max_relation_tokens / max_total_tokens / keyword_language
</code_context>

<specifics>
## Specific Ideas

- Chain 基类的核心流程顺序匹配上游 LightRAG 的 `_build_query_context()`: Search（Retriever）→ 数据转换（Document→dict）→ Truncate（token budget）→ Merge（拼装上下文模板）→ Build LLM Context（套用 rag_response 系统提示）→ LLM 生成。
- 上游 kg_query_context 模板中 entities/relations/chunks 用 ```json 代码块包裹 → Chain 拼装时完全复制此格式。reference_list 用裸文本（无 json 包裹）。
- 上游 rag_response 的引用格式是 `* [n] Document Title`，其中 Document Title 来自 file_path → Chain 的 reference_list 中 file_path 用作 Document Title。
- 上游 `_build_context_str()` 使用两阶段 token 计算：先算不含 chunks 的 kg_context 占多少 token，再动态分配合 chunk 配额。Chain 基类复制此逻辑。
- 流式管道方面：LangChain ChatOpenAI 的 `.astream()` 返回 token-by-token str，Chain 基类在此基础上附加上下文。不需要 langgraph 或复杂的 stream 中间件。
- BypassChain 是最简实现：无关键词提取、不调用 retriever、不拼装上下文模板 — 直接用 rag_response 模板（context_data 为空）调用 LLM。匹配上游 bypass 行为。
- 引用去重的 key 是 file_path — 同一文件的不同 chunk/entity/relation 只生成一条引用。如果一个 source 完全没有 file_path（罕见），跳过不纳入引用。
</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在 phase scope 内

- **对话历史管理 (CHAIN-05)**: REQUIREMENTS.md v2 中已有规划，属于未来 phase。Chain 本次不处理对话历史，每次 invoke 独立。
- **LLM 响应缓存 (CHAIN-04)**: REQUIREMENTS.md v2 中已有规划，属于未来 phase。
</deferred>

---

*Phase: 6-QA Chain*
*Context gathered: 2026-05-31*
