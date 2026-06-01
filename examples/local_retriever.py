"""Local retriever-only mode — entity vector search + graph expansion, no chain/LLM.

Local 模式先对 entities_vdb 执行向量搜索获取 Top-K 实体，再通过 Apache AGE
图数据库扩展获取关联的边和邻居实体。返回 entity + GraphTriple Document 列表，
适合嵌入 LCEL 管线使用。

Retriever-only: no chain, no LLM generation. The caller composes the LLM
step externally (e.g., via LCEL).

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/local_retriever.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import LocalRetriever
from lightrag_langchain.config import settings
from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run Local retriever — entity search + graph expansion, no chain/LLM."""

    # (1) Initialize connection pool and data-layer connections
    await init_pool()
    vector_store = PGVectorStore()
    graph_store = PGGraphStore()

    # (2) Build retriever — Local mode needs both vector_store and graph_store
    retriever = LocalRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )

    # (3) Retriever invocation — returns list[Document]
    query = "广州市三防成员单位有哪些？"
    docs = await retriever.ainvoke(query)

    # (4) Print results
    print(f"模式: local (retriever-only, entity search + graph expansion)")
    print(f"查询: {query}")
    print(f"文档数: {len(docs)}")
    print()

    if not docs:
        print("未检索到相关文档。")
    else:
        for i, doc in enumerate(docs, 1):
            content = doc.page_content
            truncated = (
                content[:200] + "..." if len(content) > 200 else content
            )
            print(f"--- 文档 {i} ---")
            print(f"page_content: {truncated}")
            print(f"metadata: {doc.metadata}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
