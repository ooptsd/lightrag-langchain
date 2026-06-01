# Phase 6: QA Chain - Pattern Map

**Mapped:** 2026-05-31
**Files analyzed:** 11 (8 new + 3 modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lightrag_langchain/chain/__init__.py` | module-init | lazy-import | `src/lightrag_langchain/retriever/__init__.py` | exact |
| `src/lightrag_langchain/chain/base.py` | service | request-response + pipeline | `src/lightrag_langchain/retriever/base.py` | role-match |
| `src/lightrag_langchain/chain/chains.py` | service | request-response | `src/lightrag_langchain/retriever/retrievers.py` | exact |
| `src/lightrag_langchain/chain/utils.py` | utility | transform | `src/lightrag_langchain/retriever/utils.py` | exact |
| `src/lightrag_langchain/chain/prompt.py` | config | const-data | `src/lightrag_langchain/keywords.py` (template embedding) | role-match |
| `src/lightrag_langchain/__init__.py` (modify) | module-init | lazy-import | `src/lightrag_langchain/__init__.py` (existing `__getattr__`) | exact |
| `tests/conftest.py` (modify) | test-fixture | n/a | `tests/conftest.py` (existing fixtures) | exact |
| `tests/test_chain_base.py` | test | n/a | `tests/test_retriever.py` + `tests/test_keywords.py` | role-match |
| `tests/test_chain_dispatch.py` | test | n/a | `tests/test_retriever.py` (subclass test classes) | role-match |
| `tests/test_chain_stream.py` | test | n/a | `tests/test_retriever.py` (AsyncMock patterns) | role-match |
| `tests/test_chain_keywords.py` | test | n/a | `tests/test_keywords.py` (keyword extraction mock) | exact |

## Pattern Assignments

### 1. `src/lightrag_langchain/chain/__init__.py` (module-init, lazy-import)

**Analog:** `src/lightrag_langchain/retriever/__init__.py` (exact match)

**Docstring/header pattern** (lines 1-15):
```python
"""LightRAG QA Chain implementations — LangChain-compatible query-to-answer pipelines.

This package provides a shared base class :class:`LightRAGBaseChain` and
six mode-specific chain subclasses (NaiveChain, LocalChain,
GlobalChain, HybridChain, MixChain, BypassChain), each
encapsulating one LightRAG query mode behind a standard ``invoke`` /
``ainvoke`` / ``astream`` interface.

All exports use lazy ``__getattr__`` so that ``import lightrag_langchain.chain``
does NOT trigger:
- Settings singleton instantiation (no .env file required at import time)
- Any LangChain imports (ChatOpenAI)
- Any LLM / keyword extraction call
- Any database connection
- Any network call
"""
```

**Lazy __getattr__ pattern** (lines 30-66):
```python
from __future__ import annotations

__all__ = [
    "LightRAGBaseChain",
    "NaiveChain",
    "LocalChain",
    "GlobalChain",
    "HybridChain",
    "MixChain",
    "BypassChain",
]


def __getattr__(name: str):
    """Lazy import for chain classes — defers import/construction until
    the exported identifier is actually accessed.

    Pattern matches :file:`lightrag_langchain/retriever/__init__.py`.
    """
    if name == "LightRAGBaseChain":
        from lightrag_langchain.chain.base import LightRAGBaseChain
        return LightRAGBaseChain
    if name == "NaiveChain":
        from lightrag_langchain.chain.chains import NaiveChain
        return NaiveChain
    if name == "LocalChain":
        from lightrag_langchain.chain.chains import LocalChain
        return LocalChain
    if name == "GlobalChain":
        from lightrag_langchain.chain.chains import GlobalChain
        return GlobalChain
    if name == "HybridChain":
        from lightrag_langchain.chain.chains import HybridChain
        return HybridChain
    if name == "MixChain":
        from lightrag_langchain.chain.chains import MixChain
        return MixChain
    if name == "BypassChain":
        from lightrag_langchain.chain.chains import BypassChain
        return BypassChain

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

---

### 2. `src/lightrag_langchain/chain/base.py` (service, pipeline)

**Analog:** `src/lightrag_langchain/retriever/base.py` (role-match -- BaseModel + Pydantic fields + PrivateAttr + asyncio.run bridge)

**Imports pattern** (lines 14-30 of retriever/base.py):
```python
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, PrivateAttr

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
    from lightrag_langchain.retriever.base import LightRAGBaseRetriever
```

**Base class Pydantic model pattern** (lines 33-85 of retriever/base.py):
```python
class LightRAGBaseChain(BaseModel):
    """Base class for all LightRAG QA chain pipelines.

    Encapsulates shared infrastructure (keyword extraction, Document-to-dict
    conversion, token budget truncation, context assembly, LLM invocation,
    streaming) so that each mode-specific subclass only needs to provide a
    retriever and select which prompt templates to use (D-02, D-05, D-06).

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
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    retriever: LightRAGBaseRetriever
    """Retriever for document fetching (D-04)."""

    llm: ChatOpenAI  # type: ignore[valid-type]
    """ChatOpenAI instance for keyword extraction and answer generation (D-06)."""

    keyword_language: str = "Chinese"
    """Language for keyword extraction."""

    top_k: int | None = None
    chunk_top_k: int | None = None

    # Private attributes
    _logger: logging.Logger = PrivateAttr(
        default_factory=lambda: logging.getLogger(__name__)
    )

    # Mode identifier — subclasses override
    mode: str
```

**Sync/async bridge pattern** (lines 110-121 of retriever/base.py):
```python
def invoke(self, query: str, *, system_prompt: str | None = None,
           hl_keywords: list[str] | None = None, ll_keywords: list[str] | None = None,
           **kwargs) -> dict:
    """Synchronous path — uses ``asyncio.run`` to bridge to async implementation."""
    return asyncio.run(self.ainvoke(
        query, system_prompt=system_prompt,
        hl_keywords=hl_keywords, ll_keywords=ll_keywords, **kwargs
    ))
```

**model_rebuild() at module bottom** (lines 155-164 of retriever/base.py):
```python
# ------------------------------------------------------------------
# Resolve Pydantic v2 forward references from TYPE_CHECKING imports
# ------------------------------------------------------------------

from langchain_openai import ChatOpenAI  # noqa: E402
from lightrag_langchain.retriever.base import LightRAGBaseRetriever  # noqa: E402

LightRAGBaseChain.model_rebuild()
```

**Additional patterns unique to chain/base.py:**

**Prompt template constants pattern** -- copy from keywords.py (lines 60-112):
```python
# Source: upstream LightRAG lightrag/prompt.py L:170-222, copied 2026-05-31
RAG_RESPONSE_PROMPT = """---角色---
你是一位专业的 AI 助手...
{context_data}
"""

# Source: upstream LightRAG lightrag/prompt.py L:224-276
NAIVE_RAG_RESPONSE_PROMPT = """---角色---
你是一位专业的 AI 助手...
{content_data}
"""

# Source: upstream LightRAG lightrag/prompt.py L:278-306
KG_QUERY_CONTEXT_TEMPLATE = """
知识图谱数据（实体）:
```json
{entities_str}
```
...
"""

# Source: upstream LightRAG lightrag/prompt.py L:308-323
NAIVE_QUERY_CONTEXT_TEMPLATE = """
文档片段...
```json
{text_chunks_str}
```
...
"""
```

**Document-to-dict conversion pattern** — reverse of retriever/utils.py (lines 36-84, 133-168, 185-203):
```python
import json
from langchain_core.documents import Document

def _doc_to_entity_dict(doc: Document) -> dict:
    """Parse entity Document's JSON page_content into dict."""
    obj = json.loads(doc.page_content)
    return {
        "entity_name": obj.get("entity_name", ""),
        "entity_type": obj.get("entity_type", ""),
        "description": obj.get("description", ""),
        "source_id": obj.get("source_id", ""),
        "file_path": obj.get("file_path", ""),
    }

def _doc_to_relation_dict(doc: Document) -> dict:
    obj = json.loads(doc.page_content)
    return {
        "src_id": obj.get("src_id", ""),
        "tgt_id": obj.get("tgt_id", ""),
        "description": obj.get("description", ""),
        "keywords": obj.get("keywords", ""),
        "weight": obj.get("weight", 0.0),
        "source_id": obj.get("source_id", ""),
        "file_path": obj.get("file_path", ""),
    }

def _doc_to_chunk_dict(doc: Document) -> dict:
    obj = json.loads(doc.page_content)
    return {
        "content": obj.get("content", ""),
        "file_path": obj.get("file_path", ""),
        "chunk_id": obj.get("chunk_id", ""),
        "reference_id": obj.get("reference_id", ""),
    }

def _docs_to_dicts(docs: list[Document]) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify and convert all Documents to typed dicts by document_type."""
    entities = []
    relations = []
    chunks = []
    for doc in docs:
        dtype = doc.metadata.get("document_type", "")
        if dtype == "entity":
            entities.append(_doc_to_entity_dict(doc))
        elif dtype == "relation":
            relations.append(_doc_to_relation_dict(doc))
        elif dtype == "chunk":
            chunks.append(_doc_to_chunk_dict(doc))
    return entities, relations, chunks
```

**Reference list generation pattern** — adapted from upstream utils.py (lines 3292-3355), D-11/D-12 (integer IDs):
```python
def _build_reference_list(
    entities: list[dict], relations: list[dict], chunks: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Generate deduplicated reference list and assign reference_ids to chunks."""
    file_path_counts: dict[str, int] = {}

    for item in entities + relations + chunks:
        fp = item.get("file_path", "")
        if fp and fp != "unknown_source":
            file_path_counts[fp] = file_path_counts.get(fp, 0) + 1

    seen: set[str] = set()
    ordered: list[tuple[str, int, int]] = []
    for i, item in enumerate(entities + relations + chunks):
        fp = item.get("file_path", "")
        if fp and fp != "unknown_source" and fp not in seen:
            ordered.append((fp, file_path_counts[fp], i))
            seen.add(fp)

    sorted_paths = sorted(ordered, key=lambda x: (-x[1], x[2]))

    fp_to_id: dict[str, int] = {}
    reference_list: list[dict] = []
    for i, (fp, _, _) in enumerate(sorted_paths):
        ref_id = i + 1
        fp_to_id[fp] = ref_id
        reference_list.append({"reference_id": ref_id, "file_path": fp})

    chunks_with_ids = []
    for chunk in chunks:
        c = chunk.copy()
        fp = c.get("file_path", "")
        c["reference_id"] = fp_to_id.get(fp, "")
        chunks_with_ids.append(c)

    return reference_list, chunks_with_ids
```

**Token budget integration pattern** -- token_budget.py function signatures (lines 77-81, 119-123, 160-167):
```python
# Phase 3 functions — call with entities/relations dicts
from lightrag_langchain.token_budget import (
    truncate_entities_by_tokens,
    truncate_relations_by_tokens,
    compute_chunk_token_budget,
    _get_tokenizer,
)

# Usage order (Claude's Discretion):
# 1. Truncate entities
entities = truncate_entities_by_tokens(entities, settings.query_params.max_entity_tokens)
# 2. Truncate relations
relations = truncate_relations_by_tokens(relations, settings.query_params.max_relation_tokens)
# 3. Measure preliminary context tokens
enc = _get_tokenizer("gpt-4o-mini")
entity_tokens_used = len(enc.encode("\n".join(json.dumps(e) for e in entities)))
relation_tokens_used = len(enc.encode("\n".join(json.dumps(r) for r in relations)))
# 4. Build preliminary sys prompt, measure tokens
sys_prompt_tokens = len(enc.encode(preliminary_sys_prompt))
# 5. Compute chunk budget
chunk_budget = compute_chunk_token_budget(
    total_tokens=settings.query_params.max_total_tokens,
    sys_prompt_tokens=sys_prompt_tokens,
    query_tokens=len(enc.encode(query)),
    entity_tokens_used=entity_tokens_used,
    relation_tokens_used=relation_tokens_used,
)
```

---

### 3. `src/lightrag_langchain/chain/chains.py` (service, request-response)

**Analog:** `src/lightrag_langchain/retriever/retrievers.py` (exact match -- multiple subclasses with minimal override)

**Imports pattern** (lines 14-43 of retrievers.py):
```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lightrag_langchain.chain.base import LightRAGBaseChain

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
    from lightrag_langchain.retriever.base import LightRAGBaseRetriever

logger = logging.getLogger(__name__)
```

**Subclass pattern** (mirrors retrievers.py line 52-82 NaiveRetriever):
```python
class NaiveChain(LightRAGBaseChain):
    """LangChain QA Chain for LightRAG **naive** query mode.

    Uses NaiveRetriever for pure vector chunk search.
    Context assembled with NAIVE_QUERY_CONTEXT_TEMPLATE + NAIVE_RAG_RESPONSE_PROMPT.
    """

    mode: str = "naive"
```

**Subclass override for context template selection (KG modes):**
```python
class LocalChain(LightRAGBaseChain):
    """LangChain QA Chain for LightRAG **local** query mode."""
    mode: str = "local"
    # Inherits KG template selection from base _build_context_str default

class GlobalChain(LightRAGBaseChain):
    mode: str = "global"

class HybridChain(LightRAGBaseChain):
    mode: str = "hybrid"

class MixChain(LightRAGBaseChain):
    mode: str = "mix"
```

**BypassChain special case** (mirrors retrievers.py BypassRetriever lines 379-398 -- empty implementation override):
```python
class BypassChain(LightRAGBaseChain):
    """LangChain QA Chain for LightRAG **bypass** query mode.

    No keyword extraction, no retrieval, no context.  Uses RAG_RESPONSE_PROMPT
    with empty context_data, calls LLM directly.
    """
    mode: str = "bypass"

    async def ainvoke(self, query: str, *, system_prompt=None,
                      hl_keywords=None, ll_keywords=None, **kwargs) -> dict:
        """Bypass: skip keywords + retrieval, direct LLM call."""
        sys_prompt = system_prompt or RAG_RESPONSE_PROMPT.format(
            context_data="", response_type="Multiple Paragraphs", user_prompt="n/a"
        )
        messages = [SystemMessage(content=sys_prompt), HumanMessage(content=query)]
        response = await self.llm.ainvoke(messages)
        return {
            "answer": response.content,
            "sources": [],
            "keywords": {"high_level": [], "low_level": []},
            "mode": "bypass",
        }
```

**model_rebuild() at module bottom** (lines 401-416 of retrievers.py):
```python
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
```

---

### 4. `src/lightrag_langchain/chain/utils.py` (utility, transform)

**Analog:** `src/lightrag_langchain/retriever/utils.py` (exact match -- pure function helpers, no I/O, no side effects)

**Docstring pattern** (lines 1-9 of retriever/utils.py):
```python
"""Shared Document-conversion utilities for LightRAG QA chains.

Pure functions (no I/O, no async, no side effects) that convert LangChain
``Document`` instances back into structured dicts for token budget truncation
and upstream prompt template assembly.

Reverse direction of :file:`retriever/utils.py` — Document → dict instead
of record → Document.
"""
```

**Pure function signature pattern** (from retriever/utils.py):
```python
from __future__ import annotations

import json

from langchain_core.documents import Document


def doc_to_entity_dict(doc: Document) -> dict:
    """Parse entity Document's JSON page_content into a structured dict.

    Parameters
    ----------
    doc:
        A Document with document_type='entity' in metadata.

    Returns
    -------
    dict
        Dict with keys: entity_name, entity_type, description, source_id, file_path.
    """
    ...


def doc_to_relation_dict(doc: Document) -> dict:
    """Parse relation Document's JSON page_content into a structured dict.

    Returns
    -------
    dict
        Dict with keys: src_id, tgt_id, description, keywords, weight, source_id, file_path.
    """
    ...


def doc_to_chunk_dict(doc: Document) -> dict:
    """Parse chunk Document's JSON page_content into a structured dict.

    Returns
    -------
    dict
        Dict with keys: content, file_path, chunk_id, reference_id.
    """
    ...


def classify_and_convert(
    docs: list[Document],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify Documents by metadata['document_type'] and convert each.

    Returns (entities, relations, chunks) tuple.
    GraphTriple Documents are skipped for context assembly.
    """
    ...
```

**Error handling pattern** (from keywords.py, lines 120-175 -- function-level docstring + type hints):
```python
"""No custom error handling — exceptions (json.JSONDecodeError, KeyError)
propagate to caller.  Pure functions have no external dependencies."""
```

---

### 5. `src/lightrag_langchain/chain/prompt.py` (config, const-data)

**Analog:** `src/lightrag_langchain/keywords.py` (role-match -- module-level constant pattern, lines 55-112)

**Module docstring pattern** (lines 1-20 of keywords.py):
```python
"""Upstream LightRAG prompt templates for QA chain context assembly.

Reuses upstream LightRAG's proven prompt templates verbatim.  Templates are
embedded as module-level constants with ``.format()``-compatible placeholders
preserved (``{context_data}``, ``{response_type}``, ``{user_prompt}``, etc.).

Usage::

    from lightrag_langchain.chain.prompt import RAG_RESPONSE_PROMPT, KG_QUERY_CONTEXT_TEMPLATE

    sys_prompt = RAG_RESPONSE_PROMPT.format(
        context_data=assembled_context,
        response_type="Multiple Paragraphs",
        user_prompt="n/a",
    )
"""
```

**Module-level constant pattern** (copy from keywords.py line 60):
```python
# Source: upstream LightRAG lightrag/prompt.py L:170-222, copied 2026-05-31
RAG_RESPONSE_PROMPT = """---角色---
你是一位专业的 AI 助手，专门从"三防"（防汛、防旱、防风、防冻）应急管理知识库中综合信息。你的主要功能是仅使用提供的**上下文**中的信息来准确回答用户查询。

---目标---
为用户查询生成全面、结构良好的回答。
回答必须整合**上下文**中找到的知识图谱和文档片段中的相关事实。
如果提供了对话历史，请加以考虑，以保持对话流畅并避免重复信息。

---指令---
1. 分步指令:
  - 结合对话历史，仔细判断用户的查询意图，充分理解用户关于应急预案或指挥的信息需求。如涉及城市特定语境，请予以关注。
  - 仔细审查**上下文**中的`Knowledge Graph Data`和`Document Chunks`。识别并提取与回答用户查询直接相关的所有信息。
  - 将提取的事实编织成连贯、有逻辑的回复。你的自有知识只能用于组织流畅的句子和连接想法，**不得**引入任何外部信息。
  - 跟踪直接支持回复中所述事实的文档片段的 reference_id。将 reference_id 与`Reference Document List`中的条目关联，以生成正确的引用。
  - 在回复末尾生成一个引用文献部分。每篇引用文献必须直接支持回复中呈现的事实。
  - 引用部分之后不得生成任何内容。

2. 内容与依据:
  - 严格依据提供的**上下文**；**不得**臆造、假设或推断任何未明确陈述的信息。
  - 如果在**上下文**中找不到答案，请说明你没有足够的信息来回答。不要试图猜测。

3. 格式与语言:
  - 回复必须与用户查询使用相同的语言。
  - 回复必须使用 Markdown 格式以增强清晰度和结构（例如，标题、粗体文本、项目符号）。
  - 回复应以{response_type}格式呈现。

4. 引用部分格式:
  - 引用部分应使用标题: `### References`
  - 引用条目应遵循格式: `* [n] Document Title`。不要在左方括号（`[`）后面插入脱字符（`^`）。
  - 引用中的 Document Title 必须保留其原始语言。
  - 每条引用单独一行输出。
  - 最多提供 5 条最相关的引用。
  - 引用之后不得生成脚注部分或任何评论、总结或解释。

5. 引用部分示例:

```

### References

* [1] Document Title One
* [2] Document Title Two
* [3] Document Title Three

```

6. 附加指令: {user_prompt}


---上下文---

{context_data}
"""
```

**Other constants** (same pattern, different placeholder names per RESEARCH.md notes):
```python
# Source: upstream LightRAG lightrag/prompt.py L:224-276, copied 2026-05-31
NAIVE_RAG_RESPONSE_PROMPT = """...
{content_data}...
"""  # NOTE: placeholder is {content_data}, NOT {context_data}

# Source: upstream LightRAG lightrag/prompt.py L:278-306, copied 2026-05-31
KG_QUERY_CONTEXT_TEMPLATE = """
知识图谱数据（实体）:
```json
{entities_str}

```

知识图谱数据（关系）:

```json
{relations_str}

```

文档片段（每个条目有一个 reference_id，对应`Reference Document List`）:

```json
{text_chunks_str}

```

引用文献列表（每个条目以 [reference_id] 开头，对应 Document Chunks 中的条目）:

```
{reference_list_str}

```

"""

# Source: upstream LightRAG lightrag/prompt.py L:308-323, copied 2026-05-31
NAIVE_QUERY_CONTEXT_TEMPLATE = """
文档片段（每个条目有一个 reference_id，对应`Reference Document List`）:

```json
{text_chunks_str}

```

引用文献列表（每个条目以 [reference_id] 开头，对应 Document Chunks 中的条目）:

```
{reference_list_str}

```

"""
```

---

### 6. `src/lightrag_langchain/__init__.py` (modify -- add 6 Chain class exports)

**Analog:** `src/lightrag_langchain/__init__.py` (existing lazy `__getattr__`, lines 22-98)

**Pattern: Add 6 new if-blocks to existing ``__getattr__`` function** (after existing retriever blocks, before the final `raise AttributeError`):
```python
    # -- Chains (chain/chains.py) ----------------------------------------------
    if name == "NaiveChain":
        from lightrag_langchain.chain.chains import NaiveChain
        return NaiveChain
    if name == "LocalChain":
        from lightrag_langchain.chain.chains import LocalChain
        return LocalChain
    if name == "GlobalChain":
        from lightrag_langchain.chain.chains import GlobalChain
        return GlobalChain
    if name == "HybridChain":
        from lightrag_langchain.chain.chains import HybridChain
        return HybridChain
    if name == "MixChain":
        from lightrag_langchain.chain.chains import MixChain
        return MixChain
    if name == "BypassChain":
        from lightrag_langchain.chain.chains import BypassChain
        return BypassChain
```

**Also update the module docstring** (lines 1-17) to mention Phase 6 chain classes alongside existing retriever exports.

---

### 7. `tests/conftest.py` (modify -- add chain-specific fixtures)

**Analog:** `tests/conftest.py` (existing fixture patterns, lines 73-201)

**Mock LLM fixture** — pattern from Phase 3/5 AsyncMock conventions:
```python
@pytest.fixture
def mock_llm():
    """Return an AsyncMock wrapping ChatOpenAI for chain unit tests.

    ``ainvoke`` returns an AIMessage-like mock with ``.content`` attribute.
    ``astream`` is an async generator yielding AIMessageChunk-like mocks.
    Individual tests override return_value/side_effect as needed.
    """
    from unittest.mock import AsyncMock, MagicMock

    llm = AsyncMock()
    # Default ainvoke: returns mock AIMessage with empty content
    mock_response = MagicMock()
    mock_response.content = ""
    llm.ainvoke = AsyncMock(return_value=mock_response)
    # Default astream: empty async generator
    async def _empty_stream(*args, **kwargs):
        return
        yield  # pragma: no cover  -- makes it an async generator
    llm.astream = MagicMock(side_effect=_empty_stream)
    return llm
```

**Mock retriever fixture** — pattern from retriever AsyncMock conventions:
```python
@pytest.fixture
def mock_retriever():
    """Return an AsyncMock wrapping LightRAGBaseRetriever for chain unit tests.

    Uses ``spec=LightRAGBaseRetriever`` so ``isinstance(mock, LightRAGBaseRetriever)``
    returns True, satisfying Pydantic v2 field validation.

    ``ainvoke`` returns empty list by default; tests override return_value.
    """
    from unittest.mock import AsyncMock

    from lightrag_langchain.retriever.base import LightRAGBaseRetriever

    retriever = AsyncMock(spec=LightRAGBaseRetriever)
    retriever.ainvoke = AsyncMock(return_value=[])
    return retriever
```

**Test Document factory helpers** — pattern from test_retriever.py `_make_*` functions (lines 39-103):
```python
@pytest.fixture
def make_entity_doc():
    """Fixture returning a callable that creates a Document with entity page_content."""
    import json
    from langchain_core.documents import Document

    def _make(entity_name="e1", entity_type="", description="",
              source_id="src-1", file_path="test/file.txt"):
        obj = {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "description": description,
            "source_id": source_id,
            "file_path": file_path,
        }
        return Document(
            page_content=json.dumps(obj),
            metadata={
                "document_type": "entity",
                "entity_name": entity_name,
                "entity_type": entity_type,
                "source_id": source_id,
                "file_path": file_path,
                "retrieval_mode": "local",
            }
        )
    return _make


@pytest.fixture
def make_chunk_doc():
    """Fixture returning a callable that creates a Document with chunk page_content."""
    import json
    from langchain_core.documents import Document

    def _make(chunk_id="c1", content="chunk text", file_path="test/file.txt"):
        obj = {
            "reference_id": "",
            "content": content,
            "file_path": file_path,
            "chunk_id": chunk_id,
        }
        return Document(
            page_content=json.dumps(obj),
            metadata={
                "document_type": "chunk",
                "chunk_id": chunk_id,
                "file_path": file_path,
                "retrieval_mode": "naive",
            }
        )
    return _make
```

---

### 8. `tests/test_chain_base.py` (test -- LightRAGBaseChain core pipeline)

**Analog:** `tests/test_retriever.py` (class-per-test-group pattern, lines 124-211) + `tests/test_keywords.py` (mock LLM pattern, lines 33-79)

**Test class organization pattern:**
```python
"""Unit tests for LightRAGBaseChain core pipeline logic.

Covers invoke/ainvoke/astream, keyword resolution, Document conversion,
token budget integration, context assembly, and reference list generation.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from langchain_core.documents import Document

from lightrag_langchain.chain.base import LightRAGBaseChain
from lightrag_langchain.chain.chains import NaiveChain, BypassChain

class TestChainInvoke:
    """invoke() — sync bridge to ainvoke."""

    def test_invoke_returns_dict_structure(self, mock_llm, mock_retriever):
        """invoke() returns dict with answer, sources, keywords, mode."""
        ...

    @pytest.mark.asyncio
    async def test_ainvoke_pipeline_order(self, mock_llm, mock_retriever):
        """ainvoke() pipeline: keywords -> retrieve -> convert -> truncate
        -> context -> LLM -> structured dict."""
        ...
```

**Async mock pattern for LLM responses** (from test_keywords.py):
```python
# Mock LLM ainvoke to return an AIMessage
mock_response = MagicMock()
mock_response.content = "Mocked answer text"
mock_llm.ainvoke = AsyncMock(return_value=mock_response)
```

**Catch expected no results** (empty retriever results, bypass -- from retriever tests):
```python
def test_chain_empty_results(self, mock_llm, mock_retriever):
    """Empty retriever results: LLM receives empty context, responds based on that."""
    mock_retriever.ainvoke.return_value = []
    mock_response = MagicMock()
    mock_response.content = "I don't have enough information"
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    chain = NaiveChain(retriever=mock_retriever, llm=mock_llm)
    result = chain.invoke("test query")

    assert result["answer"] == "I don't have enough information"
    assert result["sources"] == []
    assert result["mode"] == "naive"
```

**Fixture usage pattern** (from test_retriever.py line 127):
```python
def test_something(self, mock_retriever, mock_llm, mock_query_params_config, make_entity_doc):
    ...
```

---

### 9. `tests/test_chain_dispatch.py` (test -- 6 Chain subclass dispatch)

**Analog:** `tests/test_retriever.py` (subclass-specific test classes pattern, lines 124-696)

**Pattern: One test class per chain subclass:**
```python
class TestNaiveChain:
    """Tests for NaiveChain — naive template selection + chunk-only context."""

    def test_mode_is_naive(self, ...):
        chain = NaiveChain(retriever=mock_retriever, llm=mock_llm)
        assert chain.mode == "naive"

class TestLocalChain:
    def test_mode_is_local(self, ...):
        chain = LocalChain(retriever=mock_retriever, llm=mock_llm)
        assert chain.mode == "local"

class TestGlobalChain:
    def test_mode_is_global(self, ...): ...

class TestHybridChain:
    def test_mode_is_hybrid(self, ...): ...

class TestMixChain:
    def test_mode_is_mix(self, ...): ...

class TestBypassChain:
    """Tests for BypassChain — no keywords, no retrieval, direct LLM."""

    def test_bypass_skips_retrieval(self, mock_llm, mock_retriever):
        chain = BypassChain(retriever=mock_retriever, llm=mock_llm)
        response = MagicMock()
        response.content = "Bypass answer"
        mock_llm.ainvoke = AsyncMock(return_value=response)

        result = chain.invoke("test query")
        assert result["mode"] == "bypass"
        assert result["sources"] == []
        mock_retriever.ainvoke.assert_not_called()

class TestTemplateSelection:
    """Cross-cutting tests verifying correct template selection per mode."""
    ...
```

---

### 10. `tests/test_chain_stream.py` (test -- astream behavior)

**Analog:** `tests/test_retriever.py` (AsyncMock patterns for async testing, lines 171-189) + RESEARCH.md streaming pattern

**Async generator mock pattern:**
```python
class TestChainAstream:
    """Tests for astream() — token-by-token yield then final dict."""

    @pytest.mark.asyncio
    async def test_astream_yields_tokens_then_dict(self, mock_llm, mock_retriever):
        """astream yields str tokens, then final dict with answer/sources/keywords/mode."""
        # Mock astream to yield 3 token chunks
        async def _mock_stream(messages):
            yield MagicMock(content="Hello")
            yield MagicMock(content=" ")
            yield MagicMock(content="World")

        mock_llm.astream = MagicMock(side_effect=_mock_stream)
        mock_retriever.ainvoke.return_value = []

        chain = BypassChain(retriever=mock_retriever, llm=mock_llm)
        chunks = []
        async for chunk in chain.astream("test query"):
            chunks.append(chunk)

        # First 3 chunks are str
        assert chunks[0] == "Hello"
        assert chunks[1] == " "
        assert chunks[2] == "World"
        # Last chunk is dict
        assert isinstance(chunks[3], dict)
        assert chunks[3]["answer"] == "Hello World"
        assert chunks[3]["mode"] == "bypass"
```

**D-10: sources determined before streaming test:**
```python
@pytest.mark.asyncio
async def test_sources_ready_before_streaming(self, mock_llm, mock_retriever, make_entity_doc):
    """Reference list and keywords are computed before LLM streaming begins."""
    doc = make_entity_doc(file_path="test/file.txt")
    mock_retriever.ainvoke.return_value = [doc]

    # Capture state before LLM is called
    async def _mock_stream(messages):
        yield MagicMock(content="token")
    mock_llm.astream = MagicMock(side_effect=_mock_stream)

    chain = NaiveChain(retriever=mock_retriever, llm=mock_llm)
    async for chunk in chain.astream("test query", hl_keywords=["kw"], ll_keywords=["kw"]):
        if isinstance(chunk, dict):
            # Sources and keywords computed before any LLM yield
            assert "sources" in chunk
            assert chunk["keywords"] == {"high_level": ["kw"], "low_level": ["kw"]}
```

---

### 11. `tests/test_chain_keywords.py` (test -- keyword resolution)

**Analog:** `tests/test_keywords.py` (exact match -- keyword extraction mock pattern, lines 10-79)

**Pre-provided keywords bypass LLM test pattern:**
```python
class TestKeywordResolution:
    """Tests for CHAIN-03 — pre-provided keywords skip LLM extraction."""

    def test_pre_provided_keywords_skip_llm(self, mock_llm, mock_retriever):
        """When hl_keywords and ll_keywords are both provided, extract_keywords
        is NOT called."""
        mock_response = MagicMock()
        mock_response.content = "Answer"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        chain = NaiveChain(retriever=mock_retriever, llm=mock_llm)
        result = chain.invoke(
            "test query",
            hl_keywords=["high"],
            ll_keywords=["low"],
        )

        assert result["keywords"] == {"high_level": ["high"], "low_level": ["low"]}
        # Verify LLM was NOT called for keyword extraction
        # (ainvoke should only be called once, for the final answer)
        assert mock_llm.ainvoke.call_count == 1

    def test_no_keywords_triggers_llm_extraction(self, mock_llm, mock_retriever):
        """Without pre-provided keywords, extract_keywords() is called (via LLM)."""
        mock_response = MagicMock()
        mock_response.content = "Answer"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        chain = NaiveChain(retriever=mock_retriever, llm=mock_llm)
        result = chain.invoke("test query")

        # LLM.ainvoke called for BOTH keyword extraction AND answer generation
        assert "keywords" in result
        assert "high_level" in result["keywords"]
```

---

## Shared Patterns

### Lazy `__getattr__` export
**Source:** `src/lightrag_langchain/retriever/__init__.py` lines 30-66, `src/lightrag_langchain/__init__.py` lines 22-98
**Apply to:** `chain/__init__.py`, top-level `__init__.py` modification
```python
def __getattr__(name: str):
    if name == "ClassName":
        from lightrag_langchain.chain.module import ClassName
        return ClassName
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Pydantic BaseModel with constructor injection
**Source:** `src/lightrag_langchain/retriever/base.py` lines 33-85
**Apply to:** `chain/base.py`
```python
class LightRAGBaseChain(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    retriever: LightRAGBaseRetriever
    llm: ChatOpenAI  # type: ignore[valid-type]
    _logger: logging.Logger = PrivateAttr(default_factory=lambda: logging.getLogger(__name__))
```

### Sync/async bridge with asyncio.run()
**Source:** `src/lightrag_langchain/retriever/base.py` lines 110-121
**Apply to:** `chain/base.py invoke()` method
```python
def invoke(self, query: str, ...) -> dict:
    return asyncio.run(self.ainvoke(query, ...))
```

### Module-level constant embedding (upstream prompt templates)
**Source:** `src/lightrag_langchain/keywords.py` lines 60-84
**Apply to:** `chain/prompt.py`
```python
RAG_RESPONSE_PROMPT = """---角色---
你是一位专业的 AI 助手...
{context_data}
"""
```

### Pure function helpers (no I/O, no async, no side effects)
**Source:** `src/lightrag_langchain/retriever/utils.py` lines 36-84, 103-155, 163-203
**Apply to:** `chain/utils.py`
```python
def doc_to_entity_dict(doc: Document) -> dict:
    obj = json.loads(doc.page_content)
    return {
        "entity_name": obj.get("entity_name", ""),
        ...
    }
```

### model_rebuild() for Pydantic v2 forward references
**Source:** `src/lightrag_langchain/retriever/base.py` lines 159-164, `src/lightrag_langchain/retriever/retrievers.py` lines 401-416
**Apply to:** `chain/base.py` bottom, `chain/chains.py` bottom
```python
from langchain_openai import ChatOpenAI  # noqa: E402
from lightrag_langchain.retriever.base import LightRAGBaseRetriever  # noqa: E402

LightRAGBaseChain.model_rebuild()

for _cls in (NaiveChain, LocalChain, GlobalChain, HybridChain, MixChain, BypassChain):
    _cls.model_rebuild()
```

### Test fixtures: AsyncMock with spec= for Pydantic validation
**Source:** `tests/conftest.py` lines 159-200
**Apply to:** `conftest.py` mock_llm, mock_retriever fixtures
```python
from unittest.mock import AsyncMock
from lightrag_langchain.retriever.base import LightRAGBaseRetriever

@pytest.fixture
def mock_retriever():
    retriever = AsyncMock(spec=LightRAGBaseRetriever)
    retriever.ainvoke = AsyncMock(return_value=[])
    return retriever
```

### Test class-per-feature-group organization
**Source:** `tests/test_retriever.py` lines 124, 218, 339, 457, 549, 655, 713
**Apply to:** All test files
```python
class TestNaiveChain:
    def test_feature_a(self, ...): ...
    def test_feature_b(self, ...): ...
    @pytest.mark.asyncio
    async def test_async_feature(self, ...): ...
```

### test_*.py factory functions (_make_* pattern)
**Source:** `tests/test_retriever.py` lines 39-103
**Apply to:** chain test files for Document creation
```python
def _make_entity(name: str = "e1", ...) -> EntityRecord:
    ...

def _make_chunk(chunk_id: str = "c1", ...) -> ChunkRecord:
    ...
```

### Token budget function signatures (Phase 3 integration)
**Source:** `src/lightrag_langchain/token_budget.py` lines 77-81, 119-123, 160-167
**Apply to:** `chain/base.py` token budget pipeline step
```python
truncate_entities_by_tokens(entities: list[dict], max_tokens: int) -> list[dict]
truncate_relations_by_tokens(relations: list[dict], max_tokens: int) -> list[dict]
compute_chunk_token_budget(total_tokens, sys_prompt_tokens, query_tokens,
                           entity_tokens_used, relation_tokens_used, buffer_tokens=200) -> int
_get_tokenizer(model_name="gpt-4o-mini")  # returns tiktoken.Encoding
```

### LLM message construction pattern
**Apply to:** `chain/base.py` LLM invocation step
```python
from langchain_core.messages import SystemMessage, HumanMessage

messages = [SystemMessage(content=sys_prompt), HumanMessage(content=query)]
response = await self.llm.ainvoke(messages)
```

### ChatOpenAI astream() streaming pattern
**Apply to:** `chain/base.py` astream() method
```python
async for chunk in self.llm.astream(messages):
    token = chunk.content
    if token:
        yield token  # str
yield final_dict  # dict (last chunk per D-09)
```

---

## No Analog Found

No files without close matches. All 11 files have direct analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `src/lightrag_langchain/`, `tests/`, upstream `LightRAG/lightrag/`
**Files scanned:** 9 existing source files + 1 test file + 1 upstream file
**Pattern extraction date:** 2026-05-31
**Key upstream source files referenced:**
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py` L:170-323 (4 prompt templates)
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py` L:3292-3355 (reference list generation)
