"""Mix retriever-only mode — hybrid retrieval + chunk vector search, no chain/LLM.

Mix 模式在 Hybrid 检索的基础上追加 chunks_vdb 向量搜索，融合图知识
（entities_vdb + relationships_vdb + AGE graph triples）和原始文本块
（chunks_vdb）。返回 entity + relation + chunk + GraphTriple Document 列表，
适合嵌入 LCEL 管线使用。

Retriever-only: no chain, no LLM generation. The caller composes the LLM
step externally (e.g., via LCEL).

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/mix_retriever.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import MixRetriever
from lightrag_langchain.config import settings
from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run Mix retriever — hybrid + chunk search, no chain/LLM."""

    # (1) Initialize connection pool and data-layer connections
    await init_pool()
    vector_store = PGVectorStore()
    graph_store = PGGraphStore()

    # (2) Build retriever — Mix mode needs both vector_store and graph_store
    retriever = MixRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )

    # (3) Retriever invocation — returns list[Document]
    query = "广州市三防成员单位有哪些？"
    docs = await retriever.ainvoke(query)

    # (4) Print results
    print(f"模式: mix (retriever-only, hybrid + chunk search)")
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
