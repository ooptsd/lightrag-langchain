# Retrospective

## Milestone: v1.0 — lightrag-langchain 初始发布

**Shipped:** 2026-06-01
**Phases:** 7 | **Plans:** 23

### What Was Built

基于 Langchain 框架的 LightRAG 查询层，从已有 PostgreSQL 知识图谱数据库执行六种查询模式的检索和问答。包含全配置 API、只读数据层、LLM/Embedding/Reranker 工厂、6 种查询策略、6 个 BaseRetriever 子类、端到端 QA Chain、以及 MkDocs + Material 文档站点。

### What Worked

- **GSD discuss → plan → execute 流程**: 每阶段 2-3 个 wave-plan，atomic commits，清晰的依赖管理
- **TDD with mock-based tests**: Chain/Retriever 层使用 `AsyncMock(spec=StoreClass)` 模式，setUp fixture 中创建 test instances，不依赖真实数据库
- **Lazy `__getattr__` imports**: 全模块延迟导入，`import lightrag_langchain` 无需 .env 或网络
- **Pydantic frozen models**: EntityRecord/RelationshipRecord/ChunkRecord/GraphNode/GraphEdge 不可变，防止意外修改
- **Provider-agnostic 工厂模式**: LLM/Embedding/Reranker 通过 binding 字段切换，支持所有 OpenAI 兼容 API
- **Parallel agent spawning**: 独立任务并行执行，phase 内 wave 序列化

### What Was Inefficient

- **REQUIREMENTS.md 与 phase 完成不同步**: Phase 2/5 完成后 traceability 表未更新 (STOR/RETR 仍标记 Pending)
- **Phase 5 UAT + Verification 遗留**: 2 个 UAT 场景 + 1 个 VERIFICATION.md human_needed 遗留到里程碑关闭
- **Debug sessions 未关闭**: lazy-llm-pydantic-attribute-error (diagnosed) 和 thinking-mode-tool-choice (verifying) 未正式关闭
- **.planning/ 提交混入源码分支**: 需要 `gsd-pr-branch` 过滤 .planning/ commits

### Patterns Established

- **Wave-based execution**: 每个 Phase 拆分为 2-3 wave，wave 内可并行，wave 间串行
- **Atomic commits per plan**: 每个 plan 完成后立即提交，失败可精确 revert
- **Mock fixtures with spec=**: AsyncMock(spec=StoreClass) 满足 Pydantic v2 isinstance 验证
- **field_validator for lazy proxies**: chain/base.py detect-and-resolve 模式，检测 _config+_instance duck-type 触发延迟构造

### Key Lessons

1. **Pydantic v2 + lazy proxy**: ChatOpenAI 的 `@model_validator(mode="before")` 在构造时运行，lazy proxy 需要 `@field_validator(mode="before")` 提前展开，否则 validators 校验 __getattr__ 代理的 `.get()` 会 crash
2. **DeepSeek thinking mode + tool_choice**: thinking mode 不支持 `tool_choice` 参数，`method="function_calling"` 需要改为 `method="json_mode"` 避免不兼容
3. **AG_CATALOG search_path**: asyncpg pool release 会重置 search_path，需要在 `server_settings` 中设置 `search_path` 而非在 `_init_connection` 回调中 SET
4. **PostgreSQL LIKE 大小写敏感**: 表前缀匹配需要 `ILIKE` 而非 `LIKE`，namespace 比较需要 `.lower()`
5. **tiktoken model fallback**: 非 OpenAI model name (如 deepseek-v4-pro) tiktoken 不认识，需要 fallback 到 gpt-4o-mini

### Cost Observations

- Model mix: ~70% sonnet, ~20% opus, ~10% haiku
- Sessions: ~15 sessions across 3 days
- Notable: GSD agent spawn model 分担了大量并行工作，context window 管理有效

---

## Cross-Milestone Trends

*(First milestone — trends will populate after v1.1+)*
