"""Hybrid retriever-only mode — parallel local + global retrieval, no chain/LLM.

Hybrid 模式并行执行 Local 和 Global 检索，结果按 round-robin 方式交错合并。
返回 entity + relation + GraphTriple Document 列表，适合嵌入 LCEL 管线使用。

Retriever-only: no chain, no LLM generation. The caller composes the LLM
step externally (e.g., via LCEL).

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/hybrid_retriever.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import HybridRetriever
from lightrag_langchain.config import settings
from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run Hybrid retriever — parallel local + global, no chain/LLM."""

    # (1) Initialize connection pool and data-layer connections
    await init_pool()
    vector_store = PGVectorStore()
    graph_store = PGGraphStore()

    # (2) Build retriever — Hybrid mode needs both vector_store and graph_store
    retriever = HybridRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )

    # (3) Retriever invocation — returns list[Document]
    query = "广州市三防成员单位有哪些？"
    docs = await retriever.ainvoke(query)

    # (4) Print results
    print(f"模式: hybrid (retriever-only, parallel local + global)")
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
