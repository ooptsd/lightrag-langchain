# lightrag-langchain

## What This Is

基于 Langchain 框架的 LightRAG 查询层，直接读取 LightRAG 已处理好的 PostgreSQL 知识图谱数据库，复刻全部六种查询模式（naive / local / global / hybrid / mix / bypass），提供标准 Langchain Retriever + Chain 接口。脱离 LightRAG 运行时独立运行，只做查询不做数据写入。

已发布 v1.0，包含 7 个阶段 23 个计划，12,749 行 Python 代码，222 个测试全部通过。

## Core Value

用户可以通过 Langchain 标准 API，从 LightRAG 已构建的知识图谱数据库中执行六种查询模式的检索和问答，无需启动 LightRAG 服务。

## Current State

- **Version:** v1.0 (shipped 2026-06-01)
- **Codebase:** 12,749 Python LOC, 222 tests passing
- **Tech Stack:** Python 3.12, LangChain 1.2.3+, PostgreSQL (pgvector + Apache AGE), DeepSeek v4-pro, 阿里云 text-embedding-v4, 阿里云 gte-rerank-v2
- **Documentation:** MkDocs + Material at GitHub Pages, README.md (bilingual), examples/ (6 scripts + walkthrough.ipynb)

## Requirements

### Validated (v1.0)

- [x] .env 全配置（Phase 1） — Pydantic Settings + SecretStr + 5 个子模型
- [x] 直接读取 PostgreSQL 中的 LightRAG 数据（Phase 2） — PGVectorStore + PGGraphStore + asyncpg pool
- [x] LLM/Embedding 工厂 + provider-agnostic（Phase 3） — create_llm()/create_embedding() lazy proxies
- [x] 保留 Rerank 重排序能力（Phase 3） — Reranker Protocol + 3 种后端（aliyun/cohere/jina）+ LightRAGReranker
- [x] 关键词提取（Phase 3） — KeywordsSchema + extract_keywords() + upstream prompt templates
- [x] Token 预算控制（Phase 3） — truncate_entities/relations + chunk budget via tiktoken
- [x] 实现 6 种查询模式各自的检索策略（Phase 4） — 6 async strategy functions, 168 tests pass
- [x] 实现 Langchain BaseRetriever 接口（Phase 5） — 6 BaseRetriever subclasses + sync/async + Document with JSON metadata, 194 tests
- [x] 实现完整的 Langchain Chain 端到端管道（Phase 6） — LightRAGBaseChain 9-step pipeline + 6 mode-specific subclasses, 211 tests
- [x] 引用来源返回（Phase 6） — file_path dedup + sequential integer reference_ids + [N] footnote format
- [x] MkDocs + Material 文档站点（Phase 7） — API Reference 28+ symbols, GitHub Pages CI 部署
- [x] README.md + examples/ 目录（Phase 7） — bilingual README, 6 scripts + walkthrough.ipynb

### Active

- [ ] **CI-01**: 创建 GitHub repo 并 push 代码
- [ ] **CI-02**: GitHub Actions tag push → 自动构建 wheel + sdist → 发布到 PyPI

### Out of Scope

- 文档处理/插入 — LightRAG 负责，本项目只读
- 知识图谱构建/增量更新 — LightRAG 负责
- LightRAG 服务器部署 / Web UI — 本项目是库，不是服务
- OAuth / 用户认证 — 无关
- PR test/lint CI — 本次只做 tag→build→publish，不做 PR gate

## Current Milestone: v2.0 CI集成

**Goal:** 项目可通过 tag push 自动构建并发布到 PyPI

**Target features:**
- GitHub repo 创建并推送代码
- GitHub Actions workflow: tag push → build wheel + sdist → PyPI publish

## Context

- **LightRAG 数据库**: 已由上游 LightRAG 实例处理完成，存储在 PostgreSQL 中
  - KV Storage: PGKVStorage（text_chunks 等）
  - Graph Storage: PGGraphStorage（Apache AGE 扩展，entity 节点 + relation 边）
  - Vector Storage: PGVectorStorage（pgvector 扩展，entities_vdb / relationships_vdb / chunks_vdb）
  - Doc Status: PGDocStatusStorage
- **上游 LLM**: DeepSeek v4-pro
- **上游 Embedding**: 阿里云 text-embedding-v4（1024 维）
- **上游 Rerank**: 阿里云 gte-rerank-v2

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
| 全部 6 种查询模式各自实现检索策略 | 复刻 LightRAG 全部召回策略 | ✓ Validated (Phase 4) |
| Langchain Retriever + Chain 双层接口 | 可组合 + 端到端两种使用方式 | ✓ Validated (Phase 5, 6) |
| .env 全配置 + Pydantic Settings | 灵活切换 provider | ✓ Validated (Phase 1) |
| 保留 Rerank 能力 + 多后端 | 提升检索质量 | ✓ Validated (Phase 3) |
| Python >= 3.12, langchain >= 1.2.3 | 用户指定 | ✓ Adopted |
| MkDocs + Material for MkDocs + GitHub Pages | 文档部署 | ✓ Validated (Phase 7) |
| asyncpg connection pool + lazy init | 只读连接池 | ✓ Validated (Phase 2) |
| 6 独立 Chain 子类 + LightRAGBaseChain | 每种模式独立实现 + 共享 pipeline | ✓ Validated (Phase 6) |
| Reranker Protocol + 3 独立 Adapter | 每种后端独立类，避免 switch-case | ✓ Validated (Phase 3) |
| method="function_calling" → "json_mode" | DeepSeek thinking mode 不支持 tool_choice | ✓ Validated (keywords.py fix) |

## Next Milestone Goals

待定。运行 `/gsd-new-milestone` 开始需求收集和研究。

---
*Last updated: 2026-06-01 — milestone v2.0 CI集成 started*

