# 快速开始 (Quick Start)

本节将引导你完成 lightrag-langchain 的安装、配置和第一个查询。

## 前置条件

- **Python**: >= 3.12
- **PostgreSQL**: 已安装 [pgvector](https://github.com/pgvector/pgvector) 和 [Apache AGE](https://age.apache.org/) 扩展
- **LightRAG 数据库**：数据库已由上游 LightRAG 实例完成知识图谱构建（含有 `entities_vdb`、`relationships_vdb`、`chunks_vdb` 及 AGE 图数据）
- **uv**：推荐使用 [uv](https://docs.astral.sh/uv/) 管理 Python 环境和依赖

验证 PostgreSQL 扩展是否已安装：

```sql
SELECT * FROM pg_extension WHERE extname IN ('vector', 'age');
```

## 安装

### 使用 uv（推荐）

```bash
git clone https://github.com/<user>/lightrag-langchain.git
cd lightrag-langchain
uv sync
```

### 使用 pip

```bash
pip install .
```

## 配置 .env

1. 复制模板文件：

   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env`，填入你的实际配置。完整字段说明见 `.env.example`。以下是最小可运行配置示例：

   ```ini
   # PostgreSQL 连接
   PG_HOST=localhost
   PG_PORT=5432
   PG_USER=postgres
   PG_PASSWORD=your_password
   PG_DATABASE=lightrag

   # LLM（支持所有 OpenAI 兼容 API）
   LLM_BINDING=openai
   LLM_BINDING_HOST=https://api.openai.com/v1
   LLM_BINDING_API_KEY=sk-your-api-key
   LLM_MODEL=gpt-4o-mini

   # Embedding
   EMBEDDING_BINDING=openai
   EMBEDDING_BINDING_HOST=https://api.openai.com/v1
   EMBEDDING_BINDING_API_KEY=sk-your-api-key
   EMBEDDING_MODEL=text-embedding-3-small
   EMBEDDING_DIM=1024

   # 查询参数（使用默认值）
   TOP_K=40
   CHUNK_TOP_K=20
   MAX_ENTITY_TOKENS=6000
   MAX_RELATION_TOKENS=8000
   MAX_TOTAL_TOKENS=30000
   ```

   !!! warning "安全提醒"
       `.env` 文件包含敏感凭证，请勿提交到版本控制。`.env.example` 已在 `.gitignore` 中配置为允许跟踪，而 `.env` 会被忽略。

3. 验证配置是否有效：

   ```python
   from lightrag_langchain.config import settings
   print(settings.pg.host)  # 应输出你的 PostgreSQL 主机
   print(settings.llm.model)  # 应输出你的 LLM 模型名
   ```

## 第一个查询

以下是一个完整的 Naive 模式（纯向量搜索）查询示例：

```python
import asyncio

from lightrag_langchain import NaiveChain, NaiveRetriever, create_llm, create_embedding
from lightrag_langchain.config import settings
from lightrag_langchain.data.store import PGVectorStore


async def main():
    """Naive 模式 — 纯向量相似度搜索，不做图遍历。"""

    # 1. 创建数据层连接
    vector_store = PGVectorStore(
        embedding_dim=settings.embedding.dim,
        host=settings.pg.host,
        port=settings.pg.port,
        user=settings.pg.user,
        password=settings.pg.password.get_secret_value(),
        database=settings.pg.database,
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

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
```

> **导入说明**：Chain 和 Retriever 使用懒加载形式 `from lightrag_langchain import NaiveChain`。数据层连接类（`PGVectorStore` / `PGGraphStore`）需要直接从 `lightrag_langchain.data.store` 导入——数据层不会从顶层 re-export。

## 下一步

- 查看 [API 参考](api-reference/index.md) 了解所有类和方法
- 浏览 [示例](examples.md) 了解其他五种查询模式（Local / Global / Hybrid / Mix / Bypass）
- 运行 [examples/ 目录](https://github.com/<user>/lightrag-langchain/tree/main/examples) 中的可执行脚本
