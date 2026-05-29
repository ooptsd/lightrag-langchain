# Phase 1: Configuration - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

本 phase 交付一个完整的 .env 驱动的类型化配置系统。pydantic-settings 解析 .env 文件，5 个嵌套子模型（PostgreSQL / LLM / Embedding / Reranker / QueryParams）组成一个 frozen Settings 单例，所有下游 phase 通过 `from lightrag_langchain.config import settings` 访问。

Scope: 项目脚手架（src-layout + hatchling + pytest + ruff）+ .env 配置解析 + 类型化 API + fail-fast 校验。
Out of scope: 数据库连接、LLM 调用、Embedding 生成、Rerank 调用 — 这些属于 Phase 2/3。
</domain>

<decisions>
## Implementation Decisions

### 项目结构与工具链
- **D-01:** 配置库使用 **pydantic-settings**（Pydantic 官方配置管理，Langchain 生态标准）
- **D-02:** 包结构 **src-layout + hatchling** 构建后端（src/lightrag_langchain/，防止意外导入源码）
- **D-03:** .env 策略 **.env.example 提交 + .env gitignore**（开发者 cp .env.example .env 后填入真实值）
- **D-04:** 开发工具 **pytest + ruff**（测试 + 代码检查/格式化，不使用 flake8/black/mypy）

### 配置验证策略
- **D-05:** 验证时机 **fail-fast 启动时全量校验**（import 时立即校验所有字段，错误早发现）
- **D-06:** 默认值 **明确区分必填/可选**（PG 连接、API Key 必填；QueryParams 提供与 LightRAG 一致的默认值；Embedding 维度默认 1024）
- **D-07:** 错误信息 **分类汇总式**（一次性收集所有校验失败，按配置组分组汇总）
- **D-08:** 跨字段校验 **仅关键约束**（如 max_entity_tokens + max_relation_tokens < max_total_tokens），不强制 provider 间的逻辑一致性

### 配置 API 设计
- **D-09:** 模型结构 **嵌套子模型**（顶层 Settings 含 5 个 BaseModel 子模型：`settings.pg.host` / `settings.llm.model`），各组可独立实例化和测试
- **D-10:** 文件组织 **单文件 src/lightrag_langchain/config.py**（Phase 1 约 100-150 行，后续膨胀再拆分）
- **D-11:** 访问方式 **模块级单例**（config.py 底部 `settings = Settings()`，下游 `from lightrag_langchain.config import settings`）
- **D-12:** 不可变性 **frozen=True**（Pydantic model_config 设置 frozen=True，运行时不可修改，防止意外变更）

### Claude's Discretion
- 敏感信息处理：API Key / Password 使用 Pydantic SecretStr（自动脱敏，打印时显示 `**********`）
- 日志安全：`__repr__` / `__str__` 不暴露 SecretStr 值，错误消息中不包含连接信息
- 配置组独立测试：每个子模型有独立的 env_prefix，支持单独实例化和单元测试（对应 SC #4）
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 需求与范围
- `.planning/ROADMAP.md` §Phase 1 — Goal, success criteria (4 项), 依赖关系, requirement 映射
- `.planning/REQUIREMENTS.md` §CONF — CONF-01 到 CONF-05 详细规范（PostgreSQL / LLM / Embedding / Reranker / QueryParams 各配置项）
- `.planning/PROJECT.md` — Key Decisions 表、Constraints 节（Python>=3.12, Langchain>=1.2.3, 只读, .env 全配置, LLM/Embedding/Reranker 中立）

### 上游上下文
- `.planning/PROJECT.md` §Context — LightRAG 数据库结构（PGVector entities_vdb/relationships_vdb/chunks_vdb, AGE 图）, 上游 LLM/Embedding/Reranker 选型（DeepSeek v4-pro / 阿里云 text-embedding-v4 1024维 / gte-rerank-v2）
- `.planning/REQUIREMENTS.md` §v1 Requirements — 完整 25 项 v1 requirements 及 phase 映射
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- 无 — 全新项目，无现有代码

### Established Patterns
- Langchain 生态约定：pydantic-settings 是事实标准，ChatOpenAI 等组件默认通过环境变量配置
- 上游 LightRAG 源码位于 `/Users/lizhouyang/llm/graphrag/LightRAG`，可作为配置参数命名和默认值参考

### Integration Points
- 无 — Phase 1 是基础层，所有后续 phase 依赖它
</code_context>

<specifics>
## Specific Ideas

- 配置组独立测试是 ROADMAP 明确要求的成功标准（SC #4），`env_prefix` 是实现关键
- 上游 LightRAG 的默认参数值应作为本项目 QueryParams 默认值的参考来源
</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在 phase scope 内
</deferred>

---

*Phase: 1-Configuration*
*Context gathered: 2026-05-29*
