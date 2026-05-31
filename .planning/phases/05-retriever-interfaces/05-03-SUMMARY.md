---
phase: 05-retriever-interfaces
plan: 03
subsystem: testing
tags: [pytest, pydantic, langchain, retriever, mock, AsyncMock, forward-references, model_rebuild]

# Dependency graph
requires:
  - phase: 05-retriever-interfaces
    plan: 02
    provides: "6 retriever classes (NaiveRetriever, LocalRetriever, GlobalRetriever, HybridRetriever, MixRetriever, BypassRetriever), base class, Document conversion utils"
provides:
  - "Comprehensive unit test suite (26 tests) for all 6 retrievers with mock stores"
  - "mock_vector_store and mock_graph_store pytest fixtures in conftest.py"
  - "Top-level lazy __getattr__ exports for all 6 retriever classes (D-09)"
  - "Pydantic v2 model_rebuild() forward reference resolution"
affects: [06-chains, verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AsyncMock(spec=StoreClass) for Pydantic isinstance validation in tests"
    - "model_rebuild() at module bottom to resolve TYPE_CHECKING forward references with from __future__ import annotations"
    - "Setting _embedding PrivateAttr directly to bypass lazy create_embedding() in tests"

key-files:
  created:
    - tests/test_retriever.py
  modified:
    - tests/conftest.py
    - src/lightrag_langchain/__init__.py
    - src/lightrag_langchain/retriever/base.py
    - src/lightrag_langchain/retriever/retrievers.py

key-decisions:
  - "Used AsyncMock(spec=PGVectorStore/PGGraphStore) to pass Pydantic v2 isinstance validation after model_rebuild()"
  - "Added model_rebuild() at bottom of base.py and retrievers.py to resolve forward references from from __future__ import annotations + TYPE_CHECKING"
  - "Test embedding injection via _embedding PrivateAttr (bypasses lazy create_embedding() factory)"

patterns-established:
  - "Mock store fixtures with spec=StoreClass pattern for Pydantic v2 type validation"
  - "model_rebuild() at module bottom for TYPE_CHECKING forward references"

requirements-completed: [RETR-02, RETR-03]

# Metrics
duration: 12min
completed: 2026-05-31
---

# Phase 05 Plan 03: Retriever Testing and Lazy Exports Summary

**26-test suite verifying all 6 retrievers with mock stores, plus top-level lazy __getattr__ exports with Pydantic v2 forward reference resolution**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-31T11:32:30Z
- **Completed:** 2026-05-31T11:44:06Z
- **Tasks:** 3
- **Files modified:** 5 (1 new, 4 modified)

## Accomplishments
- Comprehensive unit test suite (896 lines, 26 tests) covering all 6 retriever classes: sync invoke(), async ainvoke(), D-04 JSON field compliance, D-05 metadata structure, edge cases (empty results, orphan entities, missing graph matches)
- mock_vector_store and mock_graph_store fixtures in conftest.py using AsyncMock(spec=StoreClass) pattern that satisfies Pydantic v2 isinstance validation
- Top-level lazy __getattr__ exports for all 6 retriever classes (NaiveRetriever through BypassRetriever) while maintaining `import lightrag_langchain` safety without .env or network
- Resolved Pydantic v2 forward reference issue by adding model_rebuild() calls in base.py and retrievers.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Add mock store fixtures to conftest.py** - `5a856ab` (feat)
2. **Task 2: Create comprehensive test suite tests/test_retriever.py** - `a5d9d38` (test)
3. **Task 3: Register retriever classes in top-level __init__.py lazy __getattr__** - `e187f6f` (feat)

## Files Created/Modified
- `tests/test_retriever.py` (new, 896 lines) - Comprehensive unit test suite for all 6 retrievers
- `tests/conftest.py` - Added mock_vector_store and mock_graph_store fixtures with spec=StoreClass
- `src/lightrag_langchain/__init__.py` - Added 6 retriever lazy __getattr__ entries (D-09)
- `src/lightrag_langchain/retriever/base.py` - Added model_rebuild() for Pydantic v2 forward references
- `src/lightrag_langchain/retriever/retrievers.py` - Added model_rebuild() for all 6 retriever classes

## Decisions Made
- Used `AsyncMock(spec=PGVectorStore)` / `AsyncMock(spec=PGGraphStore)` in fixtures so `isinstance(mock, StoreClass)` returns True, satisfying Pydantic v2 field validation after model_rebuild()
- Added `model_rebuild()` calls at the bottom of `base.py` and `retrievers.py` rather than in `__init__.py` -- ensures forward references resolve whether classes are imported directly or through lazy __getattr__
- Test embedding injection via `_embedding` PrivateAttr (bypasses the lazy `create_embedding()` factory) -- cleanest approach that avoids patching property descriptors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pydantic v2 forward reference resolution failure**
- **Found during:** Task 2 (creating test_retriever.py)
- **Issue:** All 26 tests failed with `PydanticUserError: 'NaiveRetriever' is not fully defined; you should define 'PGVectorStore', then call 'NaiveRetriever.model_rebuild()'`. Caused by `from __future__ import annotations` combined with `TYPE_CHECKING` imports -- Pydantic v2 stores annotations as strings but can't resolve them without explicit model_rebuild()
- **Fix:** Added `model_rebuild()` calls at the bottom of `base.py` (for `LightRAGBaseRetriever`) and `retrievers.py` (for all 6 retriever subclasses), with runtime imports of `PGVectorStore`, `PGGraphStore`, `EmbeddingConfig`, and `OpenAIEmbeddings` to make the types available in the module namespace for forward reference resolution
- **Files modified:** `src/lightrag_langchain/retriever/base.py`, `src/lightrag_langchain/retriever/retrievers.py`
- **Verification:** `python -m pytest tests/test_retriever.py -v` -- all 26 tests pass
- **Committed in:** `a5d9d38` (Task 2 commit)

**2. [Rule 3 - Blocking] Pydantic isinstance validation rejects AsyncMock for store fields**
- **Found during:** Task 2 (after model_rebuild fix)
- **Issue:** After model_rebuild() resolved the "not fully defined" error, Pydantic v2's `arbitrary_types_allowed=True` still validates via `isinstance(mock, PGVectorStore)`, which returned False for bare `AsyncMock()`
- **Fix:** Changed conftest fixtures to use `AsyncMock(spec=PGVectorStore)` and `AsyncMock(spec=PGGraphStore)` -- `unittest.mock` with `spec=` causes `isinstance` to return True for the spec class
- **Files modified:** `tests/conftest.py`
- **Verification:** `python -m pytest tests/test_retriever.py -v` -- all 26 tests pass
- **Committed in:** `a5d9d38` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 3 - Blocking)
**Impact on plan:** Both fixes necessary for the retriever classes to be instantiable with mock stores. No scope creep -- the retriever classes were not previously testable due to these Pydantic v2 issues.

## Issues Encountered
- The `from __future__ import annotations` + `TYPE_CHECKING` pattern used throughout the codebase creates forward reference issues with Pydantic v2. Future phases using similar patterns for new Pydantic models should include `model_rebuild()` calls from the start.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 6 retriever classes are fully tested with mock stores (sync and async paths verified)
- Top-level lazy exports work (D-09) -- `from lightrag_langchain import NaiveRetriever` is functional
- Ready for Phase 6 (LangChain QA Chain) which will consume retriever.invoke() → List[Document]

---
*Phase: 05-retriever-interfaces*
*Completed: 2026-05-31*
