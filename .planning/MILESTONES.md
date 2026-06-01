# Milestones

## v1.0 — lightrag-langchain 初始发布

**Shipped:** 2026-06-01
**Phases:** 7 | **Plans:** 23 | **Tests:** 222 passing
**Timeline:** 2026-05-29 → 2026-06-01 (3 days)
**Commits:** 156 | **Files:** 164 changed | **LOC:** 12,749 Python

### Key Accomplishments

1. **全配置 API** — Pydantic Settings + SecretStr + 5 子模型，Fail-fast 验证，30 tests
2. **只读数据层** — PGVectorStore + PGGraphStore + asyncpg 连接池，自动表发现和图检测
3. **LLM/Embedding/Reranker 工厂** — Provider-agnostic 接口，多后端 Reranker (aliyun/cohere/jina)，Token 预算控制
4. **6 种查询策略** — Naive/Local/Global/Hybrid/Mix/Bypass，与上游 LightRAG 行为对齐，168 tests
5. **6 个 BaseRetriever 子类** — 标准 Langchain 接口 + sync/async，Document + JSON metadata
6. **端到端 QA Chain** — LightRAGBaseChain 9-step pipeline + 6 模式 + invoke/ainvoke/astream，211 tests
7. **MkDocs + Material 文档** — API Reference 28+ symbols, GitHub Pages CI 部署, README.md (bilingual), examples/ (6 scripts + walkthrough.ipynb)

### Known deferred items at close: 6

See STATE.md Deferred Items for details.

### Archive

- Roadmap: `.planning/milestones/v1.0-ROADMAP.md`
- Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`
