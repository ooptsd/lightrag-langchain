---
phase: 06-qa-chain
plan: 01
subsystem: chain-foundation
tags: [prompt-templates, document-conversion, test-fixtures]
dependency_graph:
  requires: [06-CONTEXT, 06-RESEARCH, 06-PATTERNS]
  provides: [chain/prompt.py, chain/utils.py, conftest-fixtures]
  affects: [06-02, 06-03]
tech-stack:
  added: []
  patterns:
    - Module-level template constant embedding (matches keywords.py)
    - Pure function Document-to-dict conversion (reverse of retriever/utils.py)
    - AsyncMock(spec=) for Pydantic v2 field validation fixtures
    - Callable factory fixtures (conftest.py pattern)
key-files:
  created:
    - src/lightrag_langchain/chain/__init__.py
    - src/lightrag_langchain/chain/prompt.py
    - src/lightrag_langchain/chain/utils.py
  modified:
    - tests/conftest.py
decisions:
  - Upstream LightRAG prompt templates embedded verbatim as module-level string constants with .format()-compatible placeholders preserved
  - chain/prompt.py separated from chain/base.py — keeps constant-only file importable without triggering Plan 06-02 dependency chain
  - chain/__init__.py created as minimal placeholder (full lazy __getattr__ exports deferred to Plan 06-02)
  - reference_id field in chunk dict starts as empty string — Plan 06-02 reference list generation fills it in
metrics:
  duration: 96s
  completed_date: "2026-05-31"
  tasks: 3
  files: 4
---

# Phase 6 Plan 1: Chain Foundation Summary

**One-liner:** Established chain package foundation: 4 upstream LightRAG prompt templates as module-level constants, 4 Document-to-dict conversion utilities (reverse of retriever/utils.py), and 4 pytest fixtures for downstream chain tests.

## Tasks

| # | Name | Type | Commit | Files |
|---|------|------|--------|-------|
| 1 | Create chain/prompt.py | feat | `4ac6c60` | `chain/__init__.py`, `chain/prompt.py` |
| 2 | Create chain/utils.py | feat | `5586e0b` | `chain/utils.py` |
| 3 | Extend tests/conftest.py | test | `17efa69` | `tests/conftest.py` |

## What Was Built

### 1. Prompt Template Constants (`chain/prompt.py`)

Four upstream LightRAG prompt templates copied verbatim from `LightRAG/lightrag/prompt.py` L:170-323 and embedded as module-level string constants:

- **RAG_RESPONSE_PROMPT** — KG mode system prompt with `{context_data}`, `{response_type}`, `{user_prompt}` placeholders
- **NAIVE_RAG_RESPONSE_PROMPT** — Naive mode system prompt with `{content_data}` (NOT `{context_data}` — RESEARCH.md Pitfall 1)
- **KG_QUERY_CONTEXT_TEMPLATE** — KG context assembly with `{entities_str}`, `{relations_str}`, `{text_chunks_str}`, `{reference_list_str}`
- **NAIVE_QUERY_CONTEXT_TEMPLATE** — Naive context assembly with `{text_chunks_str}`, `{reference_list_str}`

Pattern: matches `keywords.py` `KEYWORDS_EXTRACTION_PROMPT` — `"""\` opening to avoid leading newline, source attribution comment referencing upstream file and line range.

### 2. Document-to-Dict Conversion Utilities (`chain/utils.py`)

Four pure functions (no I/O, no async, no side effects) that reverse the `retriever/utils.py` direction — convert LangChain `Document` instances back into structured dicts:

- **doc_to_entity_dict(doc)** → dict with `entity_name`, `entity_type`, `description`, `source_id`, `file_path`
- **doc_to_relation_dict(doc)** → dict with `src_id`, `tgt_id`, `description`, `keywords`, `weight`, `source_id`, `file_path`
- **doc_to_chunk_dict(doc)** → dict with `content`, `file_path`, `chunk_id`, `reference_id`
- **classify_and_convert(docs)** → `(entities, relations, chunks)` tuple, dispatching by `metadata["document_type"]`, skipping `graph_triple` Documents

All use `.get(key, default)` for safe JSON key access. `json.JSONDecodeError` propagates to caller (chain layer does no error recovery).

### 3. Chain Test Fixtures (`tests/conftest.py`)

Four new pytest fixtures appended after existing Phase 5 fixtures:

- **mock_llm** — `AsyncMock` with `ainvoke` returning mock AIMessage (`.content = ""`) and `astream` as empty async generator
- **mock_retriever** — `AsyncMock(spec=LightRAGBaseRetriever)` with `ainvoke` returning `[]`; `spec=` ensures Pydantic v2 `isinstance` validation passes
- **make_entity_doc** — Callable factory producing entity Documents matching `retriever/utils.py entity_to_document` JSON format
- **make_chunk_doc** — Callable factory producing chunk Documents matching `retriever/utils.py chunk_to_document` JSON format

All 183 existing tests continue to pass (194 total collected; pre-existing pool test failure excluded).

## Verification

### Task-Level

- **Task 1:** All 4 constants importable, all placeholders preserved, all `.format()` calls succeed
- **Task 2:** All 4 functions correctly parse JSON page_content, classify_and_convert dispatches by document_type, missing keys fall back to safe defaults, graph_triple skipped
- **Task 3:** Fixture patterns validated (AsyncMock spec= pattern, async generator astream), full test suite regression check passed (183/183)

### Phase-Level

```
from lightrag_langchain.chain.prompt import RAG_RESPONSE_PROMPT, NAIVE_RAG_RESPONSE_PROMPT, KG_QUERY_CONTEXT_TEMPLATE, NAIVE_QUERY_CONTEXT_TEMPLATE
from lightrag_langchain.chain.utils import doc_to_entity_dict, doc_to_relation_dict, doc_to_chunk_dict, classify_and_convert
# All imports succeed without .env or network: OK
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Created chain/__init__.py for package importability**
- **Found during:** Task 1
- **Issue:** `chain/` directory created without `__init__.py` — `from lightrag_langchain.chain.prompt import ...` would fail at Python's package resolution
- **Fix:** Created minimal `chain/__init__.py` with package docstring. Full lazy `__getattr__` exports deferred to Plan 06-02 as planned.
- **Files modified:** `src/lightrag_langchain/chain/__init__.py`
- **Commit:** `4ac6c60`

### Pre-existing Issues (Out of Scope)

- `tests/test_pool.py::TestPoolInit::test_init_creates_pool_with_config` fails with env-dependent assertion (`dev_user` vs `test`) — pre-existing, not caused by Plan 06-01 changes.

## Known Stubs

- `chain/__init__.py`: Minimal placeholder (only docstring). Full lazy `__getattr__` exports for 7 chain classes will be added in Plan 06-02. This is intentional — Plan 06-01 only provides foundation artifacts.
- `doc_to_chunk_dict` output: `reference_id` starts as `""`. Plan 06-02's `_build_reference_list()` fills it in. Intentional — documented in function docstring.

## Self-Check: PASSED

- `src/lightrag_langchain/chain/prompt.py` exists: FOUND
- `src/lightrag_langchain/chain/utils.py` exists: FOUND
- `tests/conftest.py` modified with 4 new fixtures: FOUND
- Commit `4ac6c60` exists: FOUND
- Commit `5586e0b` exists: FOUND
- Commit `17efa69` exists: FOUND
