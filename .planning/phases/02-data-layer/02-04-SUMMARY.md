---
phase: 02-data-layer
plan: 04
subsystem: data
tags:
  - graph
  - apache-age
  - cypher
  - read-only
  - parameterized-queries
requires:
  - 02-01 (data models)
  - 02-02 (pool manager)
provides:
  - PGGraphStore
affects:
  - Phase 4 (query strategy layer — calls get_node/get_edge/get_node_edges)
  - Phase 5 (LangChain retriever — wraps graph access behind retriever interface)
tech-stack:
  added: []
  patterns:
    - AGE Cypher parameterization via $1::agtype with json.dumps()
    - Dollar-quote collision avoidance with iterative tag generation
    - agtype ::vertex/::edge suffix stripping
    - Lazy graph name resolution from workspace with caching
    - Batch node lookup with UNNEST + agtype_access_operator
    - acquire_with_retry async generator for transient error handling
key-files:
  created:
    - src/lightrag_langchain/data/graph.py
    - tests/test_graph.py
  modified: []
decisions:
  - "acquire_with_retry is an async generator (not context manager) — adapted all graph.py query methods to use async for pattern"
  - "Added fallback UUID-based dollar-quote tag after 1000 collision attempts (safety valve)"
  - "Small edge batch (<=10 pairs) falls back to sequential get_edge calls to avoid UNWIND overhead"
  - ".env placed in worktree for test collection (gitignored); autouse fixture sets monkeypatched env vars"
metrics:
  duration: 25m
  completed_date: "2026-05-30"
---

# Phase 2 Plan 4: PGGraphStore Graph Query Layer — Summary

**One-liner:** Read-only Apache AGE graph query layer providing parameterized node/edge lookup and neighbor traversal with Pydantic-typed returns and transient error retry.

## Plan Execution

| Task | Name | Type | Commit | Files |
|------|------|------|--------|-------|
| 1 | Create PGGraphStore class | auto | `58fa8df` | `src/lightrag_langchain/data/graph.py` (408 lines) |
| 2 | Create unit tests | auto | `a84a918` | `tests/test_graph.py` (692 lines) |

**Tasks:** 2/2 complete
**Test results:** 97 passed (30 config + 39 graph + 17 models + 11 pool), 0 failed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adapted acquire_with_retry usage pattern**
- **Found during:** Task 1 implementation
- **Issue:** Plan specified `async with acquire_with_retry(self.pool) as conn:` but pool.py's `acquire_with_retry` is an async generator (`async for conn in acquire_with_retry(pool):`), not a context manager.
- **Fix:** All PGGraphStore methods use `async for conn in acquire_with_retry(self.pool):` with early return. The generator's `finally` block handles `pool.release(conn)` cleanup when the async generator is closed by the return.
- **Files modified:** `src/lightrag_langchain/data/graph.py`
- **Commit:** `58fa8df`

**2. [Rule 3 - Blocking] Test mock wiring for async generator**
- **Found during:** Task 2 implementation
- **Issue:** Existing `mock_pool` fixture sets up `pool.acquire.return_value.__aenter__/__aexit__` for context manager usage, but `acquire_with_retry` calls `await pool.acquire()` directly.
- **Fix:** Created `_wire_mocks()` helper in test_graph.py that replaces `pool.acquire` with `AsyncMock(return_value=mock_conn)` and sets `pool.release = AsyncMock()`. This allows the async generator to yield the mock connection correctly.
- **Files modified:** `tests/test_graph.py`
- **Commit:** `a84a918`

**3. [Rule 2 - Missing] Added extra edge cases to test coverage**
- **Found during:** Task 2 implementation
- **Issue:** Plan specified minimum 24 tests covering basic paths. Additional edge cases were needed for robustness: null properties in get_node/get_edge, optional fields None, whitespace-only agtype input, multiple colon handling in _parse_agtype, quote stripping in batch node IDs, graph name caching, empty OPTIONAL MATCH result, large/small batch edge retrieval.
- **Fix:** Expanded from 24 minimum to 39 tests covering all identified edge cases.
- **Files modified:** `tests/test_graph.py`
- **Commit:** `a84a918`

## Deferred Issues

None — all issues resolved within plan execution.

## Known Stubs

None — all methods are fully implemented with working return paths. No placeholder values, no hardcoded empty data flowing to callers.

## Threat Flags

None — the plan's `<threat_model>` covered all threat surface introduced by graph.py. All six threats (T-02-04-GRAPH-01 through -06) are mitigated as specified:
- T-02-04-GRAPH-01 (Cypher injection): `$1::agtype` with `json.dumps()` parameterization on all queries
- T-02-04-GRAPH-02 (Dollar-quote collision): iterative tag generation with UUID fallback
- T-02-04-GRAPH-03 (Write operations): `conn.fetch()` only, no `execute()` path
- T-02-04-GRAPH-04 (Graph name in errors): accept — configuration identifier, not secret
- T-02-04-GRAPH-05 (Unbounded traversal): 1-hop only via `OPTIONAL MATCH`, caller controls batch size
- T-02-04-GRAPH-06 (agtype parsing): `_parse_agtype()` strips suffixes, returns None on any parse failure

## Self-Check

- [x] `src/lightrag_langchain/data/graph.py` exists and is committed
- [x] `tests/test_graph.py` exists and is committed
- [x] Commit `58fa8df` exists (feat: PGGraphStore class)
- [x] Commit `a84a918` exists (test: 39 unit tests)
- [x] 97/97 tests pass across full suite
- [x] ruff check passes on both files
- [x] No `.execute()` calls in graph.py
- [x] All Cypher queries parameterized — no string interpolation

## Self-Check: PASSED
