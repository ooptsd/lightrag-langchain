"""LightRAG query-mode chain subclasses.

This module provides six :class:`LightRAGBaseChain` subclasses, one per
LightRAG query mode.  Each chain:

1. Sets ``mode`` to the corresponding query mode string.
2. Inherits the full QA pipeline (keyword extraction, retrieval, Document
   conversion, token budget, context assembly, LLM invocation, streaming)
   from :class:`LightRAGBaseChain`.
3. Optionally overrides ``ainvoke`` / ``astream`` for special behavior
   (BypassChain skips all pipeline steps and calls the LLM directly).

Template selection is handled by the base class through ``self.mode`` dispatch
in :meth:`~LightRAGBaseChain._build_context_str` and
:meth:`~LightRAGBaseChain._build_system_prompt` — subclasses do not need to
override those methods.
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
    """LangChain QA Chain for LightRAG **naive** query mode.

    Uses NaiveRetriever for pure vector chunk search.
    Context assembled with NAIVE_QUERY_CONTEXT_TEMPLATE + NAIVE_RAG_RESPONSE_PROMPT.
    """

    mode: str = "naive"


# ===========================================================================
# Chain 2 — Local: entity-centric graph traversal (CHAIN-01 local mode)
# ===========================================================================


class LocalChain(LightRAGBaseChain):
    """LangChain QA Chain for LightRAG **local** query mode.

    Uses LocalRetriever for entity-centric graph traversal.
    Context assembled with KG_QUERY_CONTEXT_TEMPLATE + RAG_RESPONSE_PROMPT.
    """

    mode: str = "local"


# ===========================================================================
# Chain 3 — Global: relation-centric graph traversal (CHAIN-01 global mode)
# ===========================================================================


class GlobalChain(LightRAGBaseChain):
    """LangChain QA Chain for LightRAG **global** query mode.

    Uses GlobalRetriever for relation-centric graph traversal.
    Context assembled with KG_QUERY_CONTEXT_TEMPLATE + RAG_RESPONSE_PROMPT.
    """

    mode: str = "global"


# ===========================================================================
# Chain 4 — Hybrid: parallel local + global (CHAIN-01 hybrid mode)
# ===========================================================================


class HybridChain(LightRAGBaseChain):
    """LangChain QA Chain for LightRAG **hybrid** query mode.

    Uses HybridRetriever for parallel local+global with round-robin merge.
    Context assembled with KG_QUERY_CONTEXT_TEMPLATE + RAG_RESPONSE_PROMPT.
    """

    mode: str = "hybrid"


# ===========================================================================
# Chain 5 — Mix: hybrid + chunk search (CHAIN-01 mix mode)
# ===========================================================================


class MixChain(LightRAGBaseChain):
    """LangChain QA Chain for LightRAG **mix** query mode.

    Uses MixRetriever for hybrid + chunk search merge.
    Context assembled with KG_QUERY_CONTEXT_TEMPLATE + RAG_RESPONSE_PROMPT.
    """

    mode: str = "mix"


# ===========================================================================
# Chain 6 — Bypass: direct LLM call (CHAIN-01 bypass mode)
# ===========================================================================


class BypassChain(LightRAGBaseChain):
    """LangChain QA Chain for LightRAG **bypass** query mode.

    No keyword extraction, no retrieval, no token budget.
    Calls LLM directly with RAG_RESPONSE_PROMPT (empty context_data).
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
        """Synchronous bypass — calls LLM directly."""
        return asyncio.run(
            self.ainvoke(
                query,
                system_prompt=system_prompt,
                hl_keywords=hl_keywords,
                ll_keywords=ll_keywords,
                **kwargs,
            )
        )

    async def ainvoke(
        self,
        query: str,
        *,
        system_prompt: str | None = None,
        hl_keywords: list[str] | None = None,
        ll_keywords: list[str] | None = None,
        **kwargs,
    ) -> dict:  # noqa: ARG003  # hl_keywords/ll_keywords unused in bypass
        """Bypass: skip keywords + retrieval, direct LLM call.

        No keyword extraction, no retriever call, no token budget.
        Constructs a system prompt with empty context and calls the LLM.
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
        """Bypass streaming: skip keywords + retrieval, stream LLM tokens directly.

        Yields raw ``str`` tokens then a final ``dict`` with empty sources
        and keywords (D-09, D-10).
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
