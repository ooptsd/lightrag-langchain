---
phase: 02-data-layer
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/lightrag_langchain/config.py
  - src/lightrag_langchain/data/__init__.py
  - src/lightrag_langchain/data/models.py
  - src/lightrag_langchain/data/pool.py
  - src/lightrag_langchain/data/store.py
  - src/lightrag_langchain/data/graph.py
  - tests/conftest.py
  - tests/test_models.py
  - tests/test_pool.py
  - tests/test_store.py
  - tests/test_graph.py
  - .env.example
  - pyproject.toml
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 2: Data Layer -- Code Review Report

**Reviewed:** 2026-05-30
**Depth:** standard (per-file analysis with language-specific checks)
**Files Reviewed:** 12
**Status:** issues_found (2 critical, 4 warning, 3 info)

## Summary

Reviewed 12 files spanning the complete Phase 2 data layer implementation: Pydantic record models, asyncpg connection pool manager, PGVector store, Apache AGE graph store, configuration extension, test fixtures, `.env.example` template, and `pyproject.toml` dependencies.

The architecture is well-structured with clear separation of concerns: frozen models, lazy pool singleton, dependency injection throughout, parameterized queries, and read-only enforcement. The test suite is comprehensive (115 tests across all files, all passing). No hardcoded secrets, no `eval()` or dangerous patterns, and zero `execute()` calls in store/graph code -- the read-only enforcement holds.

**Key concerns:** The `.env.example` template uses wrong env var naming (single underscore where double underscore is required by pydantic-settings nested delimiter), making the documented setup non-functional. A graph name interpolation inconsistency in `get_nodes_batch()` bypasses the dollar-quoting protection used everywhere else. Several minor code quality findings (unreachable dead code, fragile assert guard, fixture setup inconsistency) are also noted.

## Critical Issues

### CR-01: `.env.example` uses wrong env var naming convention -- application won't start from template

**File:** `.env.example:1-45`
**Issue:** The `.env.example` template uses single-underscore env var names (e.g., `PG_HOST`, `LLM_BINDING`, `TOP_K`) for most configuration entries, but the `SettingsConfigDict` in `config.py:170-178` specifies `env_nested_delimiter="__"` (double underscore). This means pydantic-settings maps `PG__HOST` to `Settings.pg.host`, NOT `PG_HOST`. The Phase 2 additions (lines 9, 11-13: `PG__WORKSPACE`, `PG__POOL_MIN_SIZE`, etc.) correctly use double underscores, but the Phase 1 entries were never updated to match.

**Impact:** A user who copies `.env.example` to `.env` and fills in values would get a `ValidationError` at startup because all required fields (`pg.host`, `pg.port`, `pg.user`, `pg.password`, `pg.database`, `llm.binding`, etc.) would not be found. The application is non-functional following documented setup.

**Evidence:** All test fixtures in `tests/test_config.py:317-321`, `tests/test_pool.py:54-66`, and `tests/test_graph.py:49-63` use double-underscore env var names (e.g., `pg__host`, `llm__binding`, `query_params__top_k`), confirming the correct format. The single-underscore names in `.env.example` (e.g., `PG_HOST`, `LLM_BINDING`) are never used in any test.

**Fix:** Update all env var names in `.env.example` to use double underscores matching the pydantic-settings nested delimiter:

```ini
# PostgreSQL (CONF-01)
PG__HOST=localhost
PG__PORT=5432
PG__USER=your_username
PG__PASSWORD=your_password
PG__DATABASE=lightrag

# Optional — workspace isolation (default: "default")
PG__WORKSPACE=default
# Optional — connection pool sizing (defaults shown)
PG__POOL_MIN_SIZE=2
PG__POOL_MAX_SIZE=10
# Optional — command timeout in seconds (default: 30)
PG__POOL_TIMEOUT=30.0

# LLM (CONF-02)
LLM__BINDING=openai
LLM__BINDING_HOST=https://api.openai.com/v1
LLM__BINDING_API_KEY=sk-your-api-key
LLM__MODEL=gpt-4o-mini
LLM__TEMPERATURE=0.0
LLM__MAX_TOKENS=9000

# Embedding (CONF-03)
EMBEDDING__BINDING=openai
EMBEDDING__BINDING_HOST=https://api.openai.com/v1
EMBEDDING__BINDING_API_KEY=sk-your-api-key
EMBEDDING__MODEL=text-embedding-3-small
EMBEDDING__DIM=1024

# Reranker (CONF-04, optional — leave empty to disable)
RERANK__BINDING=
RERANK__BINDING_HOST=
RERANK__BINDING_API_KEY=
RERANK__MODEL=
RERANK__MIN_RERANK_SCORE=0.0

# Query Parameters (CONF-05, defaults match upstream LightRAG)
QUERY_PARAMS__TOP_K=40
QUERY_PARAMS__CHUNK_TOP_K=20
QUERY_PARAMS__MAX_ENTITY_TOKENS=6000
QUERY_PARAMS__MAX_RELATION_TOKENS=8000
QUERY_PARAMS__MAX_TOTAL_TOKENS=30000
QUERY_PARAMS__COSINE_THRESHOLD=0.2
QUERY_PARAMS__KG_CHUNK_PICK_METHOD=VECTOR
```

