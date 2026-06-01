"""Global query mode — relation-centric graph traversal.

Global 模式先对 relationships_vdb 执行向量搜索获取 Top-K 关系，再通过
Apache AGE 图数据库查找关联的实体。适用于关系级别的宏观查询。

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/global_query.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import GlobalChain, GlobalRetriever, create_llm
from lightrag_langchain.config import settings
from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.pool import init_pool
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run a Global mode query — relation-centric graph traversal."""

    # (1) Initialize connection pool and data-layer connections
    await init_pool()
    vector_store = PGVectorStore()
    graph_store = PGGraphStore()

    # (2) Create LLM from settings
    llm = create_llm(settings.llm)

    # (3) Build retriever — Global mode needs both vector_store and graph_store
    retriever = GlobalRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )

    # (4) Build chain
    chain = GlobalChain(retriever=retriever, llm=llm)

    # (5) Query
    question = "广州市三防成员单位有哪些？"
    result = await chain.ainvoke(question)

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
