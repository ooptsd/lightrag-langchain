---
phase: 04-query-strategies
plan: 02
subsystem: query
tags: [postgresql, pgvector, apache-age, asyncpg, pydantic, asyncio, graph-traversal]

# Dependency graph
requires:
  - phase: 04-01
    provides: QueryResult model + GraphTriple model (frozen Pydantic)
  - phase: 02-data-layer
    provides: PGVectorStore (search_entities/relationships/chunks) + PGGraphStore (get_nodes_batch/get_node_edges/get_edges_batch)
  - phase: 01-configuration
    provides: QueryParamsConfig (top_k, chunk_top_k, kg_chunk_pick_method)
provides:
  - naive_strategy async function (QUERY-01: pure vector chunk search with WEIGHT fallback)
  - global_strategy async function (QUERY-03: relation VDB search + AGE edge/entity lookup)
  - local_strategy async function (QUERY-02: entity VDB search + AGE graph expansion)
  - _concurrent_graph_lookup + _concurrent_edge_retrieval + _build_graph_triples graph traversal helpers
affects: [04-03 (hybrid/mix strategies compose these leaf strategies)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy settings import inside strategy function bodies to defer .env dependency"
    - "asyncio.gather() with return_exceptions=True for parallel graph edge lookups (Pitfall 5)"
    - "Deduplication via compound key (src_entity_id, sorted(edge_ids), tgt_entity_id) for graph triples"
    - "Private underscore helpers (_concurrent_graph_lookup, etc.) expose graph traversal for composition"

key-files:
  created:
    - src/lightrag_langchain/query/strategies.py
  modified: []

key-decisions:
  - "KG_CHUNK_PICK_METHOD=WEIGHT falls back to VECTOR with logged warning (no KV store per Pitfall 4)"
  - "local_strategy uses asyncio.gather() for parallel get_node_edges() calls per Pitfall 5 (prevents 40 serial round-trips)"
  - "global_strategy retrieves real keywords/weight from AGE edges since VDB_RELATION lacks those columns (Pitfall 2)"
  - "_build_graph_triples is a pure sync function (no I/O) for testability and clarity"

patterns-established:
  - "All strategy functions are async, receive query_embedding: list[float], and return QueryResult"
  - "Early empty-list return pattern: if no results from vector search, return QueryResult() immediately"
  - "Graph traversal helpers follow split-responsibility: concurrent lookup -> concurrent retrieval -> sync assembly"

requirements-completed:
  - QUERY-01
  - QUERY-02
  - QUERY-03

# Metrics
duration: 2min
completed: 2026-05-30
---

# Phase 04 Plan 02: Leaf Query Strategies (Naive, Local, Global) Summary

**Three core async retrieval functions with concurrent graph traversal for LightRAG's naive/local/global query modes**

## Performance

- **Duration:** ~2min
- **Tasks:** 2
- **Files created:** 1 (`strategies.py`, 386 lines)

## Accomplishments
- `naive_strategy` (QUERY-01): Pure chunk vector search with KG_CHUNK_PICK_METHOD=WEIGHT fallback to VECTOR and logged warning (Pitfall 4)
- `global_strategy` (QUERY-03): Relation VDB search -> AGE edge batch lookup -> entity node batch lookup -> deduplicated graph triples
- `local_strategy` (QUERY-02): Entity VDB search -> concurrent edge discovery -> batch edge/neighbor retrieval -> sync GraphTriple assembly
- Three private graph traversal helpers (`_concurrent_graph_lookup`, `_concurrent_edge_retrieval`, `_build_graph_triples`) reusable by hybrid/mix strategies in Plan 03
- All strategies use lazy settings import (no .env required at import time for module-level code)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create strategies.py with naive_strategy + global_strategy** - `a911521` (feat)
2. **Task 2: Append local_strategy + graph traversal helpers** - `14f878a` (feat)

## Files Created/Modified
- `src/lightrag_langchain/query/strategies.py` - 386 lines: module docstring, 3 strategy functions (naive/global/local), 3 helper functions (_concurrent_graph_lookup, _concurrent_edge_retrieval, _build_graph_triples)

## Decisions Made
- KG_CHUNK_PICK_METHOD=WEIGHT in naive mode logs a warning and falls back to VECTOR since no KV store exists (RESEARCH.md Pitfall 4)
- local_strategy uses `asyncio.gather()` with `return_exceptions=True` to parallelize `get_node_edges()` calls, preventing 40 sequential round-trips (RESEARCH.md Pitfall 5)
- global_strategy batch-retrieves edge data from AGE graph to get real `keywords`/`weight` values, since PGVector `VDB_RELATION` table lacks those columns (RESEARCH.md Pitfall 2)
- `_build_graph_triples` is a pure synchronous function (no I/O) for testability — only Pydantic model assembly from already-fetched data

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

No stubs. All strategy functions call real store APIs and return properly populated QueryResult objects.

## Threat Flags

No new threat surface. All threat model entries (T-04-01 through T-04-SC) are addressed in the implementation as specified in the plan.

## Next Phase Readiness

- Three leaf strategies (naive, local, global) ready for composition by Plan 03 (hybrid + mix + bypass)
- Helper functions (`_concurrent_graph_lookup`, `_concurrent_edge_retrieval`, `_build_graph_triples`) are private but importable for reuse
- All strategies follow the uniform async signature pattern expected by Plan 03

---
*Phase: 04-query-strategies*
*Completed: 2026-05-30*
