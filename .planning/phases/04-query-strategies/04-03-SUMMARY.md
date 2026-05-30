---
phase: 04-query-strategies
plan: 03
subsystem: query
tags: [query-strategies, hybrid, mix, bypass, round-robin-merge, lazy-exports]
requires: [04-01, 04-02]
provides: []
affects: []
tech-stack:
  added: [pytest-asyncio]
  patterns: [async-strategy-functions, round-robin-merge, lazy-__getattr__-exports, mock-store-testing]
key-files:
  created: [src/lightrag_langchain/query/strategies.py]
  modified: [src/lightrag_langchain/query/__init__.py, tests/test_query_strategies.py, pyproject.toml, uv.lock]
decisions:
  - "Round-robin merge algorithm matches upstream LightRAG _perform_kg_search lines 3512-3566 with entity_name and sorted(src_id, tgt_id) dedup"
  - "pytest-asyncio added as dev dependency to support async strategy tests with mock stores"
  - "Entity content converted to ChunkRecord pseudo-chunks in mix_strategy for interleaving with vector chunks"
metrics:
  duration: 7m
  tasks: 3
  completed-date: 2026-05-30
---

# Phase 4 Plan 3: Complete query strategies with hybrid/mix/bypass and round-robin merge

**One-liner:** Implemented the three composite query strategies (hybrid, mix, bypass) with upstream-matching round-robin merge helpers, lazy __getattr__ exports for all 6 strategies, and 14 real async unit tests.

## What Was Built

### strategies.py (691 lines)
Complete query strategies module containing all 6 LightRAG query mode implementations:

**Plan 03 additions appended after Plan 02 baseline:**
- `_round_robin_merge_entities()` — sync helper, alternates local[i]/global[i], deduplicates by `entity_name`
- `_round_robin_merge_relations()` — sync helper, deduplicates by `tuple(sorted((src_id, tgt_id)))`
- `_round_robin_merge_chunks()` — sync helper, deduplicates by `chunk_id`
- `hybrid_strategy()` (QUERY-04) — `asyncio.gather(local_strategy, global_strategy)` with round-robin merge of entities, relations, and graph_triples with triple dedup key `(src.entity_id, sorted((edge.source_id, edge.target_id)), tgt.entity_id)`
- `bypass_strategy()` (QUERY-06) — no-op returning empty `QueryResult()`, zero database queries
- `mix_strategy()` (QUERY-05) — `asyncio.gather(hybrid_strategy, vector_store.search_chunks)`, converts entity content to ChunkRecord pseudo-chunks, merges via `_round_robin_merge_chunks`

All merge algorithms verified against upstream LightRAG `operate.py` lines 3512-3566.

### query/__init__.py (updated)
Lazy `__getattr__` branches for all 6 strategy functions matching the established pattern from `lightrag_langchain/__init__.py` (lines 18-68):
- `naive_strategy`, `local_strategy`, `global_strategy`, `hybrid_strategy`, `mix_strategy`, `bypass_strategy`
- Eager exports (`QueryResult`, `GraphTriple`) preserved from Plan 01
- `__all__` includes all 8 exported names
- `AttributeError` raised for unknown attributes

### tests/test_query_strategies.py (updated)
Replaced 6 placeholder skip-marked test classes with 14 real async tests:
- **TestQueryResultModel** (3 tests): empty construction, frozen immutability, field population
- **TestGraphTripleModel** (3 tests): required fields, full construction, frozen immutability
- **TestNaiveStrategy** (2 tests): chunk retrieval, WEIGHT fallback
- **TestLocalStrategy** (1 test): entity retrieval + graph triples
- **TestGlobalStrategy** (1 test): relation retrieval + entity lookup + triples
- **TestHybridStrategy** (1 test): parallel local+global + round-robin merge + triple dedup
- **TestMixStrategy** (1 test): hybrid + chunk search + entity-as-chunk merging
- **TestBypassStrategy** (2 tests): empty result, async function check

Test data helpers: `_make_entity()`, `_make_relation()`, `_make_chunk()`, `_make_graph_node()`, `_make_graph_edge()`

All tests use `@pytest.mark.asyncio` with `AsyncMock` store objects and `patch("lightrag_langchain.config.settings")` for settings isolation.

## Commits

| Commit | Message |
|--------|---------|
| `60a3fe4` | feat(04-03): implement hybrid/mix/bypass strategies with round-robin merge helpers |
| `3eae655` | feat(04-03): update __init__.py with lazy exports and add real strategy tests |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added pytest-asyncio dev dependency**
- **Found during:** Task 3 test execution
- **Issue:** Async tests (`@pytest.mark.asyncio`) failed because pytest-asyncio was not installed
- **Fix:** Added `pytest-asyncio>=1.4.0` to `pyproject.toml` dependency-groups.dev and installed in venv
- **Files modified:** `pyproject.toml`
- **Commit:** `3eae655`

**2. [Rule 1 - Bug] Fixed patch target in strategy tests**
- **Found during:** Task 3 test execution
- **Issue:** `patch("lightrag_langchain.query.strategies.settings")` raised `AttributeError: does not have the attribute 'settings'` because `settings` is imported lazily inside function bodies, not at module level
- **Fix:** Changed all patch targets to `patch("lightrag_langchain.config.settings")` which resolves through config.py's module-level `__getattr__`
- **Files modified:** `tests/test_query_strategies.py`
- **Commit:** `3eae655`

**3. [Rule 3 - Auto-fix Blocking] strategies.py did not exist in worktree**
- **Found during:** Task 1 start
- **Issue:** Plan 04-02 (leaf strategies: naive, local, global) was executed in a parallel worktree (`worktree-agent-a3708227879b433f1`) but its commits were not in the current worktree branch. strategies.py did not exist.
- **Fix:** Retrieved strategies.py content from the parallel worktree branch via `git show`, wrote the complete file with both Plan 02 baseline and Plan 03 additions
- **Files created:** `src/lightrag_langchain/query/strategies.py`
- **Commit:** `60a3fe4`

## Verification Evidence

### Automated Tests
```
$ python3 -m pytest tests/test_query_strategies.py -x -q
..............
14 passed in 0.05s
```

### Lazy Export Verification
```python
from lightrag_langchain.query import (naive_strategy, local_strategy, global_strategy,
    hybrid_strategy, mix_strategy, bypass_strategy, QueryResult, GraphTriple)
# All 6 strategies are async functions, exported via lazy __getattr__
# Eager exports (QueryResult, GraphTriple) still work
# AttributeError raised for unknown attributes
```

### Function Presence Verification
```
All 6 strategy functions present (8 async, 4 sync)
All Plan 03 strategies importable
__all__ includes all 6 strategies + QueryResult + GraphTriple
```

## Self-Check: PASSED

- `src/lightrag_langchain/query/strategies.py`: EXISTS
- `src/lightrag_langchain/query/__init__.py`: EXISTS (modified)
- `tests/test_query_strategies.py`: EXISTS (modified)
- `pyproject.toml`: EXISTS (modified, dev dependency added)
- Commit `60a3fe4`: EXISTS
- Commit `3eae655`: EXISTS
