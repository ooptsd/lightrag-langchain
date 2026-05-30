# Phase 3: LLM Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 3-LLM Integration
**Areas discussed:** LLM/Embedding 服务封装方式, Reranker 多后端接口设计, Keyword Extraction 实现方式, 模块文件组织 & Token 预算位置

---

## LLM/Embedding 服务封装方式

| Option | Description | Selected |
|--------|-------------|----------|
| Thin factory 函数 | create_llm(config) → ChatOpenAI, create_embedding(config) → OpenAIEmbeddings。代码最少（~40行），LangChain 标准 | ✓ |
| Wrapper 类 | LLMClient 和 EmbeddingClient wrapper，封装 ChatOpenAI。更好的 mock 隔离但更多代码 | |
| LangChain init_chat_model | 使用 init_chat_model() 统一入口，一行切换 provider。但需要遵循 LangChain provider 命名约定 | |

**Follow-up decisions:**
- LLM/Embedding 延迟初始化（`__getattr__` 模式），与 config.py 一致
- 参数只从 config 读取，factory 不提供 override
- 放在独立 `llm.py` 文件

---

## Reranker 多后端接口设计

| Option | Description | Selected |
|--------|-------------|----------|
| Factory + Protocol | create_reranker(config) 根据 RERANK_BINDING 返回对应实现，Protocol 定义接口 | ✓ |
| Abstract base class | RerankerBase + 3 个 provider 子类。类型安全但模板代码多 | |
| 独立函数 | ali_rerank() / cohere_rerank() / jina_rerank() 独立 async 函数，匹配上游 | |

| Option | Description | Selected |
|--------|-------------|----------|
| 需要 BaseDocumentCompressor | 实现 LangChain 的 BaseDocumentCompressor，可直接用于 ContextualCompressionRetriever | ✓ |
| 不需要 | 保持 Phase 3 独立，返回原始 dict | |

**Follow-up decisions:**
- 双层接口：底层 raw rerank() + 顶层 LightRAGReranker(BaseDocumentCompressor)
- HTTP 客户端：httpx（LangChain 生态标准）
- 重试策略：与 Phase 2 一致（3 retries, 1s→2s→4s, tenacity）

---

## Keyword Extraction 实现方式

| Option | Description | Selected |
|--------|-------------|----------|
| LangChain structured output | with_structured_output(KeywordsSchema)，类型安全、LangChain 惯用 | ✓ |
| 上游 Prompt + LangChain | 复用上游 prompt + ChatOpenAI.invoke() + json_repair 解析，行为与上游一致 | |
| Hybrid 回退 | 优先 structured output，失败回退 json_repair | |

**Follow-up decisions:**
- Prompt 模板复用上游 LightRAG 的 keywords_extraction 文本，改为 Pydantic Schema 解析
- Schema: 简单 Pydantic model（high_level_keywords: list[str], low_level_keywords: list[str]）
- 不支持缓存（Phase 6 通过 LangChain cache 处理）
- 语言配置通过 .env KEYWORD_LANGUAGE，默认 "Chinese"
- 不提供 json_repair 回退，不支持的 provider 快速报错

---

## 模块文件组织 & Token 预算位置

| Option | Description | Selected |
|--------|-------------|----------|
| 独立 token_budget.py | 纯计算工具函数，Phase 4/6 调用。解耦清晰，独立可测 | ✓ |
| 嵌入 keywords.py | 与关键词提取同文件，但关注点不同 | |
| 推迟到 Phase 6 | 在 Context Assembly 中实现。不符合 ROADMAP scope (LLM-05) | |

| Option | Description | Selected |
|--------|-------------|----------|
| 3-4 文件 | llm.py + reranker.py + keywords.py + token_budget.py，每个 80-150 行 | ✓ |
| 单文件 | 全部功能在一个文件，~400-500 行 | |
| 2 文件 | llm.py + reranker.py，逻辑归属不自然 | |

**Follow-up decisions:**
- Tokenizer: tiktoken（LangChain 依赖，与上游一致）
- Token 预算接口：同步纯函数 + async wrapper
- Token 参数来源：从 QueryParamsConfig 读取

---

## Claude's Discretion

- create_embedding 遵循与 create_llm 相同的 lazy pattern
- Token 预算函数命名和切分（3 个截断 + 1 个剩余计算）
- __init__.py 使用 data/__init__.py 相同的 lazy import 模式
- `__repr__` / `__str__` 不暴露 SecretStr（延续 Phase 1 安全约定）
- Reranker raw method 签名统一为 `async rerank(query, documents, top_n=None) → list[dict]`

## Deferred Ideas

None — 讨论保持在 phase scope 内
