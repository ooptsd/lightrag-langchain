---
phase: 03-llm-integration
plan: 01
subsystem: infra
tags: [pydantic-settings, pytest, langchain-openai, httpx, tenacity, tiktoken]

# Dependency graph
requires: []
provides:
  - Phase 3 dependency declarations (langchain-openai, httpx, tenacity, tiktoken with version bounds)
  - KEYWORD_LANGUAGE configuration via QueryParamsConfig.keyword_language (default "Chinese")
  - Shared pytest fixtures for Phase 3 test modules (LLM, embedding, reranker, query params, httpx)
affects: [03-02, 03-03, 03-04, 03-05]

# Tech tracking
tech-stack:
  added: [langchain-openai, httpx, tenacity, tiktoken]
  patterns:
    - Direct model construction in test fixtures (no Settings singleton dependency)
    - Inline imports inside fixture bodies (matching existing conftest.py pattern)
    - Pydantic-settings nested env var binding via env_nested_delimiter="__"

key-files:
  created: []
  modified:
    - pyproject.toml
    - .env.example
    - src/lightrag_langchain/config.py
    - tests/conftest.py

key-decisions:
  - "QUERY_PARAMS__KEYWORD_LANGUAGE uses nested delimiter form for pydantic-settings auto-binding (not bare KEYWORD_LANGUAGE)"
  - "Phase 3 test fixtures construct config models directly (not via Settings) so tests work without .env file"
  - "Fixture imports follow existing conftest.py pattern: inline imports inside fixture bodies"

patterns-established:
  - "Fixture factory pattern: config fixtures return frozen model instances constructed directly with test values"
  - "Token budget invariant check: mock_query_params_config uses 4000+5000=9000<20000 as canonical test values"

requirements-completed: [D-13]

# Metrics
duration: 2min
completed: 2026-05-30
---

# Phase 03 Plan 01: Phase 3 Infrastructure Summary

**Dependency declarations, KEYWORD_LANGUAGE config, and shared pytest fixtures for the LLM integration phase**

## Performance

- **Duration:** 2min
- **Started:** 2026-05-30T04:37:40Z
- **Completed:** 2026-05-30T04:39:35Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Declared 4 new direct dependencies (langchain-openai, httpx, tenacity, tiktoken) in pyproject.toml with version bounds
- Added QUERY_PARAMS__KEYWORD_LANGUAGE env var documentation and QueryParamsConfig.keyword_language field (default "Chinese")
- Created 5 shared pytest fixtures (mock_llm_config, mock_embedding_config, mock_reranker_config, mock_query_params_config, mock_httpx_client) for Phase 3 test modules

## Task Commits

Each task was committed atomically:

1. **Task 1: Declare Phase 3 direct dependencies in pyproject.toml** - `55a408d` (chore)
2. **Task 2: Add KEYWORD_LANGUAGE env var and config field** - `9fc1a4a` (feat)
3. **Task 3: Extend conftest.py with Phase 3 test fixtures** - `929a37a` (feat)

## Files Modified
- `pyproject.toml` - Added httpx, langchain-openai, tenacity, tiktoken to [project] dependencies list
- `.env.example` - Documented QUERY_PARAMS__KEYWORD_LANGUAGE=Chinese after Query Parameters block
- `src/lightrag_langchain/config.py` - Added keyword_language: str = "Chinese" to QueryParamsConfig
- `tests/conftest.py` - Added 5 Phase 3 fixtures: mock_llm_config, mock_embedding_config, mock_reranker_config, mock_query_params_config, mock_httpx_client

## Decisions Made
- Used `QUERY_PARAMS__KEYWORD_LANGUAGE` (nested delimiter form) instead of bare `KEYWORD_LANGUAGE` for correct pydantic-settings auto-binding with `env_nested_delimiter="__"`
- Test fixtures construct Pydantic model instances directly via constructors rather than via the Settings singleton, eliminating .env dependency for unit tests

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The KEYWORD_LANGUAGE env var defaults to "Chinese" and only needs explicit configuration for non-Chinese keyword extraction.

## Next Phase Readiness
- Phase 3 infrastructure foundation is in place: dependencies declared, config extended, test fixtures ready
- Plans 03-02 (LLM), 03-03 (Embedding), 03-04 (Reranker), and 03-05 (Keywords + Token Budget) can now proceed with their implementations
- Full test suite (115 tests) passes after all changes

---
*Phase: 03-llm-integration*
*Completed: 2026-05-30*
