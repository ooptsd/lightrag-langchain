---
phase: 06-qa-chain
plan: 03
subsystem: qa-chain
tags: [tests, chain, pipeline, streaming, keywords, dispatch]
requires: [06-02]
provides: ["CHAIN-01 verification", "CHAIN-02 verification", "CHAIN-03 verification"]
affects: ["tests/test_chain_base.py", "tests/test_chain_keywords.py", "tests/test_chain_dispatch.py", "tests/test_chain_stream.py"]
tech-stack:
  added: []
  patterns: ["model_construct for Pydantic mock bypass", "asyncio.astream async generator mocking"]
key-files:
  created:
    - tests/test_chain_base.py
    - tests/test_chain_keywords.py
    - tests/test_chain_dispatch.py
    - tests/test_chain_stream.py
  modified: []
decisions:
  - Used model_construct to bypass Pydantic v2 field validation for mock ChatOpenAI
  - Added _patch_settings fixture to mock lazy settings singleton for token budget tests
  - Used side_effect-based async generator mocking for mock_llm.astream
  - Empty retriever results verified per Claude's Discretion (no short-circuit)
  - Reference list integer IDs verified per D-12
  - All 6 chain subclass modes verified via parametrized test
metrics:
  duration: 4m38s
  completed_date: "2026-05-31"
---

# Phase 6 Plan 3: QA Chain Test Suite Summary

**One-liner:** Complete test suite (28 tests) verifying CHAIN-01/02/03 requirements, D-07 through D-12 decisions, astream contract, and all 6 chain subclass dispatch — using mock fixtures, zero real LLM/database.

## Tasks Completed

| Task | Name | Files | Lines |
|------|------|-------|-------|
| 1 | Core pipeline integration tests | tests/test_chain_base.py | 372 |
| 2 | CHAIN-03 + subclass dispatch tests | tests/test_chain_keywords.py + tests/test_chain_dispatch.py | ~328 |
| 3 | astream contract tests | tests/test_chain_stream.py | 235 |

## Test Coverage

### test_chain_base.py (10 tests, 7 classes)
- **TestChainInvoke:** invoke() returns dict with answer/sources/keywords/mode; sync bridge returns dict not coroutine
- **TestChainAinvoke:** async pipeline calls retriever then LLM in order; keywords extracted via with_structured_output
- **TestEmptyResults:** empty retriever results still call LLM (Claude's Discretion — no short-circuit)
- **TestTemplateSelection:** naive mode uses NAIVE_RAG_RESPONSE_PROMPT with {content_data}; KG modes use RAG_RESPONSE_PROMPT with Knowledge Graph Data
- **TestSystemPromptOverride:** D-08: system_prompt='CUSTOM' replaces entire prompt verbatim, no template wrapping
- **TestReferenceList:** D-11 dedup by file_path (a.txt*2 + b.txt = 2 entries); D-12 integer reference_ids; unknown_source filtered
- **TestTokenBudget:** 30+ entities with max_entity_tokens=4000 truncates without crash

### test_chain_keywords.py (4 tests)
- Pre-provided hl+ll keywords skip LLM extraction (call_count == 1)
- No keywords triggers LLM extraction (with_structured_output called)
- Partial keywords (only hl) triggers LLM extraction (CHAIN-03: both must be provided)
- BypassChain never calls keyword extraction or retriever

### test_chain_dispatch.py (9 tests)
- Parametrized mode test covering all 6 subclasses (Naive/Local/Global/Hybrid/Mix/Bypass)
- BypassChain skips retrieval + keywords; sends empty-context RAG_RESPONSE_PROMPT
- Naive vs KG template cross-check: different system prompts produced

### test_chain_stream.py (5 tests)
- D-09: astream yields str tokens then final dict (3 tokens + 1 dict = 4 chunks)
- CHAIN-02: final dict has all 4 required keys (answer/sources/keywords/mode)
- D-10: sources/kewords determined before any LLM token yields
- Edge case: empty LLM output yields answer="" in final dict
- CHAIN-03 + streaming: pre-provided keywords carried through without extraction call

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pydantic v2 rejects AsyncMock as ChatOpenAI field value**
- **Found during:** Task 1
- **Issue:** `LightRAGBaseChain.llm` is typed as `ChatOpenAI` (Pydantic BaseModel). Pydantic v2 validates model-typed fields even with `arbitrary_types_allowed=True`, and ChatOpenAI's `@model_validator(mode="before")` (validate_temperature) calls `.get("model_name")` on the mock, which on an AsyncMock returns a coroutine.
- **Fix:** Used `model_construct()` (bypasses all Pydantic field validation) for all chain instantiation in tests. Added helper functions `_make_naive_chain`, `_make_local_chain`, `_make_bypass_chain`, and `_make_chain` that wrap the appropriate `ChainClass.model_construct()` calls.
- **Files modified:** tests/test_chain_base.py, tests/test_chain_keywords.py, tests/test_chain_dispatch.py, tests/test_chain_stream.py
- **Commits:** 4e2a389, b2148b8, 948c9fa

**2. [Rule 3 - Blocking] Settings singleton fails without .env in test environment**
- **Found during:** Task 1
- **Issue:** `LightRAGBaseChain._apply_token_budget()` does `from lightrag_langchain.config import settings`, which triggers the lazy `__getattr__` → `Settings()` from .env. In tests without a valid `.env`, this raises `SettingsError`.
- **Fix:** Added `_patch_settings` fixture in each test file that pre-sets `lightrag_langchain.config._settings` to a MagicMock with `mock_query_params_config` before any chain method is called, and restores the original afterward.
- **Files modified:** tests/test_chain_base.py, tests/test_chain_keywords.py, tests/test_chain_dispatch.py, tests/test_chain_stream.py
- **Commits:** 4e2a389, b2148b8, 948c9fa

## Pre-existing Issues

- `tests/test_pool.py::TestPoolInit::test_init_creates_pool_with_config` fails because the test expects `PG_USER=test` but the real `.env` has `PG_USER=dev_user`. This is unrelated to our changes (211 other tests pass).

## Verification

```bash
# Chain test suite (28 tests)
$ python -m pytest tests/test_chain_base.py tests/test_chain_keywords.py tests/test_chain_dispatch.py tests/test_chain_stream.py -x -v
============================== 28 passed in 0.34s ==============================

# Full regression excluding pre-existing pool failure
$ python -m pytest tests/ -x --ignore=tests/test_pool.py
============================= 211 passed in 1.52s ==============================
```

## Self-Check: PASSED

- [x] tests/test_chain_base.py exists (372 lines, 10 tests)
- [x] tests/test_chain_keywords.py exists (~165 lines, 4 tests)
- [x] tests/test_chain_dispatch.py exists (~163 lines, 9 tests)
- [x] tests/test_chain_stream.py exists (235 lines, 5 tests)
- [x] All 28 tests pass: `pytest tests/test_chain_*.py -x -v` exits 0
- [x] No existing tests broken: 211 pass excluding pre-existing pool failure
- [x] All 3 commits recorded: 4e2a389, b2148b8, 948c9fa
