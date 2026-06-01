"""Bypass retriever-only mode — no retrieval step, always returns empty list.

Bypass 模式跳过所有检索步骤（无关键词提取、无向量搜索、无图查询、
无 token 预算控制），直接返回空 list[Document]。适合由 LCEL 管线的调用方
自行决定是否需要 LLM 步骤的场景。

Retriever-only: no chain, no LLM generation. Always returns [] — the caller
may use this as a no-op retriever in LCEL pipelines when retrieval is not needed.

Note: BypassRetriever does not use vector_store or embedding_config at runtime
(returns [] without any I/O), but both are required constructor args because
the base class Pydantic model requires them.

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/bypass_retriever.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import BypassRetriever
from lightrag_langchain.config import settings
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run Bypass retriever — returns empty list, no retrieval, no chain/LLM."""

    # (1) Initialize connection pool and vector store
    #     (BypassRetriever does not use them at runtime, but the Pydantic
    #      base class requires vector_store and embedding_config as args.)
    await init_pool()
    vector_store = PGVectorStore()

    # (2) Build retriever — Bypass mode returns empty results (no retrieval)
    retriever = BypassRetriever(
        vector_store=vector_store,
        embedding_config=settings.embedding,
    )

    # (3) Retriever invocation — always returns []
    query = "请简要介绍中国的应急管理体系。"
    docs = await retriever.ainvoke(query)

    # (4) Print results — bypass mode always returns empty list
    print(f"模式: bypass (retriever-only, no retrieval)")
    print(f"查询: {query}")
    print(f"文档数: {len(docs)}")
    print()

    if not docs:
        print("Bypass mode: no documents retrieved (expected)")
    else:
        # Unreachable — BypassRetriever always returns []; kept for
        # consistency with other retriever-only examples.
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
