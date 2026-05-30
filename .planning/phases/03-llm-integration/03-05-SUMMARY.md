---
phase: 03-llm-integration
plan: 05
subsystem: llm
tags: [pydantic, structured-output, keyword-extraction, langchain, lazy-imports]

# Dependency graph
requires:
  - phase: 03-01
    provides: create_llm, create_embedding (_LazyLLM proxy with ChatOpenAI)
  - phase: 03-02
    provides: create_reranker, LightRAGReranker
provides:
  - KeywordsSchema frozen Pydantic model for type-safe keyword extraction
  - extract_keywords() async function using with_structured_output(method="function_calling")
  - KEYWORDS_EXTRACTION_PROMPT and KEYWORDS_EXTRACTION_EXAMPLES embedded verbatim from upstream LightRAG
  - Top-level __init__.py with lazy __getattr__ exports for all 9 Phase 3 identifiers
affects: [04-retrieval, 06-caching]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pydantic ConfigDict(frozen=True) for immutable structured output models"
    - "Lazy __getattr__ module-level exports deferring LangChain/tiktoken/httpx imports"
    - "with_structured_output(method='function_calling') for non-OpenAI provider compatibility"
    - "Embedded upstream prompt templates with source attribution comments"

key-files:
  created:
    - src/lightrag_langchain/keywords.py
    - tests/test_keywords.py
  modified:
    - src/lightrag_langchain/__init__.py

key-decisions:
  - "Upstream LightRAG prompt templates (keywords_extraction + 3 examples) embedded verbatim with source attribution comments"
  - "method='function_calling' explicit on with_structured_output for DeepSeek/vLLM compatibility per RESEARCH.md Pitfall 1"
  - "Lazy __getattr__ pattern in __init__.py matches data/__init__.py — import lightrag_langchain succeeds without .env or network"
  - "Data-layer exports (EntityRecord, PGVectorStore, etc.) NOT re-exported at top level — accessible via data subpackage only"

patterns-established:
  - "KeywordsSchema: frozen Pydantic model pattern for structured LLM output — matches data/models.py convention"
  - "extract_keywords(): async function with duck-typed llm param — no hard ChatOpenAI import at runtime"
  - "Embedded upstream tags: Chinese emergency-management prompts stored with source line references"

requirements-completed:
  - LLM-04

# Metrics
duration: 3m5s
completed: 2026-05-30
---

# Phase 03 Plan 05: Keyword Extraction with Structured Output and Module Exports

**Type-safe keyword extraction using LangChain's with_structured_output, reusing upstream LightRAG prompt templates verbatim, with lazy __getattr__ top-level exports for all Phase 3 modules**

## Performance

- **Duration:** 3m 5s
- **Started:** 2026-05-30T05:04:16Z
- **Completed:** 2026-05-30T05:07:21Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- KeywordsSchema frozen Pydantic model with high_level_keywords and low_level_keywords list fields
- extract_keywords() formats upstream LightRAG prompt template, calls llm.with_structured_output(KeywordsSchema, method="function_calling")
- KEYWORDS_EXTRACTION_PROMPT and 3 Chinese emergency-management examples embedded verbatim from upstream prompt.py L:325-376
- Top-level __init__.py with lazy __getattr__ exporting all 9 Phase 3 identifiers (create_llm, create_embedding, create_reranker, LightRAGReranker, KeywordsSchema, extract_keywords, truncate_entities_by_tokens, truncate_relations_by_tokens, compute_chunk_token_budget)
- Import succeeds without .env file, network, or LangChain instantiation
- 6 unit tests covering frozen behavior, type validation, prompt formatting, structured output mocking, and default language

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for KeywordsSchema and extract_keywords** - `1ab1d34` (test)
2. **Task 2: Implement KeywordsSchema and extract_keywords()** - `d171047` (feat)
3. **Task 3: Update __init__.py with lazy exports** - `179e5e8` (feat)

_Note: Tasks 1-2 follow TDD RED-GREEN cycle; Task 3 is non-TDD._

## Files Created/Modified
- `src/lightrag_langchain/keywords.py` - KeywordsSchema frozen model, embedded upstream prompts, extract_keywords() async function (175 lines)
- `tests/test_keywords.py` - 6 unit tests covering LLM-04 requirements (172 lines)
- `src/lightrag_langchain/__init__.py` - Lazy __getattr__ exports for all 9 Phase 3 identifiers (68 lines, overwritten from empty)

## Decisions Made
- Upstream LightRAG prompt templates embedded verbatim with source attribution comments (L:325-349, L:351-376, copied 2026-05-30) — ensures exact behavioral match with upstream while avoiding fragile cross-repo imports
- `method="function_calling"` explicit on `with_structured_output` — per RESEARCH.md Pitfall 1, ensures compatibility with non-OpenAI providers (DeepSeek, vLLM) that do not support json_schema mode
- Lazy `__getattr__` pattern in `__init__.py` matches `data/__init__.py` pattern — consistent with existing project conventions
- Data-layer exports intentionally excluded from top-level namespace — keeps namespace focused on Phase 3+ factory/utility functions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All three tasks completed on first attempt. 154 test suite passes (all Phase 1, 2, and 3 tests).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- KeywordsSchema and extract_keywords() ready for Phase 4 retrieval pipeline integration
- Lazy __init__.py ensures clean import experience for downstream consumers
- No caching layer (per D-12) — deferred to Phase 6

---
*Phase: 03-llm-integration*
*Completed: 2026-05-30*
