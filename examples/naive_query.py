"""Naive query mode — pure vector chunk search, no graph traversal.

Naive 模式对 chunks_vdb 表执行纯向量相似度搜索，不涉及图遍历。
这是最简单的查询模式，适用于语义匹配型查询。

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/naive_query.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import NaiveChain, NaiveRetriever, create_llm
from lightrag_langchain.config import settings
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run a Naive mode query — pure vector chunk search."""

    # (1) Initialize connection pool and data-layer connections
    await init_pool()
    vector_store = PGVectorStore()

    # (2) Create LLM from settings
    llm = create_llm(settings.llm)

    # (3) Build retriever — Naive mode only needs vector_store (no graph)
    retriever = NaiveRetriever(
        vector_store=vector_store,
        embedding_config=settings.embedding,
    )

    # (4) Build chain
    chain = NaiveChain(retriever=retriever, llm=llm)

    # (5) Query
    question = "启动东莞市防风Ⅰ级应急响应后需要落实哪些措施？"
    result = await chain.ainvoke(question)

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
