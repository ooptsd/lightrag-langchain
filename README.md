# lightrag-langchain

基于 LangChain 框架的 LightRAG 知识图谱查询层 — 脱离 LightRAG 运行时独立运行，只做查询不做数据写入。

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-%3E%3D1.2.3-green)](https://www.langchain.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 项目简介

**lightrag-langchain** 是一个基于 LangChain 框架的只读查询库，直接读取 LightRAG 已处理好的 PostgreSQL 知识图谱数据库。它不依赖 LightRAG 运行时（包括 LightRAG 的 config.py/config.ini），只需数据库连接即可独立运行。

核心价值在于：用户无需启动 LightRAG 服务，就能通过 LangChain 标准 API 从知识图谱数据库中执行六种查询模式的检索和问答。库提供标准的 `Retriever` + `Chain` 接口，与 LangChain 生态（LangGraph、LangServe、LangSmith）完全兼容，可嵌入到任何基于 LangChain 构建的应用中。

本项目定位为纯查询层，不执行任何 CREATE / INSERT / UPDATE / DELETE 操作。数据库由上游 LightRAG 实例管理，本项目只读取 `entities_vdb`、`relationships_vdb`、`chunks_vdb` 向量数据及 Apache AGE 中的图结构（entity 节点 + relation 边）。

技术栈基于 Python 3.12+、LangChain >= 1.2.3、PostgreSQL + pgvector + Apache AGE，LLM 和 Embedding 均为 provider-agnostic 设计（支持所有 OpenAI 兼容 API 的 provider），并保留了 LightRAG 完整的 Rerank 重排序能力（aliyun / cohere / jina 三种后端）。

## 功能概览

完整复刻 LightRAG 全部六种查询模式：

| 模式 | 描述 |
|------|------|
| **Naive** | 纯向量相似度搜索 `chunks_vdb`，不做图遍历。适用于简单的语义匹配查询。 |
| **Local** | 实体中心图扩展。先对 `entities_vdb` 做向量搜索获取 Top-K 实体，再通过 AGE 图扩展获取关联的边和邻居实体。适用于实体级的深度查询。 |
| **Global** | 关系中心图扩展。先对 `relationships_vdb` 做向量搜索获取 Top-K 关系，再通过 AGE 图查找关联的实体。适用于关系级别的宏观查询。 |
| **Hybrid** | 并行执行 Local + Global 检索，结果按 round-robin 方式交错合并。适用于需要宏观和微观兼顾的综合查询。 |
| **Mix** | Hybrid 检索 + `chunks_vdb` 向量搜索，融合图知识和原始文本块信息。适用于力求最大覆盖的全量检索。 |
| **Bypass** | 跳过检索，直接将用户问题发送给 LLM。适用于无需外部知识的纯对话场景。 |

每种模式均提供对应的 `Retriever`（实现 LangChain `BaseRetriever`）和 `Chain`（端到端问答管道），可单独使用或组合编排。

完整的问答 Chain 管线包含：关键词提取（`extract_keywords`）→ 检索（`retriever.ainvoke`）→ Token 预算控制（`truncate_entities_by_tokens` / `truncate_relations_by_tokens` / `compute_chunk_token_budget`）→ 上下文拼装 → LLM 生成，与上游 LightRAG 的 4 阶段流程（Search → Truncate → Merge → Build LLM Context）一一对应。

## 快速开始

### 前置条件

- **Python**: >= 3.12
- **PostgreSQL**: 已安装 `pgvector` 和 `Apache AGE` 扩展，且数据库已由 LightRAG 完成知识图谱构建
- **uv**: 推荐使用 [uv](https://docs.astral.sh/uv/) 管理环境

### 安装

```bash
git clone https://github.com/<user>/lightrag-langchain.git
cd lightrag-langchain
uv sync
```

### 配置 .env

复制 `.env.example` 为 `.env`，根据实际环境修改：

```bash
cp .env.example .env
```

`.env` 中需要配置的字段分为五组：

| 配置组 | 关键字段 | 说明 |
|--------|----------|------|
| PostgreSQL | `PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, `PG_DATABASE` | 数据库连接信息 |
| LLM | `LLM_BINDING`, `LLM_BINDING_HOST`, `LLM_BINDING_API_KEY`, `LLM_MODEL` | LLM provider 配置 |
| Embedding | `EMBEDDING_BINDING`, `EMBEDDING_BINDING_HOST`, `EMBEDDING_BINDING_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` | Embedding provider 配置 |
| Reranker（可选） | `RERANK_BINDING`, `RERANK_BINDING_HOST`, `RERANK_BINDING_API_KEY`, `RERANK_MODEL` | 重排序，留空则不启用 |
| Query Parameters | `TOP_K`, `CHUNK_TOP_K`, `MAX_ENTITY_TOKENS`, `MAX_RELATION_TOKENS`, `MAX_TOTAL_TOKENS` | 检索参数 |

详细的 `.env` 说明请参考 `.env.example` 文件。

### 第一个查询

```python
from lightrag_langchain import NaiveChain, NaiveRetriever, create_llm, create_embedding
from lightrag_langchain.config import settings
from lightrag_langchain.data.store import PGVectorStore

# 1. 创建向量存储连接
vector_store = PGVectorStore(
    embedding_dim=settings.embedding.dim,
    **settings.pg.model_dump(exclude={"workspace"}),
)

# 2. 创建 LLM 和 Embedding
llm = create_llm(settings.llm)
embedding = create_embedding(settings.embedding)

# 3. 构建 Retriever 和 Chain
retriever = NaiveRetriever(
    vector_store=vector_store,
    embedding_config=settings.embedding,
)
chain = NaiveChain(retriever=retriever, llm=llm)

# 4. 执行查询
result = await chain.ainvoke("启动东莞市防风Ⅰ级应急响应后需要落实哪些措施？")
print(result["answer"])
```

> **导入说明**：Chain 和 Retriever 使用懒加载形式 `from lightrag_langchain import NaiveChain`；数据层连接类（PGVectorStore / PGGraphStore）需要直接从 `lightrag_langchain.data.store` 导入，因为数据层类不会从顶层 re-export。

## 文档和示例

- **API 文档**：完整的 API 参考文档（MkDocs + Material for MkDocs），在本地运行：
  ```bash
  uv run mkdocs serve
  ```
  部署后访问 `https://<user>.github.io/lightrag-langchain/`。

- **示例代码**：[`examples/`](examples/) 目录包含全套可运行脚本，覆盖所有六种查询模式：
  - **Chain 示例**（完整管线：检索 + LLM 生成）：
    - `naive_query.py` — Naive 模式（纯向量搜索）
    - `local_query.py` — Local 模式（实体中心图扩展）
    - `global_query.py` — Global 模式（关系中心图扩展）
    - `hybrid_query.py` — Hybrid 模式（并行 local + global）
    - `mix_query.py` — Mix 模式（hybrid + chunk 搜索）
    - `bypass_query.py` — Bypass 模式（跳过检索，直接 LLM）
  - **Retriever 示例**（仅检索，供 LCEL 调用）：
    - `naive_retriever.py` / `local_retriever.py` / `global_retriever.py`
    - `hybrid_retriever.py` / `mix_retriever.py` / `bypass_retriever.py`

  更多细节请参考 [`examples/README.md`](examples/README.md)。

## 技术栈

- **语言**: Python 3.12+
- **AI 框架**: LangChain >= 1.2.3
- **数据库**: PostgreSQL + pgvector + Apache AGE
- **LLM**: ChatOpenAI 兼容接口（支持 OpenAI / DeepSeek / MiniMax / vLLM 等所有 provider）
- **Embedding**: OpenAIEmbeddings 兼容接口
- **Reranker**: aliyun gte-rerank-v2 / cohere / jina 三种后端
- **异步**: asyncpg 连接池
- **Token 计算**: tiktoken
- **重试**: tenacity
- **文档生成**: MkDocs + Material for MkDocs + mkdocstrings

## License

MIT License.

本项目中的 prompt 模板源自 LightRAG（MIT License），详见 [pingcap/LightRAG](https://github.com/pingcap/LightRAG)。
