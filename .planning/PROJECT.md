# lightrag-langchain

## What This Is

基于 Langchain 框架的 LightRAG 查询层，直接读取 LightRAG 已处理好的 PostgreSQL 知识图谱数据库，复刻全部六种查询模式（naive / local / global / hybrid / mix / bypass），提供标准 Langchain Retriever + Chain 接口。脱离 LightRAG 运行时独立运行，只做查询不做数据写入。

## Core Value

用户可以通过 Langchain 标准 API，从 LightRAG 已构建的知识图谱数据库中执行六种查询模式的检索和问答，无需启动 LightRAG 服务。

## Requirements

### Validated

- [x] .env 全配置（Phase 1: Configuration） — Pydantic Settings + SecretStr + 5 个子模型
- [x] 直接读取 PostgreSQL 中的 LightRAG 数据（Phase 2: Data Layer） — PGVectorStore + PGGraphStore + asyncpg pool
- [x] LLM/Embedding 工厂 + provider-agnostic（Phase 3: LLM Integration, LLM-01/LLM-02） — create_llm()/create_embedding() lazy proxies
- [x] 保留 Rerank 重排序能力（Phase 3: LLM Integration, LLM-03） — Reranker Protocol + 3 种后端（aliyun/cohere/jina）+ LightRAGReranker
- [x] 关键词提取（Phase 3: LLM Integration, LLM-04） — KeywordsSchema + extract_keywords() + upstream prompt templates
- [x] Token 预算控制（Phase 3: LLM Integration, LLM-05） — truncate_entities/relations + chunk budget via tiktoken
- [x] 实现 6 种查询模式各自的检索策略（Phase 4: Query Strategies） — 6 async strategy functions + GraphTriple + QueryResult, 168 tests pass

### Active
- [ ] 实现 Langchain BaseRetriever 接口，每种模式对应一个 Retriever
- [ ] 实现完整的 Langchain Chain，端到端：查询 → 检索 → 上下文拼装 → LLM生成
- [ ] 引用来源返回

### Out of Scope

- 文档处理/插入 — LightRAG 负责，本项目只读
- 知识图谱构建/增量更新 — LightRAG 负责
- LightRAG 服务器部署 / Web UI — 本项目是库，不是服务
- OAuth / 用户认证 — 无关

## Context

- **LightRAG 数据库**: 已由上游 LightRAG 实例处理完成，存储在 PostgreSQL 中
  - KV Storage: PGKVStorage（text_chunks 等）
  - Graph Storage: PGGraphStorage（Apache AGE 扩展，entity 节点 + relation 边）
  - Vector Storage: PGVectorStorage（pgvector 扩展，entities_vdb / relationships_vdb / chunks_vdb）
  - Doc Status: PGDocStatusStorage
- **上游 LLM**: DeepSeek v4-pro（用于 LightRAG 的原始处理）
- **上游 Embedding**: 阿里云 text-embedding-v4（1024 维）
- **上游 Rerank**: 阿里云 gte-rerank-v2
- **当前工作目录**: 已有 LightRAG 源码在 `/Users/lizhouyang/llm/graphrag/LightRAG`，本项目是独立的查询层
- **LightRAG 六种查询模式**:
  1. **naive** — 纯向量相似度搜索 (chunks_vdb)，无图遍历
  2. **local** — 实体聚焦：entities_vdb 向量搜索 → 图扩展获取关联边
  3. **global** — 关系聚焦：relationships_vdb 向量搜索 → 图查找关联实体
  4. **hybrid** — local + global 合并，round-robin 交错
  5. **mix** — hybrid + chunks_vdb 向量搜索，最大覆盖
  6. **bypass** — 无检索，直接 LLM 回答

## Constraints

- **Python**: >= 3.12
- **Langchain**: >= 1.2.3
- **数据库**: PostgreSQL，需要 pgvector 和 Apache AGE 扩展
- **只读**: 不执行任何 CREATE / INSERT / UPDATE / DELETE 操作
- **配置方式**: 所有配置通过 .env 文件，不硬编码
- **LLM 中立**: 支持所有 OpenAI 兼容 API 的 LLM provider
- **Embedding 中立**: 支持 OpenAI 兼容 API 的 embedding provider
- **Reranker 中立**: 支持多种 reranker（aliyun / cohere / jina）

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 直接读 PostgreSQL，不依赖 LightRAG 运行时 | 用户要求脱离 LightRAG 部署 | ✓ Validated (Phase 2) |
| 全部 6 种查询模式各自实现检索策略 | 用户要求"全部的召回策略" | — Pending (Phase 4) |
| Langchain Retriever + Chain 双层接口 | 既提供可组合的 Retriever 也提供端到端 Chain | — Pending (Phase 5/6) |
| .env 全配置 | 用户要求，灵活切换 provider | ✓ Validated (Phase 1) |
| 保留 Rerank 能力 | 提升检索质量，用户要求保留 | ✓ Validated (Phase 3: Reranker Protocol + 3 backends) |
| Python >= 3.12 | 用户指定 | ✓ Adopted |
| langchain >= 1.2.3 | 用户指定 | ✓ Adopted |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-30 after Phase 3 (LLM Integration) completion*
