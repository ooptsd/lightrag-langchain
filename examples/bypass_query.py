"""Bypass query mode — direct LLM call, no retrieval step.

Bypass 模式跳过所有检索步骤（无关键词提取、无向量搜索、无图查询、
无 token 预算控制），直接将用户问题发送给 LLM。适用于无需外部知识的
纯对话场景。

Usage:
    cp ../.env.example ../.env   # edit with your credentials
    uv run python examples/bypass_query.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for running from examples/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lightrag_langchain import BypassChain, BypassRetriever, create_llm, create_embedding
from lightrag_langchain.config import settings
from lightrag_langchain.data.store import PGVectorStore


async def main() -> None:
    """Run a Bypass mode query — direct LLM call, no retrieval."""

    # (1) Create vector_store connection (required by BypassRetriever constructor,
    #     though internally unused — no vector search or graph lookup is performed)
    vector_store = PGVectorStore(
        embedding_dim=settings.embedding.dim,
        host=settings.pg.host,
        port=settings.pg.port,
        user=settings.pg.user,
        password=settings.pg.password.get_secret_value(),
        database=settings.pg.database,
    )

    # (2) Create LLM and embedding from settings
    llm = create_llm(settings.llm)
    embedding = create_embedding(settings.embedding)

    # (3) Build retriever — Bypass mode returns empty results (no retrieval)
    retriever = BypassRetriever(
        vector_store=vector_store,
        embedding_config=settings.embedding,
    )

    # (4) Build chain
    chain = BypassChain(retriever=retriever, llm=llm)

    # (5) Query — bypass mode: keywords=[], sources=[]
    question = "请简要介绍中国的应急管理体系。"
    result = await chain.ainvoke(question)

    print(f"模式: {result['mode']}")
    print(f"关键词: {result['keywords']}")
    print(f"来源数: {len(result['sources'])}")
    print(f"回答:\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