### CR-02: `get_nodes_batch()` interpolates graph_name without dollar-quoting -- inconsistent with `_query()`

**File:** `src/lightrag_langchain/data/graph.py:249`
**Issue:** `get_nodes_batch()` constructs SQL with `FROM {graph_name}.base AS b` (f-string interpolation), while `_query()` (line 186) correctly uses `_dollar_quote(graph_name)` to wrap the graph name in PostgreSQL dollar quoting. The `_resolve_graph_name()` method does sanitize workspace-derived names, but when a user passes `graph_name` directly through the constructor (`__init__(graph_name=...)`), `_resolve_graph_name()` returns the unsanitized user-provided value as-is (line 147-148: `if self._graph_name_resolved is not None: return self._graph_name_resolved`).

**Impact:** If a caller passes a graph name containing SQL metacharacters directly through the `PGGraphStore` constructor, the `get_nodes_batch()` query would be vulnerable to SQL injection. Database-level read-only enforcement (`default_transaction_read_only='on'`, pool.py line 113) prevents DDL/DML, but malformed SQL could cause errors, information disclosure, or unexpected behavior. Every other query method in `graph.py` routes through `_query()` which applies dollar-quoting -- this single method is the outlier.

**Fix:** Apply dollar-quoting to `graph_name` in `get_nodes_batch()` just as `_query()` does:

```python
async def get_nodes_batch(self, node_ids: list[str]) -> dict[str, GraphNode]:
    if not node_ids:
        return {}

    graph_name = await self._resolve_graph_name()
    graph_quoted = self._dollar_quote(graph_name)

    sql = f"""
        WITH input(v, ord) AS (
          SELECT v, ord
          FROM unnest($1::text[]) WITH ORDINALITY AS t(v, ord)
        ),
        ids(node_id, ord) AS (
          SELECT (to_json(v)::text)::agtype AS node_id, ord
          FROM input
        )
        SELECT i.node_id::text AS node_id,
               b.properties
        FROM {graph_quoted}.base AS b
        JOIN ids i
          ON ag_catalog.agtype_access_operator(
               VARIADIC ARRAY[b.properties, '"entity_id"'::agtype]
             ) = i.node_id
        ORDER BY i.ord
    """
    # ... rest of method unchanged
```

Note: Using `{graph_quoted}` here means the dollar-quoted identifier is embedded in the SQL. For PostgreSQL qualified table references, the identifier must be valid. An alternative is to also validate that `graph_name` only contains safe characters (`r"^[a-zA-Z0-9_]+$"`) and reject unsafe names early in `_resolve_graph_name()`.

## Warnings

### WR-01: Unreachable dead code in `_query()` method

**File:** `src/lightrag_langchain/data/graph.py:202`
**Issue:** The `return []` line after the `async for conn in acquire_with_retry(...)` loop is unreachable. `acquire_with_retry` either yields and returns (via the `return` inside the `else` branch), or raises an exception. It never silently finishes without yielding. The comment acknowledges this (`# pragma: no cover`) but dead code still degrades maintainability.

**Fix:** Remove the dead code and replace with a `raise RuntimeError` to document the invariant explicitly:

```python
# Replace lines 200-202:
async for conn in acquire_with_retry(self.pool):
    rows: list[Record] = await conn.fetch(sql, pg_params)
    return [dict(row) for row in rows]

# If we reach here, acquire_with_retry returned without yielding (impossible)
raise RuntimeError("acquire_with_retry did not yield a connection")
```

### WR-02: Fragile `assert` guard on loop invariant in retry handler

**File:** `src/lightrag_langchain/data/pool.py:172`
**Issue:** The `assert last_exc is not None` statement is removed when Python runs with the `-O` (optimize) flag. While the loop invariant guarantees `last_exc` is set (the loop always executes at least once, and each iteration either returns or sets `last_exc`), using `assert` for a program-logic guard is fragile. The `raise last_exc` immediately after would still execute, but if `last_exc` were ever `None` (e.g., due to a negative `max_retries` value), `raise None` would produce a confusing `TypeError: exceptions must derive from BaseException` instead of a clear error.

**Fix:** Replace the `assert` with an explicit runtime check:

```python
# Replace line 172:
if last_exc is None:
    raise RuntimeError(
        "acquire_with_retry: all attempts exhausted but no exception was captured"
    )
raise last_exc
```

### WR-03: `_vector_search()` interpolates `select_clause` and `table_name` into SQL

