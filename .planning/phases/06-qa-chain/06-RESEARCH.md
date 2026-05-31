# Phase 6: QA Chain - Research

**Researched:** 2026-05-31
**Domain:** LangChain LCEL Chain composition, LLM prompt engineering, streaming response generation
**Confidence:** HIGH

## Summary

Phase 6 delivers the end-to-end QA Chain that composes Phase 5 Retrievers, Phase 3 keyword extraction, and Phase 3 token budget control into a unified LangChain-compatible interface. The chain mirrors upstream LightRAG's `_build_query_context()` 4-stage pipeline (Search -> Truncate -> Merge -> Build LLM Context -> LLM Generate) but reuses existing Phase 5/3 components rather than LightRAG's monolithic internals.

The architecture is six standalone Pydantic `BaseModel` classes (one per query mode) sharing a `LightRAGBaseChain` base class that encapsulates keyword extraction, Document-to-dict conversion, token budget truncation, upstream prompt template formatting, reference list generation, and both sync/async/streaming invocation paths. Each subclass only provides its retriever instance and selects which prompt templates to use (KG templates for local/global/hybrid/mix, naive templates for naive, no context for bypass).

This is the final integration phase -- it composes all previously built components without introducing new external dependencies, new database access, or new LLM patterns.

**Primary recommendation:** Build `LightRAGBaseChain(BaseModel)` as a Pydantic class (not a LangChain `Runnable` subclass) that implements the `invoke`/`ainvoke`/`astream` interface contract through composition of Phase 5 Retriever + Phase 3 keyword extraction + Phase 3 token budget. The six mode-specific subclasses only differ in which retriever they hold and which prompt template pair they use.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Keyword extraction | API / Backend | -- | Phase 3 `extract_keywords()` async function -- pure LLM call |
| Document retrieval | API / Backend | Database / Storage | Phase 5 Retriever delegates to PGVector/PGGraphStore |
| Document-to-dict conversion | API / Backend | -- | Pure transform -- no I/O, stateless functions in base.py |
| Token budget truncation | API / Backend | -- | Phase 3 token_budget functions -- pure computation |
| Context assembly (prompt template) | API / Backend | -- | String formatting -- upstream template placeholders filled from converted dicts |
| LLM answer generation | API / Backend | -- | ChatOpenAI.ainvoke/astream -- external LLM service |
| Reference list generation | API / Backend | -- | Pure computation -- dedup by file_path, sequential numbering |
| Streaming token yield | API / Backend | -- | ChatOpenAI.astream -> AsyncIterator[AIMessageChunk] |
| Sync invocation bridge | API / Backend | -- | `asyncio.run()` bridge -- matches Phase 5 retriever pattern |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | >=2.0 | BaseModel for Chain classes, ConfigDict(arbitrary_types_allowed=True) | Matches Phase 5 LightRAGBaseRetriever pattern; constructor injection validation [VERIFIED: existing codebase] |
| langchain-core | >=1.0 | Document class, Runnable interface contract reference | Already in project dependencies; Document is the retriever output format [CITED: src/lightrag_langchain/retriever/base.py L21] |
| langchain-openai | >=1.0 | ChatOpenAI for LLM calls (.ainvoke, .astream) | Already in project; Phase 3 llm.py uses it [CITED: src/lightrag_langchain/llm.py L51] |
| tiktoken | (existing) | BPE token counting for budget calculation | Already used by Phase 3 token_budget.py [CITED: src/lightrag_langchain/token_budget.py L46] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Sync-to-async bridge (`asyncio.run()`) | `invoke()` wraps `ainvoke()` -- matches Phase 5 `_get_relevant_documents` [CITED: src/lightrag_langchain/retriever/base.py L119] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic BaseModel | LangChain Runnable | Runnable adds LCEL composition but forces config schema; BaseModel gives simpler constructor injection matching existing patterns (D-02) |

**Installation:** No new packages. Phase 6 composes existing Phase 3 and Phase 5 components.

## Package Legitimacy Audit

No new external packages are introduced in Phase 6. All dependencies (pydantic, langchain-core, langchain-openai, tiktoken) are already installed and verified by prior phases.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
User Query (str)
    │
    ├── hl_keywords/ll_keywords provided? ──No──► extract_keywords(query, llm, language)
    │                                                    │
    │                                                    ▼
    │                                           KeywordsSchema(hl, ll)
    │                                                    │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
              retriever.ainvoke(query) ───► list[Document]
                         │
                         ▼
              Document-to-dict conversion
              (parse page_content JSON, extract metadata)
                         │
                         ├── entities: list[dict]
                         ├── relations: list[dict]
                         ├── chunks: list[dict]
                         │
                         ▼
              Token Budget Truncation
              ├── truncate_entities_by_tokens(entities, max_entity_tokens)
              ├── truncate_relations_by_tokens(relations, max_relation_tokens)
              ├── Build preliminary kg_context (entities+relations, empty chunks)
              ├── Calculate sys_prompt_tokens from formatted template
              ├── compute_chunk_token_budget(...) -> chunk_token_limit
              └── Truncate chunks by chunk_token_limit
                         │
                         ▼
              Reference List Generation
              ├── Collect file_path from all truncated objects
              ├── Dedup, sort by frequency, assign [1], [2], [3]...
              └── Add reference_id to each chunk dict
                         │
                         ▼
              Context Assembly (Template Formatting)
              ├── kg_query_context.format(entities_str, relations_str, text_chunks_str, reference_list_str)
              │   OR naive_query_context.format(text_chunks_str, reference_list_str)
              │   OR bypass: context = ""
                         │
                         ▼
              System Prompt Construction
              ├── rag_response.format(context_data=assembled_context, response_type=..., user_prompt=...)
              │   OR naive_rag_response.format(content_data=assembled_context, response_type=..., user_prompt=...)
              │   OR system_prompt param (full override)
                         │
                         ▼
              LLM Call
              ├── Non-streaming: llm.ainvoke([SystemMessage(sys_prompt), HumanMessage(query)])
              │       └──► dict{answer, sources, keywords, mode}
              └── Streaming: llm.astream([...]) 
                      └──► AsyncIterator[str | dict]
                           (yield tokens, final yield = complete dict)
