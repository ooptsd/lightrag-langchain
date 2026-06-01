"""所有 LightRAG QA Chain 管线的共享基类。

提供 :class:`LightRAGBaseChain` — 一个 Pydantic ``BaseModel``，封装了完整的
端到端 chain 管线（关键词提取 → 检索 → Document 转换 → token 预算截断 →
引用列表生成 → 上下文组装 → LLM 调用 → 流式输出）。子类只需设置 ``mode``，
并可选择性地覆写 ``ainvoke`` / ``astream``（BypassChain）。

该管线复刻了上游 LightRAG 的 ``_build_query_context()`` 四阶段流程
（Search → Truncate → Merge → Build LLM Context），但组合了 Phase 5 的
Retriever、Phase 3 的关键词提取和 Phase 3 的 token 预算控制，
而非使用 LightRAG 内部的单体实现。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, PrivateAttr, field_validator

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
    """所有 LightRAG QA Chain 管线的基类。

    封装了共享基础设施（关键词提取、Document 转字典转换、token 预算截断、
    上下文组装、LLM 调用、流式输出），使每个模式特定的子类只需提供一个
    ``mode`` 值并继承所有共享逻辑（D-02、D-05、D-06）。

    Parameters
    ----------
    retriever:
        用于文档获取的 Retriever 实例（D-04 构造器注入）。
    llm:
        用于关键词提取和答案生成的 ChatOpenAI 实例（D-06）。
    keyword_language:
        关键词提取的语言，来自 settings.query_params.keyword_language。
    top_k:
        覆写全局 top_k。为 None 时使用 retriever 已有的 top_k。
    chunk_top_k:
        覆写 chunk_top_k。为 None 时使用 retriever 已有的 chunk_top_k。
    mode:
        查询模式标识符 — 子类用具体字符串覆写（例如 ``\"naive\"``、``\"local\"``、
        ``\"bypass\"``）。

    Example:
        ```python
        from lightrag_langchain.chain import NaiveChain
        from lightrag_langchain.retriever import NaiveRetriever
        from lightrag_langchain.llm import create_llm
        from lightrag_langchain.config import settings

        retriever = NaiveRetriever(vector_store=..., embedding_config=settings.embedding)
        llm = create_llm(settings.llm)
        chain = NaiveChain(retriever=retriever, llm=llm)
        result = await chain.ainvoke("your question")
        print(result["answer"])
        ```
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    retriever: LightRAGBaseRetriever
    """用于文档获取的 Retriever 实例（D-04）。"""

    llm: ChatOpenAI  # type: ignore[valid-type]
    """用于关键词提取和答案生成的 ChatOpenAI（D-06）。"""

    keyword_language: str = "Chinese"
    """关键词提取的语言。"""

    top_k: int | None = None
    """覆写全局 top_k。为 None 时使用 retriever 已有的 top_k。"""

    chunk_top_k: int | None = None
    """覆写 chunk_top_k。为 None 时使用 retriever 已有的 chunk_top_k。"""

    mode: str
    """查询模式标识符 — 子类用具体字符串覆写。"""

    @field_validator("llm", mode="before")
    @classmethod
    def _unwrap_lazy_llm(cls, v: Any) -> Any:
        """在 Pydantic 嵌套模型校验前解包 ``_LazyLLM`` 代理。

        当 ``llm`` 是 ``_LazyLLM`` 代理（来自 :func:`create_llm`）时，
        Pydantic 嵌套的 ``ChatOpenAI`` 校验会在原始代理上运行
        ``validate_temperature``（一个 ``mode="before"`` 校验器），该校验器期望一个
        dict 并调用 ``.get()``。由于 ``_LazyLLM.__getattr__`` 将调用委托给没有
        ``.get()`` 方法的 ``ChatOpenAI``，校验器会崩溃。

        此钩子检测代理、通过访问 ``.model_name`` 触发延迟构建，并返回内部的
        ``ChatOpenAI`` 实例，使 Pydantic 看到真正的模型对象。
        """
        if hasattr(v, "_config") and hasattr(v, "_instance"):
            _ = v.model_name  # trigger lazy ChatOpenAI construction
            return v._instance
        return v

    # ------------------------------------------------------------------
    # Private attributes
    # ------------------------------------------------------------------

    _logger: logging.Logger = PrivateAttr(
        default_factory=lambda: logging.getLogger(__name__)
    )
    """每个实例独立的 logger，用于警告和错误记录。"""

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
        """同步路径 — 桥接到异步实现。

        当没有事件循环运行时使用 ``asyncio.run``。当从运行中的事件循环内调用时
        （例如 FastAPI 路由、Jupyter notebook），回退到线程池执行器。
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
    ) -> dict:
        """异步执行完整 QA 管线（CHAIN-01、CHAIN-02）。

        9 个步骤，匹配上游 LightRAG chain 流程：

        1. 解析关键词（如果预先提供则跳过 LLM，CHAIN-03）
        2. 通过 Phase 5 retriever 检索文档
        3. 分类并将 Document 转换为类型化字典
        4. 应用 token 预算（entities → relations → chunk budget → 截断 chunks）
        5. 从截断后的结果构建引用列表
        6. 通过上游 prompt 模板组装上下文字符串
        7. 构建 system prompt（或使用调用方提供的覆写，D-08）
        8. 使用 [SystemMessage, HumanMessage] 调用 LLM
        9. 返回包含 answer、sources、keywords、mode 的结构化字典

        Returns
        -------
        dict
            ``{"answer": str, "sources": list[dict], "keywords": {"high_level": list[str], "low_level": list[str]}, "mode": str}``。
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
        """以逐 token 流式方式执行完整 QA 管线（CHAIN-02、D-09、D-10）。

        步骤 1-7 与 :meth:`ainvoke` 相同（关键词解析、检索、转换、token 预算、
        引用列表、上下文组装、system prompt）。

        上下文组装之后（D-10：在流式输出前确定 sources）：

        * 逐个产出 LLM 的原始 ``str`` token。
        * 流式输出结束后，产出完整的 ``dict`` 作为最后一个数据块，包含
          ``answer``、``sources``、``keywords`` 和 ``mode``。

        调用方通过 ``isinstance(chunk, dict)`` 区分文本 token 与最终字典
        （D-09）。

        Yields
        ------
        str
            LLM 流式输出中的单个 token。
        dict
            完整结果（仅最后一个数据块）：
            ``{"answer": str, "sources": list[dict], "keywords": dict, "mode": str}``。
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
        """解析关键词 — 使用预提供的或通过 LLM 提取（CHAIN-03）。

        当同时提供 *hl_keywords* 和 *ll_keywords* 时，LLM 提取步骤会被完全跳过。
        否则，使用 chain 的 LLM 实例调用 ``extract_keywords``（Phase 3）。

        Parameters
        ----------
        query:
            用户的自然语言查询。
        hl_keywords:
            预提供的高层关键词，为 ``None`` 则触发提取。
        ll_keywords:
            预提供的低层关键词，为 ``None`` 则触发提取。

        Returns
        -------
        KeywordsSchema
            包含 ``high_level_keywords`` 和 ``low_level_keywords`` 的冻结模型。
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
        """对 entities、relations 和 chunks 应用 token 预算截断。

        执行顺序（Claude 酌情决定 — RESEARCH.md 第 487-495 行）：

        a. 按 max_entity_tokens 截断 entities
        b. 按 max_relation_tokens 截断 relations
        c. 序列化已截断的 entities/relations，计算其 token 数
        d. 用空的 context_data 构建初步 system prompt，计算 token 数
        e. 根据剩余 token 计算 chunk 预算
        f. 按 chunk 预算截断 chunks（前缀截断）

        所有 Phase 3 导入均为延迟导入（在方法体内部）。

        Returns
        -------
        tuple[list[dict], list[dict], list[dict]]
            ``(entities, relations, chunks)`` — 均为已截断的。绝不修改输入列表。
        """
        from lightrag_langchain.config import settings
        from lightrag_langchain.token_budget import (
            _get_tokenizer,
            compute_chunk_token_budget,
        )

        _model_name = getattr(self.llm, "model_name", None) or "gpt-4o-mini"
        enc = _get_tokenizer(_model_name)

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
        """生成去重引用列表并为 chunks 分配 reference_id。

        算法（D-11、D-12、RESEARCH.md 第 504-528 行）：

        1. 从所有 entity/relation/chunk 字典中收集 file_path
        2. 过滤空字符串、``None``、``"unknown_source"``
        3. 统计每个 file_path 的频率
        4. 排序：按首次出现顺序，按 (-频率, 首次出现索引) 排序
        5. 分配连续的整数 reference_id：1、2、3、…
        6. 构建 reference_list：``[{"reference_id": int, "file_path": str}, ...]``
        7. 复制 chunks，根据 fp_to_id 映射分配 reference_id

        绝不修改输入的 chunk 字典——始终创建副本。

        Returns
        -------
        tuple[list[dict], list[dict]]
            ``(reference_list, chunks_with_ids)``。
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
            c["reference_id"] = fp_to_id.get(fp, None)
            chunks_with_ids.append(c)

        return reference_list, chunks_with_ids

    def _build_context_str(
        self,
        entities: list[dict],
        relations: list[dict],
        chunks: list[dict],
        reference_list: list[dict],
    ) -> str:
        """序列化所有列表并格式化对应的上游上下文模板。

        根据 ``self.mode`` 分发模板：

        * ``"naive"`` → :data:`NAIVE_QUERY_CONTEXT_TEMPLATE`
        * ``"bypass"`` → ``""``（空 — 无上下文）
        * else（local/global/hybrid/mix）→ :data:`KG_QUERY_CONTEXT_TEMPLATE`

        Parameters
        ----------
        entities:
            已截断的 entity 字典列表。
        relations:
            已截断的 relation 字典列表。
        chunks:
            已截断的 chunk 字典列表（已分配 reference_id）。
        reference_list:
            已生成的引用列表。

        Returns
        -------
        str
            格式化后的上下文字符串，可直接用于 system prompt 组装。
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

        # Format reference list string (WR-02: explicit None check, not truthiness)
        reference_list_str = "\n".join(
            f"[{ref['reference_id']}] {ref['file_path']}"
            for ref in reference_list
            if ref.get("reference_id") is not None
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
        """构建最终的 system prompt（D-07、D-08）。

        * 如果 *system_prompt* 不为 ``None``，直接返回 — 完全覆写（D-08）。
        * 如果 ``self.mode == "naive"`` → :data:`NAIVE_RAG_RESPONSE_PROMPT`
          使用 ``{content_data}`` 占位符（不是 ``{context_data}`` —
          RESEARCH.md Pitfall 1）。
        * 否则（KG 模式 + bypass）→ :data:`RAG_RESPONSE_PROMPT`
          使用 ``{context_data}`` 占位符。

        Parameters
        ----------
        context_str:
            来自 :meth:`_build_context_str` 的已组装的上下文字符串。
        system_prompt:
            完整的 system prompt 覆写（D-08）。提供时不执行格式化 — 调用方
            完全负责 prompt 内容。

        Returns
        -------
        str
            可立即用于 LLM 调用的 system prompt。
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
