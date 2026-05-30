---
phase: 02-data-layer
plan: 03
subsystem: data
tags: [pgvector, vector-search, store, read-only, table-discovery]
requires:
  - 02-01 (data models)
  - 02-02 (pool manager)
provides: PGVectorStore for entity/relationship/chunk vector similarity search
affects:
  - Phase 4 (query strategies)
  - Phase 5 (LangChain retrievers)
tech-stack:
  added: []
  patterns:
    - async for acquire_with_retry (async generator connection acquisition)
    - Parameterized PGVector cosine distance search ($1..$4 with ::vector cast)
    - information_schema table discovery with whitelist validation
key-files:
  created:
    - src/lightrag_langchain/data/store.py
    - tests/test_store.py
  modified:
    - src/lightrag_langchain/data/__init__.py
decisions: []
metrics:
  duration: 8min
  completed_date: "2026-05-30"
---

# Phase 02 Plan 03: PGVectorStore Summary

Vector similarity search store providing entity, relationship, and chunk retrieval from LightRAG PGVector tables using parameterized cosine distance queries with workspace isolation.

## What Was Built

A `PGVectorStore` class in `src/lightrag_langchain/data/store.py` that:
- **Searches entities** (`search_entities`) via `content_vector <=> $4::vector < $2` cosine distance on `LIGHTRAG_VDB_ENTITY`, returning `EntityRecord` objects with entity_name, content, source_id, file_path, created_at
- **Searches relationships** (`search_relationships`) via same pattern on `LIGHTRAG_VDB_RELATION`, returning `RelationshipRecord` objects with keywords=None, weight=None (these columns don't exist in the VDB table — they come from AGE graph edges in Plan 02-04)
- **Searches chunks** (`search_chunks`) on `LIGHTRAG_VDB_CHUNKS`, returning `ChunkRecord` objects with chunk_id, content, full_doc_id, chunk_order_index, file_path
- **Auto-discovers table names** from `information_schema.tables` matching `LIGHTRAG_VDB_*` prefix (D-12), with RuntimeError for multi-suffix ambiguity (D-13)
- **Applies workspace filtering** via `WHERE workspace=$1` on every query (D-05)
- **Handles transient errors** via `acquire_with_retry` from the pool module (D-06)
- **Supports pool injection** with lazy fallback to module-level singleton (D-07)
- **Enforces read-only** — only `conn.fetch()` is called; zero `execute()` invocations (D-15)

## Tasks Executed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create PGVectorStore class | `4f5fea5` | `src/lightrag_langchain/data/store.py` (new, +265), `src/lightrag_langchain/data/__init__.py` (modified) |
| 2 | Create unit tests | `ea5e4e0` | `tests/test_store.py` (new, +461) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] acquire_with_retry uses `async for` not `async with`**
- **Found during:** Task 1 implementation
- **Issue:** Plan specified `async with acquire_with_retry(self.pool) as conn:` but `acquire_with_retry` in pool.py is an `AsyncIterator` (async generator), not an `AsyncContextManager`. Using `async with` would fail at runtime.
- **Fix:** Used `async for conn in acquire_with_retry(self.pool):` pattern throughout store.py. Since the generator yields exactly one connection and auto-releases via its `finally` block, this is functionally equivalent.
- **Files modified:** `src/lightrag_langchain/data/store.py`
- **Commit:** `4f5fea5`

**2. [Rule 1 - Bug] Module-level pool import would fail before initialization**
- **Found during:** Task 1 implementation
- **Issue:** Plan specified `from lightrag_langchain.data.pool import acquire_with_retry, pool as _default_pool`. Importing `pool` triggers `__getattr__` which raises `RuntimeError` if the pool singleton hasn't been initialized via `init_pool()`.
- **Fix:** Imported only `acquire_with_retry` at module level. The `pool` property getter uses a lazy `import lightrag_langchain.data.pool as _pool_mod` to access the singleton, deferring the `RuntimeError` to call time rather than import time.
- **Files modified:** `src/lightrag_langchain/data/store.py`
- **Commit:** `4f5fea5`

### Auth Gates

None — no authentication gates encountered.

## Known Stubs

None — all data flows are fully wired. The `keywords=None` and `weight=None` in `RelationshipRecord` from PGVector queries are intentional per RESEARCH.md A1 (those columns don't exist in VDB_RELATION DDL); real values come from AGE graph edges in Plan 02-04.

## Threat Flags

None — all security surface is covered by the plan's `<threat_model>`.

## Self-Check: PASSED

- [x] `src/lightrag_langchain/data/store.py` exists
- [x] `tests/test_store.py` exists
- [x] Commit `4f5fea5` exists (Task 1)
- [x] Commit `ea5e4e0` exists (Task 2)
- [x] All 18 tests pass with `pytest tests/test_store.py -v`
- [x] Ruff passes on both files
- [x] Zero `execute()` calls in store.py
- [x] PGVectorStore importable via `from lightrag_langchain.data import PGVectorStore`