```

### Recommended Project Structure
```
src/lightrag_langchain/
├── chain/
│   ├── __init__.py        # Lazy __getattr__ exports for 7 classes (base + 6 chains)
│   ├── base.py            # LightRAGBaseChain(BaseModel) + shared logic
│   └── chains.py          # 6 mode-specific subclasses (NaiveChain, etc.)
├── __init__.py            # ADD: 6 Chain class lazy exports to __getattr__
```

### Pattern 1: Pydantic BaseModel with Constructor Injection (D-02, D-04, D-06)

**What:** Chain classes extend `BaseModel` with `ConfigDict(arbitrary_types_allowed=True)`. All dependencies (retriever, llm) are declared as typed Pydantic fields, injected at construction time. Matches Phase 5 `LightRAGBaseRetriever` exactly.

**When to use:** All 7 chain classes (base + 6 subclasses).

**Example:**
```python
# Source: Phase 5 pattern [CITED: src/lightrag_langchain/retriever/base.py L33-74]
from pydantic import BaseModel, ConfigDict, PrivateAttr
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
    from lightrag_langchain.retriever.base import LightRAGBaseRetriever

class LightRAGBaseChain(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    retriever: LightRAGBaseRetriever
    """Retriever instance for document fetching (D-04 constructor injection)."""

    llm: ChatOpenAI  # type: ignore[valid-type]
    """ChatOpenAI instance for keyword extraction and answer generation (D-06)."""

    keyword_language: str = "Chinese"
    """Language for keyword extraction, from settings.query_params.keyword_language."""

    top_k: int | None = None
    chunk_top_k: int | None = None

    _logger: logging.Logger = PrivateAttr(default_factory=lambda: logging.getLogger(__name__))
```

### Pattern 2: Sync/Async Bridge with asyncio.run()

**What:** `invoke()` is a synchronous method that calls `asyncio.run(self.ainvoke(...))`. Matches Phase 5 `_get_relevant_documents` bridge pattern.

**When to use:** In `LightRAGBaseChain.invoke()`.

**Example:**
```python
# Source: Phase 5 pattern [CITED: src/lightrag_langchain/retriever/base.py L110-121]
def invoke(self, query: str, *, system_prompt: str | None = None,
           hl_keywords: list[str] | None = None, ll_keywords: list[str] | None = None,
           **kwargs) -> dict:
    return asyncio.run(self.ainvoke(
        query, system_prompt=system_prompt,
        hl_keywords=hl_keywords, ll_keywords=ll_keywords, **kwargs
    ))
```

### Pattern 3: Lazy __getattr__ Export (D-05)

**What:** `chain/__init__.py` uses `def __getattr__(name)` to defer imports of all chain classes. Top-level `__init__.py` adds 6 new if-blocks for chain class exports. No import triggers construction or database connection.

**When to use:** All public exports.

**Example:**
```python
# Source: pattern from retriever/__init__.py [CITED: src/lightrag_langchain/retriever/__init__.py L30-67]
def __getattr__(name: str):
    if name == "LightRAGBaseChain":
        from lightrag_langchain.chain.base import LightRAGBaseChain
        return LightRAGBaseChain
    if name == "NaiveChain":
        from lightrag_langchain.chain.chains import NaiveChain
        return NaiveChain
    # ... 5 more ...
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Pattern 4: Module-Level Prompt Template Constants (D-07)

**What:** Upstream LightRAG prompt templates embedded verbatim as module-level string constants. Placeholders like `{context_data}`, `{response_type}`, `{user_prompt}` are preserved for `.format()` at call time. Matches Phase 3 `KEYWORDS_EXTRACTION_PROMPT` pattern.

**When to use:** All prompt template constants in `chain/base.py`.

**Example:**
```python
# Source: Phase 3 pattern [CITED: src/lightrag_langchain/keywords.py L60-84]
# Source strings: upstream LightRAG [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py L170-222, L278-306]
RAG_RESPONSE_PROMPT = """---角色---
你是一位专业的 AI 助手...
---上下文---

{context_data}
"""

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
```

### Anti-Patterns to Avoid

- **Do NOT inherit from LangChain Runnable:** The chains are Pydantic BaseModel classes (D-02), not Runnable subclasses. They implement the invoke/ainvoke/astream interface contract through custom methods, not by subclassing Runnable. This avoids forcing the config/RunnableConfig schema that Runnable requires.

- **Do NOT create LLM/Retriever inside the Chain:** Constructor injection only (D-04, D-06). Chain never touches Settings, .env, or database connections directly.

- **Do NOT decode page_content outside Document-to-dict conversion:** Always use the shared conversion functions. Never inline `json.loads(doc.page_content)` in chain logic.

- **Do NOT skip token budget for bypass/naive with no entities:** Naive mode still uses `compute_chunk_token_budget()` with zero entity/relation tokens. Bypass has no context at all (no token budget needed).

- **Do NOT mutate truncated lists in place:** Token budget functions return new lists. The original lists from Document conversion are kept for reference list generation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing of Document page_content | Inline `json.loads()` | Shared conversion functions in `base.py` | 4 Document types with different JSON shapes; centralized parsing ensures consistency and testability |
| Token counting | Custom tokenizer or char counting | Phase 3 `tiktoken` via `_get_tokenizer("gpt-4o-mini")` | Must match upstream LightRAG's BPE tokenizer for budget accuracy [CITED: src/lightrag_langchain/token_budget.py L29-48] |
| Reference list dedup | Custom dedup logic | Dedicated function in base.py following upstream `generate_reference_list_from_chunks()` algorithm [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py L3292-3355] | Upstream uses frequency-sorted dedup with sequential numbering; must match for LLM citation accuracy |
| LLM message construction | Manual dict/list assembly | `langchain_core.messages.SystemMessage` + `HumanMessage` for `.ainvoke()`; raw string for `.astream()` | ChatOpenAI accepts both; SystemMessage/HumanMessage provides clean separation |
| Streaming token aggregation | Manual buffer/concat | `async for chunk in llm.astream(messages): yield chunk.content` | ChatOpenAI.astream yields `AIMessageChunk` with `.content` per token [VERIFIED: Python inspect of ChatOpenAI.astream signature] |

**Key insight:** The custom solution for this phase is the pipeline orchestration itself -- composing existing components in the correct order. Everything else (tokenization, LLM calls, retrieval, keyword extraction) already exists in Phase 3 and Phase 5.

## Upstream LightRAG Chain Flow (Detailed)

### Full Pipeline (KG modes: local/global/hybrid/mix)

Based on upstream `kg_query()` [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py L2962-3169]:

```
1. get_keywords_from_query(query, query_param, global_config, hashing_kv)
   └── Returns (hl_keywords: list[str], ll_keywords: list[str])
   └── Uses pre-provided keywords from query_param if available, else LLM extraction

2. _build_query_context(query, ll_keywords_str, hl_keywords_str, ...)
   ├── Stage 1: _perform_kg_search() → search_result dict
   ├── Stage 2: _apply_token_truncation() → truncation_result dict  
   ├── Stage 3: _merge_all_chunks() → merged_chunks list
   └── Stage 4: _build_context_str() → (context_str, raw_data dict)
       ├── Serialize entities/relations to JSON strings
       ├── Calculate preliminary kg_context tokens (entities+relations, no chunks)
       ├── Calculate preliminary system prompt tokens (with empty context_data)
       ├── available_chunk_tokens = max_total - sys_prompt - kg_context - query - buffer(200)
       ├── process_chunks_unified(..., chunk_token_limit=available_chunk_tokens)
       ├── generate_reference_list_from_chunks(truncated_chunks)
       ├── Rebuild chunks_context with reference_ids
       ├── Format kg_query_context template with {entities_str, relations_str, text_chunks_str, reference_list_str}
       └── Return (context_str, raw_data)

3. sys_prompt = rag_response.format(context_data=context_str, response_type=..., user_prompt=...)

4. response = await use_model_func(query, system_prompt=sys_prompt, stream=param.stream)
```

### Naive Mode Pipeline

Based on upstream `naive_query()` [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py L4751-4994]:

```
1. _get_vector_context(query, chunks_vdb, query_param) → chunks list
2. Calculate sys_prompt overhead tokens (with empty content_data)
3. available_chunk_tokens = max_total - sys_prompt - query - buffer(200)
4. process_chunks_unified(..., chunk_token_limit=available_chunk_tokens)
5. generate_reference_list_from_chunks(processed_chunks)
6. Format naive_query_context with {text_chunks_str, reference_list_str}
7. Format naive_rag_response with {content_data=context, response_type, user_prompt}
8. Call LLM
```

### Bypass Mode Pipeline

Based on upstream `aquery_llm()` [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/lightrag.py L2941-2978]:

```
1. Skip ALL retrieval and keyword extraction
2. use_llm_func(query, system_prompt=system_prompt or PROMPTS["rag_response"], stream=param.stream)
3. Return response directly (str for non-streaming, AsyncIterator for streaming)
```

### Key Differences for Phase 6 Implementation

The Phase 6 chain differs from upstream in these ways:

| Aspect | Upstream LightRAG | Phase 6 Chain |
|--------|-------------------|---------------|
| Keyword extraction | `get_keywords_from_query()` -- monolith with caching, pre-provided keywords from query_param | `extract_keywords()` (Phase 3) -- pure LLM call; pre-provided keywords passed as method args (D-03) |
| Retrieval | Internal functions accessing storage directly | `retriever.ainvoke(query)` → `list[Document]` (Phase 5) |
| Token budget execution order | Entity truncation in Stage 2, chunk truncation in Stage 4 with dynamic limit | Same order: entities → relations → compute chunk budget → truncate chunks (matches Claude's Discretion) |
| Context assembly | `_build_context_str()` -- single monolithic function | Decomposed into sequential steps in base chain method |
| LLM call | `use_model_func()` -- internal function reference | `self.llm.ainvoke(messages)` / `self.llm.astream(messages)` |
| Streaming return | QueryResult with response_iterator | AsyncIterator yielding str tokens then final dict (D-09) |
| No results | Returns None, caller handles | Empty context passed to LLM, LLM decides response (Claude's Discretion) |

## Prompt Template Details

### rag_response (KG modes system prompt)

**Source:** [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py L170-222]

Placeholders:
- `{context_data}` -- The assembled kg_context string (entities + relations + chunks + reference list)
- `{response_type}` -- Format instruction, default "Multiple Paragraphs" 
- `{user_prompt}` -- Additional instructions appended to template, default "n/a"

Note: upstream appends `\n\n{user_prompt}` before insertion; Phase 6 receives `user_prompt` as part of template formatting.

### naive_rag_response (naive mode system prompt)

**Source:** [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py L224-276]

Placeholders:
- `{content_data}` -- Different key name! (not `context_data`). The assembled naive_query_context string (chunks + reference list)
- `{response_type}` -- Same as above
- `{user_prompt}` -- Same as above

### kg_query_context (KG modes context template)

**Source:** [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py L278-306]

Placeholders:
- `{entities_str}` -- JSON-per-line serialized entity dicts
- `{relations_str}` -- JSON-per-line serialized relation dicts
- `{text_chunks_str}` -- JSON-per-line serialized chunk dicts (each with `reference_id` and `content`)
- `{reference_list_str}` -- Newline-separated `[reference_id] file_path` entries

Format: Entities and relations wrapped in ` ```json ` blocks, chunks in ` ```json ` block, reference list in bare ``` block.

### naive_query_context (naive mode context template)

**Source:** [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py L308-323]

Placeholders:
- `{text_chunks_str}` -- JSON-per-line serialized chunk dicts
- `{reference_list_str}` -- Same as above

## Document to Dict Conversion (Reverse of Phase 5 utils.py)

The chain must reverse the Document JSON format created by Phase 5 retriever utils. The `document_type` in metadata determines the parse target:

### Entity Document → Entity Dict

**Input Document** [CITED: src/lightrag_langchain/retriever/utils.py L66-84]:
```json
{"entity_name": "...", "entity_type": "...", "description": "...", "source_id": "...", "file_path": "..."}
```
**Metadata:** `source_id`, `file_path`, `retrieval_mode`, `document_type: "entity"`, `entity_name`, `entity_type`

**Output Dict** (for token budget and context assembly):
```python
{
    "entity_name": str,
    "entity_type": str,
    "description": str,
    "source_id": str,
    "file_path": str,
}
```

### Relation Document → Relation Dict

**Input Document** [CITED: src/lightrag_langchain/retriever/utils.py L133-151]:
```json
{"src_id": "...", "tgt_id": "...", "description": "...", "keywords": "...", "weight": 1.0, "source_id": "...", "file_path": "..."}
```
**Metadata:** `source_id`, `file_path`, `retrieval_mode`, `document_type: "relation"`, `src_id`, `tgt_id`, `keywords`, `weight`

**Output Dict:**
```python
{
    "src_id": str,
    "tgt_id": str,
    "description": str,
    "keywords": str,
    "weight": float,
    "source_id": str,
    "file_path": str,
}
```

### Chunk Document → Chunk Dict

**Input Document** [CITED: src/lightrag_langchain/retriever/utils.py L185-198]:
```json
{"reference_id": "", "content": "...", "file_path": "...", "chunk_id": "..."}
```
**Metadata:** `source_id: ""`, `file_path`, `retrieval_mode`, `document_type: "chunk"`, `chunk_id`, `chunk_order_index`

**Output Dict:**
```python
{
    "content": str,
    "file_path": str,
    "chunk_id": str,
    "reference_id": "",  # filled later by reference list generation
}
```

### GraphTriple Documents → Skipped for Context Assembly

GraphTriple Documents [CITED: src/lightrag_langchain/retriever/utils.py L235-264] are NOT converted to dicts for context assembly. They represent graph edges (src_entity --[relation]--> tgt_entity) and their structured data is already captured through entity/relation Documents. Their `file_path` in metadata is always `""`, so they contribute nothing to reference lists.

However, their `source_id` in metadata (from `triple.src_entity.source_id or triple.relation.source_id`) should be collected for reference list file_path lookup if non-empty.

### Document Classification

The conversion function uses `doc.metadata["document_type"]` to dispatch:
- `"entity"` → `_doc_to_entity_dict(doc)`
- `"relation"` → `_doc_to_relation_dict(doc)`  
- `"chunk"` → `_doc_to_chunk_dict(doc)`
- `"graph_triple"` → `_doc_to_triple_dict(doc)` (metadata only, for file_path extraction)

## Token Budget Integration

**Source:** [CITED: src/lightrag_langchain/token_budget.py]

### Execution Order (Claude's Discretion)

```
1. Convert Documents to dicts → entities[], relations[], chunks[]
2. Truncate entities:  truncate_entities_by_tokens(entities, settings.query_params.max_entity_tokens)
3. Truncate relations: truncate_relations_by_tokens(relations, settings.query_params.max_relation_tokens)
4. Build preliminary kg_context (entities + relations only, empty chunks) to measure tokens
5. Build preliminary system prompt (with empty context_data) to measure tokens
6. chunk_budget = compute_chunk_token_budget(
       total_tokens=settings.query_params.max_total_tokens,
       sys_prompt_tokens=len(preliminary_sys_prompt),
       query_tokens=len(query),
       entity_tokens_used=len(serialized_entities),
       relation_tokens_used=len(serialized_relations),
       buffer_tokens=200
   )
7. Truncate chunks by chunk_budget (prefix truncation by token count)
8. Build final context with truncated lists
```

### Token Counting for Context Assembly

The chain needs to count tokens for the context assembly step (steps 4-6). Use tiktoken directly:
```python
from lightrag_langchain.token_budget import _get_tokenizer
enc = _get_tokenizer("gpt-4o-mini")
sys_prompt_tokens = len(enc.encode(preliminary_sys_prompt))
entity_tokens_used = len(enc.encode("\n".join(json.dumps(e) for e in entities)))
```

### Modes Without Entities/Relations

- **Naive mode:** entities=[] and relations=[], so `entity_tokens_used=0` and `relation_tokens_used=0`. Only `compute_chunk_token_budget()` with zero KG tokens.
- **Bypass mode:** No token budget at all -- no context goes to the LLM.

## Reference List Generation (D-11, D-12)

**Algorithm** (simplified from upstream [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py L3292-3355]):

```
1. Collect all file_path values from:
   - entity dicts: dict["file_path"]
   - relation dicts: dict["file_path"]
   - chunk dicts: dict["file_path"]
   - graph_triple metadata: doc.metadata.get("source_id") → may map to file_path via cross-reference
   
2. Filter: skip empty "", None, "unknown_source"

3. Dedup by file_path (string equality)

4. Sort by occurrence frequency (descending), then by first appearance order

5. Assign sequential integer IDs: 1, 2, 3, ... (D-12: integer, not string "1")

6. Add reference_id to each chunk dict that has a matching file_path

7. Build reference_list: [{"reference_id": 1, "file_path": "..."}, ...]

8. Format reference_list_str for prompt:
   "\n".join(f"[{ref['reference_id']}] {ref['file_path']}" for ref in reference_list if ref["reference_id"])
```

**Key design decisions:**
- reference_id is type `int` in the output dict, matching D-12 ("自增数字")
- In the prompt template string, it's formatted as `[1]`, `[2]`, etc.
- Chunks without valid file_path get empty reference_id
- Reference list appears in the prompt's "引用文献列表" section

## Streaming Implementation (D-09, D-10)

### ChatOpenAI.astream() Behavior

**Verified:** `ChatOpenAI.astream()` signature is `(self, input, config, stop, **kwargs) -> AsyncIterator[AIMessageChunk]` [VERIFIED: Python inspect of langchain_openai ChatOpenAI]. Each chunk's `.content` is a string (typically one or a few tokens).

### Chain astream() Contract (D-09)

```python
async def astream(
    self, query: str, *,
    system_prompt: str | None = None,
    hl_keywords: list[str] | None = None,
    ll_keywords: list[str] | None = None,
    **kwargs
) -> AsyncIterator[str | dict]:
```

Yields:
- First N chunks: `str` -- raw token text from LLM
- Last chunk: `dict` -- complete structured result `{"answer": str, "sources": list[dict], "keywords": dict, "mode": str}`

### Implementation Pattern

```python
async def astream(self, query: str, *, system_prompt=None, hl_keywords=None, ll_keywords=None, **kwargs):
    # Step 1: Extract keywords (or use pre-provided, D-03)
    keywords = await self._resolve_keywords(query, hl_keywords, ll_keywords)
    
    # Step 2: Retrieve documents via Phase 5 Retriever
    docs = await self.retriever.ainvoke(query)
    
    # Step 3: Convert Documents to dicts, apply token budget
    entities, relations, chunks = self._docs_to_dicts(docs)
    entities = truncate_entities_by_tokens(...)
    relations = truncate_relations_by_tokens(...)
    # ... compute chunk budget, truncate chunks ...
    
    # Step 4: Generate reference list (D-10: BEFORE LLM call)
    reference_list = self._build_reference_list(entities, relations, chunks)
    chunks = self._assign_reference_ids(chunks, reference_list)
    
    # Step 5: Assemble context, build system prompt
    context_str = self._build_context_str(entities, relations, chunks, reference_list)
    sys_prompt = self._build_system_prompt(context_str, system_prompt)
    
    # Step 6: Pre-compute the final dict (D-10: all data ready before streaming)
    final_dict = {
        "answer": "",  # filled after streaming
        "sources": reference_list,
        "keywords": {"high_level": keywords.high_level_keywords, "low_level": keywords.low_level_keywords},
        "mode": self.mode,
    }
    
    # Step 7: Stream tokens, accumulate full answer
    messages = [SystemMessage(content=sys_prompt), HumanMessage(content=query)]
    full_answer = []
    async for chunk in self.llm.astream(messages):
        token = chunk.content
        if token:
            full_answer.append(token)
            yield token  # D-09: yield str for each token
    
    # Step 8: Yield final structured dict
    final_dict["answer"] = "".join(full_answer)
    yield final_dict  # D-09: yield dict as last chunk
```

### astream_events Alternative

LangChain also provides `astream_events()` which yields structured events (e.g., `on_chat_model_stream` with the token in `event["data"]["chunk"].content`). However, D-09 specifies `astream`, which is the simpler `AsyncIterator[str | dict]` contract. The `astream()` approach is sufficient and avoids event filtering complexity.

## Existing Patterns to Follow

### Pattern A: Two-File Package Structure

**Reference:** `retriever/` package [CITED: src/lightrag_langchain/retriever/]

```
retriever/
├── __init__.py    # Lazy __getattr__ exports
├── base.py        # LightRAGBaseRetriever (BaseRetriever) + shared infrastructure
├── retrievers.py  # 6 mode-specific subclasses
└── utils.py       # Pure conversion functions

→ Chain package:
chain/
├── __init__.py    # Lazy __getattr__ exports
├── base.py        # LightRAGBaseChain (BaseModel) + shared pipeline logic
└── chains.py      # 6 mode-specific subclasses
```

### Pattern B: model_rebuild() for Forward References

**Reference:** [CITED: src/lightrag_langchain/retriever/base.py L159-164, retriever/retrievers.py L405-416]

At module bottom, import TYPE_CHECKING types and call `model_rebuild()`:
```python
from lightrag_langchain.retriever.base import LightRAGBaseRetriever  # noqa: E402
for _cls in (NaiveChain, LocalChain, GlobalChain, HybridChain, MixChain, BypassChain):
    _cls.model_rebuild()
```

### Pattern C: Test Structure

**Reference:** [CITED: tests/test_retriever.py]

- Class per chain/test group: `class TestNaiveChain`
- Fixture injection: `mock_vector_store`, `mock_embedding_config`, `mock_llm_config`
- Mock LLM pattern: `AsyncMock` for `llm.ainvoke()`, `AsyncMock` for `llm.astream()` (yielding mock chunks)
- Mock retriever: `AsyncMock(spec=LightRAGBaseRetriever)` with `ainvoke` returning test Documents
- `@pytest.mark.asyncio` on async test methods
- Test data helpers: `_make_entity()`, `_make_chunk()`, `_make_relation()` functions

### Pattern D: Top-Level __init__.py Extension

**Reference:** [CITED: src/lightrag_langchain/__init__.py L22-98]

Add 6 new if-blocks to the existing `__getattr__` function:
```python
# -- Chains (chain/chains.py) --------------------------------------------
if name == "NaiveChain":
    from lightrag_langchain.chain.chains import NaiveChain
    return NaiveChain
# ... 5 more ...
```

## Concrete Chain Pipeline Pseudocode

### Full ainvoke Pipeline (the shared base implementation)

```python
async def ainvoke(self, query: str, *, system_prompt=None, hl_keywords=None, ll_keywords=None, **kwargs) -> dict:
    # 1. Resolve keywords (CHAIN-03: skip if pre-provided)
    if hl_keywords is not None and ll_keywords is not None:
        keywords = KeywordsSchema(high_level_keywords=hl_keywords, low_level_keywords=ll_keywords)
    else:
        keywords = await extract_keywords(query, self.llm, self.keyword_language)
    
    # 2. Retrieve documents (Phase 5)
    docs = await self.retriever.ainvoke(query)
    
    # 3. Convert Documents to typed dicts
    entities, relations, chunks, _triples = self._docs_to_dicts(docs)
    
    # 4. Apply token budget
    entities, relations, chunks = await self._apply_token_budget(entities, relations, chunks, query)
    
    # 5. Generate reference list
    reference_list, chunks = self._build_reference_list(entities, relations, chunks)
    
    # 6. Assemble context string
    context_str = self._build_context_str(entities, relations, chunks, reference_list)
    
    # 7. Build system prompt
    sys_prompt = self._build_system_prompt(context_str, system_prompt)
    
    # 8. Call LLM
    messages = [SystemMessage(content=sys_prompt), HumanMessage(content=query)]
    response = await self.llm.ainvoke(messages)
    answer = response.content
    
    # 9. Return structured dict (D-03 output format)
    return {
        "answer": answer,
        "sources": reference_list,
        "keywords": {"high_level": keywords.high_level_keywords, "low_level": keywords.low_level_keywords},
        "mode": self.mode,
    }
```

### Mode-Specific Subclass Responsibilities

Each of the 6 subclasses only needs to provide:
1. A `mode` class attribute (str): `"naive"`, `"local"`, `"global"`, `"hybrid"`, `"mix"`, `"bypass"`
2. Optionally override `_build_context_str()` template selection:
   - KG modes (local/global/hybrid/mix): use `KG_QUERY_CONTEXT_TEMPLATE` + `RAG_RESPONSE_PROMPT`
   - Naive mode: use `NAIVE_QUERY_CONTEXT_TEMPLATE` + `NAIVE_RAG_RESPONSE_PROMPT`
   - Bypass mode: skip context assembly entirely, use `RAG_RESPONSE_PROMPT` with empty `{context_data}`

### BypassChain Special Case

BypassChain overrides `ainvoke`:
1. Skip keyword extraction (no keywords for bypass)
2. Skip retriever call (no documents)
3. Skip token budget (no context)
4. Build system prompt with `RAG_RESPONSE_PROMPT.format(context_data="", ...)`
5. Call LLM directly
6. Return `{"answer": ..., "sources": [], "keywords": {"high_level": [], "low_level": []}, "mode": "bypass"}`

## Common Pitfalls

### Pitfall 1: {context_data} vs {content_data} Placeholder Mismatch

**What goes wrong:** Using `rag_response` template's `{context_data}` for naive mode, which needs `naive_rag_response` template's `{content_data}`. Or vice versa.

**Why it happens:** The two templates look very similar (nearly identical text) but have different placeholder names.

**How to avoid:** Encode template selection in subclass, not in base class. Each subclass maps to ONE template pair. Test each subclass independently.

**Warning signs:** KeyError on `.format()` -- wrong placeholder name for the template.

### Pitfall 2: Token Budget Applied to Untruncated Lists

**What goes wrong:** Applying `compute_chunk_token_budget()` before `truncate_entities_by_tokens()` completes, causing inaccurate remaining budget.

**Why it happens:** The preliminary kg_context calculation step (step 4 in the budget flow) requires the ALREAD-TRUNCATED entities/relations to compute accurate token counts.

**How to avoid:** Strict ordering: truncate entities -> truncate relations -> compute KG context tokens -> compute chunk budget -> truncate chunks. Never reorder.

**Warning signs:** Total token usage exceeds `max_total_tokens`, causing LLM context overflow errors.

### Pitfall 3: ChatOpenAI Does NOT Accept Raw String for astream

**What goes wrong:** Passing a raw prompt string to `llm.astream()` instead of a message list.

**Why it happens:** Some LangChain LLMs accept raw strings, but ChatOpenAI expects `Sequence[BaseMessage]`.

**How to avoid:** Always construct `[SystemMessage(content=sys_prompt), HumanMessage(content=query)]` for LLM calls. Test with a real or mock ChatOpenAI.

**Warning signs:** TypeError from langchain_openai about unexpected input type.

### Pitfall 4: Missing reference_id on Chunks in Prompt

**What goes wrong:** Chunks are included in the prompt without `reference_id` fields, so the LLM cannot cite sources.

**Why it happens:** Reference list generation happens AFTER the chunk dicts are built for the prompt. The function `_assign_reference_ids()` must be called before `_build_context_str()`.

**How to avoid:** Make reference list generation a distinct, mandatory step in the pipeline. The final chunk dicts passed to the context template MUST have `reference_id` populated.

**Warning signs:** LLM response says "[citation needed]" or generates hallucinated reference numbers not in the reference list.

### Pitfall 5: GraphTriple Documents with Empty file_path

**What goes wrong:** GraphTriple Documents always have `file_path: ""` in metadata [CITED: src/lightrag_langchain/retriever/utils.py L242]. Including them in file_path collection adds empty strings.

**Why it happens:** GraphTriples represent relationships between entities already captured in entity/relation Documents. Their file_path is always empty because they come from graph traversal, not from the chunks_vdb table.

**How to avoid:** When collecting file_paths for reference list, filter out empty strings. GraphTriples can be skipped entirely for context assembly -- their data is already covered by entity and relation Documents.

**Warning signs:** Reference list contains empty entries or "unknown_source" entries.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Upstream LightRAG monolithic `kg_query()` | Decomposed Phase 3 + Phase 5 + Phase 6 composition | Phase 6 (new) | Testable in isolation; each component independently verifiable |
| Upstream `use_model_func()` callback | Direct `self.llm.ainvoke()` / `self.llm.astream()` | Phase 6 (new) | Standard LangChain interface; no callback indirection |
| Upstream `json_repair` for keyword extraction | `llm.with_structured_output(KeywordsSchema, method="function_calling")` | Phase 3 | Type-safe extraction without fragile repair [CITED: src/lightrag_langchain/keywords.py L167-170] |

**Deprecated/outdated:**
- Upstream `json_repair` fallback for LLM parsing: Phase 3 replaced it with structured output. Phase 6 does not reintroduce it.
- Upstream `hashing_kv` caching: Phase 6 v1 does not implement caching (CHAIN-04 deferred to v2).

## Code Examples

### Document-to-Dict Conversion (base.py utility functions)

```python
# Source: reverse of retriever/utils.py [CITED: src/lightrag_langchain/retriever/utils.py]
import json

def _doc_to_entity_dict(doc: Document) -> dict:
    """Parse entity Document's JSON page_content into dict for token budget."""
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

def docs_to_dicts(docs: list[Document]) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify and convert all Documents to typed dicts."""
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
        # graph_triple: skip -- data already in entity/relation dicts
    return entities, relations, chunks
```

### Reference List Generation (base.py)

```python
# Adapted from upstream [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py L3292-3355]
def _build_reference_list(
    entities: list[dict], relations: list[dict], chunks: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Generate deduplicated reference list and assign reference_ids to chunks.

    Returns (reference_list, chunks_with_ids).
    """
    # Collect file_paths from all sources
    file_path_counts: dict[str, int] = {}
    
    for item in entities + relations + chunks:
        fp = item.get("file_path", "")
        if fp and fp != "unknown_source":
            file_path_counts[fp] = file_path_counts.get(fp, 0) + 1
    
    # Sort by frequency (descending), then first appearance order
    seen: set[str] = set()
    ordered: list[tuple[str, int, int]] = []
    for i, item in enumerate(entities + relations + chunks):
        fp = item.get("file_path", "")
        if fp and fp != "unknown_source" and fp not in seen:
            ordered.append((fp, file_path_counts[fp], i))
            seen.add(fp)
    
    sorted_paths = sorted(ordered, key=lambda x: (-x[1], x[2]))
    
    # Build reference_id mapping (1-indexed integers)
    fp_to_id: dict[str, int] = {}
    reference_list: list[dict] = []
    for i, (fp, _, _) in enumerate(sorted_paths):
        ref_id = i + 1
        fp_to_id[fp] = ref_id
        reference_list.append({"reference_id": ref_id, "file_path": fp})
    
    # Assign reference_ids to chunks
    chunks_with_ids = []
    for chunk in chunks:
        c = chunk.copy()
        fp = c.get("file_path", "")
        c["reference_id"] = fp_to_id.get(fp, "")
        chunks_with_ids.append(c)
    
    return reference_list, chunks_with_ids
```

### Context Assembly (base.py)

```python
def _build_kg_context_str(
    entities: list[dict], relations: list[dict],
    chunks: list[dict], reference_list: list[dict]
) -> str:
    """Build the KG context string matching upstream format."""
    entities_str = "\n".join(json.dumps(e, ensure_ascii=False) for e in entities)
    relations_str = "\n".join(json.dumps(r, ensure_ascii=False) for r in relations)
    
    text_units = [{"reference_id": c["reference_id"], "content": c["content"]} for c in chunks]
    text_units_str = "\n".join(json.dumps(tu, ensure_ascii=False) for tu in text_units)
    
    reference_list_str = "\n".join(
        f"[{ref['reference_id']}] {ref['file_path']}"
        for ref in reference_list if ref["reference_id"]
    )
    
    return KG_QUERY_CONTEXT_TEMPLATE.format(
        entities_str=entities_str,
        relations_str=relations_str,
        text_chunks_str=text_units_str,
        reference_list_str=reference_list_str,
    )
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ChatOpenAI.astream() yields AIMessageChunk with `.content` containing partial token strings (typically 1-3 tokens per chunk) | Streaming Implementation | If chunk size differs significantly (e.g., full sentences), the user experience of "token-by-token" streaming would be chunkier than expected. The contract still holds but granularity changes. |
| A2 | `model_rebuild()` is sufficient for Pydantic v2 forward references with TYPE_CHECKING imports | Architecture Patterns | If Pydantic v2 changes model_rebuild behavior, constructor validation may fail. Already proven working in Phase 5, so risk is minimal. |
| A3 | The upstream `rag_response` template's `{user_prompt}` placeholder receives the string "n/a" when no user_prompt is set (matching upstream behavior) | Prompt Template Details | If upstream behavior differs, the LLM prompt format may diverge. Low risk -- this is a documented upstream convention. |
| A4 | `asyncio.run()` in `invoke()` works correctly when there is no existing event loop | Pattern 2 | If called from within an existing event loop (e.g., Jupyter notebook), `asyncio.run()` will raise RuntimeError. This is a known LangChain limitation, also present in Phase 5 retriever. |
| A5 | GraphTriple Documents are correctly skippable for context assembly because their entity/relation data is already represented through entity and relation Documents | Document Conversion | If a GraphTriple contains unique information not present in entity/relation Documents, skipping them would lose data. Verified by code inspection of Phase 4 QueryResult structure and Phase 5 retriever output. |

## Open Questions

1. **Token budget for naive mode with no keyword extraction?**
   - What we know: Naive mode has no entities/relations, so `entity_tokens_used=0` and `relation_tokens_used=0`. The chunk budget calculation reduces to `max_total_tokens - sys_prompt_tokens - query_tokens - buffer(200)`.
   - What's unclear: Whether the chain should also compute `kg_context_tokens` for the naive context template (which includes the template structure itself, not just the chunk data).
   - Recommendation: Follow upstream naive_query behavior [CITED: operate.py L4830-4836] -- calculate using the naive_query_context template with empty chunks to get template overhead, subtract from available budget.

2. **Should the chain expose top_k/chunk_top_k as Pydantic fields?**
   - What we know: Claude's Discretion lists `top_k` and `chunk_top_k` as Pydantic fields. But the retriever already has its own top_k from construction time. Having both could create confusion.
   - What's unclear: Whether these fields on the chain override the retriever's values, or are passed as kwargs, or are purely informational.
   - Recommendation: Keep them as Pydantic fields with default `None` (matching retriever pattern). If `None`, use retriever's existing top_k. If set, pass as kwargs to retriever.ainvoke().

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.12+ | -- |
| pydantic | Chain BaseModel | Yes | >=2.0 (installed) | -- |
| langchain-core | Document class | Yes | >=1.0 (installed) | -- |
| langchain-openai | ChatOpenAI for LLM calls | Yes | >=1.0 (installed) | -- |
| tiktoken | Token budget counting | Yes | (installed) | -- |

**Missing dependencies with no fallback:** None -- all dependencies already satisfied by Phase 3 and Phase 5.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | tests/conftest.py (existing) |
| Quick run command | `pytest tests/test_chain.py -x -v` |
| Full suite command | `pytest tests/ -x -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHAIN-01 | Full pipeline: query -> keywords -> retrieval -> context -> LLM -> answer with citations | integration | `pytest tests/test_chain.py::TestFullPipeline -x` | No (Wave 0) |
| CHAIN-01 | Empty retriever results -> LLM receives empty context and responds | unit | `pytest tests/test_chain.py::TestEmptyResults -x` | No (Wave 0) |
| CHAIN-02 | `invoke(query) -> dict` returns answer + sources + keywords + mode | unit | `pytest tests/test_chain.py::TestInvoke -x` | No (Wave 0) |
| CHAIN-02 | `ainvoke(query) -> dict` async non-blocking | unit | `pytest tests/test_chain.py::TestAinvoke -x` | No (Wave 0) |
| CHAIN-02 | `astream(query)` yields token strings then final dict | unit | `pytest tests/test_chain.py::TestAstream -x` | No (Wave 0) |
| CHAIN-03 | Pre-provided hl_keywords/ll_keywords bypass LLM keyword extraction | unit | `pytest tests/test_chain.py::TestPreProvidedKeywords -x` | No (Wave 0) |
| CHAIN-03 | Without pre-provided keywords, LLM extraction is called | unit | `pytest tests/test_chain.py::TestLLMKeywordExtraction -x` | No (Wave 0) |
| D-07 | KG modes use rag_response + kg_query_context templates | unit | `pytest tests/test_chain.py::TestKGTemplates -x` | No (Wave 0) |
| D-07 | Naive mode uses naive_rag_response + naive_query_context templates | unit | `pytest tests/test_chain.py::TestNaiveTemplates -x` | No (Wave 0) |
| D-08 | system_prompt parameter replaces entire system prompt | unit | `pytest tests/test_chain.py::TestCustomSystemPrompt -x` | No (Wave 0) |
| D-11 | Reference list deduplicates by file_path across entities/relations/chunks | unit | `pytest tests/test_chain.py::TestReferenceList -x` | No (Wave 0) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_chain.py -x -v` (quick validation of chain logic)
- **Per wave merge:** `pytest tests/ -x -v` (full regression suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_chain.py` -- covers all CHAIN-01, CHAIN-02, CHAIN-03 behaviors
- [ ] `tests/conftest.py` -- ADD: `mock_llm` fixture (AsyncMock wrapping ChatOpenAI), `mock_retriever` fixture (AsyncMock spec=LightRAGBaseRetriever), test Document factory helpers
- [ ] `src/lightrag_langchain/chain/` -- entire package does not exist yet

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Chain has no user/auth context -- all inputs are programmatic |
| V3 Session Management | no | Chain is stateless per invocation |
| V4 Access Control | no | No multi-tenant or user-level access control in chain layer |
| V5 Input Validation | yes | Query string validation (non-empty), keyword type validation, Document metadata integrity (trusted internal data) |
| V6 Cryptography | no | No cryptographic operations in chain layer |

### Known Threat Patterns for LangChain + LLM Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via query string | Tampering | Query passes through keyword extraction and is embedded in a structured prompt; the system prompt's "only use context" instruction limits injection impact. No custom mitigation needed beyond upstream template design. |
| LLM output parsing failure | Denial of Service | Chain does not parse LLM output -- answer is raw string. No structured output extraction to fail. |
| Token budget exhaustion (overly long context) | Denial of Service | Token budget is strictly enforced before LLM call. Hard limits from `QueryParamsConfig.max_total_tokens` prevent unbounded context. |

## Sources

### Primary (HIGH confidence)
- Upstream LightRAG `prompt.py` -- all 4 prompt templates verified verbatim: `rag_response` (L170-222), `naive_rag_response` (L224-276), `kg_query_context` (L278-306), `naive_query_context` (L308-323) [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py]
- Upstream LightRAG `operate.py` -- Full chain pipeline: `kg_query()` (L2962-3169), `_build_query_context()` (L4037-4154), `_build_context_str()` (L3854-4033), `naive_query()` (L4751-4994) [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py]
- Upstream LightRAG `utils.py` -- `generate_reference_list_from_chunks()` (L3292-3355) [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py]
- Upstream LightRAG `lightrag.py` -- `aquery_llm()` bypass handling (L2892-2978) [CITED: /Users/lizhouyang/llm/graphrag/LightRAG/lightrag/lightrag.py]
- Phase 5 `retriever/base.py` -- BaseModel pattern, ConfigDict, PrivateAttr, asyncio.run bridge [CITED: src/lightrag_langchain/retriever/base.py]
- Phase 5 `retriever/utils.py` -- Document JSON format for all 4 types [CITED: src/lightrag_langchain/retriever/utils.py]
- Phase 3 `token_budget.py` -- Function signatures, types, truncation logic [CITED: src/lightrag_langchain/token_budget.py]
- Phase 3 `keywords.py` -- extract_keywords signature, KeywordsSchema, template embedding pattern [CITED: src/lightrag_langchain/keywords.py]
- LangChain Runnable interface -- verified via `inspect.signature()` (invoke, ainvoke, astream signatures) [VERIFIED: Python runtime]
- ChatOpenAI.astream() signature -- verified via `inspect.signature()` returning `AsyncIterator[AIMessageChunk]` [VERIFIED: Python runtime]

### Secondary (MEDIUM confidence)
- Phase 5 CONTEXT.md -- Retriever design decisions (D-01 through D-06), integration points [CITED: .planning/phases/05-retriever-interfaces/05-CONTEXT.md]
- Phase 3 CONTEXT.md -- LLM/Keyword/Token budget design decisions [CITED: .planning/phases/03-llm-integration/03-CONTEXT.md]
- PROJECT.md -- Key decisions, constraints [CITED: .planning/PROJECT.md]

### Tertiary (LOW confidence)
- None -- all findings verified against upstream source code or existing project codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project; no new packages needed
- Architecture: HIGH -- patterns directly replicate proven Phase 5 retriever design; upstream chain flow verified line-by-line
- Pitfalls: HIGH -- identified from specific placeholder names, function signatures, and Document format details verified in source code

**Research date:** 2026-05-31
**Valid until:** 2026-07-31 (stable domain; LangChain and Pydantic APIs change slowly)
