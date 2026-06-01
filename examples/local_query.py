"""Local query mode — entity-centric graph traversal.

Local 模式先对 entities_vdb 执行向量搜索获取 Top-K 实体，再通过 Apache AGE
图数据库扩展获取关联的边和邻居实体。适用于实体级的深度查询。

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/local_query.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import LocalChain, LocalRetriever, create_llm
from lightrag_langchain.config import settings
from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run a Local mode query — entity-centric graph traversal."""

    # (1) Initialize connection pool and data-layer connections
    await init_pool()
    vector_store = PGVectorStore()
    graph_store = PGGraphStore()

    # (2) Create LLM from settings
    llm = create_llm(settings.llm)

    # (3) Build retriever — Local mode needs both vector_store and graph_store
    retriever = LocalRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )

    # (4) Build chain
    chain = LocalChain(retriever=retriever, llm=llm)

    # (5) Query
    question = "珠江流域超标准洪水时水库抢险标准是什么？"
    result = await chain.ainvoke(question)

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
