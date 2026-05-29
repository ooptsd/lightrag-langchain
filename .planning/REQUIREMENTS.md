# Requirements: lightrag-langchain

**Defined:** 2026-05-29
**Core Value:** 用户可以通过 Langchain 标准 API，从 LightRAG 已构建的知识图谱数据库中执行六种查询模式的检索和问答，无需启动 LightRAG 服务。

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### STOR — 数据层

- [ ] **STOR-01**: 从 PGVector 读取 entities_vdb（entity_name, content, source_id, file_path）
- [ ] **STOR-02**: 从 PGVector 读取 relationships_vdb（src_id, tgt_id, content, keywords, weight）
- [ ] **STOR-03**: 从 PGVector 读取 chunks_vdb（content, full_doc_id, chunk_order_index, file_path）
- [ ] **STOR-04**: 从 Apache AGE 图数据库读取 entity 节点（entity_id, entity_type, description, source_id）和 relation 边（source_node_id, target_node_id, description, keywords, weight）

### QUERY — 查询模式

- [ ] **QUERY-01**: Naive 模式 — 纯向量相似度搜索 chunks_vdb，KG_CHUNK_PICK_METHOD 选择 VECTOR/WEIGHT，不做图遍历
- [ ] **QUERY-02**: Local 模式 — entities_vdb 向量搜索 Top-K 实体 → AGE 图扩展获取关联边和邻居实体
- [ ] **QUERY-03**: Global 模式 — relationships_vdb 向量搜索 Top-K 关系 → AGE 图查找关联实体
- [ ] **QUERY-04**: Hybrid 模式 — local + global 并行检索，round-robin 交错合并结果
- [ ] **QUERY-05**: Mix 模式 — hybrid 检索 + chunks_vdb 向量搜索，混合图知识和原始文本块
- [ ] **QUERY-06**: Bypass 模式 — 无检索，直接将查询 + conversation_history 发送给 LLM 生成回答

### RETR — Retriever 接口

- [ ] **RETR-01**: 为每种查询模式实现 Langchain `BaseRetriever` 子类（NaiveRetriever / LocalRetriever / GlobalRetriever / HybridRetriever / MixRetriever / BypassRetriever）
- [ ] **RETR-02**: 支持同步 `invoke` 和异步 `ainvoke`，返回 `List[Document]`（page_content + metadata 含来源引用）
- [ ] **RETR-03**: metadata 中包含 source_id, file_path, entity/relation 引用信息

### CHAIN — Chain 接口

- [ ] **CHAIN-01**: 实现完整问答 LCEL Chain：查询 → 关键词提取 → 检索 → 上下文拼装（含 token 预算控制）→ LLM 生成
- [ ] **CHAIN-02**: 支持 `invoke` / `ainvoke` / `astream` 三种调用方式
- [ ] **CHAIN-03**: 支持在 QueryParam 中直接传入 `hl_keywords` / `ll_keywords` 跳过 LLM 关键词提取

### CONF — 配置

- [ ] **CONF-01**: .env 配置 PostgreSQL 连接（PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE）
- [ ] **CONF-02**: .env 配置 LLM（LLM_BINDING, LLM_BINDING_HOST, LLM_BINDING_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS）
- [ ] **CONF-03**: .env 配置 Embedding（EMBEDDING_BINDING, EMBEDDING_BINDING_HOST, EMBEDDING_BINDING_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIM）
- [ ] **CONF-04**: .env 配置 Reranker（RERANK_BINDING, RERANK_BINDING_HOST, RERANK_BINDING_API_KEY, RERANK_MODEL, MIN_RERANK_SCORE）
- [ ] **CONF-05**: .env 配置查询参数（TOP_K, CHUNK_TOP_K, MAX_ENTITY_TOKENS, MAX_RELATION_TOKENS, MAX_TOTAL_TOKENS, COSINE_THRESHOLD, KG_CHUNK_PICK_METHOD）

### LLM — LLM / Embedding / Reranker 集成

- [ ] **LLM-01**: ChatOpenAI 兼容接口接入 — 支持所有 OpenAI API 格式的 LLM provider（DeepSeek, MiniMax, OpenAI, vLLM 等）
- [ ] **LLM-02**: OpenAIEmbeddings 兼容接口接入 — 支持 OpenAI 格式的 embedding provider
- [ ] **LLM-03**: 多 Reranker 支持 — aliyun dashscope (gte-rerank-v2) / cohere / jina，通过 `RERANK_BINDING` 切换
- [ ] **LLM-04**: LLM 关键词提取 — 从用户查询中提取 high-level keywords（宏观主题）和 low-level keywords（具体实体）
- [ ] **LLM-05**: Token 预算控制 — 动态分配 entity/relation/chunk 的 token 配额，max_entity_tokens + max_relation_tokens < max_total_tokens，剩余 token 分配给 chunks

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### STOR — 扩展存储

- **STOR-05**: 支持多 PostgreSQL workspace 隔离
- **STOR-06**: 支持 PGKV Storage 读取 text_chunks（当前用 chunks_vdb content 字段代替）

### CHAIN — 高级功能

- **CHAIN-04**: LLM 响应缓存（复用 LightRAG 的 ENABLE_LLM_CACHE 逻辑）
- **CHAIN-05**: 会话/对话历史管理

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| 文档处理/插入 | LightRAG 负责，本项目只读 |
| 知识图谱构建/增量更新 | LightRAG 负责 |
| Web UI / REST API 服务 | 本项目是 Python 库，不是服务 |
| LightRAG 运行时部署 | 核心目标就是脱离 LightRAG 部署 |
| 用户认证/授权 | 与查询无关 |
| PGKV Storage (KV 存储层) | chunks_vdb content 字段已包含文本，用户确认不需要 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| STOR-01 | — | Pending |
| STOR-02 | — | Pending |
| STOR-03 | — | Pending |
| STOR-04 | — | Pending |
| QUERY-01 | — | Pending |
| QUERY-02 | — | Pending |
| QUERY-03 | — | Pending |
| QUERY-04 | — | Pending |
| QUERY-05 | — | Pending |
| QUERY-06 | — | Pending |
| RETR-01 | — | Pending |
| RETR-02 | — | Pending |
| RETR-03 | — | Pending |
| CHAIN-01 | — | Pending |
| CHAIN-02 | — | Pending |
| CHAIN-03 | — | Pending |
| CONF-01 | — | Pending |
| CONF-02 | — | Pending |
| CONF-03 | — | Pending |
| CONF-04 | — | Pending |
| CONF-05 | — | Pending |
| LLM-01 | — | Pending |
| LLM-02 | — | Pending |
| LLM-03 | — | Pending |
| LLM-04 | — | Pending |
| LLM-05 | — | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 0
- Unmapped: 25 ⚠️

---
*Requirements defined: 2026-05-29*
*Last updated: 2026-05-29 after initial definition*
