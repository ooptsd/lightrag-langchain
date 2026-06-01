"""Mix query mode — hybrid retrieval + chunk vector search for maximum coverage.

Mix 模式在 Hybrid 检索的基础上追加 chunks_vdb 向量搜索，融合图知识
（entities_vdb + relationships_vdb + AGE graph triples）和原始文本块
（chunks_vdb）。适用于力求最大覆盖的全量检索场景。

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/mix_query.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import MixChain, MixRetriever, create_llm
from lightrag_langchain.config import settings
from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run a Mix mode query — hybrid retrieval + chunk vector search."""

    # (1) Initialize connection pool and data-layer connections
    await init_pool()
    vector_store = PGVectorStore()
    graph_store = PGGraphStore()

    # (2) Create LLM from settings
    llm = create_llm(settings.llm)

    # (3) Build retriever — Mix mode needs both vector_store and graph_store
    retriever = MixRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )

    # (4) Build chain
    chain = MixChain(retriever=retriever, llm=llm)

    # (5) Query
    question = "广州市三防成员单位有哪些？"
    result = await chain.ainvoke(question)

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
