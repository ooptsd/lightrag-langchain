"""Shared base class for all LightRAG QA chain pipelines.

Provides :class:`LightRAGBaseChain` — a Pydantic ``BaseModel`` that encapsulates
the full end-to-end chain pipeline (keyword extraction → retrieval → Document
conversion → token budget truncation → reference list generation → context
assembly → LLM invocation → streaming).  Subclasses only need to set ``mode``
and optionally override ``ainvoke`` / ``astream`` (BypassChain).

The pipeline mirrors upstream LightRAG's ``_build_query_context()`` 4-stage
flow (Search → Truncate → Merge → Build LLM Context) but composes Phase 5
Retrievers, Phase 3 keyword extraction, and Phase 3 token budget control
instead of LightRAG's monolithic internals.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, AsyncIterator

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, PrivateAttr

from lightrag_langchain.chain.prompt import (
    KG_QUERY_CONTEXT_TEMPLATE,
    NAIVE_QUERY_CONTEXT_TEMPLATE,
    NAIVE_RAG_RESPONSE_PROMPT,
    RAG_RESPONSE_PROMPT,
)
from lightrag_langchain.chain.utils import classify_and_convert

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI

    from lightrag_langchain.keywords import KeywordsSchema
    from lightrag_langchain.retriever.base import LightRAGBaseRetriever


class LightRAGBaseChain(BaseModel):
    """Base class for all LightRAG QA chain pipelines.

    Encapsulates shared infrastructure (keyword extraction, Document-to-dict
    conversion, token budget truncation, context assembly, LLM invocation,
    streaming) so that each mode-specific subclass only needs to provide a
    ``mode`` value and inherits all shared logic (D-02, D-05, D-06).

    Parameters
    ----------
    retriever:
        Retriever instance for document fetching (D-04 constructor injection).
    llm:
        ChatOpenAI instance for keyword extraction and answer generation (D-06).
    keyword_language:
        Language for keyword extraction, from settings.query_params.keyword_language.
    top_k:
        Override global top_k. When None, uses retriever's existing top_k.
    chunk_top_k:
        Override chunk_top_k. When None, uses retriever's existing chunk_top_k.
    mode:
        Query mode identifier — subclasses override with a concrete string
        (e.g. ``"naive"``, ``"local"``, ``"bypass"``).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    retriever: LightRAGBaseRetriever
    """Retriever instance for document fetching (D-04)."""

    llm: ChatOpenAI  # type: ignore[valid-type]
    """ChatOpenAI for keyword extraction and answer generation (D-06)."""

    keyword_language: str = "Chinese"
    """Language for keyword extraction."""

    top_k: int | None = None
    """Override global top_k. When None, uses retriever's existing top_k."""

    chunk_top_k: int | None = None
    """Override chunk_top_k. When None, uses retriever's existing chunk_top_k."""

    mode: str
    """Query mode identifier — subclasses override with a concrete string."""

    # ------------------------------------------------------------------
    # Private attributes
    # ------------------------------------------------------------------

    _logger: logging.Logger = PrivateAttr(
        default_factory=lambda: logging.getLogger(__name__)
    )
    """Per-instance logger for warnings and errors."""

    # =====================================================================
    # Public methods
    # =====================================================================

    def invoke(
        self,
        query: str,
        *,
        system_prompt: str | None = None,
        hl_keywords: list[str] | None = None,
        ll_keywords: list[str] | None = None,
        **kwargs,
    ) -> dict:
        """Synchronous path — uses ``asyncio.run`` to bridge to async implementation.

        Matches :class:`LightRAGBaseRetriever._get_relevant_documents` pattern
        (:file:`retriever/base.py` line 110-121).
        """
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
    ) -> dict:
        """Execute the full QA pipeline asynchronously (CHAIN-01, CHAIN-02).

        9-step pipeline matching upstream LightRAG chain flow:

        1. Resolve keywords (skip LLM if pre-provided, CHAIN-03)
        2. Retrieve documents via Phase 5 retriever
        3. Classify and convert Documents to typed dicts
        4. Apply token budget (entities → relations → chunk budget → truncate chunks)
        5. Build reference list from truncated results
        6. Assemble context string via upstream prompt template
        7. Build system prompt (or use caller-provided override, D-08)
        8. Call LLM with [SystemMessage, HumanMessage]
        9. Return structured dict with answer, sources, keywords, mode

        Returns
        -------
        dict
            ``{"answer": str, "sources": list[dict], "keywords": {"high_level": list[str], "low_level": list[str]}, "mode": str}``.
        """
        # Step 1: Resolve keywords (CHAIN-03)
        keywords = await self._resolve_keywords(query, hl_keywords, ll_keywords)

        # Step 2: Retrieve documents (Phase 5)
        docs: list[Document] = await self.retriever.ainvoke(query)

        # Step 3: Convert Documents to typed dicts
        entities, relations, chunks = classify_and_convert(docs)

        # Step 4: Apply token budget
        entities, relations, chunks = await self._apply_token_budget(
            entities, relations, chunks, query
        )

        # Step 5: Generate reference list (D-11, D-12)
        reference_list, chunks = self._build_reference_list(
            entities, relations, chunks
        )

        # Step 6: Assemble context string
        context_str = self._build_context_str(
            entities, relations, chunks, reference_list
        )

        # Step 7: Build system prompt
        sys_prompt = self._build_system_prompt(context_str, system_prompt)

        # Step 8: Call LLM
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=query),
        ]
        response = await self.llm.ainvoke(messages)

        # Step 9: Return structured dict (D-03 output format)
        return {
            "answer": response.content,
            "sources": reference_list,
            "keywords": {
                "high_level": keywords.high_level_keywords,
                "low_level": keywords.low_level_keywords,
            },
            "mode": self.mode,
        }

    async def astream(
        self,
        query: str,
        *,
        system_prompt: str | None = None,
        hl_keywords: list[str] | None = None,
        ll_keywords: list[str] | None = None,
        **kwargs,
    ) -> AsyncIterator[str | dict]:
        """Execute the full QA pipeline as a token-by-token stream (CHAIN-02, D-09, D-10).

        Steps 1-7 are identical to :meth:`ainvoke` (keyword resolution, retrieval,
        conversion, token budget, reference list, context assembly, system prompt).

        After context assembly (D-10: sources determined before streaming):

        * Yields raw ``str`` tokens from the LLM one at a time.
        * After the stream ends, yields a complete ``dict`` as the final chunk
          containing ``answer``, ``sources``, ``keywords``, and ``mode``.

        Callers distinguish text chunks from the final dict via
        ``isinstance(chunk, dict)`` (D-09).

        Yields
        ------
        str
            Individual tokens from the LLM stream.
        dict
            Complete result (last chunk only):
            ``{"answer": str, "sources": list[dict], "keywords": dict, "mode": str}``.
        """
        # Steps 1-7: identical to ainvoke pipeline
        keywords = await self._resolve_keywords(query, hl_keywords, ll_keywords)
        docs = await self.retriever.ainvoke(query)
        entities, relations, chunks = classify_and_convert(docs)
        entities, relations, chunks = await self._apply_token_budget(
            entities, relations, chunks, query
        )
        reference_list, chunks = self._build_reference_list(
            entities, relations, chunks
        )
        context_str = self._build_context_str(
            entities, relations, chunks, reference_list
        )
        sys_prompt = self._build_system_prompt(context_str, system_prompt)

        # Pre-compute the final dict (D-10: all data ready before streaming)
        final_dict: dict = {
            "answer": "",  # filled after streaming
            "sources": reference_list,
            "keywords": {
                "high_level": keywords.high_level_keywords,
                "low_level": keywords.low_level_keywords,
            },
            "mode": self.mode,
        }

        # Stream tokens from LLM (D-09: yield raw str)
        messages = [SystemMessage(content=sys_prompt), HumanMessage(content=query)]
        full_answer: list[str] = []
        async for chunk in self.llm.astream(messages):
            token = chunk.content
            if token:
                full_answer.append(token)
                yield token  # D-09: yield str for each token

        # Final structured dict (D-09: yield dict as last chunk)
        final_dict["answer"] = "".join(full_answer)
        self._last_result = final_dict  # CR-02: survive early consumer exit
        yield final_dict

    # =====================================================================
    # Internal methods
    # =====================================================================

    async def _resolve_keywords(
        self,
        query: str,
        hl_keywords: list[str] | None,
        ll_keywords: list[str] | None,
    ) -> KeywordsSchema:
        """Resolve keywords — use pre-provided or extract via LLM (CHAIN-03).

        When both *hl_keywords* and *ll_keywords* are provided, the LLM
        extraction step is skipped entirely.  Otherwise, ``extract_keywords``
        (Phase 3) is called with the chain's LLM instance.

        Parameters
        ----------
        query:
            The user's natural-language query.
        hl_keywords:
            Pre-provided high-level keywords, or ``None`` to trigger extraction.
        ll_keywords:
            Pre-provided low-level keywords, or ``None`` to trigger extraction.

        Returns
        -------
        KeywordsSchema
            Frozen model with ``high_level_keywords`` and ``low_level_keywords``.
        """
        if hl_keywords is not None and ll_keywords is not None:
            from lightrag_langchain.keywords import KeywordsSchema

            return KeywordsSchema(
                high_level_keywords=hl_keywords,
                low_level_keywords=ll_keywords,
            )

        from lightrag_langchain.keywords import extract_keywords

        return await extract_keywords(query, self.llm, self.keyword_language)

    async def _apply_token_budget(
        self,
        entities: list[dict],
        relations: list[dict],
        chunks: list[dict],
        query: str,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """Apply token budget truncation to entities, relations, and chunks.

        Execution order (Claude's Discretion — RESEARCH.md lines 487-495):

        a. Truncate entities by max_entity_tokens
        b. Truncate relations by max_relation_tokens
        c. Serialize truncated entities/relations, count their tokens
        d. Build preliminary system prompt with empty context_data, count tokens
        e. Compute chunk budget from remaining tokens
        f. Truncate chunks by chunk budget (prefix truncation)

        All Phase 3 imports are lazy (inside method body).

        Returns
        -------
        tuple[list[dict], list[dict], list[dict]]
            ``(entities, relations, chunks)`` — all truncated. Never mutates
            input lists.
        """
        from lightrag_langchain.config import settings
        from lightrag_langchain.token_budget import (
            _get_tokenizer,
            compute_chunk_token_budget,
        )

        enc = _get_tokenizer("gpt-4o-mini")

        # Step a: Truncate entities using json.dumps (consistent with context assembly)
        _max_entity = settings.query_params.max_entity_tokens
        if _max_entity <= 0:
            entities = []
        else:
            _entity_cumulative = 0
            for _i, _e in enumerate(entities):
                _entity_cumulative += len(
                    enc.encode(json.dumps(_e, ensure_ascii=False) + "\n")
                )
                if _entity_cumulative > _max_entity:
                    entities = entities[:_i]
                    break

        # Step b: Truncate relations using json.dumps (consistent with context assembly)
        _max_relation = settings.query_params.max_relation_tokens
        if _max_relation <= 0:
            relations = []
        else:
            _relation_cumulative = 0
            for _i, _r in enumerate(relations):
                _relation_cumulative += len(
                    enc.encode(json.dumps(_r, ensure_ascii=False) + "\n")
                )
                if _relation_cumulative > _max_relation:
                    relations = relations[:_i]
                    break

        # Step c: Count tokens used by truncated entities and relations
        entity_tokens_used = len(
            enc.encode(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in entities)
            )
        )
        relation_tokens_used = len(
            enc.encode(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in relations)
            )
        )

        # Step d: Build preliminary system prompt with empty context_data, count tokens
        preliminary_sys_prompt = RAG_RESPONSE_PROMPT.format(
            context_data="",
            response_type="Multiple Paragraphs",
            user_prompt="n/a",
        )
        sys_prompt_tokens = len(enc.encode(preliminary_sys_prompt))
        query_tokens = len(enc.encode(query))

        # Step e: Compute chunk budget
        chunk_budget = compute_chunk_token_budget(
            total_tokens=settings.query_params.max_total_tokens,
            sys_prompt_tokens=sys_prompt_tokens,
            query_tokens=query_tokens,
            entity_tokens_used=entity_tokens_used,
            relation_tokens_used=relation_tokens_used,
        )

        # Step f: Truncate chunks by chunk_budget (prefix truncation)
        truncated: list[dict] = []
        cumulative = 0
        for chunk in chunks:
            serialized = json.dumps(chunk, ensure_ascii=False)
            cumulative += len(enc.encode(serialized))
            if cumulative > chunk_budget:
                break
            truncated.append(chunk)

        return entities, relations, truncated

    def _build_reference_list(
        self,
        entities: list[dict],
        relations: list[dict],
        chunks: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """Generate deduplicated reference list and assign reference_ids to chunks.

        Algorithm (D-11, D-12, RESEARCH.md lines 504-528):

        1. Collect file_path from all entity/relation/chunk dicts
        2. Filter empty strings, ``None``, ``"unknown_source"``
        3. Count frequency per file_path
        4. Order: first-appearance, sorted by (-frequency, first_appearance_index)
        5. Assign sequential integer reference_ids: 1, 2, 3, …
        6. Build reference_list: ``[{"reference_id": int, "file_path": str}, ...]``
        7. Copy chunks, assign reference_id from fp_to_id mapping

        Never mutates input chunk dicts — always creates copies.

        Returns
        -------
        tuple[list[dict], list[dict]]
            ``(reference_list, chunks_with_ids)``.
        """
        # Step 1-3: Collect file_path counts
        file_path_counts: dict[str, int] = {}
        for item in entities + relations + chunks:
            fp = item.get("file_path", "")
            if fp and fp != "unknown_source":
                file_path_counts[fp] = file_path_counts.get(fp, 0) + 1

        # Step 4: Track first-appearance order, sort by (-frequency, first_index)
        seen: set[str] = set()
        ordered: list[tuple[str, int, int]] = []
        for i, item in enumerate(entities + relations + chunks):
            fp = item.get("file_path", "")
            if fp and fp != "unknown_source" and fp not in seen:
                ordered.append((fp, file_path_counts[fp], i))
                seen.add(fp)

        sorted_paths = sorted(ordered, key=lambda x: (-x[1], x[2]))

        # Step 5-6: Build reference_id mapping and reference list
        fp_to_id: dict[str, int] = {}
        reference_list: list[dict] = []
        for i, (fp, _count, _first_idx) in enumerate(sorted_paths):
            ref_id = i + 1  # D-12: integer type, 1-indexed
            fp_to_id[fp] = ref_id
            reference_list.append({"reference_id": ref_id, "file_path": fp})

        # Step 7: Copy chunk dicts, assign reference_id
        chunks_with_ids: list[dict] = []
        for chunk in chunks:
            c = chunk.copy()
            fp = c.get("file_path", "")
            c["reference_id"] = fp_to_id.get(fp, "")
            chunks_with_ids.append(c)

        return reference_list, chunks_with_ids

    def _build_context_str(
        self,
        entities: list[dict],
        relations: list[dict],
        chunks: list[dict],
        reference_list: list[dict],
    ) -> str:
        """Serialize all lists and format the appropriate upstream context template.

        Template dispatch by ``self.mode``:

        * ``"naive"`` → :data:`NAIVE_QUERY_CONTEXT_TEMPLATE`
        * ``"bypass"`` → ``""`` (empty — no context)
        * else (local/global/hybrid/mix) → :data:`KG_QUERY_CONTEXT_TEMPLATE`

        Parameters
        ----------
        entities:
            Truncated entity dicts.
        relations:
            Truncated relation dicts.
        chunks:
            Truncated chunk dicts (with reference_ids assigned).
        reference_list:
            Generated reference list.

        Returns
        -------
        str
            Formatted context string ready for system prompt assembly.
        """
        # Serialize entities and relations
        entities_str = "\n".join(
            json.dumps(e, ensure_ascii=False) for e in entities
        )
        relations_str = "\n".join(
            json.dumps(r, ensure_ascii=False) for r in relations
        )

        # Transform chunks into {"reference_id", "content"} format
        text_units = [
            {"reference_id": c["reference_id"], "content": c["content"]}
            for c in chunks
            if c.get("content")
        ]
        text_chunks_str = "\n".join(
            json.dumps(tu, ensure_ascii=False) for tu in text_units
        )

        # Format reference list string
        reference_list_str = "\n".join(
            f"[{ref['reference_id']}] {ref['file_path']}"
            for ref in reference_list
            if ref.get("reference_id")
        )

        # Template dispatch by mode
        if self.mode == "naive":
            return NAIVE_QUERY_CONTEXT_TEMPLATE.format(
                text_chunks_str=text_chunks_str,
                reference_list_str=reference_list_str,
            )

        if self.mode == "bypass":
            return ""

        # KG modes: local, global, hybrid, mix
        return KG_QUERY_CONTEXT_TEMPLATE.format(
            entities_str=entities_str,
            relations_str=relations_str,
            text_chunks_str=text_chunks_str,
            reference_list_str=reference_list_str,
        )

    def _build_system_prompt(
        self, context_str: str, system_prompt: str | None
    ) -> str:
        """Build the final system prompt (D-07, D-08).

        * If *system_prompt* is not ``None``, return it directly —
          complete override (D-08).
        * If ``self.mode == "naive"`` → :data:`NAIVE_RAG_RESPONSE_PROMPT`
          with ``{content_data}`` placeholder (NOT ``{context_data}`` —
          RESEARCH.md Pitfall 1).
        * Else (KG modes + bypass) → :data:`RAG_RESPONSE_PROMPT` with
          ``{context_data}`` placeholder.

        Parameters
        ----------
        context_str:
            Assembled context string from :meth:`_build_context_str`.
        system_prompt:
            Complete system prompt override (D-08).  When provided, no
            formatting is performed — the caller is fully responsible for
            the prompt content.

        Returns
        -------
        str
            The system prompt ready for LLM invocation.
        """
        if system_prompt is not None:
            return system_prompt  # D-08: complete override, no formatting

        if self.mode == "naive":
            # Pitfall 1: NAIVE_RAG_RESPONSE_PROMPT uses {content_data}
            return NAIVE_RAG_RESPONSE_PROMPT.format(
                content_data=context_str,
                response_type="Multiple Paragraphs",
                user_prompt="n/a",
            )

        # KG modes (local/global/hybrid/mix) + bypass
        return RAG_RESPONSE_PROMPT.format(
            context_data=context_str,
            response_type="Multiple Paragraphs",
            user_prompt="n/a",
        )


# ------------------------------------------------------------------
# Resolve Pydantic v2 forward references from TYPE_CHECKING imports
# ------------------------------------------------------------------

from langchain_openai import ChatOpenAI  # noqa: E402
from lightrag_langchain.retriever.base import LightRAGBaseRetriever  # noqa: E402

LightRAGBaseChain.model_rebuild()
