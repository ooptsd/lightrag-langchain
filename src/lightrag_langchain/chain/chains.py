"""LightRAG 查询模式 Chain 子类。

此模块提供六个 :class:`LightRAGBaseChain` 子类，每个对应一种
LightRAG 查询模式。每个 chain：

1. 将 ``mode`` 设置为对应的查询模式字符串。
2. 从 :class:`LightRAGBaseChain` 继承完整的 QA 管线（关键词提取、检索、
   Document 转换、token 预算、上下文组装、LLM 调用、流式输出）。
3. 可选择性地覆写 ``ainvoke`` / ``astream`` 以实现特殊行为
   （BypassChain 跳过所有管线步骤，直接调用 LLM）。

模板选择由基类通过 ``self.mode`` 分发在
:meth:`~LightRAGBaseChain._build_context_str` 和
:meth:`~LightRAGBaseChain._build_system_prompt` 中处理 — 子类无需
覆写这些方法。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from lightrag_langchain.chain.base import LightRAGBaseChain
from lightrag_langchain.chain.prompt import RAG_RESPONSE_PROMPT

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI

    from lightrag_langchain.retriever.base import LightRAGBaseRetriever

logger = logging.getLogger(__name__)


# ===========================================================================
# Chain 1 — Naive: pure vector chunk search (CHAIN-01 naive mode)
# ===========================================================================


class NaiveChain(LightRAGBaseChain):
    """LightRAG **naive** 查询模式的 LangChain QA Chain。

    使用 NaiveRetriever 进行纯向量 chunk 搜索。
    上下文用 NAIVE_QUERY_CONTEXT_TEMPLATE + NAIVE_RAG_RESPONSE_PROMPT 组装。

    Example:
        ```python
        from lightrag_langchain.chain import NaiveChain

        chain = NaiveChain(retriever=naive_retriever, llm=llm)
        result = await chain.ainvoke("What is this document about?")
        ```
    """

    mode: str = "naive"


# ===========================================================================
# Chain 2 — Local: entity-centric graph traversal (CHAIN-01 local mode)
# ===========================================================================


class LocalChain(LightRAGBaseChain):
    """LightRAG **local** 查询模式的 LangChain QA Chain。

    使用 LocalRetriever 进行以 entity 为中心的图遍历。
    上下文用 KG_QUERY_CONTEXT_TEMPLATE + RAG_RESPONSE_PROMPT 组装。

    Example:
        ```python
        from lightrag_langchain.chain import LocalChain

        chain = LocalChain(retriever=local_retriever, llm=llm)
        result = await chain.ainvoke("Which entities relate to flood control?")
        ```
    """

    mode: str = "local"


# ===========================================================================
# Chain 3 — Global: relation-centric graph traversal (CHAIN-01 global mode)
# ===========================================================================


class GlobalChain(LightRAGBaseChain):
    """LightRAG **global** 查询模式的 LangChain QA Chain。

    使用 GlobalRetriever 进行以 relation 为中心的图遍历。
    上下文用 KG_QUERY_CONTEXT_TEMPLATE + RAG_RESPONSE_PROMPT 组装。

    Example:
        ```python
        from lightrag_langchain.chain import GlobalChain

        chain = GlobalChain(retriever=global_retriever, llm=llm)
        result = await chain.ainvoke("What relationships exist between these entities?")
        ```
    """

    mode: str = "global"


# ===========================================================================
# Chain 4 — Hybrid: parallel local + global (CHAIN-01 hybrid mode)
# ===========================================================================


class HybridChain(LightRAGBaseChain):
    """LightRAG **hybrid** 查询模式的 LangChain QA Chain。

    使用 HybridRetriever 进行并行 local+global 的轮询合并。
    上下文用 KG_QUERY_CONTEXT_TEMPLATE + RAG_RESPONSE_PROMPT 组装。

    Example:
        ```python
        from lightrag_langchain.chain import HybridChain

        chain = HybridChain(retriever=hybrid_retriever, llm=llm)
        result = await chain.ainvoke("Give me a comprehensive analysis of this topic")
        ```
    """

    mode: str = "hybrid"


# ===========================================================================
# Chain 5 — Mix: hybrid + chunk search (CHAIN-01 mix mode)
# ===========================================================================


class MixChain(LightRAGBaseChain):
    """LightRAG **mix** 查询模式的 LangChain QA Chain。

    使用 MixRetriever 进行 hybrid + chunk 搜索合并。
    上下文用 KG_QUERY_CONTEXT_TEMPLATE + RAG_RESPONSE_PROMPT 组装。

    Example:
        ```python
        from lightrag_langchain.chain import MixChain

        chain = MixChain(retriever=mix_retriever, llm=llm)
        result = await chain.ainvoke("Find everything relevant to this query")
        ```
    """

    mode: str = "mix"


# ===========================================================================
# Chain 6 — Bypass: direct LLM call (CHAIN-01 bypass mode)
# ===========================================================================


class BypassChain(LightRAGBaseChain):
    """LightRAG **bypass** 查询模式的 LangChain QA Chain。

    无关键词提取、无检索、无 token 预算。
    直接使用 RAG_RESPONSE_PROMPT（空的 context_data）调用 LLM。

    Example:
        ```python
        from lightrag_langchain.chain import BypassChain

        chain = BypassChain(retriever=bypass_retriever, llm=llm)
        result = await chain.ainvoke("Tell me a joke")
        ```
    """

    mode: str = "bypass"

    # ------------------------------------------------------------------
    # Override invoke / ainvoke / astream — completely skip pipeline
    # ------------------------------------------------------------------

    def invoke(
        self,
        query: str,
        *,
        system_prompt: str | None = None,
        hl_keywords: list[str] | None = None,
        ll_keywords: list[str] | None = None,
        **kwargs,
    ) -> dict:
        """同步 bypass — 直接调用 LLM。

        当没有事件循环运行时使用 ``asyncio.run``。当从运行中的事件循环内调用时
        回退到线程池执行器。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.ainvoke(
                    query,
                    system_prompt=system_prompt,
                    hl_keywords=hl_keywords,
                    ll_keywords=ll_keywords,
                    **kwargs,
                )
            )
        else:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.ainvoke(
                        query,
                        system_prompt=system_prompt,
                        hl_keywords=hl_keywords,
                        ll_keywords=ll_keywords,
                        **kwargs,
                    ),
                )
                return future.result()

    async def ainvoke(
        self,
        query: str,
        *,
        system_prompt: str | None = None,
        hl_keywords: list[str] | None = None,
        ll_keywords: list[str] | None = None,
        **kwargs,
    ) -> dict:  # noqa: ARG003  # hl_keywords/ll_keywords unused in bypass
        """Bypass：跳过关键词提取 + 检索，直接调用 LLM。

        无关键词提取、无 retriever 调用、无 token 预算。
        用空上下文构建 system prompt 并调用 LLM。
        """
        sys_prompt = system_prompt or RAG_RESPONSE_PROMPT.format(
            context_data="",
            response_type="Multiple Paragraphs",
            user_prompt="n/a",
        )
        messages = [SystemMessage(content=sys_prompt), HumanMessage(content=query)]
        response = await self.llm.ainvoke(messages)
        return {
            "answer": response.content,
            "sources": [],
            "keywords": {"high_level": [], "low_level": []},
            "mode": "bypass",
        }

    async def astream(
        self,
        query: str,
        *,
        system_prompt: str | None = None,
        hl_keywords: list[str] | None = None,
        ll_keywords: list[str] | None = None,
        **kwargs,
    ) -> AsyncIterator[str | dict]:  # noqa: ARG003  # hl_keywords/ll_keywords unused in bypass
        """Bypass 流式输出：跳过关键词提取 + 检索，直接流式输出 LLM token。

        产出原始 ``str`` token，然后产出带有空 sources 和 keywords 的
        最终 ``dict``（D-09、D-10）。
        """
        sys_prompt = system_prompt or RAG_RESPONSE_PROMPT.format(
            context_data="",
            response_type="Multiple Paragraphs",
            user_prompt="n/a",
        )
        messages = [SystemMessage(content=sys_prompt), HumanMessage(content=query)]

        final_dict: dict = {
            "answer": "",
            "sources": [],
            "keywords": {"high_level": [], "low_level": []},
            "mode": "bypass",
        }

        full_answer: list[str] = []
        async for chunk in self.llm.astream(messages):
            token = chunk.content
            if token:
                full_answer.append(token)
                yield token

        final_dict["answer"] = "".join(full_answer)
        self._last_result = final_dict  # CR-02: survive early consumer exit
        yield final_dict


# ------------------------------------------------------------------
# Resolve Pydantic v2 forward references from TYPE_CHECKING imports
# ------------------------------------------------------------------

from langchain_openai import ChatOpenAI  # noqa: E402
from lightrag_langchain.retriever.base import LightRAGBaseRetriever  # noqa: E402

for _cls in (
    NaiveChain,
    LocalChain,
    GlobalChain,
    HybridChain,
    MixChain,
    BypassChain,
):
    _cls.model_rebuild()
