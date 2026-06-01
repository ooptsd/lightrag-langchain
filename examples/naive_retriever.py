"""Naive retriever-only mode — pure vector chunk search, no chain/LLM.

Naive 模式对 chunks_vdb 表执行纯向量相似度搜索，不涉及图遍历。
这是最简单的检索模式，返回 chunk Document 列表，适合嵌入 LCEL 管线使用。

Retriever-only: no chain, no LLM generation. The caller composes the LLM
step externally (e.g., via LCEL).

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/naive_retriever.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import NaiveRetriever
from lightrag_langchain.config import settings
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run Naive retriever — pure vector chunk search, no chain/LLM."""

    # (1) Initialize connection pool and vector store
    await init_pool()
    vector_store = PGVectorStore()

    # (2) Build retriever — Naive mode only needs vector_store (no graph)
    retriever = NaiveRetriever(
        vector_store=vector_store,
        embedding_config=settings.embedding,
    )

    # (3) Retriever invocation — returns list[Document]
    query = "启动东莞市防风Ⅰ级应急响应后需要落实哪些措施？"
    docs = await retriever.ainvoke(query)

    # (4) Print results
    print(f"模式: naive (retriever-only, vector chunk search)")
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
