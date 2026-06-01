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

from lightrag_langchain import MixChain, MixRetriever, create_llm, create_embedding
from lightrag_langchain.config import settings
from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run a Mix mode query — hybrid retrieval + chunk vector search."""

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

    # (3) Build retriever — Mix mode needs both vector_store and graph_store
    retriever = MixRetriever(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_config=settings.embedding,
    )

    # (4) Build chain
    chain = MixChain(retriever=retriever, llm=llm)

    # (5) Query
    question = "洪水防汛应急响应的完整体系是什么？"
    result = await chain.ainvoke(question)

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
