"""Hybrid query mode — parallel local + global retrieval with round-robin merge.

Hybrid 模式并行执行 Local 和 Global 检索，结果按 round-robin 方式交错合并。
适用于需要宏观和微观兼顾的综合查询。

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/hybrid_query.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import HybridChain, HybridRetriever, create_llm, create_embedding
from lightrag_langchain.config import settings
from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run a Hybrid mode query — parallel local + global retrieval."""

    # (1) Create data-layer connections
    vector_store = PGVectorStore(
        embedding_dim=settings.embedding.dim,
        host=settings.pg.host,
        port=settings.pg.port,
        user=settings.pg.user,
        password=settings.pg.password.get_secret_value(),
        database=settings.pg.database,
    )
    graph_store = PGGraphStore(
        host=settings.pg.host,
        port=settings.pg.port,
        user=settings.pg.user,
        password=settings.pg.password.get_secret_value(),
        database=settings.pg.database,
        workspace=settings.pg.workspace,
    )

    # (2) Create LLM and embedding from settings
    llm = create_llm(settings.llm)
    embedding = create_embedding(settings.embedding)

    # (3) Build retriever — Hybrid mode needs both vector_store and graph_store
    retriever = HybridRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )

    # (4) Build chain
    chain = HybridChain(retriever=retriever, llm=llm)

    # (5) Query
    question = "防风应急响应和防汛应急响应有何异同？"
    result = await chain.ainvoke(question)

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