**File:** `src/lightrag_langchain/data/store.py:188-195`
**Issue:** The `_vector_search()` method constructs SQL via f-string interpolation of `select_clause` and `table_name`. While these values come from trusted sources (hardcoded string literals in the search methods, and `information_schema` system catalog for table names), and the actual user-controlled data (workspace, threshold, limit, embedding) is properly parameterized via `$1..$4`, interpolating structural SQL elements is a defense-in-depth concern. If future code changes make these values partially user-controlled, the injection vector is already present.

**Fix:** Consider replacing the f-string with a pre-defined SQL template or adding a validation step. For the table name, validate against a whitelist (which `_ensure_tables()` already does):

```python
def _build_vector_search_sql(self, table_name: str, select_clause: str) -> str:
    """Validate and construct the read-only vector search SQL."""
    # Whitelist: table_name must be one of the discovered tables
    valid_tables = set(self._tables.values()) if self._tables else set()
    if table_name not in valid_tables:
        raise RuntimeError(f"Table {table_name!r} not in discovered tables {valid_tables}")
    return (
        f"{select_clause} "
        f"FROM {table_name} "
        f"WHERE workspace = $1 "
        f"AND content_vector <=> $4::vector < $2 "
        f"ORDER BY content_vector <=> $4::vector "
        f"LIMIT $3"
    )
```

### WR-04: Inconsistency in graph name handling between `_query()` and `get_nodes_batch()`

**File:** `src/lightrag_langchain/data/graph.py:186,249`
**Issue:** The `_query()` method (line 186) applies `_dollar_quote()` to graph names before interpolation: `cypher({graph_quoted}::name, ...)`. But `get_nodes_batch()` (line 249) interpolates the graph name directly: `FROM {graph_name}.base AS b`. The same graph name value receives different safety treatment depending on which code path is taken. This inconsistency makes it harder to reason about the security properties of the graph name handling and increases the risk of missing a dangerous code path during future refactoring.

**Fix:** See CR-02 fix above for the specific code change. Ensure ALL graph name interpolation paths use dollar-quoting.

## Info

### IN-01: `__all__` omits lazy-imported store classes

**File:** `src/lightrag_langchain/data/__init__.py:11-17`
**Issue:** `__all__` lists only the 5 Pydantic model types, but `PGVectorStore` and `PGGraphStore` are accessible via `__getattr__` lazy imports. This means `from lightrag_langchain.data import *` would only bring in the models, not the store classes. IDE autocompletion based on `__all__` would not suggest `PGVectorStore` or `PGGraphStore`.

**Fix:** Add `PGVectorStore` and `PGGraphStore` to `__all__`:

```python
__all__ = [
    "EntityRecord",
    "RelationshipRecord",
    "ChunkRecord",
    "GraphNode",
    "GraphEdge",
    "PGVectorStore",
    "PGGraphStore",
]
```

### IN-02: `keywords` fields typed as `str | None` but represent comma-separated lists

**File:** `src/lightrag_langchain/data/models.py:67,163`
**Issue:** `RelationshipRecord.keywords` and `GraphEdge.keywords` are typed as `str | None`, but they contain comma-separated keyword strings (e.g., `"kw1,kw2"`). While this matches the LightRAG PostgreSQL DDL (TEXT column), the type gives no indication that the value is structured. The test fixtures confirm comma-separated values (e.g., `test_models.py:77` uses `"kw1,kw2"`).

**Fix:** Add a docstring comment clarifying the format, or consider adding a `@property` that parses into a `list[str]`:

```python
keywords: str | None = None
"""Comma-separated keywords (e.g., ``"employer,staff"``). ``None`` when not set."""
```

### IN-03: `mock_pool` fixture sets up context-manager behavior but retry uses direct acquire

**File:** `tests/conftest.py:31-46`
**Issue:** The `mock_pool` fixture configures `pool.acquire.return_value.__aenter__` and `__aexit__` for context-manager usage (`async with pool.acquire() as conn`). However, `acquire_with_retry()` in `pool.py` calls `conn = await pool.acquire()` directly (no context manager). Every test module that uses `acquire_with_retry` must override the fixture setup with `_wire_pool_for_acquire_with_retry()` (`test_store.py:35-45`) or `_wire_mocks()` (`test_graph.py:78-86`), creating friction for new test authors.

**Fix:** Either update the `mock_pool` fixture in `conftest.py` to support both usage patterns, or add a separate `mock_pool_for_retry` fixture. Alternatively, document the override pattern clearly in a `README` or docstring:

```python
@pytest.fixture
def mock_pool_direct():
    """Return an AsyncMock wrapping asyncpg.Pool for use with acquire_with_retry.
    
    Use this fixture when the code under test uses acquire_with_retry()
    (which calls await pool.acquire() directly, not as context manager).
    """
    from unittest.mock import AsyncMock
    pool = AsyncMock()
    pool.acquire = AsyncMock()   # Direct async call, not context manager
    pool.release = AsyncMock()
    return pool
```

---

_Reviewed: 2026-05-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
